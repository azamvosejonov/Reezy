from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from models import User, Advertisement as AdvertisementModel
from database import SessionLocal, get_db
from routers.auth import get_current_user, oauth2_scheme

from schemas import AdvertisementCreate, Advertisement as AdvertisementSchema, AdvertisementApprove, AdvertisementStats

# Use the same oauth2_scheme from auth.py
# This will handle both header and cookie authentication

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
):
    """
    Check if the current user is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive"
        )
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
):
    """
    Check if the current user is an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

router = APIRouter(prefix="/advertisements", tags=["advertisements"])

# Constants
VIEWS_PER_DOLLAR = 900
MAX_BUDGET = 1000

@router.post("/", response_model=AdvertisementSchema, status_code=status.HTTP_201_CREATED)
async def create_advertisement(
    ad_data: AdvertisementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new advertisement
    
    - **title**: Advertisement title
    - **description**: Detailed description
    - **image_url**: URL of the advertisement image
    - **target_url**: URL where the ad should lead
    - **is_active**: Whether the ad is active
    - **start_date**: When the ad should start showing
    - **end_date**: When the ad should stop showing
    """
    # Create the advertisement with the current user's ID
    db_ad = AdvertisementModel(
        title=ad_data.title,
        description=ad_data.description,
        image_url=str(ad_data.image_url) if ad_data.image_url else None,
        target_url=str(ad_data.target_url),
        is_active=ad_data.is_active,
        start_date=ad_data.start_date,
        end_date=ad_data.end_date,
        user_id=current_user.id,  # Use the authenticated user's ID
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by=current_user.id  # Set created_by to current user's ID
    )
    
    db.add(db_ad)
    db.commit()
    db.refresh(db_ad)
    
    return db_ad

@router.get("/my-ads", response_model=List[AdvertisementSchema])
async def get_my_advertisements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all advertisements for the currently authenticated user
    """
    return db.query(AdvertisementModel).filter(
        AdvertisementModel.user_id == current_user.id
    ).all()

@router.get("/pending", response_model=List[AdvertisementSchema])
async def get_pending_advertisements(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all pending advertisements (admin only)"""
    return db.query(AdvertisementModel).filter(
        AdvertisementModel.is_approved == False
    ).all()

@router.post("/{ad_id}/approve", response_model=AdvertisementSchema)
async def approve_advertisement(
    ad_id: int,
    approval: AdvertisementApprove,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Approve or reject an advertisement (admin only)"""
    ad = db.query(AdvertisementModel).filter(AdvertisementModel.id == ad_id).first()
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found"
        )
    
    ad.is_approved = approval.is_approved
    ad.admin_id = current_user.id
    ad.approved_at = datetime.utcnow()
    ad.is_active = approval.is_approved
    
    db.commit()
    db.refresh(ad)
    
    # Notify user about approval status
    # notify_user_about_ad_status(ad.user_id, ad.is_approved)
    
    return ad

@router.get("/{ad_id}/stats", response_model=AdvertisementStats)
async def get_advertisement_stats(
    ad_id: int,
    db: Session = Depends(get_db)
):
    """Get statistics for an advertisement"""
    # TODO: Add a way to identify the user without authentication
    current_user_id = 1  # Using a dummy user ID
    ad = db.query(AdvertisementModel).filter(
        AdvertisementModel.id == ad_id, 
        AdvertisementModel.user_id == current_user_id
    ).first()
    
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Advertisement not found"
        )
    
    # Calculate click-through rate (CTR)
    ctr = 0.0
    if ad.views_count > 0:
        ctr = (ad.clicks_count / ad.views_count) * 100  # As percentage
    
    return {
        "id": ad.id,
        "views": ad.views_count,
        "clicks": ad.clicks_count,
        "click_through_rate": ctr,
        "start_date": ad.start_date,
        "end_date": ad.end_date,
        "created_at": ad.created_at
    }

def increment_ad_views(ad_id: int, db: Session):
    """Increment the view count for an advertisement"""
    ad = db.query(AdvertisementModel).filter(
        (AdvertisementModel.id == ad_id) &
        (AdvertisementModel.is_active == True) &
        (AdvertisementModel.is_approved == True) &
        (AdvertisementModel.views_count < AdvertisementModel.max_views)
    ).with_for_update().first()
    
    if ad:
        ad.views_count += 1
        
        # If we've reached the maximum views, deactivate the ad
        if ad.views_count >= ad.max_views:
            ad.is_active = False
        
        db.commit()
        db.refresh(ad)
        return True
    
    return False
