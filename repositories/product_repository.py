from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete
from sqlalchemy.orm import joinedload
from models import Product

class ProductRepository:
    """
    Класс, который отвечает ТОЛЬКО за работу с базой данных через SQLAlchemy
    """
    def __init__(self, db: AsyncSession):
        # Теперь принимаем сессию SQLAlchemy, а не пул asyncpg
        self.db = db

    # Вспомогательный метод, чтобы не ломать старый код, ожидающий словари
    def _to_dict_(self, product: Product) -> dict:
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "owner_username": product.owner.username if product.owner else product.owner_username,
            "avatar_url": product.owner.avatar_url if product.owner else None
        }

    async def get_all_products(self, limit: int, offset: int):
        stmt = (
            # Выбераем все из таблицы products
            select(Product)
            .options(joinedload(Product.owner))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        # Получаем список объектов
        products = result.scalars().all()
        
        return [self._to_dict_(p) for p in products]
        
        
    async def get_all_by_user(self, username: str, limit: int, offset: int):
        stmt = (
            select(Product)
            .options(joinedload(Product.owner))
            .where(Product.owner_username == username)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        products = result.scalars().all()
        
        return [self._to_dict_(p) for p in products]
        
        
    async def create(self, name: str, price: float, username: str, creator_username: str):
        stmt = (
            insert(Product)
            .values(name=name, price=price, owner_username=username, creator_username=creator_username)
            .returning(Product)
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        
        # Для сохранения нужно сделать commit
        await self.db.commit()
        
        return self._to_dict_(product) if product else None
        
    
    async def get_by_id(self, product_id: int):
        stmt = (
            select(Product)
            .options(joinedload(Product.owner))
            .where(Product.id == product_id)
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        
        return self._to_dict_(product) if product else None
    
        
    async def delete(self, product_id: int):
        stmt = (delete(Product).where(Product.id == product_id))
        await self.db.execute(stmt)
        await self.db.commit()
        

    async def update(self, product_id: int, name: str | None, price: float | None):
        # Подготавливаем словарь только с теми значениями, которые не None
        update_data = {}
        if name is not None:
            update_data['name'] = name
            
        if price is not None:
            update_data['price'] = price
            
        if not update_data:
            return None # Нечего обновлять
        
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .values(**update_data)
            .returning(Product)
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        await self.db.commit()
        
        return self._to_dict_(product) if product else None
        
    
    async def transfer_product_ownership(self, username: str, product_id: int):
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .values(owner_username=username)
            .returning(Product)
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        await self.db.commit()
        
        return self._to_dict_(product) if product else None