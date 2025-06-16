from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy import and_

from models.user import User

from models.advertisement import Advertisement
from schemas.advertisement import AdvertisementCreate, AdvertisementUpdate, AdvertisementInDBBase

class AdvertisementService:
    """Service for advertisement related operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_advertisement(
        self, 
        advertisement: AdvertisementCreate, 
        user_id: int = 0
    ) -> AdvertisementInDBBase:
        """
        Create a new advertisement.
        
        Args:
            advertisement: Advertisement data to create
            user_id: ID of the user creating the advertisement (optional)
            
        Returns:
            The created advertisement
        """
        # By default, advertisements are not active until approved
        db_ad = Advertisement(
            title=advertisement.title,
            description=advertisement.description,
            image_url=advertisement.image_url,
            target_url=str(advertisement.target_url),
            is_active=False,  # Set to False until approved
            start_date=advertisement.start_date,
            end_date=advertisement.end_date,
            created_by=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            views_count=0,
            clicks_count=0,
            max_views=1000,
            is_approved=False
        )
        
        self.db.add(db_ad)
        self.db.commit()
        self.db.refresh(db_ad)
        
        return db_ad

    async def approve_advertisement(
        self,
        ad_id: int,
        approver_email: str,
        is_approved: bool
    ) -> AdvertisementInDBBase:
        """
        Approve or reject an advertisement.
        
        Args:
            ad_id: ID of the advertisement to approve/reject
            approver_email: Email of the user approving/rejecting
            is_approved: Whether to approve or reject the advertisement
            
        Returns:
            The updated advertisement
        """
        # Get the advertisement
        advertisement = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        if not advertisement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Advertisement with ID {ad_id} not found"
            )

        # Get the approver user
        approver = self.db.query(User).filter(User.email == approver_email).first()
        if not approver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approver with email {approver_email} not found"
            )

        # Only kaxorovorif6@gmail.com can approve advertisements
        if approver.email != "kaxorovorif6@gmail.com":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only kaxorovorif6@gmail.com can approve advertisements"
            )

        # Update the advertisement status
        advertisement.is_approved = is_approved
        advertisement.is_active = is_approved  # Set active status based on approval
        advertisement.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(advertisement)
        
        return advertisement
    
    async def get_advertisement(self, ad_id: int) -> Optional[AdvertisementInDBBase]:
        """
        Get an advertisement by ID.
        
        Args:
            ad_id: ID of the advertisement to retrieve
            
        Returns:
            The advertisement if found, None otherwise
        """
        return self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    
    async def list_advertisements(
        self, 
        skip: int = 0, 
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[AdvertisementInDBBase]:
        """
        List advertisements with optional filtering.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            is_active: Filter by active status
            
        Returns:
            List of advertisements
        """
        query = self.db.query(Advertisement)
        
        if is_active is not None:
            query = query.filter(Advertisement.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    async def update_advertisement(
        self, 
        ad_id: int, 
        advertisement: AdvertisementUpdate,
        user_id: int
    ) -> Optional[AdvertisementInDBBase]:
        """
        Update an advertisement.
        
        Args:
            ad_id: ID of the advertisement to update
            advertisement: Updated advertisement data
            user_id: ID of the user performing the update
            
        Returns:
            The updated advertisement if found, None otherwise
        """
        db_ad = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        
        if not db_ad:
            return None
            
        # Check if user is the owner or admin
        if db_ad.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to update this advertisement"
            )
        
        update_data = advertisement.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_ad, field, value)
        
        db_ad.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(db_ad)
        
        return db_ad
    
    async def delete_advertisement(self, ad_id: int, user_id: int) -> bool:
        """
        Delete an advertisement.
        
        Args:
            ad_id: ID of the advertisement to delete
            user_id: ID of the user performing the deletion
            
        Returns:
            True if the advertisement was deleted, False otherwise
        """
        db_ad = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        
        if not db_ad:
            return False
            
        # Check if user is the owner or admin
        if db_ad.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to delete this advertisement"
            )
        
        self.db.delete(db_ad)
        self.db.commit()
        
        return True
    
    async def get_active_advertisements(self) -> List[AdvertisementInDBBase]:
        """
        Get all active advertisements that are within their date range.
        
        Returns:
            List of active advertisements
        """
        now = datetime.utcnow()
        
        return self.db.query(Advertisement).filter(
            Advertisement.is_active == True,
            Advertisement.start_date <= now,
            (Advertisement.end_date.is_(None) | (Advertisement.end_date >= now))
        ).all()
