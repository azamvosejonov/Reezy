from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import relationship

from config import settings
from database import Base

# Import for type checking to avoid circular imports
if TYPE_CHECKING:
    from .user import User

class Follower(Base):
    """Association table for followers/following relationships."""
    __tablename__ = 'followers'  # Base table name without prefix
    __table_args__ = {'schema': settings.SQLALCHEMY_DB_TABLE_PREFIX.rstrip('_') if settings.SQLALCHEMY_DB_TABLE_PREFIX else None}
    
    # Foreign keys reference the users table without schema/prefix
    follower_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    followed_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Use string-based references to avoid circular imports
    follower = relationship("User", foreign_keys=[follower_id], back_populates="follower_relationships")
    followed = relationship("User", foreign_keys=[followed_id], back_populates="followed_relationships")
    
    def __repr__(self):
        return f"<Follower {self.follower_id} -> {self.followed_id}>"
