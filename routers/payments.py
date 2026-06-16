from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_pool
from auth import get_current_user
from repositories.product_repository import ProductRepository
from  services.payment_service import payment_service
from models import User

router = APIRouter(prefix='/payment', tags=['Платежи'])

@router.post('/checkout/{product_id}')
async def buy_products(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_pool)
):
    # 1. Инициализируем репозиторий
    product_repo = ProductRepository(db)

    # 2. Ищем товар в базе
    product = await product_repo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Товар не найден')

    # 3. Базовая защита: запрещаем юзеру покупать собственный товар
    if product['owner_username'] == current_user['username']:
        raise HTTPException(status_code=400, detail='Нельзя купить свой собственный товар')
    
    # 4. Обращаемся к нашему PaymentService для генерации сессии Stripe
    checkout_url = await payment_service.create_checkout_session(product, current_user)

    # 5. Возвращаем ссылку фронтенду
    return {'checkout_url': checkout_url}