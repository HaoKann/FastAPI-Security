from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from create_db import get_db_session
from repositories.cart import add_item_to_cart

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


@router.get('/view', response_model=list[CartItemResponse])
async def get_cart_items(
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get('id')
    
     