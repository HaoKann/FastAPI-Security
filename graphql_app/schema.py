import strawberry
from strawberry.types import Info
from typing import Optional, List
from graphql_app.auth import authenticate_user

# # Импорт SQLAlchemy
from create_db import async_session_maker
from sqlalchemy import select
from models import Product

# --- Создаем "Слепок" товара (ProductType) ---
# Это то, как товар будет выглядеть для GraphQL.
# Поля должны совпадать с тем, что вернет база данных.
@strawberry.type
class ProductType:
    id: strawberry.ID # strawberry.ID (это спец-тип для GraphQL, понимает UUID)
    name: str
    description: Optional[str] # Optional означает, что поле может быть null(пустым)
    price: int


# --- 2. Резолверы

# ЧТЕНИЕ
# info: Info — это специальный параметр Strawberry, в нем лежит объект запроса
async def get_products(info: Info) -> List[ProductType]:
    # Открываем сессию SQLAlchemy вместо старого пула
    async with async_session_maker() as db:
        # Безопасный запрос через SQLAlchemy
        result = await db.execute(select(Product))
        products = result.scalars.all()
        
        # Превращаем объекты базы данных в красивые объекты ProductType
        return [
            ProductType(
                id = p.id,
                name=p.name,
                price=p.price,
                description=p.description
            )
            for p in products
        ]


# ЧТЕНИЕ ОДНОГО ТОВАРА
# Взвращаем Optional[ProductType], так как товара может и не быть
async def get_product(info: Info, product_id: int) -> Optional[ProductType]:
    async with async_session_maker() as db:
        # Ищем товар по ID
        result = await db.execute(select(Product).where(Product.id==product_id))
        p = result.scalar_one_or_none()
        
        if p:
            return [
                ProductType(
                    id=p.id,
                    name=p.name,
                    price=p.price,
                    description=p.description
                )
            ]
        return None
    
        
# ЗАПИСЬ (СОЗДАНИЕ ТОВАРА)
async def create_product(info: Info, name: str, price: int, description: Optional[str] = None) -> ProductType:
    request = info.context['request']

    # --- ПРОВЕРКА БЕЗОПАСНОСТИ ---
    # Если токена нет или он кривой — тут вылетит ошибка, и код ниже не сработает
    user = authenticate_user(request)
    
    # БЕЗОПАСНОЕ ИЗВЛЕЧЕНИЕ: если user это словарь - берем 'username', если строка - берем как есть
    username = user['username'] if isinstance(user, dict) else user
    print(f"Запрос выполнил пользователь: {user}")
   
    async with async_session_maker() as db:
        # Создаем объект товара (привязываем его к текущему пользователю)
        new_product = Product(
            name=name,
            price=price,
            description=description,
            creator_username=username,
            owner_username=username
        )
        
        db.add(new_product)
        await db.commit()
        # Обновляем объект, чтобы база данных вернула нам сгенерированный ID
        await db.refresh(new_product)
        
        # Возвращаем созданный объект для GraphQL
        return ProductType(
            id=new_product.id,
            price=new_product.price,
            description=new_product.description,
            name=new_product.name
        )        

# --- 3. Структура API ---

# Список доступных вопросов (Queries)
@strawberry.type
class Query:

    # Старый hello для теста
    @strawberry.field
    def hello(self) -> str:
        return 'GraphQL работает!'
    
    # Новое поле products.
    # Мы говорим: "Это поле вернет СПИСОК (List) объектов ProductType".
    # resolver=get_products связывает это поле с функцией выше.
    products: List[ProductType] = strawberry.field(resolver=get_products)

    # Один конкретный товар
    # Мы указываем resolver=get_product. Strawberry увидит аргумент product_id в функции
    # и автоматически добавит его в схему API.
    product: Optional[ProductType] = strawberry.field(resolver=get_product)


# Список доступных действий (Mutations)
@strawberry.type
class Mutation:
    # Мы называем действие 'addProduct'. 
    # Strawberry поймет, какие аргументы нужны, посмотрев на функцию create_product
    add_product: ProductType = strawberry.field(resolver=create_product)




# --- 4. Сборка Схемы ---
# Важно: теперь передаем и query, и mutation
schema = strawberry.Schema(query=Query, mutation=Mutation)