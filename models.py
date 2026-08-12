from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship

# Это базовый класс для всех моделей
class Base(DeclarativeBase):
    pass

# --- Модель таблицы Users ---
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    
    # Новое поле для ролевой модели. По умолчанию все становятся обычными пользователями
    role = Column(String, default='user')
    
    products = relationship('Product', back_populates='owner')
    

# --- Модель таблицы Products ---
class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, server_default='true')
    image_url = Column(String, nullable=True)
    
    # Связь с юзером (внешний ключ)
    owner_username = Column(String, ForeignKey('users.username'), nullable=False)
    
    # Поле для хранения оригинального создателя товара
    creator_username = Column(String, nullable=True)
    
    owner = relationship('User', back_populates='products')

# --- Модель таблицы Calculations (для фоновых задач) ---
class Calculation(Base):
    __tablename__ = 'calculations'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    task = Column(String, nullable=False)   
    result = Column(String, nullable=False)