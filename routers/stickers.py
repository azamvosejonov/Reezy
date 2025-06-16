from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from models.user import User
from services.sticker_service import StickerService
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/stickers", tags=["stickers"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
logger = logging.getLogger(__name__)

@router.get("/available", response_model=List[dict])
async def get_available_stickers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all available stickers that the user can purchase.
    """
    try:
        service = StickerService(db)
        return service.get_available_stickers(current_user.id)
    except Exception as e:
        logger.error(f"Error getting available stickers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving available stickers"
        )

@router.get("/my", response_model=List[dict])
async def get_my_stickers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all stickers owned by the current user.
    """
    try:
        service = StickerService(db)
        return service.get_user_stickers(current_user.id)
    except Exception as e:
        logger.error(f"Error getting user stickers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving your stickers"
        )

@router.post("/purchase/{sticker_id}", response_model=dict)
async def purchase_sticker(
    sticker_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Purchase a sticker with coins.
    """
    try:
        service = StickerService(db)
        return service.purchase_sticker(current_user.id, sticker_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error purchasing sticker: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your purchase"
        )

@router.get("/balance", response_model=dict)
async def get_my_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's coin balance and recent transactions.
    """
    try:
        service = StickerService(db)
        return service.get_coin_balance(current_user.id)
    except Exception as e:
        logger.error(f"Error getting coin balance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving your coin balance"
        )

# Admin endpoints
@router.post("/admin/add-coins", response_model=dict)
async def admin_add_coins(
    user_id: int,
    amount: int,
    description: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add coins to a user's balance (admin only).
    """
    # Check if current user is admin (kaxorovorif6@gmail.com)
    if current_user.email != "kaxorovorif6@gmail.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    
    try:
        service = StickerService(db)
        return service.add_coins(user_id, amount, description)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding coins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the coin balance"
        )

@router.post("/admin/create-sticker", response_model=dict)
async def admin_create_sticker(
    name: str,
    image_url: str,
    is_animated: bool = True,
    price: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new premium sticker (admin only).
    """
    # Check if current user is admin (kaxorovorif6@gmail.com)
    if current_user.email != "kaxorovorif6@gmail.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    
    try:
        service = StickerService(db)
        return service.create_premium_sticker(name, image_url, is_animated, price)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating sticker: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the sticker"
        )
