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
@router.post('/', response_model=Product)
async def create_product(name: str, price: float, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_pool)):
    """Создает новый продукт для текущего пользователя."""
    username = current_user['username']
    async with pool.acquire() as conn:
            try:
                new_product_record = await conn.fetchrow(
                    # RETURNING * возвращает все только что вставленные данные.
                    "INSERT INTO products (name, price, owner_username) VALUES ($1, $2, $3) RETURNING *",
                    name, price, username
                )
                if not new_product_record:
                     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail= 'Не удалось создать продукт')            

                new_product = Product(**dict(new_product_record))
                background_tasks.add_task(manager.broadcast, f"Новый продукт: {new_product.json()}")
                return new_product
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")
            