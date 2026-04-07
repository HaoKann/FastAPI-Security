from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from uuid import UUID
import json

# Импортируем наш репозиторий
from repositories.product_repository import ProductRepository

class ProductService:
    def __init__(self, repository: ProductRepository, redis=None, background_tasks=None, manager=None):
        self.repo = repository
        self.redis = redis
        self.background_tasks = background_tasks
        self.manager = manager

    async def _clear_cache(self, username: str):
        """Вспомогательный метод для очистки кэша юзера"""
        if self.redis:
            try:
                cached_keys = await self.redis.keys(f"products:{username}:*")
                if cached_keys:
                    await self.redis.delete(*cached_keys)
                    print(f"🧹 Кэш сброшен для пользователя {username}")
            except Exception as e:
                print(f"⚠️ Ошибка сброса кэша: {e}")

    async def get_products(self, username: str, limit: int, offset: int):
        CACHE_KEY = f"products:{username}:{limit}:{offset}"

        # 1. Проверяем кэш
        if self.redis:
            try:
                cached_data = await self.redis.get(CACHE_KEY)
                if cached_data:
                    print(f"✅ CACHE HIT: Товары для пользователя {username} из Redis")
                    return json.loads(cached_data)
            except Exception:
                pass # Игнорируем ошибку чтения и идем в БД


        # 2. Идем в базу через Репозиторий!
        print(f"❌ CACHE MISS: Идем в базу за товарами для {username}")
        records = await self.repo.get_all_by_user(username, limit, offset)
        products_data = jsonable_encoder(records)
        
        # 3. Сохраняем в кэш
        if self.redis:
            try:
                await self.redis.set(CACHE_KEY, json.dumps(products_data), ex=60)
            except Exception:
                pass

        return products_data

    async def create_product(self, username: str, name: str, price: float):
        # 1 Создаем товар в БД через репозиторий
        new_product = await self.repo.create(name, price, username)
        if not new_product:
            raise HTTPException(status_code=500, detail="Не удалось создать продукт")
        
        # 2 Отправляем уведомления через WebSocket(если есть подключение)
        if self.background_tasks and self.manager:
            self.background_tasks.add_task(
                self.manager.broadcast,
                f"Новый продукт {json.dumps(jsonable_encoder(new_product))}"
            )

        # 3 Сбрасываем кеш
        await self._clear_cache(username)
        return new_product
    

    async def delete_product(self, username: str, product_id: UUID):
        # 1 Сначала достаем товар для проверки права
        product = await self.repo.get_by_id(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail='Товарт не найден')
        
        # Проверка что только владелец может удалить свой товар
        if product['owner_username'] != username:
            raise HTTPException(status_code=403, detail='Вы не можете удалить чужой товар')
        
        # 2 Удаляем через репозиторий
        await self.repo.delete(product_id)

        # 3 Уведомление и очистка кеша
        if self.background_tasks and self.manager:
            self.background_tasks.add_task(self.manager.broadcast, f"Продукт ID {product_id} удален")
        await self._clear_cache(username)


    async def update_product(self, username: str, product_id: UUID, name: str | None, price: float | None):
        # 1 Проверка прав 
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail='Продукт не найден')
        
        if product['owner_username'] != username:
            raise HTTPException(status_code=403, detail='Нельзя редактировать чужой продукт')
        
        # 2 Обновляю в БД через репозиторий
        updated_product = await self.repo.update(product_id, name, price)

        # 3 Уведомление и очистка кеша
        if self.background_tasks and self.manager:
            self.background_tasks.add_task(
                self.manager.broadcast,
                    f"Продукт {json.dumps(jsonable_encoder(updated_product))} был обновлен"
            )
        await self._clear_cache(username)

        return updated_product 