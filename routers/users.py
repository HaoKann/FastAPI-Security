from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from s3_service import s3_client
from auth import get_current_user
from database import get_pool

router = APIRouter(tags=['Users'])

@router.patch('/users/me/avatar')
async def update_avatar(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user), # Требуем, чтобы пользователь был залогинен
    pool = Depends(get_pool) #  Подключаемся к базе
):
    # 1. Проверяем формат файла (только картинки)
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # 2. Загружаем файл в MinIO и получаем ссылку
    # (FastAPI передает файл потоком, не загружая память)
    avatar_url = await s3_client.upload_file(file)

    # 3. Записываем ссылку в базу данных
    # Используем $1, $2 для защиты от SQL-инъекций
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET avatar_url = $1 WHERE username = $2",
            avatar_url,
            current_user
        )

    return {
        "message": "Avatar updated successfully",
        "avatar_url": avatar_url,
        "user": current_user
    }



