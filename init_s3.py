import asyncio
from aioboto3 import Session
from config import settings # <--- Импортируем объект settings
import json
import sys

# Хак для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def make_bucket_public():
    print(f"Подключение к S3: {settings.S3_ENDPOINT_URL}") # <-- Используем settings.
    
    session = Session()
    async with session.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    ) as s3:
        bucket_name = settings.S3_BUCKET_NAME
        
        # 1. Проверяем/Создаем бакет
        try:
            await s3.head_bucket(Bucket=bucket_name)
            print(f"Бакет '{bucket_name}' найден.")
        except:
            print(f"Бакет '{bucket_name}' не найден. Создаем...")
            await s3.create_bucket(Bucket=bucket_name)

        # 2. Политика публичного доступа
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicRead",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                }
            ]
        }
        
        # 3. Применяем
        await s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        print(f"✅ Успех! Бакет '{bucket_name}' готов к работе.")

if __name__ == "__main__":
    asyncio.run(make_bucket_public())