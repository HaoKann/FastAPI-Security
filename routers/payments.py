from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from models import CartItem, Cart, User
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from create_db import get_db_session
from auth import get_current_user
from repositories.product_repository import ProductRepository
from services.product_service import ProductService 
from services.payment_service import payment_service
import stripe
from config import settings
from websocket import manager
from bg_tasks import send_email_to_user_task
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory='templates')

router = APIRouter(prefix='/payment', tags=['Payments'])

async def find_user_cart_items(db: AsyncSession, username: str):
    query = (
            select(CartItem)
            .join(Cart)
            .join(User)
            .options(joinedload(CartItem.product))
            .where(User.username == username)
        )
    result = await db.execute(query)
    cart_items = result.scalars().all()
    
    if not cart_items:
        raise HTTPException(status_code=404, detail='Ваша корзина пуста')
    
    return cart_items


async def clear_user_cart(db: AsyncSession, username: str):
    """
    Функция для полной очистки корзины пользователя после успешной оплаты.
    """
    # Находим корзину пользователя
    query = select(Cart).join(User).where(User.username == username)
    result = await db.execute(query)
    cart = result.scalar_one_or_none()
    
    if cart:
        # Удаляем все записи из CartItem, которые привязаны к этой корзине
        delete_query = delete(CartItem).where(CartItem.cart_id == cart.id)
        await db.execute(delete_query)
        await db.commit()


@router.post('/checkout')
async def buy_products(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    # 1. Ищем все товары в корзине пользователя. 
    # Используем joinedload, чтобы база сразу подтянула данные о самих товарах (Product)
    cart_items = await find_user_cart_items(db=db, username=current_user['username'])
    
    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ваша корзина пуста. Добавьте товары перед оформлением заказа."
        )
    
    # 3. Защита: проверяем каждый товар в корзине циклом
    for item in cart_items:
        if item.product.owner_username == current_user['username']:
            raise HTTPException(
                status_code=400, 
                detail=f'Нельзя купить свой собственный товар: {item.product.name}'
            )
    # 4. Обращаемся к нашему PaymentService для генерации сессии Stripe
    checkout_url = await payment_service.create_checkout_session(cart_items, current_user)

    # 5. Возвращаем ссылку фронтенду
    return {'checkout_url': checkout_url}


@router.get('/success')
async def payment_success(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='success.html'
    )
    
@router.get('/cancel')
async def payment_cancel(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='cancel.html'
    )

@router.post('/webhook')
async def stripe_webhook(
    request: Request, 
    stripe_signature: str = Header(None), 
    db: AsyncSession = Depends(get_db_session)
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
        metadata = session['metadata']

        # Получаем данные покупателя
        buyer_username = metadata['username']
        
        # ДО ЦИКЛА: достаем email покупателя один раз, так как он один на весь чек
        customer_details = session.get('customer_details')      
        buyer_email = customer_details.get('email') if customer_details else None
                
        # Находим все товары, которые лежали в корзине в момент покупки
        cart_items = await find_user_cart_items(db=db, username=buyer_username)
        
        # Проходимся по каждому купленному товару по очереди
        for item in cart_items:
            product_id = item.product_id
            
            # Благодаря joinedload, вся инфа о товаре уже лежит в item.product
            product_info = item.product
            
            print(f"✅ Пользователь {buyer_username} купил товар {product_id} - {product_info.name}")

            previous_owner = product_info.owner_username

            # 3.1. Отправляем уведомление бывшему продавцу (если он есть)
            if previous_owner:
                await manager.send_personal_message(
                    message=f"Ваш товар {product_info.name} был куплен {buyer_username}", 
                    username=previous_owner
                )

            # 3.2. Меняем владельца товара в базе данных (используем сервис!)
            await product_service.change_product_ownership(buyer_username, product_id) 

            # 3.3. Отправляем письмо покупателю с купленным товаром            
            if buyer_email:
                send_email_to_user_task.delay(buyer_email, product_id)
                print(f"📨 Задача на отправку письма для {buyer_email} передана в Celery")
            else:
                print("⚠️ Stripe не передал email покупателя")

        # 4. После того как все товары обработаны, полностью очищаем корзину!
        await clear_user_cart(db=db, username=buyer_username)
        print(f"🛒 Корзина пользователя {buyer_username} успешно очищена.")

            
    # Обязательно возвращаем 200 OK, чтобы Stripe не пытался слать запрос снова
    return {'status': 'success'}