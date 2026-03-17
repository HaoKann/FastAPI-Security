from typing import List, Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
import json
from uuid import UUID

# Импортируем зависимости из наших центральных модулей
from auth import get_current_user
from database import get_pool
from websocket import manager # Для отправки уведомлений

# Создаем APIRouter для этого модуля
router = APIRouter(
    prefix = '/products', # Все пути в этом файле будут начинаться с /products
    tags=['Products'], # Группировка в документации Swagger
    dependencies=[Depends(get_current_user)] # ЗАЩИЩАЕМ ВСЕ ЭНДПОИНТЫ ЗДЕСЬ
)

# --- Модели Pydantic (относятся только к продуктам) ---
class Product(BaseModel):
    id: UUID
    name: str
    price: float
    owner_username: str

class ProductCreate(BaseModel):
    name: str
    price: float

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None


# --- Эндпоинты ---
# Защищённый эндпоинт, который возвращает список продуктов, принадлежащих текущему пользователю.
@router.get('/', response_model=List[Product])
async def get_products(
    request: Request, # <--- 1. Добавляем Request, чтобы добраться до Redis
    # Добавляем параметры limit (сколько взять) и offset (сколько пропустить)
    limit: int = 10,
    offset: int = 0,
    current_user: dict = Depends(get_current_user), 
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Возвращает список продуктов текущего пользователя с кэшированием."""
    username = current_user['username']

    #  Безопасно достаем Redis (если его нет, вернет None)
    redis = getattr(request.app.state, 'redis', None)
    
    #  УНИКАЛЬНЫЙ КЛЮЧ ДЛЯ ЮЗЕРА
    # Если использовать просто "products", данные перемешаются между юзерами!
    # ВАЖНО: Ключ кэша теперь должен зависеть от страницы!
    # Иначе на странице 2 мы увидим кэш от страницы 1.
    CACHE_KEY = f"products:{username}:{limit}:{offset}"

    # --- ЭТАП 1: Проверка Кэша ---
    if redis:
        try:
            cached_data = await redis.get(CACHE_KEY)
            if cached_data:
                print(f"✅ CACHE HIT: Товары для пользователя {username} из Redis")
                # Возвращаем список словарей. Pydantic сам превратит их в список Product
                return json.loads(cached_data)
        except Exception as e:
            print(f"⚠️ Ошибка чтения из Redis (игнорируем и идем в БД): {e}")

    # --- ЭТАП 2: Запрос в БД ---
    print(f"❌ CACHE MISS: Идем в базу за товарами для {username}")
    async with pool.acquire() as conn:
            try:
                # 2. SQL запрос с LIMIT и OFFSET
                # $2 - limit, $3 - offset
                products_records = await conn.fetch(
                    "SELECT id, name, price, owner_username FROM products WHERE owner_username = $1 LIMIT $2 OFFSET $3",
                    username, limit, offset
                )

                # ВАЖНО: jsonable_encoder безопасно переварит UUID и Decimal!
                # 1. Сначала превращаем записи БД в обычные словари
                products_data = jsonable_encoder([dict(p) for p in products_records])

                # --- ЭТАП 3: Сохранение в Кэш (ЭТОГО НЕ БЫЛО) ---
                if redis:
                    try:
                        # Теперь json.dumps сработает без ошибок
                        # Превращаем список словарей в строку и сохраняем на 60 сек
                        await redis.set(CACHE_KEY, json.dumps(products_data), ex=60)
                    except Exception as e:
                      print(f"⚠️ Ошибка записи в Redis: {e}")  

                # Возвращаем словари (Pydantic сам проверит их по схеме response_model)
                return products_data
            
            except Exception as e:
                # Логируем ошибку, чтобы видеть её в консоли
                print(f"DB Error: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка при получении продуктов: {str(e)}")

                
           

# Защищённый эндпоинт для создания нового продукта, доступный только авторизованным пользователям.
# ИСПРАВЛЕНО: Эндпоинт теперь принимает Pydantic-модель ProductCreate
@router.post('/', response_model=Product)
async def create_product(
            product_data: ProductCreate, 
            background_tasks: BackgroundTasks, 
            request: Request,
            current_user: dict = Depends(get_current_user), 
            pool: asyncpg.Pool = Depends(get_pool),
            ):
    """Создает новый продукт для текущего пользователя."""
    username = current_user['username']
    async with pool.acquire() as conn:
            try:
                new_product_record = await conn.fetchrow(
                    # RETURNING * возвращает все только что вставленные данные.
                    "INSERT INTO products (name, price, owner_username) VALUES ($1, $2, $3) RETURNING *",
                    product_data.name, product_data.price, username
                )
                if not new_product_record:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail= 'Не удалось создать продукт')            

                new_product = Product(**dict(new_product_record))
                background_tasks.add_task(manager.broadcast, f"Новый продукт: {new_product.model_dump_json()}")

                # --- СБРОС КЭША REDIS ---
                redis = getattr(request.app.state, 'redis', None)
                if redis:
                    try:
                        # Ищем все ключи кэша продуктов текущего юзера (для всех страниц)
                        cache_keys = await redis.keys(f"products:{username}:*")
                        if cache_keys:
                            await redis.delete(*cache_keys)
                            print(f"🧹 Кэш сброшен для пользователя {username}")
                    except Exception as e:
                        print(f"⚠️ Ошибка сброса кэша: {e}")

                return new_product
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")
            
# Эндпоинт для удаления продукта
@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Удаляет продукт по ID. Только владелец может удалить свой продукт."""
    username = current_user['username']

    async with pool.acquire() as conn:
        try:
            # 1. Проверяем, существует ли продукт и кто его владелец
            product_row = await conn.fetchrow(
                "SELECT owner_username FROM products WHERE id = $1",
                product_id
            )

            if not product_row:
                raise HTTPException(status_code=404, detail="Продукт не найден")
            
            # 2. Проверяем права (только владелец может удалить)
            if product_row['owner_username'] != username:
                raise HTTPException(status_code=403, detail="Вы не можете удалить чужой продукт")
            
            # 3. Удаляем
            await conn.execute("DELETE FROM products WHERE id = $1", product_id)

            # 4. Отправляем уведомление
            background_tasks.add_task(manager.broadcast, f"Продукт ID {product_id} был удален пользователем {username}")

            # --- СБРОС КЭША REDIS ---
            redis = getattr(request.app.state, 'redis', None)
            if redis:
                try:
                    # Ищем все ключи кэша продуктов текущего юзера (для всех страниц)
                    cache_keys = await redis.keys(f"products:{username}:*")
                    if cache_keys:
                        await redis.delete(*cache_keys)
                        print(f"🧹 Кэш сброшен для пользователя {username}")
                except Exception as e:
                    print(f"⚠️ Ошибка сброса кэша: {e}")

            # Возвращаем 204 (Успех, нет контента)
            return
        
        except HTTPException:
            raise # Пробрасываем наши ошибки (404, 403) дальше
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при удалении: {str(e)}")
        

# Эндпоинт для обновления продукта
@router.put('/{product_id}', response_model=Product)
async def update_product(
    product_id: UUID,
    products_update: ProductUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Обновляет продукт. Можно изменить имя, цену или и то, и другое."""
    username = current_user['username']

    async with pool.acquire() as conn:
        try:
            # 1. Проверяем существование и права (как в delete)
            product_row = await conn.fetchrow(
                "SELECT owner_username FROM products WHERE id = $1",
                product_id
            )

            if not product_row:
                raise HTTPException(status_code=404, detail="Продукт не найден")
            
            if product_row['owner_username'] != username:
                raise HTTPException(status_code=403, detail="Нельзя редактировать чужой продукт")

            # 2. Выполняем обновление
            # Используем SQL функцию COALESCE: если передали null ($1), оставляем старое значение (name)
            updated_row = await conn.fetchrow(
                '''
                UPDATE products
                SET name = COALESCE($1, name),
                    price = COALESCE($2, price)
                WHERE id = $3
                RETURNING *
                ''', 
                products_update.name,
                products_update.price,
                product_id
            )

            # 3. Преобразуем в Pydantic-модель
            updated_product = Product(**dict(updated_row))

            # 4. Уведомление
            background_tasks.add_task(manager.broadcast, f"Продукт обновлен: {updated_product.model_dump_json()}")

            # --- СБРОС КЭША REDIS ---
            redis = getattr(request.app.state, 'redis', None)
            if redis:
                try:
                    # Ищем все ключи кэша продуктов текущего юзера (для всех страниц)
                    cache_keys = await redis.keys(f"products:{username}:*")
                    if cache_keys:
                        await redis.delete(*cache_keys)
                        print(f"🧹 Кэш сброшен для пользователя {username}")
                except Exception as e:
                    print(f"⚠️ Ошибка сброса кэша: {e}")

            return updated_product
        
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")