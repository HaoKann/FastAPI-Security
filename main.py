from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')


# Создание пула подключений
# Загружает зависимости и настраивает подключение к PostgreSQL через пул соединений (ThreadedConnectionPool). 
# Это позволяет эффективно управлять соединениями с базой.
db_pool = pool.ThreadedConnectionPool(
    1, # минимальное количество подключений
    20, # максимальное количество подключений
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)


# Настройка
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30 
REFRESH_TOKEN_EXPIRE_DAYS = 7 

app = FastAPI()

# Функция для получения пользователя
def get_user(username: str):
    # Получает соединение с базой данных из пула подключений (db_pool).
    conn = db_pool.getconn()
    # try: и finally: 
    #  Обеспечивает безопасное управление ресурсами, гарантируя,
    #  что соединение с базой будет возвращено, даже если произойдёт ошибка.
    try: # — блок, где выполняются операции, которые могут вызвать ошибку (например, запрос к базе).
        with conn.cursor() as cur: # conn.cursor() — это как открыть текстовый редактор для работы с базой. 
            # Курсор нужен, чтобы отправлять команды (например, SELECT) и получать результаты.
            # %s — это placeholder (заполнитель), 
            # который заменяется на безопасное значение из кортежа (username,). Это защищает от SQL-инъекций.
            cur.execute("SELECT username, hashed_password FROM users WHERE username = %s", (username,)) # (username,) — кортеж с одним элементом (запятая обязательна для одиночного значения), передающий имя пользователя в запрос.
            # Извлекает одну строку результата запроса.
            # После выполнения execute курсор содержит результат запроса. 
            # fetchone() берёт первую (и, в данном случае, единственную) строку.
            user = cur.fetchone()
            if user:
                return {"username": user[0], "hashed_password": user[1]}
            return None
    finally: # — блок, который выполняется в любом случае (успех или ошибка), чтобы вернуть соединение в пул (db_pool.putconn(conn)).
        db_pool.putconn(conn)

# Хэширование паролей 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Pydantic модели
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

# FastAPI использует эту модель для автоматической валидации (например, проверяет, что price — число) и генерации документации в Swagger. 
# В response_model она гарантирует, что ответ будет соответствовать этой структуре.
class Product(BaseModel):
    id: int
    name: str
    price: float
    owner_username: str

class UserCreate(BaseModel):
    username: str
    password: str

# Функции для работы с паролями
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Генерация JWT токена
def create_tokens(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    # Access Token
    access_expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({'exp': access_expire, 'type': 'access'})
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Refresh Token
    refresh_expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({'exp': refresh_expire, 'type': 'refresh'})
    refresh_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Сохранение refresh-токена в базе 
    conn = db_pool.getconn()  # Берет соединение с базой данных из пула (db_pool), как ключ от машины, чтобы выполнить запрос.
    try:
        # Создаёт курсор (cur) для выполнения SQL-запросов. 
        # Курсор — это специальный объект в библиотеке psycopg2, позволяет Python взаимодействовать с БД PostgreSQL. 
        # Он действует как "указатель" или "инструмент", с помощью которого ты отправляешь SQL-запросы (например, SELECT, INSERT) и получаешь результаты.
        # with гарантирует, что курсор закроется автоматически после завершения блока. 
        with conn.cursor() as cur:
            cur.execute(
                # %s — заполнители, которые заменяются на значения из кортежа (data['sub'], refresh_token, refresh_expire)
                "INSERT INTO refresh_tokens (username, refresh_token, expiry) VALUES (%s, %s, %s)",
                    (data['sub'], refresh_token, refresh_expire)
            )
            conn.commit()
    # Ловит любые ошибки (например, если таблица не существует или данные некорректны).
    except Exception as e:
        # Откатывает изменения, если произошла ошибка, чтобы база осталась в прежнем состоянии.
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения refresh-токена: {str(e)}")
    finally:
        # Возвращает соединение в пул, как сдача ключа после поездки
        db_pool.putconn(conn)

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer'
    }

