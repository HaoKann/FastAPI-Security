from typing import List
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel

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
    id: int
    name: str
    price: float
    owner_username: str

class ProductCreate(BaseModel):
    name: str
    price: float


# --- Эндпоинты ---
# Защищённый эндпоинт, который возвращает список продуктов, принадлежащих текущему пользователю.
@router.get('/', response_model=List[Product])
async def get_products(current_user: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_pool)):
    """Возвращает список продуктов текущего пользователя."""
    username = current_user['username']
    async with pool.acquire() as conn:
            try:
                products_records = await conn.fetch(
                    "SELECT id, name, price, owner_username FROM products WHERE owner_username = $1",
                    username
                )
                if not products_records:
                    return [] # Возвращаем пустой список, если продуктов нет
                # ИСПРАВЛЕНО: Преобразуем записи из БД в Pydantic модели более элегантным способом
                return [Product(**dict(p)) for p in products_records]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f'Ошибка при получении продуктов {str(e)}')
           

# Защищённый эндпоинт для создания нового продукта, доступный только авторизованным пользователям.
# ИСПРАВЛЕНО: Эндпоинт теперь принимает Pydantic-модель ProductCreate
@router.post('/', response_model=Product)
async def create_product(product_data: ProductCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_pool)):
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
                return new_product
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")
            

# Эндпоинт для удаления продукта
@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    background_tasks: BackgroundTasks,
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

            # Возвращаем 204 (Успех, нет контента)
            return
        
        except HTTPException:
            raise # Пробрасываем наши ошибки (404, 403) дальше
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при удалении: {str(e)}")