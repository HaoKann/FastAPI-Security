from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase

# Это базовый класс для всех моделей
class Base(DeclarativeBase):
    pass

# --- Модель таблицы Users ---
# Раньше было: CREATE TABLE users (id SERIAL PRIMARY KEY, ...)
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


# --- Модель таблицы Products ---
# Раньше было: CREATE TABLE products (...)
class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, server_default='true')

    # Связь с юзером (внешний ключ)
    owner_username = Column(String, ForeignKey('users.username'), nullable=False)
