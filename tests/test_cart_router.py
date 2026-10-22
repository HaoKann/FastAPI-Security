import pytest
from models import Product

@pytest.fixture
async def sample_product(db_session, sample_user):
    """Фикстура для создания тестового товара."""
    product = Product(
        name='test_product',
        price=1000.0,
        description = 'test_product',
        image_url = 'http://example.com/test_product.jpg',
        owner_username = sample_user.username
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product

# 1. ТЕСТЫ POST /cart/add
@pytest.mark.asyncio
async def test_router_add_product_to_cart_success(ac, auth_headers, sample_product):
    """Успешное добавление товара с авторизацией."""
    payload = {
        'product_id': sample_product.id,
        'amount': 2
    }
    response = await ac.post('/cart/add', json=payload, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json() == {'message': 'Товар успешно добавлен в корзину!'}
    
    
@pytest.mark.asyncio
async def test_router_add_product_validation_error(ac, auth_headers, sample_product):
    """Проверка валидации Pydantic: amount <= 0 должен возвращать 422 Unprocessable Entity."""
    payload = {
        'product_id': sample_product.id,
        'amount': 0
    }
    
    response = await ac.post('/cart/add', json=payload, headers=auth_headers)
    
    assert response.status_code == 422

    
# 2. ТЕСТЫ GET /cart/view

@pytest.mark.asyncio
async def test_get_cart_items_empty(ac, auth_headers):
    """Получение пустой корзины авторизованным пользователем."""
    response = await ac.get('/cart/view', headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json == {'items': [], 'total_price': 0}
    

@pytest.mark.asyncio
async def test_get_cart_items_with_products(ac, auth_headers, sample_product):
    """Получение корзины с товарами и проверка ответа CartResponse."""
    await ac.post('/cart/add', json={'product_id': sample_product.id, 'amount': 2}, headers=auth_headers)
    
    response = await ac.get('/cart/view', headers=auth_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data['total_price'] == 2000
    assert len(data['items']) == 1
    assert data['items'][0]['product_id'] == sample_product.id
    assert data['items'][0]['name'] == 'test_product'
    assert data['items'][0]['amount'] == 2 
    
    
# 3. ТЕСТЫ DELETE /cart/delete/{product_id}

@pytest.mark.asyncio
async def test_router_delete_item_from_cart(ac, auth_headers, sample_product):
    """Успешное изменение количества товара."""
    await ac.post('/cart/add', json={'product_id': sample_product.id, 'amount': 1}, headers=auth_headers)
        
    response = await ac.delete(f'/cart/delete/{sample_product.id}', headers=auth_headers)     
    assert response.status_code == 200
    assert response.json() == {'message': 'Товар успешно удален из корзины'}


# 4. ТЕСТЫ PUT /cart/update

@pytest.mark.asyncio
async def test_router_update_cart_item_amount_success(ac, auth_headers, sample_product):
    await ac.post('/cart/add', json={'product_id': sample_product.id, 'amount': 1}, headers=auth_headers)
    
    payload = {
        'product_id': sample_product.id,
        'amount': 5
    }    
    
    response = await ac.put('/cart/update', headers=auth_headers, json=payload)
    
    assert response.status_code == 200
    assert response.json() == {'message': 'Количество успешно изменено'}
    
    
@pytest.mark.asyncio
async def test_router_update_cart_item_amount_not_found(ac, auth_headers):
    """Проверка ветки 'result is None' -> 404 при отсутствии корзины."""
    payload = {
        'product_id': 9999,
        "amount": 5
    }
    response = await ac.put('/cart/update', headers=auth_headers, json=payload)
    
    assert response.status_code == 404
    assert response.json() == {'detail': 'Корзина не найдена'}
    
    
# 5. ТЕСТ ДОСТУПА БЕЗ АВТОРИЗАЦИИ (401)

@pytest.mark.asyncio
async def test_router_unauthorized_access(ac):
    """Запрос без auth_headers должен возвращать 401 Unauthorized."""
    response = await ac.get('/cart/view')
    assert response.status_code == 401
