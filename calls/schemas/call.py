from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl

class CallBase(BaseModel):
    """Base schema for call data."""
    receiver_id: int = Field(..., description="ID of the user receiving the call")
    call_type: str = Field("voice", description="Type of call (voice/video)")
    
class CallCreate(CallBase):
    """Schema for creating a new call."""
    pass

class CallUpdate(BaseModel):
    """Schema for updating a call."""
    status: Optional[str] = Field(None, description="New status of the call")
    duration: Optional[int] = Field(None, description="Duration of the call in seconds")
    call_sid: Optional[str] = Field(None, description="Call SID from WebRTC/Twilio")

class CallInDBBase(CallBase):
    """Base schema for call data in the database."""
    id: int
    caller_id: int
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class Call(CallInDBBase):
    """Schema for returning call data."""
    pass

class CallParticipantBase(BaseModel):
    """Base schema for call participant data."""
    is_muted: bool = False
    is_video_on: bool = False

class CallParticipantCreate(CallParticipantBase):
    """Schema for adding a participant to a call."""
    user_id: int

class CallParticipantUpdate(CallParticipantBase):
    """Schema for updating a call participant."""
    left_at: Optional[datetime] = None

class CallParticipantInDB(CallParticipantBase):
    """Schema for call participant data in the database."""
    id: int
    call_id: int
    user_id: int
    joined_at: datetime
    left_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CallWithParticipants(CallInDBBase):
    """Schema for call data including participants."""
    participants: List[CallParticipantInDB] = []

class CallTokenResponse(BaseModel):
    """Schema for call token response."""
    token: str = Field(..., description="Authentication token for WebRTC")
    call_id: int = Field(..., description="ID of the call")
    user_id: int = Field(..., description="ID of the current user")
    call_type: str = Field(..., description="Type of call (voice/video)")

class CallOffer(BaseModel):
    """Schema for WebRTC offer."""
    sdp: str = Field(..., description="Session Description Protocol offer")
    type: str = Field(..., description="Type of the offer")

class IceCandidate(BaseModel):
    """Schema for ICE candidate."""
    candidate: str = Field(..., description="ICE candidate string")
    sdp_mid: Optional[str] = Field(None, description="Media stream identification")
    sdp_mline_index: Optional[int] = Field(None, description="Index of the media description")

class CallSignal(BaseModel):
    """Schema for call signaling data."""
    type: str = Field(..., description="Type of signal (offer, answer, candidate, etc.)")
    data: dict = Field(..., description="Signal data (offer, answer, candidate, etc.)")
    call_id: int = Field(..., description="ID of the call")
    sender_id: int = Field(..., description="ID of the user sending the signal")
    receiver_id: int = Field(..., description="ID of the user receiving the signal")
