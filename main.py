from datetime import datetime, timedelta, time
from time import sleep
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
from psycopg2 import pool
from dotenv import load_dotenv
import logging
from tenacity import retry, stop_after_attempt, wait_fixed
import asyncio

load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')


# Настройки логирования
# Базовая конфигурация логирования
logging.basicConfig(level=logging.INFO)
# Создание логгера, привязанного к текущему модулю
logger = logging.getLogger(__name__)

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

# Функции для работы с паролями
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Хэширует пароль с помощью bcrypt для безопасного хранения.
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
# Принимает данные пользователя, проверяет, не существует ли такой username, хэширует пароль и сохраняет в users. 
# Затем выдаёт токены.
@app.post('/register', response_model=Token)
# user: UserCreate — объект, созданный из JSON-запроса (например, {"username": "alice", "password": "password123"}).
async def register(user: UserCreate):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # Проверка сущестует ли пользователь
            cur.execute('SELECT username FROM users WHERE username = %s', (user.username,))
            # Возвращает первую строку, если пользователь существует. Если да, выбрасывается HTTPException с кодом 400.
            if cur.fetchone(): 
                raise HTTPException(status_code=400, detail='Пользователь уже сущестует')
            
            # Хэшируем пароль и сохраняем пользователя
            hashed_password = get_password_hash(user.password)
            cur.execute(
                'INSERT INTO users (username, hashed_password) VALUES (%s, %s)',
                (user.username, hashed_password)
            )
            conn.commit()

            # Генерируем токены
            return create_tokens(data={'sub': user.username})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f'Ошибка регистрации {str(e)}')
    finally:
        # Возвращает соединение в пул.
        db_pool.putconn(conn)

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
async def refresh_token(token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невалидный refresh-токен",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # Проверяем, что пользователь все еще существует в системе
        if get_user(username) is None:
            raise credentials_exception
        
        # Если все хорошо, генерируем новую пару токенов
        return create_tokens(data={"sub": username})
    except JWTError:
        # Exception — это общий класс всех исключений в Python. 
        # Указывая except Exception, ты ловишь любые ошибки, которые могут возникнуть в блоке try
        # as e присваивает пойманное исключение переменной e, 
        # чтобы ты мог использовать информацию об ошибке (например, текст ошибки).
        raise credentials_exception
    


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



# BackgroundTasks позволяет запускать тяжёлые задачи (как факториал) в фоне, не блокируя клиента.
# 1. Фоновые задачи (BackgroundTasks) — для тяжёлых вычислений
# Функция для симуляции тяжёлых вычислений. Это пример задачи, которую можно выполнить в фоне.

# Функция с повторными попытками
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2)) # 3 попытки с задержкой 2 секунды
async def compute_factorial_async(n: int, username: str):
    try:
        logger.info(f"Начало вычисление факториала {n} для {username}")
        await asyncio.sleep(5) # Асинхронная задержка
        result = 1
        for i in range(1, n + 1):
            result *= i
        conn = db_pool.getconn()
        async with await conn.cursor() as cur: # Асинхронный курсор (требуется psycopg3)
            await cur.execute(
                'INSERT INTO calculations (username, task, result) VALUES (%s, %s, %s)',
                (username, f"factorial of {n}", result)
            )
            await conn.commit()
        logger.info(f"Успешно вычислен факториал {n} = {result}")
    except Exception as e:
        logger.error(f"Ошибка при вычислении факториала {n}: {str(e)}")
        await conn.rollback()
        raise # Передаём ошибку дальше для retry
    finally:
        db_pool.putconn(conn)


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
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                # RETURNING id, name, price, owner_username возвращает только что вставленные данные.
                "INSERT INTO products (name, price, owner_username) VALUES (%s, %s, %s) RETURNING id, name, price, owner_username",
                (name, price, current_user)
            )
            product_id = cur.fetchone()[0] # Получает первую (и единственную) строку результата вставки.
            conn.commit()

            # ИСПРАВЛЕНО: Возвращаем Pydantic модель и отправляем JSON в broadcast
            new_product = Product(id=product_id, name=name, price=price, owner_username=current_user)
            background_tasks.add_task(manager.broadcast, f"Новый продукт: {new_product.json()}")

            return new_product
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания продукта: {str(e)}")
    finally:
        db_pool.putconn(conn)




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








