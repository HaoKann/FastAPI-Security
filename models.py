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
    
    # Новое поле для ролевой модели (RBAC). По умолчанию все становятся обычными пользователями
    role = Column(String, default='user')
    
    products = relationship('Product', back_populates='owner')
    cart = relationship('Cart', back_populates='user', uselist=False)
    

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
    cart_items = relationship('CartItem', back_populates='product')


# --- Модель таблицы Calculations (для фоновых задач) ---
class Calculation(Base):
    __tablename__ = 'calculations'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, ForeignKey('users.username'), nullable=False)
    task = Column(String, nullable=False)   
    result = Column(String, nullable=False)
    

class Cart(Base):
    __tablename__ = 'carts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    user = relationship('User', back_populates='cart')
    items = relationship('CartItem', back_populates='cart')


class CartItem(Base):
    __tablename__ = 'cart_items'
    
    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey('carts.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    amount = Column(Integer, default=1)
    
    cart = relationship('Cart', back_populates='items')
    product = relationship('Product', back_populates='cart_items')
    
    