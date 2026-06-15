import stripe
import uuid
from fastapi import HTTPException
from config import settings
from routers.products import Product
from models import User


# Инициализируем Stripe с нашим секретным ключом из config.py
stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentService:
    async def create_checkout_session(self, product: Product, user: User) -> str:
        """
        Создает сессию оплаты в Stripe и возвращает защищенный URL для редиректа.
        """
        # 1. Переводим цену в центы (Stripe принимает только целые числа в минимальных единицах валюты)
        # Например: $10.50 -> 1050 центов
        price_in_cents = int(product.price * 100)

        # 2. Генерируем Idempotency Key (защита от случайных повторных списаний)
        # Уникальный ключ: юзер + товар + случайный UUID.
        # Если юзер кликнет 5 раз подряд, Stripe создаст только одну сессию для этого ключа.
        idem_key = f"checkout_{user.username}_prod_{product.id}_{uuid.uuid4()}"

        try:
            # Создаем саму сессию в Stripe
            session = stripe.checkout.Session.create(
                payment_method_types=['card'], # Разрешаем платить картами
                line_items=[{
                    'price_data': {
                        'currency':'usd',
                        'product_data': {
                            'name':product.name,
                            'description': f'Породавец: {product.owner_username}'
                        },
                        'unit_amount': price_in_cents,
                    },
                    'quantity': 1,
                }],
                mode='payment', # Разовый платеж (не подписка)

                # В metadata мы кладем ID товара и юзера.
                # Когда оплата пройдет, Stripe пришлет нам вебхук с этими данными, 
                # и мы поймем, кто за что заплатил.
                metadata={
                    "product_id": str(product.id),
                    "username": user.username
                },

                # Куда перекинуть юзера после успешной или отмененной оплаты
                # Пока ставим заглушки на локалхост
                success_url="http://localhost:8000/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:8000/cancel",

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
 