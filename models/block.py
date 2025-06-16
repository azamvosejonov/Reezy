from sqlalchemy import Column, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime

from config import settings
from database import Base

# Import User for type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .user import User


class Block(Base):
    """Model for tracking user blocks."""
    __tablename__ = "blocks"
    
    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    blocked_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    # These are viewonly relationships since we handle the many-to-many through the association table
    blocker = relationship("User", foreign_keys=[blocker_id], back_populates="blocks_made")
    blocked = relationship("User", foreign_keys=[blocked_id], back_populates="blocks_received")
    
    __table_args__ = (
        {'schema': settings.SQLALCHEMY_DB_TABLE_PREFIX.rstrip('_') if settings.SQLALCHEMY_DB_TABLE_PREFIX else None}
    )
    
    def __repr__(self):
        return f"<Block {self.blocker_id} -> {self.blocked_id}>"
