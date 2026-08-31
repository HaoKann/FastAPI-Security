from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from auth import get_current_user
from models import Product

router = APIRouter(
    prefix='/cart',
    tags=['Cart'],
    dependencies=[Depends(get_current_user)]
)

class CartItemCreate(BaseModel):
    product_id: int
    amount: int