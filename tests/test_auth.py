from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import AsyncMock
from models import User
import auth
import pytest
from fastapi import HTTPException

# --- Тесты для эндпоинта /auth/register ---
def test_register_user_success(client: TestClient):
    # Шаг 1: Готовим данные нового пользователя
    user_data = {
        "username": "new_test_user",
        "password": "strongpassword123"
    }

    # Шаг 2: Отправляем POST-запрос на /auth/register
    response = client.post('/auth/register', json=user_data)

    # Шаг 3: Проверяем результат
    assert response.status_code == status.HTTP_200_OK # Ожидаем успешный ответ
    response_data = response.json()
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert response_data['token_type'] == 'bearer'

def test_register_user_already_exists(client: TestClient):
    # Шаг 1: Готовим данные пользователя, которого мы сейчас создадим
    user_data = {
        "username": "existing_user",
        "password": "password123"
    }

    # Шаг 2: Регистрируем его в первый раз (ожидаем успеха)
    response1 = client.post('/auth/register', json=user_data)
    assert response1.status_code == status.HTTP_200_OK

    # Шаг 3: Пытаемся зарегистрировать его еще раз с теми же данными
    response2 = client.post('/auth/register', json=user_data)

    # Шаг 4: Проверяем, что сервер вернул ошибку
    assert response2.status_code == status.HTTP_400_BAD_REQUEST # Ожидаем ошибку "Bad Request"
    assert response2.json() == {'detail': 'Пользователь с таким именем уже существует'}


def test_login_success(client: TestClient):
    """
    Тест успешного входа в систему.
    1. Сначала регистрируем пользователя.
    2. Потом логинимся с теми же данными.
    """

    # Шаг 1: Регистрируем пользователя
    # "Правильный" пароль должен совпадать с тем, что зашит в mock_verify_password
    user_data = {
        "username": "login_user",
        "password": "strongpassword123"
    }
    response_register = client.post('/auth/register', json=user_data)
    assert response_register.status_code == status.HTTP_200_OK

    # Шаг 2: Пытаемся залогиниться
    # ВАЖНО: FastAPI для /token ожидает данные в виде form data, а не JSON!
    # Поэтому мы используем 'data=', а не 'json='
    login_data = {
        "username": "login_user",
        "password": "strongpassword123"
    }
    response_login = client.post('/auth/login', data=login_data)

    # Шаг 3: Проверяем результат
    assert response_login.status_code == status.HTTP_200_OK
    data = response_login.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_user_not_found(client: TestClient):
    """
    Тест входа с несуществующим пользователем.
    """
    login_data = {
        "username": "ghost_user", # Этот пользователь НЕ был зарегистрирован
        "password": "any_password"
    }
    response_login = client.post('/auth/login', data=login_data)

    # Ожидаем ошибку 401 Unauthorized (или 404, в зависимости от логики)
    # 401 более безопасен, т.к. не говорит, что именно неверно (логин или пароль)
    assert response_login.status_code == status.HTTP_401_UNAUTHORIZED
    data = response_login.json()
    assert "access_token" not in data
    assert "detail" in data


def test_login_wrong_password(client: TestClient):
    """
    Тест входа с неправильным паролем.
    """
    # Шаг 1: Регистрируем пользователя
    user_data = {
        "username": "wrong_pass_user",
        "password": "strongpassword123" # "Правильный" пароль
    }
    response_register = client.post('/auth/register', json=user_data)
    assert response_register.status_code == status.HTTP_200_OK

    # Шаг 2: Пытаемся залогиниться с неверным паролем
    login_data = {
        "username": "wrong_pass_user",
        "password": "this_is_wrong_password" # "Неправильный" пароль
    }
    response_login = client.post('/auth/login', data=login_data)

    # Шаг 3: Проверяем результат
    assert response_login.status_code == status.HTTP_401_UNAUTHORIZED
    data = response_login.json()
    assert "access_token" not in data
    assert "detail" in data


def test_protected_route_success(client: TestClient):
    # 1. Register a new user
    user_data = {'username':'protected_user', 'password':'protected_password'}
    client.post('/auth/register', json=user_data)
    
    # 2. Login to get the token
    login_response = client.post('/auth/login', data=user_data)
    access_token = login_response.json()['access_token']
    
    
    # 3. Call the protected route USING the token
    # 🎯 YOUR TURN: How do you format the headers dictionary?
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response =  client.get('/auth/protected', headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'message': 'Привет, protected_user! Это защищенная зона'}
    
    
def test_read_users_me_no_avatar(client: TestClient):
    user_data = {'username':'user_without_avatar', 'password': 'good_password'}
    client.post('/auth/register', json=user_data)
    
    login_response = client.post('/auth/login', data=user_data)
    access_token = login_response.json()['access_token']
    
    headers = {'Authorization': f'Bearer {access_token}'}
    response = client.get('/auth/me', headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['avatar_url'] is None
    
    
def test_read_users_me_with_avatar(client: TestClient):
    # 1. Mock the S3 client so it returns a fake presigned URL
    auth.s3_client.get_presigned_url = AsyncMock(return_value='https://fake-s3-link.com/temp-avatar')
    
    # 2. Create a fake user that already has a base avatar filename
    fake_user = User(username='avatar_user', avatar_url='avatar.png')
    
    # 3. Use the VIP Pass! Override the dependency to return our fake user
    client.app.dependency_overrides[auth.get_current_user] = lambda: fake_user
    
    # 4. Call the route (No headers needed, the VIP pass skips the token check)
    response = client.get('/auth/me')
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['avatar_url'] == 'https://fake-s3-link.com/temp-avatar'
    
    # 5. Clean up the VIP pass so it doesn't affect other tests
    client.app.dependency_overrides.clear()
    
    
def test_role_checker_forbidden():
    # 1. Create the guard (only allows admins)
    guard = auth.RoleChecker(['admin'])
    
    # 2. Create a fake user who is just a regular 'user'
    hacker_user = User(username='hacker', role='user')
    
    # 3. Use pytest.raises to check that the guard blocks them
    with pytest.raises(HTTPException) as exc_info:
        guard(hacker_user)
        
    
    # 4. Verify the correct error was thrown
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == 'У вас нет прав для выполнения этого действия'
    
    
def test_role_checker_admin():
    guard = auth.RoleChecker(['admin'])
    admin = User(username='admin', role='admin')
    
    result = guard(admin)
        
    assert result == admin
    
    
def test_protected_route_with_refresh_token_fails(client: TestClient):
    user_data = {'username':'protected_user', 'password':'protected_password'}
    client.post('/auth/register', json=user_data)
    
    login_response = client.post('/auth/login', data=user_data)
    refresh_token = login_response.json()['refresh_token']
    
    headers = {'Authorization': f'Bearer {refresh_token}'}
    response = client.get('/auth/protected', headers=headers)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_route_with_fake_token(client: TestClient):
    user_data = {'username':'protected_user', 'password':'protected_password'}
    client.post('/auth/register', json=user_data)
    
    client.post('/auth/login', data=user_data)
    
    
    headers = {'Authorization': f'Bearer {'fake_token'}'}
    response = client.get('/auth/protected', headers=headers)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    
@pytest.mark.asyncio
async def test_get_user_from_db_none():
    user = 'fake_user'
    result = await auth.get_user_from_db(db=None, username=user)
    
    assert result is None
