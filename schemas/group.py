from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    image: Optional[str] = None

class GroupCreate(GroupBase):
    creator_id: int

class GroupUpdate(GroupBase):
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None

class GroupInDB(GroupBase):
    id: int
    creator_id: int
    created_at: datetime
    is_active: bool = True

    model_config = {"from_attributes": True}

class GroupMemberBase(BaseModel):
    user_id: int
    group_id: int

class GroupMemberCreate(GroupMemberBase):
    pass

class GroupMemberInDB(GroupMemberBase):
    id: int
    joined_at: datetime

    model_config = {"from_attributes": True}

class GroupAdminBase(BaseModel):
    user_id: int
    group_id: int

class GroupAdminCreate(GroupAdminBase):
    pass

class GroupAdminInDB(GroupAdminBase):
    id: int
    granted_at: datetime

    model_config = {"from_attributes": True}


class GroupMessageBase(BaseModel):
    """Base schema for group message data."""
    content: Optional[str] = None
    user_id: int


class GroupMessageCreate(GroupMessageBase):
    """Schema for creating a new group message."""
    pass


class GroupMessageInDB(GroupMessageBase):
    """Schema for group message data in the database."""
    id: int
    group_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: Dict[str, Any] = {}

    model_config = {"from_attributes": True}
