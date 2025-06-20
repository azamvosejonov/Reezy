from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class MediaType(str, Enum):
    """Supported media types for stories."""
    IMAGE = "image"
    VIDEO = "video"


class StoryBase(BaseModel):
    """Base schema for story data."""
    media_url: str = Field(..., description="URL of the story media file")
    media_type: MediaType = Field(..., description="Type of media (image or video)")
    expires_in_hours: Optional[int] = Field(
        24,
        ge=1,
        le=168,
        description="Number of hours until the story expires (1-168 hours, default: 24)"
    )


class StoryCreate(StoryBase):
    """Schema for creating a new story."""
    user_id: int = Field(..., description="ID of the user creating the story")

    @validator('media_url')
    def validate_media_url(cls, v):
        if not v.startswith('/media/stories/'):
            raise ValueError("Media URL must start with '/media/stories/'")
        return v


class StoryUpdate(BaseModel):
    """Schema for updating a story."""
    is_active: Optional[bool] = Field(
        None,
        description="Set to false to archive the story before it expires"
    )


class StoryResponse(StoryBase):
    """Schema for story response."""
    id: int
    user_id: int
    created_at: datetime
    expires_at: datetime
    is_active: bool
    view_count: int = 0
    is_expired: bool = False
    user: Dict[str, Any]

    model_config = {"from_attributes": True}


class StoryListResponse(BaseModel):
    """Schema for listing stories with user information."""
    items: List[Dict[str, Any]]
    total: int


class StoryViewResponse(BaseModel):
    """Schema for story view response."""
    id: int
    story_id: int
    user_id: int
    viewed_at: datetime
    user: Dict[str, Any]

    model_config = {"from_attributes": True}


class StoryViewListResponse(BaseModel):
    """Schema for listing story views."""
    items: List[Dict[str, Any]]
    total: int
