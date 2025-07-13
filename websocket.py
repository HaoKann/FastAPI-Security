# WebSocket, WebSocketDisconnect — добавляет поддержку WebSocket-протокола и обработку разрыва соединения.
from fastapi import WebSocket, WebSocketDisconnect, Query
# starlette — это основа FastAPI, а status — набор кодов для HTTP и WebSocket.
from starlette import status
from typing import Optional, List
from jose import JWTError, jwt
from database import get_user
import os

# Настройка
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'

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
