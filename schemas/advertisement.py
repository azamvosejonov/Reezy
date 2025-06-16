from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field, model_validator, validator
from dateutil.parser import parse

class AdvertisementBase(BaseModel):
    """Base schema for advertisement data."""
    title: str = Field(..., max_length=255, description="Title of the advertisement")
    description: Optional[str] = Field(None, description="Detailed description of the advertisement")
    image_url: Optional[str] = Field(None, description="URL to the advertisement image")
    target_url: Optional[HttpUrl] = Field(None, description="URL where the advertisement should redirect to")
    is_active: Optional[bool] = Field(True, description="Whether the advertisement is active")
    start_date: Optional[datetime] = Field(default_factory=datetime.utcnow, description="When the advertisement should start showing")
    end_date: Optional[datetime] = Field(None, description="When the advertisement should stop showing")

    @validator('target_url', pre=True)
    def validate_target_url(cls, v):
        """Validate target URL"""
        if v is None:
            return "https://example.com"  # Default URL if none provided
        return v

    @validator('start_date', pre=True)
    def validate_start_date(cls, v):
        """Validate start date"""
        if v is None:
            return datetime.utcnow()
        return v

    @validator('end_date', pre=True)
    def validate_end_date(cls, v):
        """Validate end date"""
        if v is None:
            return None
        try:
            return parse(v)
        except (ValueError, TypeError):
            return None

class AdvertisementCreate(AdvertisementBase):
    """Schema for creating a new advertisement."""
    pass

class AdvertisementUpdate(BaseModel):
    """Schema for updating an existing advertisement."""
    title: Optional[str] = Field(None, max_length=255, description="Updated title of the advertisement")
    description: Optional[str] = Field(None, description="Updated description")
    image_url: Optional[HttpUrl] = Field(None, description="Updated image URL")
    target_url: Optional[HttpUrl] = Field(None, description="Updated target URL")
    is_active: Optional[bool] = Field(None, description="Update active status")
    start_date: Optional[datetime] = Field(None, description="Updated start date")
    end_date: Optional[datetime] = Field(None, description="Updated end date")

class AdvertisementInDBBase(AdvertisementBase):
    """Base schema for advertisement stored in the database."""
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

    model_config = {"from_attributes": True}

class Advertisement(AdvertisementInDBBase):
    """Schema for returning advertisement data."""
    pass

class AdvertisementList(BaseModel):
    """Schema for a list of advertisements."""
    total: int
    items: List[Advertisement]


class AdvertisementApprove(BaseModel):
    """Schema for approving/rejecting advertisements."""
    is_approved: bool = Field(..., description="Whether the advertisement is approved")
    rejection_reason: Optional[str] = Field(
        None, 
        max_length=500, 
        description="Reason for rejection if applicable"
    )


class AdvertisementStats(BaseModel):
    """Schema for advertisement statistics."""
    id: int
    views: int = 0
    clicks: int = 0
    click_through_rate: float = 0.0
    start_date: datetime
    end_date: Optional[datetime] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}
    
@model_validator(mode='after')
def calculate_ctr(self) -> 'AdvertisementStats':
    """Calculate click-through rate."""
    if self.views > 0:
        self.click_through_rate = (self.clicks / self.views) * 100
    return self
