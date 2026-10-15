# Сервис генерации PDF файлов оплаты который будет принимать данные о платеже и возвращать PDF-файл
# в виде байтового потока io.BytesIO без сохранения на диск

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def generate_receipt_pdf(payment_id: str, amount: float, currency: str, user_email: str ) -> io.BytesIO:
    """Генерирует PDF-чек в памяти и возвращает BytesIO поток."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Заголовок / Шапка
    p.setFont('Helvetica-Bold', 20)
    p.drawString(50, height - 60, "FastApi Store")
    
    p.setFont("Helvetica", 10)
    p.setFillColor(colors.gray)
    p.drawString(50, height - 75, "Payment Receipt")
    
    # Разделительная линия
    p.setStrokeColor(colors.lightgrey)
    p.setLineWidth(1)
    p.line(50, height - 90, width - 50, height - 90)
    
    # Детали платежа
    p.setFillColor(colors.black)
    p.setFont('Helvetica-Bold', 12)
    p.drawString(50, height - 130, 'Payment Details:')
    
    p.setFont('Helvetica', 11)
    p.drawString(50, height - 160, f"Receipt ID: {payment_id}")
    p.drawString(50, height - 180, f"Customer Email: {user_email}")
    p.drawString(50, height - 200, f"SUCCESS ")

    # Таблица / Сумма
    p.setFillColor(colors.whitesmoke)
    p.rect(50, height - 260, width - 100, 40, fill=1, stroke=0)
    
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(70, height - 245, "Total Paid:")
    p.drawString(width - 150, height - 245, f"{amount:.2f} {currency.upper()}")
    
    # Подвал
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColor(colors.gray)
    p.drawString(50, 50, "Thank you for your purchase! FastAPI-Security Team.")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer
    
    