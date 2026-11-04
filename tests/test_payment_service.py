from fastapi import HTTPException
import pytest
from unittest.mock import MagicMock, patch
import stripe
from services.payment_service import PaymentService

@pytest.mark.asyncio
@patch("stripe.checkout.Session.create") # Подменяем метод Stripe
async def test_create_checkout_session_success(mock_stripe_create):
    service = PaymentService()
    
    # 1. Готовим фейкового юзера
    fake_user = MagicMock()
    fake_user.username = 'test_user'
    
    # 2. Готовим фейковый товар и кладем его в фейковую корзину
    fake_product = MagicMock()
    fake_product.name = 'test_product'
    fake_product.price = 10.00
    fake_product.owner_username = 'test_owner_username'
    
    fake_cart_item = MagicMock()
    fake_cart_item.cart_id = 1
    fake_cart_item.amount = 2
    fake_cart_item.product = fake_product
    
    cart_items = [fake_cart_item]
    
    # 3. Настраиваем ответ Stripe
    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.com/pay/123'
    
    mock_stripe_create.return_value = fake_session
    session_url = await service.create_checkout_session(cart_items=cart_items, user = fake_user)
    
    assert session_url == fake_session.url
    
@pytest.mark.asyncio
@patch('stripe.checkout.Session.create')
async def test_create_checkout_stripe_error(mock_stripe_create):
    service = PaymentService()
    
    # 1. Готовим фейкового юзера
    fake_user = MagicMock()
    fake_user.username = 'test_user'
        
    # 2. Готовим фейковый товар и кладем его в фейковую корзину
    fake_product = MagicMock()
    fake_product.name = 'test_product'
    fake_product.price = 10.00
    fake_product.owner_username = 'test_owner_username'
        
    fake_cart_item = MagicMock()
    fake_cart_item.cart_id = 1
    fake_cart_item.amount = 2
    fake_cart_item.product = fake_product
        
    cart_items = [fake_cart_item]
        
    # 3. Настраиваем ответ Stripe
    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.com/pay/123'
    
    # 4. Выбрасываем ошибку 
    mock_stripe_create.side_effect = stripe.error.StripeError('Fake error!', http_body=None)
    
    # 5. Ловим HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.create_checkout_session(cart_items=cart_items, user=fake_user)
        
    assert exc_info.value.status_code == 400

    

@pytest.mark.asyncio
@patch('stripe.checkout.Session.create')
async def test_create_checkout_exception(mock_stripe_create):
    service = PaymentService()
    
    # 1. Готовим фейкового юзера
    fake_user = MagicMock()
    fake_user.username = 'test_user'
        
        # 2. Готовим фейковый товар и кладем его в фейковую корзину
    fake_product = MagicMock()
    fake_product.name = 'test_product'
    fake_product.price = 10.00
    fake_product.owner_username = 'test_owner_username'
        
    fake_cart_item = MagicMock()
    fake_cart_item.cart_id = 1
    fake_cart_item.amount = 2
    fake_cart_item.product = fake_product
        
    cart_items = [fake_cart_item]
        
    # 3. Настраиваем ответ Stripe
    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.com/pay/123'
    
    # 4. Выбрасываем ошибку 
    mock_stripe_create.side_effect = Exception('Error!')
    
    # 5. Ловим HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.create_checkout_session(cart_items=cart_items, user=fake_user)
        
    assert exc_info.value.status_code == 500

    
    