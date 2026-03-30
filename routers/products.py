from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from uuid import UUID

# Импортируем зависимости из наших центральных модулей
from auth import get_current_user
from database import get_product_service
from services.product_service import ProductService

# Создаем APIRouter для этого модуля
router = APIRouter(
    prefix = '/products', # Все пути в этом файле будут начинаться с /products
    tags=['Products'], # Группировка в документации Swagger
    dependencies=[Depends(get_current_user)] # ЗАЩИЩАЕМ ВСЕ ЭНДПОИНТЫ ЗДЕСЬ
)


# Модели Pydantic
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
    # Добавляем параметры limit (сколько взять) и offset (сколько пропустить)
    limit: int = 10,
    offset: int = 0,
    current_user: dict = Depends(get_current_user), 
    service: ProductService = Depends(get_product_service) # <--- ВНЕДРЕНИЕ СЕРВИСА
):
    """Возвращает список продуктов текущего пользователя."""
    return await service.get_products(current_user['username'], limit, offset)

                
           
# Защищённый эндпоинт для создания нового продукта, доступный только авторизованным пользователям.
# ИСПРАВЛЕНО: Эндпоинт теперь принимает Pydantic-модель ProductCreate
@router.post('/', response_model=Product)
async def create_product(
    product_data: ProductCreate, 
    current_user: dict = Depends(get_current_user), 
    service: ProductService = Depends(get_product_service)
):
    return await service.create_product(
        username=current_user['username'],
        name=product_data.name,
        price=product_data.price
    )
            
# Эндпоинт для удаления продукта
@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    await service.delete_product(
        username=current_user['username'],
        product_id=product_id
    )
    return
        

# Эндпоинт для обновления продукта
@router.put('/{product_id}', response_model=Product)
async def update_product(
    product_id: UUID,
    products_update: ProductUpdate,
    current_user: dict = Depends(get_current_user),
    service: ProductService = Depends(get_product_service)
):
    return await service.update_product(
        username=current_user['username'],
        product_id=product_id,
        name=products_update.name,
        price=products_update.price
    )