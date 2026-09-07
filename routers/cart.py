from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from create_db import get_db_session
from repositories.cart import add_item_to_cart, get_cart_items, delete_items_from_cart

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
    description: str
    image_url: str
    amount: int
    
class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_price: int

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