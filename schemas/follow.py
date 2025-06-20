from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class FollowRequestResponse(BaseModel):
    """Response model for follow requests."""
    id: int
    requester_id: int
    requested_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
