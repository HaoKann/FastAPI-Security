import pytest
from fastapi import HTTPException
from models import Cart, Product, User, CartItem
from repositories import cart


@pytest.fixture
async def sample_user(db_session):
    """Фикстура для создания тестового пользователя."""
    user = User(
        username='test_user',
        hashed_password='hashed_password',
        avatar_url='http://avatar.png',
        role='user'
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

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

# 1. ТЕСТЫ ДОБАВЛЕНИЯ В КОРЗИНУ (add_item_to_cart)

@pytest.mark.asyncio
async def test_add_item_to_cart_product_not_found(db_session, sample_user):
    """Тест ошибки 404 при добавлении несуществующего товара."""
    with pytest.raises(HTTPException) as exc_info:
        await cart.add_item_to_cart(db=db_session, user_id=sample_user.id, product_id=99999, amount=1)
        
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == 'Товар не найден'
    
@pytest.mark.asyncio
async def test_add_item_to_cart_creates_new_cart(db_session, sample_user, sample_product):
    """Тест создания новой корзины и добавления первого товара."""
    result = await cart.add_item_to_cart(
        db=db_session,
        user_id=sample_user.id,
        product_id=sample_product.id,
        amount=2
    )
    
    assert result == {'message': 'Товар успешно добавлен в корзину!'}
    
    # Проверяем, что корзина и позиция действительно создались в БД
    user_cart = await cart.find_cart(db=db_session, user_id=sample_user.id)
    assert user_cart is not None
    
    item = await cart.find_existing_cart_item(db_session, cart_id=user_cart.id, product_id=sample_product.id)
    assert item is not None
    assert item.amount == 2
    
    
@pytest.mark.asyncio
async def test_add_item_to_cart_increment_existing_item(db_session, sample_user, sample_product):
    """Тест увеличения количества уже добавленного товара."""
    # Добавляем сначала 1 штуку
    await cart.add_item_to_cart(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=1)
    # Добавляем ещё 3 штуки
    await cart.add_item_to_cart(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=3)
    
    user_cart = await cart.find_cart(db=db_session, user_id=sample_user.id)
    item = await cart.find_existing_cart_item(db=db_session, cart_id=user_cart.id, product_id=sample_product.id)
    
    assert item.amount == 4
    
# 2. ТЕСТЫ ПОЛУЧЕНИЯ КОРЗИНЫ (get_cart_items)

@pytest.mark.asyncio
async def test_get_cart_items_no_cart(db_session, sample_user):
    """Тест получения корзины, если у пользователя ее еще нет."""
    response = await cart.get_cart_items(db=db_session, user_id=sample_user.id)
    assert response == {'items': [], 'total_price': 0}
    
    
@pytest.mark.asyncio
async def test_get_cart_items_success(db_session, sample_user, sample_product):
    """Тест успешного получения содержимого корзины с подсчетом суммы."""
    await cart.add_item_to_cart(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=2)
    
    response = await cart.get_cart_items(db=db_session, user_id=sample_user.id)
    
    assert response['total_price'] == 2000 # 1000.0 * 2
    assert len(response['items']) == 1
    assert response['items'][0]['product_id'] == sample_product.id
    assert response['items'][0]['name'] == 'test_product'
    assert response['items'][0]['amount'] == 2
    
    
# 3. ТЕСТЫ УДАЛЕНИЯ ИЗ КОРЗИНЫ (delete_items_from_cart)

@pytest.mark.asyncio
async def test_delete_items_from_cart_no_cart(db_session, sample_user):
    """Тест удаления из корзины, когда самой корзины нет."""
    response = await cart.delete_items_from_cart(db=db_session, user_id=sample_user.id, product_id=1)
    assert response == {'message': 'Корзина не найдена'}
    
@pytest.mark.asyncio
async def test_delete_items_from_cart_success(db_session, sample_user, sample_product):
    """Тест успешного удаления товара из корзины."""
    await cart.add_item_to_cart(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=1)
    
    response = await cart.delete_items_from_cart(db=db_session, user_id=sample_user.id, product_id=sample_product.id)
    assert response == {'message': 'Товар успешно удален из корзины'}
    
    # Проверяем, что корзина пуста
    cart_data = await cart.get_cart_items(db=db_session, user_id=sample_user.id)
    assert len(cart_data['items']) == 0
    
# 4. ТЕСТЫ ОБНОВЛЕНИЯ КОЛИЧЕСТВА (update_cart_item_amount)

@pytest.mark.asyncio
async def test_update_cart_item_amount_no_cart(db_session, sample_user):
    """Тест обновления количества, если у пользователя нет корзины."""
    response = await cart.update_cart_item_amount(db=db_session, user_id=sample_user.id, product_id=1, amount=5)
    assert response is None

    
@pytest.mark.asyncio
async def test_update_cart_item_amount_item_not_in_cart(db_session, sample_user, sample_product):
    """Тест обновления количества товара, которого нет в корзине."""
    # Создаем корзину пользователю, добавляя товар
    await cart.add_item_to_cart(db_session, user_id=sample_user.id, product_id=sample_product.id, amount=1)
    
    # Пытаемся обновить несуществующий product_id=999
    response = await cart.update_cart_item_amount(db=db_session, user_id=sample_user.id, product_id=999, amount=5)
    assert response == {'message': 'Товара в корзине нет'}
    
@pytest.mark.asyncio
async def test_update_cart_item_amount_positive(db_session, sample_user, sample_product):
    """Тест успешного изменения количества на новое положительное значение."""
    await cart.add_item_to_cart(db_session, user_id=sample_user.id, product_id=sample_product.id, amount=1)
    
    response = await cart.update_cart_item_amount(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=5)
    assert response == {'message': 'Количество успешно изменено'}
    
    user_cart = await cart.find_cart(db_session, user_id=sample_user.id)
    item = await cart.find_existing_cart_item(db_session, cart_id=user_cart.id, product_id=sample_product.id)
    assert item.amount == 5
    
@pytest.mark.asyncio
async def test_update_cart_item_amount_zero_or_less(db_session, sample_product, sample_user):
    """Тест удаления товара при передаче количества <= 0."""
    await cart.add_item_to_cart(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=2)
    
    # Передаем amount=0
    response = await cart.update_cart_item_amount(db=db_session, user_id=sample_user.id, product_id=sample_product.id, amount=0)
    assert response == {'message': 'Количество успешно изменено'}
    
    # Проверяем, что товар действительно удален из БД
    user_cart = await cart.find_cart(db_session, user_id=sample_user.id)
    item = await cart.find_existing_cart_item(db_session, cart_id=user_cart.id, product_id=sample_product.id)
    assert item is None