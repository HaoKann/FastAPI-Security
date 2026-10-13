from bg_tasks import send_email_to_user_task
from fastapi import app

@app.post('/api/test_receipt')
def test_send_receipt(email: str, product_id: int = 1, amount: float = 49.99 ):
    """Тестовый эндпоинт для проверки генерации PDF и отправки Email."""
    send_email_to_user_task(
        user_email=email,
        amount=amount,
        product_id=product_id,
        currency='usd'
    )
    return {'status': 'ok', 'message': f'Задача отправлена в Celery для {email}'}