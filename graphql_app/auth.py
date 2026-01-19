import jwt
import os
from fastapi import Request


SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_for_local_development")
ALGORITHM = 'HS256'


# --- 1. Вспомогательная функция проверки токена ---
def authenticate_user(request: Request) -> str:
    """
    Достает токен из заголовка, проверяет его и возвращает имя пользователя.
    Если что-то не так — выбрасывает ошибку.
    """
    # 1. Достаем заголовок Authorization
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise Exception("Not authenticated: Заголовок Authorization отсутствует")
    
    # 2. Ожидаем формат "Bearer <token>"
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != 'bearer':
            raise Exception("Invalid authentication scheme")
    
        # 3. Расшифровываем токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise Exception("Invalid token: username not found")
        
        return username
    
    # Ловим любую ошибку (просрочен, мусор вместо токена, ошибка подписи)
    # и возвращаем понятное сообщение
    except Exception:
        raise Exception("Could not validate credentials (Invalid Token)")