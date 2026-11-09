from fastapi import HTTPException
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.product_service import ProductService
import json

@pytest.mark.asyncio
async def test_get_product_by_id():
    # 1. Создаем фейковый репозиторий
    mock_repo = AsyncMock()
    
    # Фейковые данные, которые "вернет" база
    fake_product = {'id': 1, 'name': 'test_name', 'price': 100}
    mock_repo.get_by_id.return_value = fake_product
    
    # 2. Создаем сервис, передавая ему нашу подделку вместо реальной базы
    service = ProductService(repository=mock_repo)
    
    result = await service.get_product_by_id(fake_product['id'])
    
    assert result == fake_product
    
    
@pytest.mark.asyncio
async def test_get_list_of_all_products():
    mock_repo = AsyncMock()
    
    fake_products_list =  [{'id': 1, 'name': 'test_name_1', 'price': 100}, {'id': 2, 'name': 'test_name_2', 'price': 200}]
    mock_repo.get_all_products.return_value = fake_products_list
    
    service = ProductService(repository=mock_repo)
    result = await service.get_list_of_all_products(limit=10, offset=1)
    
    assert result == fake_products_list
 
    
@pytest.mark.asyncio
async def test_create_product():
    mock_repo = AsyncMock()
    mock_redis = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
    
    service = ProductService(
            repository=mock_repo,
            redis=mock_redis,
            background_tasks=mock_bg,
            manager=mock_manager
        )
    
    fake_new_product = {'id': 1, 'name': 'test_name', 'price': 200.99, 'username': 'test_username', 'creator_username': 'test_creator_username'}
    mock_repo.create.return_value = fake_new_product
    
    result = await service.create_product(username='test_username', name='test_name', price= 200.99)
    
    assert result == fake_new_product


@pytest.mark.asyncio
async def test_create_product_failed():
    mock_repo = AsyncMock()
    mock_redis = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
    
    service = ProductService(
            repository=mock_repo,
            redis=mock_redis,
            background_tasks=mock_bg,
            manager=mock_manager
        )
    
    mock_repo.create.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.create_product(username='test_username', name='test_name', price= 200.99)
    
    assert exc_info.value.status_code == 500
    
    
@pytest.mark.asyncio
async def test_delete_product_success():
    mock_repo = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
        
    service = ProductService(
        repository=mock_repo,
        background_tasks=mock_bg,
        manager=mock_manager
    )
    
    fake_product_to_delete = {'id': 1, 'name': 'test_name', 'price': 200.99, 'username': 'test_username', 'owner_username': 'test_username','role': 'admin'}
    mock_repo.get_by_id.return_value = fake_product_to_delete

    await service.delete_product(username='test_name', product_id=fake_product_to_delete['id'], role='admin')
    
    mock_repo.delete.assert_called_once_with(1)
    
    
@pytest.mark.asyncio
async def test_delete_product_not_found():
    mock_repo = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
        
    service = ProductService(
        repository=mock_repo,
        background_tasks=mock_bg,
        manager=mock_manager
    )
    
    mock_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_product(username='test_name', product_id=1, role='admin')
    
    assert exc_info.value.status_code == 404
    
    
@pytest.mark.asyncio
async def test_delete_product_unauthorized():
    mock_repo = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
        
    service = ProductService(
        repository=mock_repo,
        background_tasks=mock_bg,
        manager=mock_manager
    )
    
    fake_product_to_delete = {'id': 1, 'name': 'test_name', 'price': 200.99, 'username': 'username', 'owner_username': 'test_username','role': 'user'}
    mock_repo.get_by_id.return_value = fake_product_to_delete

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_product(username='test_name', product_id=fake_product_to_delete['id'], role='user')
    
    assert exc_info.value.status_code == 403
    
    
@pytest.mark.asyncio
async def test_get_products_cache_hit():
    mock_repo = AsyncMock()
    mock_redis = AsyncMock()
    
    service = ProductService(repository=mock_repo, redis=mock_redis)
    
    # Готовим фейковые данные в виде JSON-строки
    fake_cached_data = json.dumps([{'id': 1, 'name': 'cached_product'}])
    
    mock_redis.get.return_value = fake_cached_data
    
    result = await service.get_products(username='test_user', limit=5, offset=1)
    
    mock_repo.get_all_by_user.assert_not_called()
    
    assert result[0]['name'] == 'cached_product'
    
@pytest.mark.asyncio
async def test_get_products_cache_miss():
    mock_repo = AsyncMock()
    mock_redis = AsyncMock()
    
    service = ProductService(repository=mock_repo, redis=mock_redis)
    
    # 1. Set the fake database response
    fake_db_data = [{'id': 1, 'name': 'fresh'}]
    mock_repo.get_all_by_user.return_value = fake_db_data
    
    # 2. Make Redis return None to simulate an empty cache
    mock_redis.get.return_value = None
    
    # 3. Call the service
    result = await service.get_products(username='test_user', limit=5, offset=1)
    
    # 4. Verify the database was actually called to fetch data
    mock_repo.get_all_by_user.assert_called_once_with('test_user', 5, 1)
    
    # 5. Verify the data was saved to Redis 
    mock_redis.set.assert_called_once_with(f'products:test_user:5:1', json.dumps(fake_db_data), ex=60) 
    
    assert result == fake_db_data
  
    
@pytest.mark.asyncio
async def test_update_product_success():
    mock_repo = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
    
    service = ProductService(repository=mock_repo, background_tasks=mock_bg, manager=mock_manager)
    
    fake_product_to_update = {'owner_username': 'test_user', 'product_id': 1}
    mock_repo.get_by_id.return_value = fake_product_to_update
    mock_repo.update.return_value = fake_product_to_update

    result = await service.update_product(username='test_user', role='admin', product_id=fake_product_to_update['product_id'])
    
    assert result == fake_product_to_update
    

@pytest.mark.asyncio
async def test_update_product_error():
    mock_repo = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
    
    service = ProductService(repository=mock_repo, background_tasks=mock_bg, manager=mock_manager)
    
    fake_product_to_update = {'owner_username': 'test_user', 'product_id': 1}
    mock_repo.get_by_id.return_value = None
    mock_repo.update.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.update_product(username='test_user', role='admin', product_id=fake_product_to_update['product_id'])
    
    assert exc_info.value.status_code == 404
    

@pytest.mark.asyncio
async def test_update_product_unauthorized():
    mock_repo = AsyncMock()
    mock_bg = MagicMock()
    mock_manager = AsyncMock()
    
    service = ProductService(repository=mock_repo, background_tasks=mock_bg, manager=mock_manager)
    
    fake_product_to_update = {'owner_username': 'other_user', 'product_id': 1}
    mock_repo.get_by_id.return_value = fake_product_to_update
    mock_repo.update.return_value = fake_product_to_update

    with pytest.raises(HTTPException) as exc_info:
        await service.update_product(username='test_user', role='user', product_id=fake_product_to_update['product_id'])
    
    assert exc_info.value.status_code == 403