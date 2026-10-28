import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from s3_service import S3Service
from fastapi import HTTPException

# 1. Простой тест: проверка работы без обращения к S3 при пустом имени
@pytest.mark.asyncio
async def test_get_presigned_url_empty_name():
    service = S3Service()
    
    # Передаем пустое имя файла
    result = await service.get_presigned_url("")
    
    # Ожидаем, что функция сразу вернет None
    assert result is None
    
    
# 2. Сложный тест: мокаем асинхронный клиент S3 для успешной генерации ссылки
@pytest.mark.asyncio
async def test_get_presigned_url_success():
    serivce = S3Service()
    expected_url = "https://s3.fake.com/my-bucket/avatar.png?token=123"
    
    # Шаг A: Создаем мок самого S3-клиента и задаем ответ для генерации ссылки
    mock_s3_client = AsyncMock()
    mock_s3_client.generate_presigned_url.return_value = expected_url
    
    # Шаг B: Настраиваем поддержку контекстного менеджера (async with)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    # Шаг C: Подменяем вызов service.session.client(...) нашим моком
    with patch.object(serivce.session, 'client', return_value=mock_ctx):
        # Если передали полный URL, функция должна отрезать до "avatar.png"
        result = await serivce.get_presigned_url("http://s3.com/bucket/avatar.png")
        
        # Проверки (Assertions)
        assert result == expected_url
        
        # Проверяем, что метод S3 был вызван ровно 1 раз и с правильным очищенным именем 'avatar.png'
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            ClientMethod='get_object',
            Params={'Bucket': serivce.bucket, 'Key': 'avatar.png'},
            ExpiresIn=3600
        )
        
# 3. Тест обработки ошибок: если S3 выбросил исключение
@pytest.mark.asyncio
async def test_get_presigned_url_exception():
    service = S3Service()
    
    # Настраиваем мок так, чтобы генерация ссылки вызывала ошибку
    mock_s3_client = AsyncMock()
    mock_s3_client.generate_presigned_url.side_effect = Exception("S3 Connection Error")
    
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    with patch.object(service.session, 'client', return_value=mock_ctx):
        result = await service.get_presigned_url('avatar.png')
        
    # В блоке except функция перехватывает ошибку и возвращает None
    assert result is None
    
@pytest.mark.asyncio
async def test_upload_file_empty_filename():
    service = S3Service()
    # Создаем фейковый файл 
    fake_file = MagicMock()
    fake_file.filename = ''
    
    file = await service.upload_file(fake_file)

    assert file is None
    
    
@pytest.mark.asyncio
async def test_upload_file_success():
    service = S3Service()
    
    # 1. Создаем фейковый файл с нужными атрибутами
    fake_file = MagicMock()
    fake_file.filename = 'test.jpg'
    fake_file.content_type = 'image/jpeg'
    fake_file.file = MagicMock() # Имитируем байтовый поток файла для s3.upload_fileobj
    
    # 2. Создаем нашего "каскадера" (s3-клиент)
    mock_s3_client = AsyncMock()
    # Бакет существует, поэтому head_bucket просто отрабатывает без ошибок
    mock_s3_client.head_bucket.return_value = {}
    
    # 3. Создаем "дверь" (контекстный менеджер)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    # 4. Подменяем реальный клиент и запускаем функцию
    with patch.object(service.session, 'client', return_value=mock_ctx):
        result = await service.upload_file(fake_file)
        
    # 5. Проверяем результаты
    assert result is not None
    assert result.endswith('.jpg')
    
    # Проверяем, что нужные методы каскадера действительно вызывались
    mock_s3_client.head_bucket.assert_called_once_with(Bucket=service.bucket)
    mock_s3_client.upload_fileobj.assert_called_once()
 
    
@pytest.mark.asyncio
async def test_upload_file_exception():
    service = S3Service()
    fake_file = MagicMock()
    fake_file.filename='test.txt'
    fake_file.content_type = 'image/jpg'
    fake_file.file = MagicMock()
    
    mock_s3_client = AsyncMock()
    mock_s3_client.upload_fileobj.side_effect = Exception('Boom!')
    
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    with patch.object(service.session, 'client', return_value=mock_ctx):
        with pytest.raises(HTTPException) as exc_info:
            await service.upload_file(fake_file)
            
    assert exc_info.value.status_code == 500
    
    
    
@pytest.mark.asyncio
async def test_upload_file_bucket_not_found_creates_new():
    service = S3Service()
        
    fake_file = MagicMock()
    fake_file.filename = 'test.jpg'
    fake_file.content_type = 'image/jpeg'
    fake_file.file = MagicMock() 
        
    mock_s3_client = AsyncMock()
    
    # Имитируем, что бакета нет
    mock_s3_client.head_bucket.side_effect = Exception('Not Found')
    
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    with patch.object(service.session, 'client', return_value=mock_ctx):
        result = await service.upload_file(fake_file)
    
    # Проверяем, что файл всё равно загрузился 
    assert result is not None
    
    # И самое главное: проверяем, что наш код действительно создал бакет и раздал права
    mock_s3_client.create_bucket.assert_called_once_with(Bucket=service.bucket)
    mock_s3_client.put_bucket_policy.assert_called_once()
    
    

