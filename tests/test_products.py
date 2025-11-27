from fastapi.testclient import TestClient
from fastapi import status

# --- Тест 1: Проверка получения пустого списка ---
def test_get_products_empty(client: TestClient, auth_headers: dict):
    """
    Тест: GET /products (когда продуктов еще нет)
    Проверяем, что аутентифицированный пользователь 
    получает пустой список, а не ошибку.
    
    Фикстуры:
    - client: Наш "Postman"
    - auth_headers: Наш "помощник", который уже залогинился
    """
    # Вызываем эндпоинт, используя "волшебный" заголовок
    response = client.get('/products', headers=auth_headers)

    # Проверяем, что все прошло успешно (код 200)
    assert response.status_code == status.HTTP_200_OK

    # Проверяем, что тело ответа - это пустой список
    assert response.json() == []


# --- Тест 2: Успешное создание продукта ---
def test_create_product(client: TestClient, auth_headers: dict):
    """
    Тест: POST /products (успешное создание продукта)
    Проверяем, что пользователь может создать продукт.
    """
    # 1. Готовим данные для нового продукта
    product_data = {
        "name": "Игровой ПК 'Vortex'",
        "price": 1999.99
    }

    # 2. Отправляем POST-запрос с данными (json=) и заголовком (headers=)
    response = client.post("/products", json=product_data, headers=auth_headers)

    # 3. Проверяем, что сервер ответил "200 OK"
    assert response.status_code == status.HTTP_200_OK

    # 4. Проверяем, что сервер вернул нам созданный продукт
    data = response.json()
    assert data["name"] == "Игровой ПК 'Vortex'"
    assert data["price"] == 1999.99
    assert data["id"] is not None # Убеждаемся, что ID был присвоен

    # 5. Проверяем, что "владелец" - это наш 'test_user' из фикстуры
    assert data["owner_username"] == "test_user"


# --- Тест 3: Проверка получения списка после создания ---
def test_get_products_after_creation(client: TestClient, auth_headers: dict):
    """
    Тест: GET /products (после создания)
    Проверяем, что эндпоинт GET теперь возвращает продукт,
    который мы только что создали.
    """
    # --- Шаг 1: Сначала создаем продукт ---
    product_data = {
        "name": "Ноутбук 'Shadow'",
        "price": 1200.00
    }
    create_response = client.post("/products", json=product_data, headers=auth_headers)
    assert create_response.status_code == status.HTTP_200_OK

    # --- Шаг 2: Теперь запрашиваем список продуктов ---
    get_response = client.get("/products", headers=auth_headers)

    # Проверяем, что все Ок
    assert get_response.status_code == status.HTTP_200_OK

    # Проверяем, что в списке есть ровно 1 элемент
    data = get_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Ноутбук 'Shadow'"
    assert data[0]["owner_username"] == "test_user"



# --- Тест 4: Проверка защиты роутера (без токена) ---
def test_create_product_unauthenticated(client: TestClient):
    """
    Тест: POST /products (без токена)
    Проверяем, что зависимость `Depends(get_current_user)`
    на уровне роутера работает и "выкидывает" неавторизованных.
    """
    product_data = {
        "name": "Украденный ПК",
        "price": 10.00
    }

    # Отправляем запрос БЕЗ auth_headers
    response = client.post("/products", json=product_data)

    # Ожидаем 401 Unauthorized (Нет доступа)
    assert response.status_code == status.HTTP_403_FORBIDDEN
 

# --- Тест 5: Успешное удаление продукта ---
def test_delete_product_success(client: TestClient, auth_headers: dict):
    """Тест: Создаем продукт, удаляем его, проверяем что его нет."""

    # 1. Создаем продукт (чтобы было что удалять)
    create_resp = client.post("/products", json={"name": "Temp", "price": 10}, headers=auth_headers)
    product_id = create_resp.json()["id"]

    # 2. Удаляем его
    delete_resp = client.delete(f"/products/{product_id}", headers=auth_headers)

    # 3. Ожидаем 204 No Content (успешное удаление)
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

    # 4. Проверяем, что список продуктов теперь пуст (или этого продукта там нет)
    get_resp = client.get("/products", headers=auth_headers)
    products = get_resp.json()
    # Проверяем, что продукта с таким ID нет в списке
    assert not any(p['id'] == product_id for p in products)


# --- Тест 6: Удаление несуществующего продукта ---
def test_delete_product_not_found(client: TestClient, auth_headers: dict):
    """Тест: Попытка удалить продукт с ID 99999."""
    delete_resp = client.delete("/products/99999", headers=auth_headers)
    assert delete_resp.status_code == status.HTTP_404_NOT_FOUND


# --- Тест 7: Попытка удалить чужой продукт ---
def test_delete_others_product_forbidden(client: TestClient, auth_headers: dict):
    """
    Тест безопасности:
    1. User1 создает продукт.
    2. User2 (Вор) пытается его удалить.
    3. Сервер должен запретить (403).
    """

    # 1. User1 (auth_headers) создает продукт
    create_resp = client.post('/products', json={"name": "My precious", "price": 100}, headers=auth_headers)
    product_id = create_resp.json()["id"]

    # 2. Регистрируем ВТОРОГО пользователя ('thief')
    thief_data = {"username": "thief", "password": "strongpassword123"}
    client.post('/auth/register', json=thief_data)

    # 3. Логинимся за вора
    login_resp = client.post('/auth/login', data=thief_data)
    thief_token = login_resp.json()['access_token']
    thief_headers = {"Authorization": f"Bearer {thief_token}"}

    # 4. Вор пытается удалить продукт первого пользователя
    delete_resp = client.delete(f"/products/{product_id}", headers=thief_headers)

    # 5. Ожидаем отказ (403 Forbidden)
    assert delete_resp.status_code == status.HTTP_403_FORBIDDEN

