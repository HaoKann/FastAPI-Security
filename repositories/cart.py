from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from models import Cart, CartItem
from sqlalchemy.ext.asyncio import AsyncSession


async def add_item_to_cart(db: AsyncSession, user_id: int, product_id: int, amount: int):
    # 1. Ищем корзину пользователя
    find_cart = select(Cart).where(Cart.user_id == user_id)
    result = await db.execute(find_cart)
    cart = result.scalar_one_or_none()
    
    # 2. Если корзины нет, создаем ее
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    
    find_existing_cart_item = select(CartItem).where(CartItem.cart_id==cart.id, CartItem.product_id==product_id)
    result = await db.execute(find_existing_cart_item)
    existing_item = result.scalar_one_or_none()
    
    if existing_item:
        existing_item.amount += amount
    else:    
        new_cart_item = CartItem(cart_id=cart.id, product_id=product_id, amount=amount)
        db.add(new_cart_item)
        
    await db.commit()

    return {'message':'Товар успешно добавлен в корзину!'}


async def get_cart_items(db: AsyncSession, user_id: int):
    find_cart = select(Cart).where(Cart.user_id==user_id)
    result = await db.execute(find_cart)
    cart = result.scalar_one_or_none()    
    
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
    find_cart = select(Cart).where(Cart.user_id==user_id)
    result = await db.execute(find_cart)
    cart = result.scalar_one_or_none()
    
    if not cart:
        return {'meassage': 'Корзина не найдена'}
    
    delete_item = delete(CartItem).where(CartItem.cart_id==cart.id, CartItem.product_id==product_id)
    result = await db.execute(delete_item)
    await db.commit()
    
    return {'message': 'Товар успешно удален из корзины'}
