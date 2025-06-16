from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

class BlockedPostBase(BaseModel):
    """Base schema for blocked post operations."""
    post_id: int = Field(..., description="ID of the post to block")
    reason: Optional[str] = Field(
        None, 
        max_length=255,
        description="Optional reason for blocking the post"
    )

class BlockedPostCreate(BlockedPostBase):
    """Schema for creating a new blocked post entry."""
    pass

class BlockedPostUpdate(BaseModel):
    """Schema for updating a blocked post entry."""
    reason: Optional[str] = Field(
        None, 
        max_length=255,
        description="Updated reason for blocking the post"
    )
    
    model_config = ConfigDict(from_attributes=True)

class BlockedPostInDBBase(BlockedPostBase):
    """Base schema for blocked post data stored in the database."""
    id: int
    user_id: int = Field(..., description="ID of the user who blocked the post")
    created_at: datetime = Field(..., description="Timestamp when the post was blocked")
    
    model_config = ConfigDict(from_attributes=True)

class BlockedPost(BlockedPostInDBBase):
    """Schema for returning blocked post data to the client."""
    pass

class BlockedPostList(BaseModel):
    """Schema for returning a paginated list of blocked posts."""
    items: List[BlockedPost] = Field(..., description="List of blocked posts")
    total: int = Field(..., description="Total number of blocked posts")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    
    model_config = ConfigDict(from_attributes=True)