# Эндпоинт для регистрации
@app.post('/register', response_model==Token)


# Эндпоинт для получения токена
@app.post("/token", response_model=Token)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    
    return create_tokens(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )


# Эндпоинт для обновления токенов
@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Неверный тип токена")
        
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=400, detail="Невалидный токен")
        
        # Проверка наличия refresh-токена в базе
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    # Выполняет запрос для поиска refresh-токена в базе, проверяя, что он ещё не истёк
                    "SELECT refresh_token FROM refresh_tokens WHERE username = %s AND expiry > %s",
                    (username, datetime.utcnow())
                )
                # Извлекает первую строку результата (если токен найден).
                stored_refresh_token = cur.fetchone()
                if not stored_refresh_token or stored_refresh_token[0] != refresh_token:
                    raise HTTPException(status_code=401, detail="Невалидный refresh-токен")
                
                # Удаляет использованный refresh-токен из базы (одноразовый токен).
                cur.execute(
                    "DELETE FROM refresh_tokens WHERE username = %s AND refresh_token = %s",
                    (username, refresh_token)
                )
                conn.commit()
                
                return create_tokens(data={"sub": username})
        # Exception — это общий класс всех исключений в Python. 
        # Указывая except Exception, ты ловишь любые ошибки, которые могут возникнуть в блоке try
        # as e присваивает пойманное исключение переменной e, 
        # чтобы ты мог использовать информацию об ошибке (например, текст ошибки).
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Ошибка проверки refresh-токена: {str(e)}")
        finally:
            db_pool.putconn(conn)

    except JWTError:
        raise HTTPException(status_code=401, detail="Невалидный или просроченный токен")
    


# Защищённый эндпоинт для пользователя и просмотра продуктов . Говорим FastAPI, что будем искать токен в заголовке: Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')

# Защищенный эндпоинт для пользователя
@app.get('/protected')
async def protected_route(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=401, detail='Неверный токен')
        return {'message': f'Привет, {username}! Это защищенная зона'}
    except JWTError:
        raise HTTPException(status_code=401, detail='Неверный токен')

# Защищённый эндпоинт для просмотра продуктов  
# Функция для извлечения имени пользователя из токена. Использует Depends(oauth2_scheme) для автоматической проверки токена(авторизации юзера)
def get_current_user(token: str = Depends(oauth2_scheme)):
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=401, detail='Неверный токен')
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail='Неверный токен')


# Защищённый эндпоинт, который возвращает список продуктов, принадлежащих текущему пользователю.
@app.get('/products/', response_model=List[Product])
async def get_products(current_user: str = Depends(get_current_user)):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, price, owner_username FROM products WHERE owner_username = %s",
                (current_user,)
            )
            products = cur.fetchall() # Получает все строки результата.
            if not products:
                return [] # Возвращаем пустой список, если продуктов нет
            return [
                {
                    "id": p[0], 
                    "name": p[1], 
                    "price": float(p[2]) if p[2] is not None else 0.0,
                    "owner_username": p[3]
                } 
                for p in products
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Ошибка при получении продуктов {str(e)}')
    finally:
        db_pool.putconn(conn)  # Возвращает соединение в пул, даже если произошла ошибка.


# Защищённый эндпоинт для создания нового продукта, доступный только авторизованным пользователям.
@app.post('/products/', response_model=Product)
async def create_product(name: str, price: float, current_user: str = Depends(get_current_user)):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                # RETURNING id, name, price, owner_username возвращает только что вставленные данные.
                "INSERT INTO products (name, price, owner_username) VALUES (%s, %s, %s) RETURNING id, name, price, owner_username",
                (name, price, current_user)
            )
            product = cur.fetchone() # Получает первую (и единственную) строку результата вставки.
            conn.commit()
            return {"id": product[0], "name": product[1], "price": float(product[2]), "owner_username": product[3]}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")
    finally:
        db_pool.putconn(conn)