from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
from config import settings

# Import for type checking to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.user import User

class CallStatus:
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    REJECTED = "rejected"

class CallType:
    VOICE = "voice"
    VIDEO = "video"

class Call(Base):
    """Call model for storing call information."""
    __tablename__ = f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}calls"
    
    id = Column(Integer, primary_key=True, index=True)
    caller_id = Column(Integer, ForeignKey(f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey(f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}users.id"), nullable=False)
    call_type = Column(String(20), nullable=False, default=CallType.VOICE)
    status = Column(String(20), nullable=False, default=CallStatus.RINGING)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds
    call_sid = Column(String(255), nullable=True)  # For WebRTC or Twilio call ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships with simplified string literals and proper back_populates
    caller = relationship(
        "User",
        foreign_keys=[caller_id],
        primaryjoin="Call.caller_id == User.id",
        viewonly=True,
        overlaps="calls_made,initiated_calls"
    )
    receiver = relationship(
        "User",
        foreign_keys=[receiver_id],
        primaryjoin="Call.receiver_id == User.id",
        viewonly=True,
        overlaps="calls_received,received_calls"
    )
    participants = relationship(
        "CallParticipant",
        back_populates="call",
        foreign_keys="CallParticipant.call_id",
        primaryjoin="Call.id == CallParticipant.call_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        overlaps="call_relation"
    )
    
    def __repr__(self):
        return f"<Call {self.id}: {self.caller_id} -> {self.receiver_id} ({self.status})>"

class CallParticipant(Base):
    """Tracks participants in a call (for group calls)."""
    __tablename__ = f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}call_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey(f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}calls.id"), nullable=False)
    user_id = Column(Integer, ForeignKey(f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)
    is_muted = Column(Boolean, default=False)
    is_video_on = Column(Boolean, default=False)
    
    # Relationships with proper back_populates and overlaps
    call = relationship(
        "Call",
        foreign_keys=[call_id],
        primaryjoin="CallParticipant.call_id == Call.id",
        back_populates="participants",
        lazy="selectin",
        overlaps="call_relation,participants"
    )
    user = relationship(
        "User",
        foreign_keys=[user_id],
        primaryjoin="CallParticipant.user_id == User.id",
        lazy="selectin"
    )
    
    def __repr__(self):
        return f"<CallParticipant {self.user_id} in Call {self.call_id}>"
