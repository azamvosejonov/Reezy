from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

class FollowRequestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"

class FollowRequest(Base):
    __tablename__ = 'follow_requests'

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    requested_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(Enum(FollowRequestStatus), default=FollowRequestStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    requester = relationship("User", foreign_keys=[requester_id], back_populates="sent_follow_requests")
    requested = relationship("User", foreign_keys=[requested_id], back_populates="received_follow_requests")
