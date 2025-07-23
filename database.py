import asyncpg
from passlib.context import CryptContext
from typing import Optional
import os

# Хэширование паролей 
# Утилиты для аутентификации 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_db_pool():
    return await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'fastapi_auth'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '123456789')
    )


# Функция для получения пользователя
async def get_user(db_pool, username: str) -> Optional[dict]:
    # Конструкция async with гарантирует, что соединение будет корректно возвращено в пул после завершения блока, 
    # даже если возникнет ошибка.
    # Получает соединение с базой данных из пула подключений (db_pool).
    # db_pool.acquire() асинхронно берёт соединение из пула
    async with db_pool.acquire() as conn:
        # fetchrow() выполняет запрос и возвращает одну строку как словарь, что упрощает доступ к данным (user["username"] вместо user[0]).
        # $1 как параметр вместо %s по синтаксису asyncpg, заменяемый значением username
        # Это безопасный способ передачи данных, защищающий от SQL-инъекций (в отличие от ручного подстановления строк).
        user = await conn.fetchrow("SELECT username, hashed_password FROM users WHERE username = $1", username)
        if user:
            return {'username': user['username'], 'hashed_password': user['hashed_password']}
        return None
        

# Хэширует пароль с помощью bcrypt для безопасного хранения.
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Функции для работы с паролями
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

__all__ = ['get_db_pool', 'get_user', 'get_password_hash', 'verify_password']
