from pydantic import BaseModel, Field
from typing import Optional

class AdvertisementApproval(BaseModel):
    """Schema for advertisement approval."""
    ad_id: int = Field(..., description="ID of the advertisement to approve/reject")
    is_approved: bool = Field(..., description="Whether to approve (True) or reject (False) the advertisement")
    user_id: Optional[int] = Field(None, description="ID of the user approving the advertisement")

    class Config:
        json_schema_extra = {
            "example": {
                "ad_id": 1,
                "is_approved": True,
                "user_id": 1
            }
        }
