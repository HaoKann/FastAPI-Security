from datetime import timedelta
from typing import Optional, List
 # BackgroundTasks добавляет поддержку фоновых задач.
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging
# starlette — это основа FastAPI, а status — набор кодов для HTTP и WebSocket.
from starlette import status

from database import connect_to_db, get_pool, close_db_connection 
from bg_tasks import compute_factorial_async, compute_sum_range
from auth import create_tokens, get_current_user
import os
from websocket import manager, WebSocket, WebSocketDisconnect

load_dotenv()

# Настройки логирования
# Базовая конфигурация логирования
# Уровень INFO означает, что будут записываться информационные сообщения и выше (например, ошибки).
logging.basicConfig(level=logging.INFO)
# Создаёт логгер, привязанный к текущему модулю (__name__ — имя файла, например, main). 
# Это позволяет разделять логи по модулям.
logger = logging.getLogger(__name__)


app = FastAPI()


# Настройка
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'


# Глобальная переменная для пула
db_pool = None

# Инициализация пула соединений при старте приложения
@app.on_event('startup')
async def startup_event():
    global db_pool
    db_pool = await get_db_pool()
    print('DB pool initialized:', db_pool is not None)
    if db_pool is None:
        print("Warning: Failed to initialize DB Pool. Check database connection.")


# Зависимость для получения db_pool
async def get_db_pool_dependency():
    global db_pool
    if db_pool is None:
        db_pool = await get_db_pool()
        print('DB Pool reinitialized in get_db:', db_pool is not None)
    return db_pool

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/token')

# Зависимость для текущего пользователя с передачей db_pool
# Упрощенная зависимость для текущего пользователя
async def get_current_user_simple(token: str = Depends(oauth2_scheme), db_pool = Depends(get_db_pool_dependency)):
    print('Token recieved from Depends:', token)
    print('Raw Authorization header:', oauth2_scheme.__dict__.get('header', 'Not found'))
    print('SECRET_KEY:', SECRET_KEY)
    print('ALGORITHM:', ALGORITHM)
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print('Decoded payload:', payload)
        username = payload.get('sub')
        if username is None or payload.get('type') != 'access':
            print('Invalid token structure:', {'sub': username, 'type': payload.get('type')})
            raise HTTPException(status_code=401, detail='Invalid token')
        user = await get_user(db_pool, username) 
        print('User from DB:', user)
        if user is None:
            print('User not found in DB for username:', username)
            raise HTTPException(status_code=401, detail='User not found')
        return username
    except JWTError as e:
        print('JWTError:', str(e))
        raise HTTPException(status_code=401, detail='Invalid token')
    except Exception as e:
        print('Unexpected error:', str(e))
        raise HTTPException(status_code=500, detail='Internal server error')


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
    if await get_user(db_pool, user.username):
        raise HTTPException(status_code=400, detail='Пользователь уже существует')
    hashed_password = get_password_hash(user.password)
    
    # Использует асинхронное соединение для записи.
    async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                'INSERT INTO users (username, hashed_password) VALUES ($1, $2)',
                user.username, hashed_password
            ) # Изменения фиксируются автоматически при выходе из блока, если нет ошибок
            return await create_tokens(db_pool, 
                                data={'sub': user.username}, 
                                secret_key=os.getenv('SECRET_KEY'), 
                                algorithm=os.getenv('ALGORITHM', 'HS256')
                                )

# Эндпоинт для получения токена
@app.post("/token", response_model=Token)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user(db_pool, form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    return await create_tokens(
        db_pool,
        data={"sub": user["username"]},
        secret_key=os.getenv('SECRET_KEY'),
        algorithm=os.getenv('ALGORITHM', 'HS256'),
        expires_delta=timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30)))
    )

# Эндпоинт для обновления токенов
@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM', 'HS256')])
        username = payload.get("sub")
        if payload.get('type') != 'refresh' or not username:
            raise HTTPException(status_code=400, detail='Неверный refresh-токен')
        return await create_tokens(
                                    db_pool, 
                                    data={'sub':username}, 
                                    secret_key=os.getenv('SECRET_KEY'), 
                                    algorithm=os.getenv('ALGORITHM','HS256')
                                   )
    except JWTError:
        raise HTTPException(status_code=400, detail='Неверный refresh токен')
    

# Защищенный эндпоинт для пользователя
@app.get('/protected')
async def protected_route(current_user: str = Depends(get_current_user_simple)):
    return {'message': f'Привет, {current_user}! Это защищенная зона'}

# Защищённый эндпоинт, который возвращает список продуктов, принадлежащих текущему пользователю.
@app.get('/products/', response_model=List[Product])
async def get_products(current_user: str = Depends(get_current_user_simple), db_pool = Depends(get_db_pool_dependency)):
    async with db_pool.acquire() as conn:
            try:
                products = await conn.fetch(
                    "SELECT id, name, price, owner_username FROM products WHERE owner_username = $1",
                    current_user
                )
                if not products:
                    return [] # Возвращаем пустой список, если продуктов нет
                return [
                    {
                        "id": p['id'], 
                        "name": p['name'], 
                        "price": float(p['price']) if p['price'] is not None else 0.0,
                        "owner_username": p['owner_username']
                    } 
                    for p in products
                ]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f'Ошибка при получении продуктов {str(e)}')
           

