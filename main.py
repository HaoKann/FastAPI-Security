import asyncio
from datetime import timedelta
from typing import Optional, List
 # BackgroundTasks добавляет поддержку фоновых задач.
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging
from psycopg_pool import AsyncConnectionPool
from passlib.context import CryptContext
from starlette.status import WS_1008_POLICY_VIOLATION
from tenacity import retry, stop_after_attempt, wait_fixed
import os
import datetime

# --- 1. НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ ---

load_dotenv()

# Настройки логирования
# Базовая конфигурация логирования
# Уровень INFO означает, что будут записываться информационные сообщения и выше (например, ошибки).
logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Создаёт логгер, привязанный к текущему модулю (__name__ — имя файла, например, main). 
# Это позволяет разделять логи по модулям.
logger = logging.getLogger(__name__)


app = FastAPI()

# Настройки подключения к БД
DB_CONNINFO = (f"host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} "
               f"dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} "
               f"password={os.getenv('DB_PASSWORD')}")

# Настройки JWT
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


# Инициализация приложения и пула соединений
app = FastAPI(title='Advanced FastAPI App')
db_pool = AsyncConnectionPool(conninfo=DB_CONNINFO, min_size=1, max_size=20)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')


# --- 2. МОДЕЛИ ДАННЫХ (PYDANTIC) ---

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


# --- 3. УТИЛИТЫ И РАБОТА С БД ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли обычный пароль хешированному."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Хеширует пароль."""
    return pwd_context.hash(password)

async def get_user(username: str) -> str:
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT username, hashed_password FROM users WHERE username = %s', (username,))
            user = await cur.fetchone
            if user:
                return {'username': user[0], 'hashed_password': user[1]}
            return None

def create_tokens(data: dict) -> dict:
    """Создает новую пару access и refresh токенов."""
    # Создаем access token
    access_expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_payload = {**data, 'exp': access_expire, 'type': 'access'}
    access_token = jwt.encode(access_payload, SECRET_KEY, algorithm=ALGORITHM)

    # Создаем refresh token
    refresh_expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_payload = {**data, "exp": refresh_expire, "type": "refresh"}
    refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"} 


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    # Декодирует токен, проверяет его валидность и возвращает данные пользователя из БД.
    # Используется как зависимость в защищенных эндпоинтах.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Проверяем, что это именно access токен
        if payload.get("type") != "access":
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        user = await get_user(username)
        if user is None:
            raise credentials_exception
        return user['username']
    except JWTError:
        # Эта ошибка возникает, если токен просрочен или подпись неверна
        raise credentials_exception


# --- 4. МЕНЕДЖЕР WEBSOCKET ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()


# --- 5. ФОНОВЫЕ ЗАДАЧИ ---
async def notify_completion(username: str, result: int, task_name: str):
    await asyncio.sleep(1)
    await manager.broadcast(f"Уведомление для {username}: Задача '{task_name}' завершена! Результат: {result}")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def compute_factorial_async(n: int, username: str, background_tasks: BackgroundTasks):
    try:
        logger.info(f"Начато вычисление факториала {n} для {username}.")
        await asyncio.sleep(5)
        result = 1
        for i in range(1, n + 1):
            result *= i
        
        async with db_pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO calculations (username, task, result) VALUES (%s, %s, %s)",
                (username, f"factorial of {n}", str(result))
            )
        logger.info(f"Успешно вычислен факториал {n} = {result}")
        background_tasks.add_task(notify_completion, username, result, f"Факториал {n}")
    except Exception as e:
        logger.error(f"Ошибка при вычислении факториала {n}: {e}")
        raise



# --- 6. ЭНДПОИНТЫ API ---


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



