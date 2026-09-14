from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from models import Cart, CartItem
from sqlalchemy.ext.asyncio import AsyncSession


async def find_cart(db: AsyncSession, user_id: int):
    query = select(Cart).where(Cart.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()
    
    
async def find_existing_cart_item(db: AsyncSession, cart_id: int, product_id: int):
        query = select(CartItem).where(CartItem.cart_id==cart_id, CartItem.product_id==product_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()


async def add_item_to_cart(db: AsyncSession, user_id: int, product_id: int, amount: int):
    # 1. Ищем корзину пользователя
    cart = await find_cart(db=db, user_id=user_id)
    
    # 2. Если корзины нет, создаем ее
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    
    existing_item = await find_existing_cart_item(db=db, cart_id=cart.id, product_id=product_id)
    
    if existing_item:
        existing_item.amount += amount
    else:    
        new_cart_item = CartItem(cart_id=cart.id, product_id=product_id, amount=amount)
        db.add(new_cart_item)
        
    await db.commit()

    return {'message':'Товар успешно добавлен в корзину!'}


async def get_cart_items(db: AsyncSession, user_id: int):
    
    cart = await find_cart(db=db, user_id=user_id)  
    
    if not cart:
        return {
            'items': [],
            'total_price': 0
        }
    
    find_items = select(CartItem).where(CartItem.cart_id==cart.id).options(joinedload(CartItem.product))
    result = await db.execute(find_items)
    cart_items = result.scalars().all()
    
    
    response_items = []
    total_price = 0
    
    for item in cart_items:
        
        item_total = item.product.price * item.amount
        total_price += item_total
        
        response_items.append({
            "product_id": item.product_id,
            "name": item.product.name,
            "price": item.product.price,
            "description": item.product.description,
            "image_url": item.product.image_url,
            "amount": item.amount
        })
        
    return {
        "items": response_items,
        "total_price": total_price
    }
    
async def delete_items_from_cart(db: AsyncSession, user_id: int, product_id: int): 
    
    cart = await find_cart(db=db, user_id=user_id)
    
    if not cart:
        return {'meassage': 'Корзина не найдена'}
    
    delete_item = delete(CartItem).where(CartItem.cart_id==cart.id, CartItem.product_id==product_id)
    result = await db.execute(delete_item)
    await db.commit()
    
    return {'message': 'Товар успешно удален из корзины'}


async def update_cart_item_amount(db: AsyncSession, user_id: int, product_id: int, amount: int):
    
    cart = await find_cart(db=db, user_id=user_id)
    if not cart:
        return None
        
    existing_item = await find_existing_cart_item(db=db, cart_id=cart.id, product_id=product_id)
    
    if existing_item:
        if amount <= 0:
            await db.delete(existing_item)
        else:    
            existing_item.amount = amount
            
        await db.commit()
        return {'message': 'Количество успешно изменено'}
    else:
        return {'message': 'Товара в корзине нет'}
    
    