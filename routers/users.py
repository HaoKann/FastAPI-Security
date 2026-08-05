from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from s3_service import s3_client
from auth import get_current_user
from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from database import get_db_session
from models import User

router = APIRouter(tags=['Users'])

@router.post('/users/me/avatar')
async def update_avatar(
    file: Annotated[UploadFile, File(...)],
    current_user: dict = Depends(get_current_user), # Требуем, чтобы пользователь был залогинен
    db: AsyncSession = Depends(get_db_session) # Подключаемся к базе через SQLAlchemy
):
    # 1. Проверяем формат файла (только картинки)
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # 2. Загружаем файл в MinIO и получаем ссылку
    # (FastAPI передает файл потоком, не загружая память)
    try:
        avatar_url = await s3_client.upload_file(file)
        if not avatar_url:
            raise Exception("S3 client returned None")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки в S3: {e}")
        # Возвращаем красивую ошибку фронтенду, а не 500 Internal Server Error
        raise HTTPException(status_code=503, detail='Сервис хранения картинок сейчас недоступен. Попробуйте позже')
    
    # Берем username из словаря current_user
    username = current_user['username']
    
    # 3. Записываем ссылку в базу данных с помощью SQLAlchemy
    stmt = (
        update(User)
        .where(User.username == username)
        .values(avatar_url=avatar_url)
    )
    
    await db.execute(stmt)
    
    await db.commit()

    return {
        "message": "Avatar updated successfully",
        "avatar_url": avatar_url,
        "user": current_user
    }



