from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv
from database import get_user

load_dotenv()

# Говорим FastAPI, что будем искать токен в заголовке: Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')


# Генерация JWT токена
async def create_tokens(db_pool, data: dict, secret_key: str, algorithm: str, expires_delta: Optional[timedelta] = None):
    # Создаём копию данных для модификации
    to_encode = data.copy()

    # Преобразуем timedelta в timestamp (количество секунд с эпохи)
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        to_encode.update({'exp': expire.timestamp()})

    # Access Token
    to_encode['type'] = 'access'
    print("to_encode:", to_encode)
    access_token = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    
    # Refresh Token
    to_encode['type'] = 'refresh'
    to_encode.pop('exp', None)
    to_encode.update({'exp':(datetime.utcnow() + timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 7)))).timestamp()})
    refresh_token = jwt.encode(to_encode, secret_key, algorithm=algorithm)

    # Сохранение refresh-токена в базе 
    async with db_pool.acquire() as conn: # Асинхронно берет соединение с базой данных из пула (db_pool), как ключ от машины, чтобы выполнить запрос.
            try:
                refresh_expire = datetime.utcnow() + timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 7)))
                await conn.execute(
                        "INSERT INTO refresh_tokens (username, refresh_token, expiry) VALUES ($1, $2, $3)",
                        data['sub'], refresh_token, refresh_expire
                    )
            # Ловит любые ошибки (например, если таблица не существует или данные некорректны).
            except Exception as e:
                # Откатывает изменения, если произошла ошибка, чтобы база осталась в прежнем состоянии.
                raise HTTPException(status_code=500, detail=f"Ошибка сохранения refresh-токена: {str(e)}")
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'bearer'
            }

# Защищённый эндпоинт для просмотра продуктов  
# Функция для извлечения имени пользователя из токена. Использует Depends(oauth2_scheme) для автоматической проверки токена(авторизации юзера)
def get_current_user_dependency(db_pool):
    async def get_current_user(token: str = Depends(oauth2_scheme)): # Токен извлечётся автоматически
        try:
            print('Decoding token with SECRET_KEY:', os.getenv('SECRET_KEY'), 'and ALGORITHM:', os.getenv('ALGORITHM', 'HS256'))
            payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM', 'HS256')])
            username: str = payload.get('sub')
            print('Decoded username:', username)
            if username is None:
                raise HTTPException(status_code=401, detail='Invalid authentication credentials')
            user = await get_user(db_pool, username)
            print('User from DB:', user)
            if user is None:
                raise HTTPException(status_code=401, detail='Invalid authentication credentials')
            return username
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail='Invalid authentication credentials')
    return get_current_user