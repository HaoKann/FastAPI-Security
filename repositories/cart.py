from sqlalchemy import select
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