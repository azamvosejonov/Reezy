from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class BlockBase(BaseModel):
    """Base schema for block data."""
    blocked_id: int = Field(..., description="ID of the user to block")

class BlockCreate(BlockBase):
    """Schema for creating a new block."""
    pass

class BlockInDBBase(BlockBase):
    """Base schema for block data stored in the database."""
    id: int
    blocker_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

class Block(BlockInDBBase):
    """Schema for returning block data."""
    pass

class BlockStatus(BaseModel):
    """Schema for block status response."""
    is_blocked: bool
    blocked_at: Optional[datetime] = None
