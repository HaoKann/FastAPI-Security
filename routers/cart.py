from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from create_db import get_db_session
from repositories.cart import add_item_to_cart, get_cart_items, delete_items_from_cart, update_cart_item_amount

router = APIRouter(
    prefix='/cart',
    tags=['Cart'],
    dependencies=[Depends(get_current_user)]
)

class CartItemCreate(BaseModel):
    product_id: int
    amount: int
    
class CartItemResponse(BaseModel):
    product_id: int
    name: str
    price: int
    description: Optional[str] = None
    image_url: Optional[str] = None
    amount: int
    
class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_price: int
    
class CartItemChangeAmount(BaseModel):
    product_id: int
    amount: int

@router.post('/add')
async def add_products_to_cart(
    item: CartItemCreate, # Эти данные нужно брать из тела запроса (JSON)
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    user_id = current_user.get('id')
    
    result = await add_item_to_cart(
        db=db,
        user_id=user_id,
        product_id=item.product_id,
        amount=item.amount
    )
    return result


@router.get('/view', response_model=CartResponse)
async def get_items_from_cart(
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get('id')
    
    result = await get_cart_items(
        db=db,
        user_id=user_id
    )
    return result


@router.delete('/delete/{product_id}')
async def delete_item_from_cart(
    product_id: int,
    db: AsyncSession = Depends(get_db_session), 
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get('id')
    
    result = await delete_items_from_cart(
        db=db,
        user_id=user_id,
        product_id=product_id
    )
    return result


@router.put('/update')
async def change_amount_of_product(
    item: CartItemChangeAmount,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get('id')
    
    result = await update_cart_item_amount(
        db=db,
        product_id=item.product_id,
        amount=item.amount,
        user_id=user_id
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Корзина не найдена")    
    
    return result   
    
    