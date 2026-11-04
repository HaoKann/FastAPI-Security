from fastapi import HTTPException
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.product_service import ProductService

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