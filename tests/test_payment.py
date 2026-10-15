from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
import io
from services.pdf_service import generate_receipt_pdf

client = TestClient(app)

def test_send_receipt():
    """Тест успешной отправки задачи генерации чека в Celery."""
    
    # С помощью patch заменяем реальную отправку в Celery на заглушку (mock),
    # чтобы при прогоне автотестов не отправлялись реальные письма
    with patch("bg_tasks.send_email_to_user_task.delay") as mock_celery_task:
        
        # Настраиваем возвращаемое значение заглушки
        mock_celery_task.return_value = True
        
        # Делаем запрос к нашему API (эндпоинт должен быть объявление в main.py или роутере)
        response = client.post(
            '/payment/api/test_receipt',
            params={
                "email": "damirbaizhanov02042005@gmail.com",
                "product_id": 101,
                "amount": 150.00
            }
        )
        
        # Проверяем ответы
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        
        # Проверяем, что задача Celery действительно вызывалась 1 раз с правильными аргументами
        mock_celery_task.assert_called_once_with(
            user_email='damirbaizhanov02042005@gmail.com',
            product_id=101,
            amount=150.00,
            currency="usd"
        )
              
def test_generate_receipt_pdf_success():
    """Тест успешной генерации PDF-чека."""
    payment_id = "test_pay_12345"
    amount = 99.99
    currency = 'usd'
    user_email = 'testuser@example.com'
    
    # Вызываем функцию генерации
    pdf_buffer = generate_receipt_pdf(
        user_email=user_email,
        payment_id=payment_id,
        amount=amount,
        currency=currency
    )
    
    # 1. Проверяем, что вернулся объект io.BytesIO
    assert isinstance(pdf_buffer, io.BytesIO)
    
    # 2. Проверяем, что курсор находится в начале файла (благодаря buffer.seek(0))
    assert pdf_buffer.tell() == 0
    
    # 3. Получаем байты PDF
    pdf_bytes = pdf_buffer.getvalue()
    
    # 4. Файл не должен быть пустым
    assert len(pdf_bytes) > 0
    
    # 5. Проверяем "магические байты" заголовка PDF (любой валидный PDF начинается с %PDF)
    assert pdf_bytes.startswith(b"%PDF")
        
        
def test_generate_receipt_pdf_different_currencies_and_amount():
    """Тест генерации чека с целыми числами и другими валютами."""
    pdf_buffer = generate_receipt_pdf(
        payment_id='pay_999',
        amount=100.0,
        currency='eur',
        user_email="buyer@domain.com"
    )
    
    pdf_bytes = pdf_buffer.getvalue()
    
    assert isinstance(pdf_buffer, io.BytesIO)
    assert pdf_bytes.startswith(b"%PDF")