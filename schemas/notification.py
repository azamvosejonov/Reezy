from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

class NotificationType(str, Enum):
    """Types of notifications."""
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    MENTION = "mention"
    SHARE = "share"
    MESSAGE = "message"
    SYSTEM = "system"

class NotificationBase(BaseModel):
    """Base schema for notifications."""
    type: NotificationType
    message: str
    is_read: bool = False
    user_id: int
    actor_id: int  # The user who triggered the notification
    reference_id: Optional[int] = None  # ID of the related entity (post_id, comment_id, etc.)
    reference_type: Optional[str] = None  # Type of the reference (post, comment, etc.)

class NotificationCreate(NotificationBase):
    """Schema for creating a new notification."""
    pass

class NotificationUpdate(BaseModel):
    """Schema for updating a notification (e.g., marking as read)."""
    is_read: Optional[bool] = None

class Notification(NotificationBase):
    """Schema for notification response."""
    id: int
    created_at: datetime
    updated_at: datetime
    actor: Dict[str, Any]  # Basic info about who triggered the notification
    
    model_config = {"from_attributes": True}

class NotificationList(BaseModel):
    """Schema for a list of notifications with pagination support."""
    items: List[Notification]
    total: int
    page: int
    pages: int
    has_more: bool