# Защищённый эндпоинт для создания нового продукта, доступный только авторизованным пользователям.
@app.post('/products/', response_model=Product, tags=['Products'])
async def create_product(name: str, price: float, background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user_simple), db_pool = Depends(get_db_pool_dependency)):
    async with db_pool.acquire() as conn:
            try:
                result = await conn.fetchrow(
                    # RETURNING id, name, price, owner_username возвращает только что вставленные данные.
                    "INSERT INTO products (name, price, owner_username) VALUES ($1, $2, $3) RETURNING id, name, price, owner_username",
                    name, price, current_user
                )
                # ИСПРАВЛЕНО: Возвращаем Pydantic модель и отправляем JSON в broadcast
                new_product = Product(id=result['id'], 
                                      name=result['name'], 
                                      price=result['price'], 
                                      owner_username=result['owner_username']
                                      )
                background_tasks.add_task(manager.broadcast, f"Новый продукт: {new_product.json()}")
                return new_product
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")
            

# Эндпоинт для запуска вычисления суммы
@app.post('/compute/sum')
async def start_sum_computation(start: int, end: int, current_user: str = Depends(get_current_user_simple), background_tasks: BackgroundTasks = None):
    if start > end:
        raise HTTPException(status_code=400, detail='Начало диапазона должно быть меньше или равно концу')
    # Проверка наличия объекта background_tasks
    if background_tasks:
        background_tasks.add_task(compute_sum_range, start, end, current_user, db_pool)
    return {'message': f'Асинхронное вычисление суммы от {start} до {end} начато в фоне'}


# Эндпоинт для запуска фоновых задач
# Принимает число n, запускает вычисление факториала в фоне и сразу возвращает ответ.
@app.post('/compute/async')
# current_user: str = Depends(get_current_user) — проверяет авторизацию
# background_tasks: BackgroundTasks = None — объект для фоновых задач.
# BackgroundTasks — это специальный класс из FastAPI, который позволяет запускать задачи асинхронно после отправки HTTP-ответа.
# = None означает, что этот параметр необязательный. Если клиент не передаёт его явно (что обычно происходит), он будет None по умолчанию.
async def start_async_computation(n: int, current_user: str = Depends(get_current_user_simple), background_tasks: BackgroundTasks = None):
    if n <= 0:
        raise HTTPException(status_code=400, detail='Число должно быть положительным')
    # проверяет, существует ли объект BackgroundTasks. Если он есть (например, передан в эндпоинт), задача добавляется в очередь фоновых задач. 
    # Если None (например, если ты вызовешь функцию напрямую без контекста FastAPI), задача не запустится.
    if background_tasks:
        # add_task — метод, который добавляет функцию compute_factorial в очередь фоновых задач с аргументами n (число) 
        # и current_user (имя пользователя).
        background_tasks.add_task(compute_factorial_async, n, current_user, db_pool)
    return {'message': f'Асинхронные вычисления факториала {n} начато в фоне. Результат будет сохранен (максимум 3 попытки)'}



# Устанавливает WebSocket-соединение, проверяет токен и обрабатывает сообщения.
# Зачем: Создаёт чат и уведомления в реальном времени.
# @app.websocket(WebSocket-роут) нужен для создания постоянного соединения
# Создан для уведомлений о завершении фоновых задач (например, compute_factorial_async или compute_sum_range)
@app.websocket("/ws/products")
# websocket: WebSocket — объект соединения
# token: str = Query(...) — токен авторизации, переданный как параметр запроса (обязательный, так как ... указывает на это).
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Объявляет переменную username, которая может быть None (опциональный тип), для хранения имени пользователя
    username: Optional[str] = None
    try:
        # Шаг 1: Декодируем токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Шаг 2: Проверяем тип токена (должен быть access)
        if payload.get("type") != "access":
            # Закрывает соединение с кодом ошибки 1008 (нарушение политики) и сообщением.
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type")
            # Прерывает выполнение функции при ошибке
            return

        username = payload.get("sub")
        # Шаг 3: Проверяет, что username существует и пользователь найден в базе. Если нет, закрывает соединение.
        if username is None or await get_user(db_pool, username) is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return
        
    # Ловит ошибки декодирования токена (например, истёкший или неверный токен).
    except JWTError:
        # Если токен невалидный или просрочен
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    # Если все проверки пройдены, подключаем пользователя
    # Подключает клиента через manager
    await manager.connect(websocket)
    # Уведомляет всех подключённых клиентов о новом пользователе.
    await manager.broadcast(f"Клиент '{username}' присоединился к чату.")
    # Начинает блок для обработки сообщений, где может произойти разрыв соединения.
    try:
        # Ожидаем сообщения
        while True:
            # Асинхронно получает текстовое сообщение от клиента.
            data = await websocket.receive_text()
            # Рассылает полученное сообщение всем клиентам с именем отправителя.
            await manager.broadcast(f"{username}: {data}")
    # Ловит событие разрыва соединения.
    except WebSocketDisconnect:
        # Удаляет клиента из списка активных соединений.
        manager.disconnect(websocket)
        await manager.broadcast(f"Клиент '{username}' покинул чат.")



# Добавление WebSocket-эндпоинта (/ws/chat)
# Цель: Настроить чат, где пользователи могут отправлять сообщения.
# Предназначен для интерактивного чата, где пользователи сами отправляют сообщения.
@app.websocket('/ws/chat')
async def websocket_chat(websocket: WebSocket, token: str = Query(...)):
    username: Optional[str] = None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return 
        username = payload.get('sub')
        if username is None or await get_user(db_pool, username) is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return 
    await manager.connect(websocket)
    await manager.broadcast(f"Клиент '{username}' присоединился к чату ")
    try:
        # Бесконечный цикл, слушающий входящие сообщения.
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{username}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Клиент '{username}' покинул чат ")



