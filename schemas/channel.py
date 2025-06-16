from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl, Field


class ChannelBase(BaseModel):
    name: str
    description: Optional[str] = None
    image: Optional[str] = None  # This is the field causing the error

class ChannelCreate(ChannelBase):
    creator_id: int

class ChannelUpdate(ChannelBase):
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    is_active: Optional[bool] = None

class ChannelInDB(ChannelBase):
    id: int
    creator_id: int
    created_at: datetime
    is_active: bool = True
    subscriber_count: int = 0
    message_count: int = 0
    is_subscribed: bool = False

    model_config = {"from_attributes": True}


class ChannelResponse(ChannelInDB):
    """Schema for channel response with additional data."""
    creator: Dict[str, Any]  # Basic user info


class ChannelListResponse(BaseModel):
    """Schema for paginated list of channels."""
    items: List['ChannelResponse']
    total: int
    page: int
    pages: int
    has_more: bool

# Channel message schemas
class ChannelMessageBase(BaseModel):
    text: str
    media_url: Optional[str] = Field(
        None,
        description="URL to the media file (image or video)",
        example="https://example.com/media/image.jpg"
    )

class ChannelMessageCreate(ChannelMessageBase):
    pass

class ChannelMessageInDB(ChannelMessageBase):
    id: int
    channel_id: int
    from_user_id: int
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False

    model_config = {"from_attributes": True}


class ChannelMessageResponse(ChannelMessageInDB):
    """Schema for channel message response with user data."""
    user: Dict[str, Any]  # Basic user info who sent the message

# Channel subscriber schemas
class ChannelSubscriberBase(BaseModel):
    user_id: int
    channel_id: int

class ChannelSubscriberCreate(ChannelSubscriberBase):
    pass

class ChannelSubscriberInDB(ChannelSubscriberBase):
    id: int
    subscribed_at: datetime

    model_config = {"from_attributes": True}

# Channel comment schemas
class ChannelCommentBase(BaseModel):
    text: str

class ChannelCommentCreate(ChannelCommentBase):
    pass

class ChannelCommentInDB(ChannelCommentBase):
    id: int
    message_id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
