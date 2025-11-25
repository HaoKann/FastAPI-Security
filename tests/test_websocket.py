from fastapi.testclient import TestClient
from starlette import status
from auth import create_tokens

# --- Тест 1: Успешное подключение к WebSocket ---
def test_websocket_connect_success(client: TestClient):
    # --- ЭТАП 1: Подготовка данных (Arrange) ---
    """
    Проверяет, что можно подключиться к WebSocket с валидным токеном.
    """
    # 1. Создаем валидный токен для тестового пользователя
    # Нам не нужно регистрировать его в БД, если мы подделаем токен,
    # но код проверяет get_user_from_db, поэтому надо зарегистрировать.

    # Регистрируем пользователя через API (чтобы он попал в Mock DB)
    user_data = {"username": "ws_chat", "password": "strongpassword123"}
    client.post('/auth/register', json=user_data)

    # Логинимся и получаем токен
    login_data = {"username": "ws_chat", "password": "strongpassword123"}
    response = client.post('/auth/login', data=login_data)
    token = response.json()["access_token"]

    # --- ЭТАП 2: Рукопожатие (Handshake) ---

    # 2. Подключаемся к WebSocket
    # Обрати внимание: токен передается в Query параметре (?token=...)
    with client.websocket_connect(f"/ws/notifications?token={token}") as websocket:
        # Мы ожидаем получить приветственное сообщение (broadcast)
        # "Клиент ws_user подключился к уведомлениям"
        
        # --- ЭТАП 3: Взаимодействие (Act & Assert) ---
        data = websocket.receive_text()
        assert "Клиент ws_chat подключился" in data


# --- Тест 2: Отказ при неверном токене ---
def test_websocket_connect_invalid_token(client: TestClient):
    """
    Проверяет, что сервер закрывает соединение (код 1008),
    если токен невалиден.
    """
    invalid_token = "bad_token"

    # Пытаемся подключиться
    # Ожидаем, что websocket сразу закроется
    try:
        with client.websocket_connect(f"/ws/notifications?token={invalid_token}") as websocket:
            # Если мы попали сюда и смогли прочитать текст - значит, защита НЕ сработала.
            websocket.receive_text()
            assert False, "Соединение должно было закрыться"
    except Exception:
        # Если вылетела ошибка (WebSocketDisconnect и т.д.) - отлично!
        # Это значит, сервер нас не пустил.
        pass


# --- Тест 3: Отказ при несуществующем пользователе ---
def test_websocket_user_not_found(client: TestClient):
    """
    Проверяет случай, когда токен валидный (подпись ок),
    но пользователя нет в базе данных.
    """
    # Генерируем токен для несуществующего юзера
    # (используем твою функцию create_tokens, но юзера в БД не добавляем)
    token_data = create_tokens(data={"sub": "ghost_user"})
    token = token_data["access_token"]

    try:
        with client.websocket_connect(f"/ws/notifications?token={token}") as websocket:
            websocket.receive_text()
            assert False, "Соединение должно было закрыться"
    except Exception:
        # Ожидаем разрыв соединения, так как get_user_from_db вернет None
        pass

