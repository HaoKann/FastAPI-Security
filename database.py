import asyncpg
from passlib.context import CryptContext
from typing import Optional

# Хэширование паролей 
# Утилиты для аутентификации 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_db_pool():
    return await asyncpg.create_pool(dsn="postgresql://postgres:123456789@localhost/fastapi_auth")

db_pool = get_db_pool()

# Функция для получения пользователя
async def get_user(username: str) -> Optional[dict]:
    # Получает соединение с базой данных из пула подключений (db_pool).
    async with db_pool.connection() as conn:
    #  Обеспечивает безопасное управление ресурсами, гарантируя,
    #  что соединение с базой будет возвращено, даже если произойдёт ошибка.
        async with conn.cursor() as cur: # conn.cursor() — это как открыть текстовый редактор для работы с базой. 
            # Курсор нужен, чтобы отправлять команды (например, SELECT) и получать результаты.
            # %s — это placeholder (заполнитель), 
            # который заменяется на безопасное значение из кортежа (username,). Это защищает от SQL-инъекций.
            await cur.execute("SELECT username, hashed_password FROM users WHERE username = %s", (username,)) # (username,) — кортеж с одним элементом (запятая обязательна для одиночного значения), передающий имя пользователя в запрос.
            # Извлекает одну строку результата запроса.
            # После выполнения execute курсор содержит результат запроса. 
            # fetchone() берёт первую (и, в данном случае, единственную) строку.
            user = await cur.fetchone()
            if user:
                return {"username": user[0], "hashed_password": user[1]}
            return None
        

# Хэширует пароль с помощью bcrypt для безопасного хранения.
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Функции для работы с паролями
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

__all__ = ['db_pool', 'get_user', 'get_password_hash', 'verify_password']
