from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

class PostBase(BaseModel):
    """Base schema for post data."""
    body: Optional[str] = Field(None, max_length=5000)
    
class MediaType(str, Enum):
    """Supported media types for posts."""
    IMAGE = "image"
    VIDEO = "video"

class PostCreate(PostBase):
    """Schema for creating a new post with optional media, enhancements, and location."""
    media_url: Optional[str] = Field(
        None,
        description="URL of the uploaded media file (image or video)"
    )
    media_type: Optional[MediaType] = Field(
        None,
        description="Type of media (image or video)"
    )
    filter_type: Optional[str] = Field(
        None,
        description="Optional filter to apply to the media (e.g., 'sepia', 'black_and_white')",
        pattern="^[a-zA-Z0-9_-]*$"
    )
    text_overlay: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional text to overlay on the media"
    )
    text_position: Optional[str] = Field(
        "bottom",
        description="Position of the text overlay",
        pattern="^(top|center|bottom|top-left|top-right|bottom-left|bottom-right)$"
    )
    sticker_id: Optional[int] = Field(
        None,
        ge=1,
        description="Optional ID of a sticker to add to the post"
    )
    latitude: Optional[float] = Field(
        None,
        ge=-90,
        le=90,
        description="Latitude coordinate of where the post was created"
    )
    longitude: Optional[float] = Field(
        None,
        ge=-180,
        le=180,
        description="Longitude coordinate of where the post was created"
    )
    location_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Human-readable name of the location"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "body": "Check out this amazing view!",
                "media_url": "/media/posts/12345.jpg",
                "media_type": "image",
                "filter_type": "vintage",
                "text_overlay": "Vacation vibes",
                "text_position": "bottom",
                "sticker_id": 42,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "location_name": "New York, NY"
            }
        }
    
    @model_validator(mode='after')
    def validate_media_fields(self) -> 'PostCreate':
        """Validate that media_url and media_type are provided together."""
        if bool(self.media_url) != bool(self.media_type):
            raise ValueError("Both media_url and media_type must be provided together")
        return self

class PostUpdate(PostBase):
    """Schema for updating an existing post."""
    pass

class PostInDBBase(PostBase):
    """Base schema for post data stored in the database."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
    
    model_config = {"from_attributes": True}


class Post(PostInDBBase):
    """Schema for post representation."""
    user: Dict[str, Any]  # Basic user info (id, username, profile_picture)
    
    model_config = {"from_attributes": True}

class PostResponse(PostInDBBase):
    """Schema for post response."""
    media_url: Optional[str] = None
    media_type: Optional[MediaType] = None
    filter_type: Optional[str] = None
    text_overlay: Optional[str] = None
    text_position: Optional[str] = None
    sticker_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    user: Dict[str, Any]
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
    is_saved: bool = False
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "body": "Check out this amazing view!",
                "media_url": "/media/posts/12345.jpg",
                "media_type": "image",
                "filter_type": "vintage",
                "text_overlay": "Vacation vibes",
                "text_position": "bottom",
                "sticker_id": 42,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "location_name": "New York, NY",
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-01T12:00:00",
                "user_id": 1,
                "user": {
                    "id": 1,
                    "username": "johndoe",
                    "avatar_url": "/media/avatars/1.jpg"
                },
                "like_count": 42,
                "comment_count": 7,
                "is_liked": False,
                "is_saved": False
            }
        }

class PostListResponse(BaseModel):
    """Schema for listing posts with pagination."""
    items: List[PostResponse]
    total: int
    page: int
    pages: int
    
class TaskStatusResponse(BaseModel):
    """Schema for task status response."""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class LikeBase(BaseModel):
    """Base schema for post likes."""
    post_id: int
    user_id: int


class LikeCreate(LikeBase):
    """Schema for creating a new like."""
    pass


class Like(LikeBase):
    """Schema for like response."""
    id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class CommentBase(BaseModel):
    """Base schema for comments."""
    content: str = Field(..., max_length=1000)
    post_id: int
    user_id: int
    parent_id: Optional[int] = None  # For nested comments


class CommentCreate(CommentBase):
    """Schema for creating a new comment."""
    pass


class Comment(CommentBase):
    """Schema for comment response."""
    id: int
    created_at: datetime
    updated_at: datetime
    user: Dict[str, Any]  # Basic user info
    like_count: int = 0
    is_liked: bool = False
    
    model_config = {"from_attributes": True}
