from datetime import timedelta
from typing import Optional, List
 # BackgroundTasks добавляет поддержку фоновых задач.
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging
# starlette — это основа FastAPI, а status — набор кодов для HTTP и WebSocket.
from starlette import status

from database import db_pool, get_password_hash, verify_password, get_user, get_db_pool
from bg_tasks import compute_factorial_async, compute_sum_range
from websocket import manager
from auth import create_tokens, get_current_user, oauth2_scheme
import os

load_dotenv()

# Настройки логирования
# Базовая конфигурация логирования
# Уровень INFO означает, что будут записываться информационные сообщения и выше (например, ошибки).
logging.basicConfig(level=logging.INFO)
# Создаёт логгер, привязанный к текущему модулю (__name__ — имя файла, например, main). 
# Это позволяет разделять логи по модулям.
logger = logging.getLogger(__name__)


app = FastAPI()

# Инициализация пула соединений при старте приложения
@app.on_event('startup')
async def startup_event():
    global db_pool
    db_pool = await get_db_pool()

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

# Определяет структуру данных для регистрации (имя и пароль)
class UserCreate(BaseModel):
    username: str
    password: str



# Эндпоинт для регистрации
# Принимает данные пользователя, проверяет, не существует ли такой username, хэширует пароль и сохраняет в users. 
# Затем выдаёт токены.
@app.post('/register', response_model=Token)
# user: UserCreate — объект, созданный из JSON-запроса (например, {"username": "alice", "password": "password123"}).
async def register(user: UserCreate, background_tasks: BackgroundTasks = None):
    # Асинхронно проверяет наличие пользователя.
    if await get_user(user.username):
        raise HTTPException(status_code=400, detail='Пользователь уже существует')
    hashed_password = get_password_hash(user.password)
    # Использует асинхронное соединение для записи.
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'INSERT INTO users (username, hashed_password) VALUES (%s, %s)',
                (user.username, hashed_password)
            )
    return await create_tokens(data={'sub': user.username}, secret_key=os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM', 'HS256'))

# Эндпоинт для получения токена
@app.post("/token", response_model=Token)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    return await create_tokens(
        data={"sub": user["username"]},
        secret_key=os.getenv('SECRET_KEY'),
        algorithm=os.getenv('ALGORITHM', 'HS256'),
        expires_delta=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
    )


# Эндпоинт для обновления токенов
@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(refresh_token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM', 'HS256')])
        username = payload.get("sub")
        if payload.get('type') != 'refresh' or not username:
            raise HTTPException(status_code=400, detail='Неверный refresh-токен')
        return await create_tokens(data={'sub':username}, secret_key=os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM','HS256'))
    except JWTError:
        raise HTTPException(status_code=400, detail='Неверный refresh токен')
    

# Защищенный эндпоинт для пользователя
@app.get('/protected')
async def protected_route(current_user: str = Depends(get_current_user)):
        return {'message': f'Привет, {current_user}! Это защищенная зона'}
   

# Защищённый эндпоинт, который возвращает список продуктов, принадлежащих текущему пользователю.
@app.get('/products/', response_model=List[Product])
async def get_products(current_user: str = Depends(get_current_user)):
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "SELECT id, name, price, owner_username FROM products WHERE owner_username = %s",
                    (current_user,)
                )
                products = await cur.fetchall() # Получает все строки результата.
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
           
# Эндпоинт для запуска вычисления суммы
@app.post('/compute/sum')
async def start_sum_computation(start: int, end: int, current_user: str = Depends(get_current_user), background_tasks: BackgroundTasks = None):
    if start > end:
        raise HTTPException(status_code=400, detail='Начало диапазона должно быть меньше или равно концу')
    # Проверка наличия объекта background_tasks
    if background_tasks:
        background_tasks.add_task(compute_sum_range, start, end, current_user)
    return {'message': f'Асинхронное вычисление суммы от {start} до {end} начато в фоне'}


# Эндпоинт для запуска фоновых задач
# Принимает число n, запускает вычисление факториала в фоне и сразу возвращает ответ.
@app.post('/compute/async')
# current_user: str = Depends(get_current_user) — проверяет авторизацию
# background_tasks: BackgroundTasks = None — объект для фоновых задач.
# BackgroundTasks — это специальный класс из FastAPI, который позволяет запускать задачи асинхронно после отправки HTTP-ответа.
# = None означает, что этот параметр необязательный. Если клиент не передаёт его явно (что обычно происходит), он будет None по умолчанию.
async def start_async_computation(n: int, current_user: str = Depends(get_current_user), background_tasks: BackgroundTasks = None):
    if n <= 0:
        raise HTTPException(status_code=400, detail='Число должно быть положительным')
    # проверяет, существует ли объект BackgroundTasks. Если он есть (например, передан в эндпоинт), задача добавляется в очередь фоновых задач. 
    # Если None (например, если ты вызовешь функцию напрямую без контекста FastAPI), задача не запустится.
    if background_tasks:
        # add_task — метод, который добавляет функцию compute_factorial в очередь фоновых задач с аргументами n (число) 
        # и current_user (имя пользователя).
        background_tasks.add_task(compute_factorial_async, n, current_user)
    return {'message': f'Асинхронные вычисления факториала {n} начато в фоне. Результат будет сохранен (максимум 3 попытки)'}


# Защищённый эндпоинт для создания нового продукта, доступный только авторизованным пользователям.
@app.post('/products/', response_model=Product, tags=['Products'])
async def create_product(name: str, price: float, background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    # RETURNING id, name, price, owner_username возвращает только что вставленные данные.
                    "INSERT INTO products (name, price, owner_username) VALUES (%s, %s, %s) RETURNING id, name, price, owner_username",
                    (name, price, current_user)
                )
                product_id = (await cur.fetchone())[0] # Получает первую (и единственную) строку результата вставки.
                await conn.commit()
                # ИСПРАВЛЕНО: Возвращаем Pydantic модель и отправляем JSON в broadcast
                new_product = Product(id=product_id, name=name, price=price, owner_username=current_user)
                background_tasks.add_task(manager.broadcast, f"Новый продукт: {new_product.json()}")
                return new_product
            except Exception as e:
                await conn.rollback()
                raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")







