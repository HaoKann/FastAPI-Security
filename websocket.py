# WebSocket, WebSocketDisconnect — добавляет поддержку WebSocket-протокола и обработку разрыва соединения.
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, Query, status
from typing import Optional
import asyncpg
from jose import jwt, JWTError


from auth import SECRET_KEY, ALGORITHM, get_user_from_db
from database import get_pool

# Создаем APIRouter. Все эндпоинты в этом файле будут привязаны к нему.
router = APIRouter(
    tags=['WebSockets'] # Группировка в документации
)


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


# --- Эндпоинты WebSocket ---

@router.websocket('/ws/notifications')
async def websocket_notification(
    websocket: WebSocket,
    token: str = Query(...),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """
    Эндпоинт для получения уведомлений от сервера (например, о завершении фоновых задач).
    Клиент подключается и слушает.
    """
    username: Optional[str] = None
    try:
        # Шаг 1: Проверяем токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) 
        if payload.get('type') != 'access':
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason='Invalid token type')
            return
        
        # Шаг 2: Проверяем пользователя
        username = payload.get('sub')
        # Мы закрываем соединение, если имя пользователя не найдено ИЛИ
        # если функция get_user_from_db вернула None (т.е. not await...).
        if not username or not await get_user_from_db(pool, username):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason='User not found')
            return
        
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason='Invalid or expired token')
        return
    
    # Шаг 3: Если все проверки пройдены, подключаем клиента
    await manager.connect(websocket)
    await manager.broadcast(f'Клиент {username} подключился к уведомлениям')
    try:
        # Бесконечный цикл для поддержания соединения
        while True:
            # Просто ждем, пока соединение не будет разорвано.
            # Мы не ожидаем сообщений от клиента на этом эндпоинте.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f'Клиент {username} отключился')


@router.websocket('/ws/chat')
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """
    Эндпоинт для интерактивного чата.
    Клиент подключается, может отправлять и получать сообщения.
    """
    username: Optional[str] = None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('type') != 'access':
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        username = payload.get('sub')
        if not username or not await get_user_from_db(pool, username):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await manager.connect(websocket)
    await manager.broadcast(f'Клиент {username} подключился к чату')
    try:
        # Бесконечный цикл для обмена сообщениями
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f'{username}: {data}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        await manager.broadcast(f'Клиент {username} покинул чат') 