from datetime import datetime, timedelta
from typing import Optional, List
# WebSocket, WebSocketDisconnect — добавляет поддержку WebSocket-протокола и обработку разрыва соединения.
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
 # BackgroundTasks добавляет поддержку фоновых задач.
from fastapi.background import BackgroundTasks 
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
# AsyncConnectionPool позволяет использовать асинхронные запросы (await), 
# что улучшает производительность и совместимость с asyncio.
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging
# tenacity для настройки повторных попыток задач при сбоях.
from tenacity import retry, stop_after_attempt, wait_fixed
# Поддержка асинхронного программирования для не блокирующих операций.
import asyncio
# starlette — это основа FastAPI, а status — набор кодов для HTTP и WebSocket.
from starlette import status

from database import get_user, get_password_hash, verify_password, db_pool
from bg_tasks import compute_factorial_async, compute_sum_range


load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Строка подключения для psycopg, объединяет все переменные окружения (DB_HOST, DB_PORT, и т.д.) в одну строку.
DB_CONNINFO = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

# Настройки логирования
# Базовая конфигурация логирования
# Уровень INFO означает, что будут записываться информационные сообщения и выше (например, ошибки).
logging.basicConfig(level=logging.INFO)
# Создаёт логгер, привязанный к текущему модулю (__name__ — имя файла, например, main). 
# Это позволяет разделять логи по модулям.
logger = logging.getLogger(__name__)


# Создаёт пул асинхронных соединений с базой. min_size=1 — минимальное число соединений, max_size=20 — максимальное.
db_pool = AsyncConnectionPool(conninfo=DB_CONNINFO, min_size=1, max_size=20)


# Настройка
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30 
REFRESH_TOKEN_EXPIRE_DAYS = 7 

app = FastAPI()




# Хэширование паролей 
# Утилиты для аутентификации 
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

# Определяет структуру данных для регистрации (имя и пароль)
class UserCreate(BaseModel):
    username: str
    password: str


# Генерация JWT токена
async def create_tokens(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        to_encode.update({'exp': datetime.utcnow() + timedelta(minutes=expires_delta)})

    # Access Token
    to_encode['type'] = 'access'
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Refresh Token
    to_encode['type'] = 'refresh'
    to_encode.pop('exp', None)
    to_encode.update({'exp': datetime.utcnow() + timedelta(days=7)})
    refresh_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {'access_token': access_token, 'refresh_token': refresh_token, 'token_type': 'bearer'}

    # Сохранение refresh-токена в базе 
    async with db_pool.connection() as conn: # Асинхронно берет соединение с базой данных из пула (db_pool), как ключ от машины, чтобы выполнить запрос.
        async with conn.cursor() as cur:
        # Создаёт курсор (cur) для выполнения SQL-запросов. 
        # Курсор — это специальный объект в библиотеке psycopg2, позволяет Python взаимодействовать с БД PostgreSQL. 
        # Он действует как "указатель" или "инструмент", с помощью которого ты отправляешь SQL-запросы (например, SELECT, INSERT) и получаешь результаты.
        # with гарантирует, что курсор закроется автоматически после завершения блока. 
            try:
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
    return await create_tokens(data={'sub': user.username})

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
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )


# Эндпоинт для обновления токенов
@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str = Depends(get_refresh_token)):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if payload.get('type') != 'refresh' or not username:
            raise HTTPException(status_code=400, detail='Неверный refresh-токен')
        return await create_tokens(data={'sub':username})
    except JWTError:
        raise HTTPException(status_code=400, detail='Неверный refresh токен')
    
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
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            raise HTTPException(status_code=401, detail='Invalid authentication credentials')
        user = await get_user(username)
        if user is None:
            raise HTTPException(status_code=401, detail='Invalid authentication credentials')
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid authentication credentials')


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



# 2. WebSocket подключения
# Зачем: Позволяет организовать чат и уведомления.
# ConnectionManager - определяет класс для управления WebSocket-подключениями (например, чат).
class ConnectionManager:  
    # Инициализирует объект класса при его создании.
    def __init__(self):
        self.active_connections: list[WebSocket] = [] # Создаёт пустой список для хранения всех активных WebSocket-соединений. 
        # Тип list[WebSocket] указывает, что список содержит объекты типа WebSocket.

    # connect: Принимает соединение, добавляет его в список
    # Асинхронный метод для подключения нового клиента
    async def connect(self, websocket: WebSocket):
        # Принимает входящее WebSocket-соединение, устанавливая "рукопожатие" между клиентом и сервером.
        await websocket.accept()
        # Добавляет новое соединение в список активных
        self.active_connections.append(websocket)

    # disconnect: Удаляет соединение при разрыве.
    def disconnect(self, websocket: WebSocket):
        # Проверяет, есть ли соединение в списке, чтобы избежать ошибки при удалении.
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    # broadcast: Асинхронный метод для отправки сообщения всем подключённым клиентам.
    async def broadcast(self, message: str):
        # Проходит по всем активным соединениям.
        for connection in self.active_connections:
            # Отправляет текстовое сообщение каждому клиенту асинхронно.
            await connection.send_text(message)

# ConnectionManager управляет подключениями и рассылает сообщения
manager = ConnectionManager()


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
        if username is None or get_user(username) is None:
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
        if username is None or await get_user(username) is None:
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






