from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from openai.types.beta.threads.message import Attachment
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum

class MessageType(str, Enum):
    """Types of messages."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"

class MessageBase(BaseModel):
    """Base schema for messages."""
    content: str = Field(..., max_length=5000)
    message_type: MessageType = MessageType.TEXT
    parent_message_id: Optional[int] = None
    reply_to_message_id: Optional[int] = None

class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    recipient_id: int  # For direct messages
    # For group messages, use the group_id from the endpoint

class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    content: Optional[str] = Field(None, max_length=5000)
    is_read: Optional[bool] = None

class MessageInDB(MessageBase):
    """Schema for message data in the database."""
    id: int
    sender_id: int
    conversation_id: int
    is_read: bool = False
    is_edited: bool = False
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    attachments: List[Attachment] = []

    model_config = {"from_attributes": True}

class Message(MessageInDB):
    """Schema for message response with additional data."""
    sender: Dict[str, Any]  # Basic user info
    recipient: Optional[Dict[str, Any]] = None  # For direct messages
    parent_message: Optional[Dict[str, Any]] = None  # For replies
    reply_to: Optional[Dict[str, Any]] = None  # For replies
    attachments: List[Attachment] = []  # For media/files

class ConversationBase(BaseModel):
    """Base schema for conversations."""
    title: Optional[str] = None
    is_group: bool = False

class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation."""
    participant_ids: List[int]  # User IDs to include in the conversation

class ConversationUpdate(ConversationBase):
    """Schema for updating a conversation."""
    title: Optional[str] = None

class ConversationInDB(ConversationBase):
    """Schema for conversation data in the database."""
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class Conversation(ConversationInDB):
    """Schema for conversation response with additional data."""
    participants: List[Dict[str, Any]]  # List of users in the conversation
    last_message: Optional[Dict[str, Any]] = None  # Last message in the conversation
    unread_count: int = 0  # Number of unread messages

class ConversationList(BaseModel):
    """Schema for a list of conversations with pagination."""
    items: List[Conversation]
    total: int
    page: int
    pages: int
    has_more: bool
