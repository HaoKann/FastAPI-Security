import asyncio
from aioboto3 import Session
from config import settings
import json
import sys

# Хак для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def make_public():
    # 👇 ИСПРАВЛЕНИЕ ЗДЕСЬ:
    # Мы подменяем "minio" на "localhost", чтобы скрипт работал с твоего ПК
    endpoint = settings.S3_ENDPOINT_URL.replace("minio", "localhost")
    
    print(f"🔌 Подключение к: {endpoint}")

    session = Session()
    async with session.client(
        "s3",
        endpoint_url=endpoint, # Используем исправленный адрес
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    ) as s3:
        bucket = settings.S3_BUCKET_NAME
        
        try:
            # Проверяем, есть ли бакет
            await s3.head_bucket(Bucket=bucket)
            print(f"✅ Бакет '{bucket}' найден.")
        except:
            print(f"❌ Бакет '{bucket}' не найден или недоступен. Пробуем создать...")
            await s3.create_bucket(Bucket=bucket)

        print(f"🔓 Открываем доступ для бакета: {bucket}...")
        
        # Политика: Public Read
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicRead",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"]
                }
            ]
        }
        
        await s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        print("✅ Успех! Бакет теперь публичный. Обнови картинку в браузере!")

if __name__ == "__main__":
    asyncio.run(make_public())