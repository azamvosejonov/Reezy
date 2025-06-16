from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class LiveStreamBase(BaseModel):
    """Base schema for livestreams."""
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_live: bool = False

class LiveStreamCreate(LiveStreamBase):
    """Schema for creating a new livestream."""
    pass

class LiveStreamUpdate(LiveStreamBase):
    """Schema for updating a livestream."""
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_live: Optional[bool] = None

class LiveStreamInDBBase(LiveStreamBase):
    """Base schema for livestream data in the database."""
    id: int
    host_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str  # active, ended
    viewer_count: int = 0
    saved_post_id: Optional[int] = None

    model_config = {"from_attributes": True}

class LiveStream(LiveStreamInDBBase):
    """Schema for livestream response with additional data."""
    host: Dict[str, Any]  # Basic user info
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False

class LiveStreamList(BaseModel):
    """Schema for listing livestreams with pagination."""
    items: List[LiveStream]
    total: int
    page: int
    pages: int
    has_more: bool

# Comment schemas
class LiveStreamCommentBase(BaseModel):
    """Base schema for livestream comments."""
    text: str

class LiveStreamCommentCreate(LiveStreamCommentBase):
    """Schema for creating a new livestream comment."""
    pass

class LiveStreamCommentInDB(LiveStreamCommentBase):
    """Schema for livestream comment data in the database."""
    id: int
    user_id: int
    livestream_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

class LiveStreamComment(LiveStreamCommentInDB):
    """Schema for livestream comment response with additional data."""
    user: Dict[str, Any]  # Basic user info
