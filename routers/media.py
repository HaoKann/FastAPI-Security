from fastapi import APIRouter, UploadFile, File, HTTPException
from s3_service import s3_client

router = APIRouter(
    prefix="/media",
    tags=["Media"]
)

@router.post('/upload')
async def upload_file(file: UploadFile = File(...)):
    # 1. Проверка: только картинки
    if not file.content_type.startswith("image/"):
        # Выбрасываем ошибку 400 (Bad Request)
        return HTTPException(status_code=400, detail='File must be an image')
    
    # 2. Загрузка
    url = await s3_client.upload_file(file)

    return {
        "filename": file.filename,
        "url": url
    }
