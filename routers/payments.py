from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_pool
from auth import get_current_user
from repositories.product_repository import ProductRepository
from services.product_service import ProductService 
from services.payment_service import payment_service
from models import User
import stripe
from config import settings
from websocket import manager
from bg_tasks import send_email_to_user_task

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


@router.post('/webhook')
async def stripe_webhook(
    request: Request, 
    stripe_signature: str = Header(None), 
    db: AsyncSession = Depends(get_pool)
):
    # Инициализируем сервис
    product_repo = ProductRepository(db)
    product_service = ProductService(product_repo)

    # Читаем тело запроса как сырые байты
    payload = await request.body()

    try:
        # Stripe проверяет подпись с помощью нашего секрета из .env
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail='Invalid signature')
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid payload')
    
    # 3. Обрабатываем успешную оплату
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        print("🔍 ДАННЫЕ СЕССИИ ОТ STRIPE:")
        print(session)

        metadata = session['metadata']

        product_id = int(metadata['product_id'])
        buyer_username = metadata['username']

        # Достаем email покупателя безопасно
        customer_details = session.get('customer_details', {})
        buyer_email = customer_details.get('email')

        print(f"✅ Пользователь {buyer_username} купил товар {product_id}")
        
        product_info = await product_service.get_product_by_id(product_id)
        previous_owner = product_info['owner_username']

        # 1. Отправляем уведомление продавцу (WebSockets)
        await manager.send_personal_message(
            message=f'Ваш товар {product_info['name']} был куплен {buyer_username}', 
            username=previous_owner
        )

        # 2. Меняем владельца в БД
        await product_service.change_product_ownership(metadata['username'], int(metadata['product_id']) )
        
        # 3. Отправляем фоновую задачу на email (Celery)
        if buyer_email:
            send_email_to_user_task.delay(buyer_email, product_id)
            print(f"📨 Задача на отправку письма для {buyer_email} передана в Celery")
        else:
            print("⚠️ Stripe не передал email покупателя")

            
    # Обязательно возвращаем 200 OK, чтобы Stripe не пытался слать запрос снова
    return {'status': 'success'}