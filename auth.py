from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv
from database import db_pool, get_user

load_dotenv()

# Защищённый эндпоинт для пользователя и просмотра продуктов . Говорим FastAPI, что будем искать токен в заголовке: Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')


# Генерация JWT токена
async def create_tokens(data: dict, secret_key: str, algorithm: str, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        to_encode.update({'exp': datetime.utcnow() + expires_delta})

    # Access Token
    to_encode['type'] = 'access'
    access_token = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    
    # Refresh Token
    to_encode['type'] = 'refresh'
    to_encode.pop('exp', None)
    to_encode.update({'exp': timedelta(days=7)})
    refresh_token = jwt.encode(to_encode, secret_key, algorithm=algorithm)

    # Сохранение refresh-токена в базе 
    async with db_pool.connection() as conn: # Асинхронно берет соединение с базой данных из пула (db_pool), как ключ от машины, чтобы выполнить запрос.
        async with conn.cursor() as cur:
        # Создаёт курсор (cur) для выполнения SQL-запросов. 
        # Курсор — это специальный объект в библиотеке psycopg2, позволяет Python взаимодействовать с БД PostgreSQL. 
        # Он действует как "указатель" или "инструмент", с помощью которого ты отправляешь SQL-запросы (например, SELECT, INSERT) и получаешь результаты.
        # with гарантирует, что курсор закроется автоматически после завершения блока. 
            try:
                refresh_expire = datetime.utcnow() + timedelta(days=7)
                await cur.execute(
                        # %s — заполнители, которые заменяются на значения из кортежа (data['sub'], refresh_token, refresh_expire)
                        "INSERT INTO refresh_tokens (username, refresh_token, expiry) VALUES (%s, %s, %s)",
                        (data['sub'], refresh_token, refresh_expire)
                    )
                await conn.commit()
            # Ловит любые ошибки (например, если таблица не существует или данные некорректны).
            except Exception as e:
                # Откатывает изменения, если произошла ошибка, чтобы база осталась в прежнем состоянии.
                await conn.rollback()
                raise HTTPException(status_code=500, detail=f"Ошибка сохранения refresh-токена: {str(e)}")
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'bearer'
            }

# Защищённый эндпоинт для просмотра продуктов  
# Функция для извлечения имени пользователя из токена. Использует Depends(oauth2_scheme) для автоматической проверки токена(авторизации юзера)
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try: 
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM', 'HS256')])
        username: str = payload.get('sub')
        if username is None:
            raise HTTPException(status_code=401, detail='Invalid authentication credentials')
        user = await get_user(username)
        if user is None:
            raise HTTPException(status_code=401, detail='Invalid authentication credentials')
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid authentication credentials')