from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, synonym
from datetime import datetime

from config import settings
from database import Base


class Advertisement(Base):
    """Advertisement model for storing advertisement details."""
    __tablename__ = "advertisements"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(512), nullable=True)
    target_url = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey(f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey(f"{settings.SQLALCHEMY_DB_TABLE_PREFIX}users.id"), nullable=True)
    views_count = Column(Integer, default=0, nullable=False)
    clicks_count = Column(Integer, default=0, nullable=False)
    max_views = Column(Integer, default=1000, nullable=False)  # Default max views
    is_approved = Column(Boolean, default=False, nullable=False)  # Track approval status
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="advertisements")
    admin = relationship("User", foreign_keys=[admin_id], back_populates="admin_approved_ads")
    
    # For backward compatibility
    created_by = synonym('user_id')
    
    def __repr__(self):
        return f"<Advertisement {self.title} (ID: {self.id})>"
