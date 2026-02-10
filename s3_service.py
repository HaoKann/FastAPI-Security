import aioboto3
from fastapi import UploadFile, HTTPException
from config import settings
import uuid # Чтобы создавать уникальные имена (avatar.jpg -> 123-abc-456.jpg)

class S3Service:
    def __init__(self):
        # Конфигурация для подключения к MinIO/AWS S3
        self.config = {
            "endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
        }
        self.bucket = settings.S3_BUCKET_NAME
        self.session = aioboto3.Session()

    async def upload_file(self, file: UploadFile) -> str:
        """
        Загружает файл в хранилище и возвращает публичную ссылку.
        """
        # 1. Генерируем уникальное имя файла
        # split(".")[-1] берет расширение (например, "png" или "jpg")
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
            
            # 4. Формируем ссылку
            # Внутри Docker ссылка выглядит как http://minio:9000/...
            file_url = f"{settings.S3_ENDPOINT_URL}/{self.bucket}/{unique_filename}"

            # Браузер не знает хост "minio", он знает "localhost".
            # Меняем minio на localhost, чтобы можно было открыть картинку.
            if "minio" in file_url:
                file_url = file_url.replace('minio','localhost')

            return file_url
        
        except Exception as e:
            print(f"❌ S3 Upload Error: {e}")    
            raise HTTPException(status_code=500, detail="Failed to upload file")


# Создаем один экземпляр, чтобы использовать его везде
s3_client = S3Service()