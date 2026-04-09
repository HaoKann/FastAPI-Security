import aioboto3
from fastapi import UploadFile, HTTPException
from config import settings
import uuid # Чтобы создавать уникальные имена (avatar.jpg -> 123-abc-456.jpg)

class S3Service:
    def __init__(self):
        # Хитрый трюк: вытаскиваем регион (us-east-005) из ссылки Backblaze для правильной генерации подписей
        region = 'us-east-1'
        if 'backblaze' in settings.S3_ENDPOINT_URL:
            # Превращаем "https://s3.us-east-005.backblazeb2.com" -> "us-east-005"
            region = settings.S3_ENDPOINT_URL.replace('https://', '').split('.')[1]


        # Конфигурация для подключения к MinIO/AWS S3
        self.config = {
            "endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "region_name": region # <-- Обязательно для облака!
        }
        self.bucket = settings.S3_BUCKET_NAME
        self.session = aioboto3.Session()

    async def upload_file(self, file: UploadFile) -> str | None:
        """
        Загружает файл в хранилище и возвращает публичную ссылку.
        """
        # 1. Генерируем уникальное имя файла
        # split(".")[-1] берет расширение (например, "png" или "jpg")
        if not file.filename:
            return None # Если имени нет, прерываем функцию и возвращаем пустоту
        
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        try:
            # 2. Подключаемся к MinIO
            async with self.session.client("s3", **self.config) as s3:
                # 3. Загружаем файл (потоком)
                await s3.upload_fileobj(
                    file.file,
                    self.bucket,
                    unique_filename,
                    ExtraArgs={"ContentType": file.content_type} # Чтобы браузер понимал, что это картинка
                )

                # Возвращаем просто имя файла, чтобы записать его в БД (например, '123-456.png')
                return unique_filename
        
        except Exception as e:
            print(f"❌ S3 Upload Error: {e}")    
            raise HTTPException(status_code=500, detail="Failed to upload file")

    async def get_presigned_url(self, object_name: str, expires_in: int = 3600) -> str | None:
        """
        Генерирует временную ссылку (пропуск) на просмотр приватного файла.
        expires_in = 3600 (ссылка работает 1 час).
        """
        if not object_name:
            return None
        
        # Защита: если в базе осталась старая полная ссылка (http...), вытащим из нее только имя
        if object_name.startswith('http'):
            object_name = object_name.split('/')[-1]

        try:
            async with self.session.client('s3', **self.config) as s3:
                # Генерируем временный URL
                url = await s3.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={'Bucket': self.bucket, 'Key': object_name},
                    ExpiresIn=expires_in
                )
                return url
        except Exception as e:
            print(f"❌ Error generating presigned URL: {e}")
            return None

# Создаем один экземпляр, чтобы использовать его везде
s3_client = S3Service()