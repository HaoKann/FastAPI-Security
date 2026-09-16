import stripe
import uuid
from fastapi import HTTPException
from config import settings


# Инициализируем Stripe с нашим секретным ключом из config.py
stripe.api_key = settings.STRIPE_SECRET_KEY


#  Создает сессию оплаты в Stripe и возвращает защищенный URL для редиректа.

class PaymentService:
    async def create_checkout_session(self, cart_items: list, user: dict) -> str:
        
        stripe_line_items = []
        
        for item in cart_items:
            # 1. Переводим цену в центы (Stripe принимает только целые числа в минимальных единицах валюты)
            price_in_cents = int(item.product['price'] * 100)
            
            # 2. Создаем словарь для конкретного товара в формате Stripe
            line_item = {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item.product.name,
                        'description': f"Продавец {item.product.owner_username}"
                    },
                    'unit_amount': price_in_cents,
                },
                # 3. Указываем количество именно этого товара, которое юзер добавил в корзину
                'quantity': item.amount,
            }
            
            # 4. Добавляем готовый товар в общий список
            stripe_line_items.append(line_item)
        
        # 5. Генерируем Idempotency Key (защита от дублей)
        # Теперь он привязан к корзине пользователя, а не к одному товару
        idem_key = f"checkout_cart{user['username']}_{uuid.uuid4()}"

        try:
            # Создаем саму сессию в Stripe
            session = stripe.checkout.Session.create(
                payment_method_types=['card'], # Разрешаем платить картами
                
                mode='payment', # Разовый платеж (не подписка)

                # В metadata кладем только username.
                # Вебхук по этому имени найдет корзину и обработает покупку.
                metadata={
                    "username": user['username']
                },

                # Куда перекинуть юзера после успешной или отмененной оплаты
                # Пока ставим заглушки на локалхост
                success_url="http://localhost:8001/payment/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:8001/payment/cancel",

                # Применяем защиту от дублей
                idempotency_key=idem_key
            )

            # Возвращаем URL, на который нужно перенаправить пользователя
            return session.url
        
        except stripe.error.StripeError as e:
            print(f"❌ Stripe Error: {e}")
            raise HTTPException(status_code=400, detail='Ошибка при создании платежа на стороне Stripe')
        except Exception as e:
            print(f"❌ System Error: {e}")
            raise HTTPException(status_code=500, detail='Внутренняя ошибка сервера')


# Создаем единственный экземпляр сервиса (паттерн Singleton)
payment_service = PaymentService()
 