from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from schemas.advertisement_approval import AdvertisementApproval

from sqlalchemy.sql.functions import current_user

from schemas.advertisement import (
    AdvertisementCreate,
    AdvertisementUpdate,
    Advertisement,
    AdvertisementList
)
from services.advertisement_service import AdvertisementService
from models import User
from database import SessionLocal
from routers.auth import get_current_user

router = APIRouter(prefix="/advertisements", tags=["advertisements"])
logger = logging.getLogger(__name__)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
@router.post("/", response_model=Advertisement, status_code=status.HTTP_201_CREATED, operation_id="create_advertisement")
async def create_advertisement(
    advertisement: AdvertisementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new advertisement.
    
    - **title**: Advertisement title (required)
    - **description**: Detailed description (optional)
    - **image_url**: URL to the advertisement image (optional)
    - **target_url**: URL where the ad should redirect (optional)
    - **is_active**: Whether the ad is active (default: False until approved)
    - **start_date**: When the ad should start showing (default: now)
    - **end_date**: When the ad should stop showing (optional)
    
    Note: Advertisements are not active until approved by kaxorovorif6@gmail.com
    """
    try:
        service = AdvertisementService(db)
        return await service.create_advertisement(advertisement)
    except Exception as e:
        logger.error(f"Error creating advertisement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the advertisement"
        )


    """
    Create a new advertisement.
    
    - **title**: Advertisement title (required)
    - **description**: Detailed description (optional)
    - **image_url**: URL to the advertisement image (optional)
    - **target_url**: URL where the ad should redirect (required)
    - **is_active**: Whether the ad is active (default: True)
    - **start_date**: When the ad should start showing (default: now)
    - **end_date**: When the ad should stop showing (optional)
    """
    try:
        # Create advertisement with authenticated user's ID
        service = AdvertisementService(db)
        return await service.create_advertisement(advertisement, current_user.id)
    except Exception as e:
        logger.error(f"Error creating advertisement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the advertisement"
        )

@router.get("/{ad_id}", response_model=Advertisement)
async def get_advertisement(
    ad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get an advertisement by ID.
    
    - **ad_id**: ID of the advertisement to retrieve
    """
    service = AdvertisementService(db)
    advertisement = await service.get_advertisement(ad_id)
    if advertisement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advertisement with ID {ad_id} not found"
        )
    return advertisement

@router.get("/", response_model=AdvertisementList)
async def list_advertisements(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List advertisements with pagination and filtering.
    
    Only shows active and approved advertisements.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Number of records to return (1-100)
    - **is_active**: Filter by active status (optional)
    """
    try:
        service = AdvertisementService(db)
        # Only show active and approved advertisements
        advertisements = await service.list_advertisements(
            skip=skip,
            limit=limit,
            is_active=True  # Only show active advertisements
        )
        
        # Filter out unapproved advertisements
        advertisements = [ad for ad in advertisements if ad.is_approved]
        
        total = len(advertisements)
        return {
            "total": total,
            "items": advertisements
        }
    except Exception as e:
        logger.error(f"Error listing advertisements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving advertisements"
        )
    """
    List advertisements with pagination and filtering.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Number of records to return (1-100)
    - **is_active**: Filter by active status (optional)
    """
    try:
        service = AdvertisementService(db)
        advertisements = await service.list_advertisements(
            skip=skip,
            limit=limit,
            is_active=is_active
        )
        total = len(advertisements)
        return {
            "total": total,
            "items": advertisements
        }
    except Exception as e:
        logger.error(f"Error listing advertisements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving advertisements"
        )

@router.put("/{ad_id}", response_model=Advertisement)
async def update_advertisement(
    ad_id: int,
    advertisement: AdvertisementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an advertisement.
    
    Only the advertisement creator can update it.
    """
    try:
        service = AdvertisementService(db)
        updated_ad = await service.update_advertisement(
            ad_id=ad_id,
            advertisement=advertisement,
            user_id=current_user.id
        )
        
        if not updated_ad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Advertisement not found"
            )
            
        return updated_ad
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating advertisement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the advertisement"
        )

@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_advertisement(
    ad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an advertisement.
    
    Only the advertisement creator can delete it.
    """
    try:
        service = AdvertisementService(db)
        success = await service.delete_advertisement(ad_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Advertisement not found"
            )
            
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting advertisement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the advertisement"
        )

@router.get("/active/", response_model=List[Advertisement], operation_id="get_active_advertisements")
async def get_active_advertisements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all active advertisements that are within their date range.
    
    This endpoint requires authentication.
    """
    try:
        service = AdvertisementService(db)
        return await service.get_active_advertisements()
    except Exception as e:
        logger.error(f"Error retrieving active advertisements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving active advertisements"
        )
