from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .message import MessageType, Attachment

class ChannelMessageBase(BaseModel):
    """Base schema for channel messages."""
    text: Optional[str] = Field(None, max_length=5000)
    message_type: MessageType = MessageType.TEXT
    attachments: List[Attachment] = []

class ChannelMessageCreate(ChannelMessageBase):
    """Schema for creating a new channel message."""
    channel_id: int

class ChannelMessageInDB(ChannelMessageBase):
    """Schema for channel message data in the database."""
    id: int
    from_user_id: int
    channel_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    attachments: List[Attachment] = []

    class Config:
        from_attributes = True

class ChannelMessage(ChannelMessageInDB):
    """Schema for channel message response with additional data."""
    sender: Dict[str, Any]
    attachments: List[Attachment] = []

    class Config:
        from_attributes = True
