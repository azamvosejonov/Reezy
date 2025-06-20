from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class UserSettings(Base):
    """User settings model for storing user preferences."""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    preferred_country = Column(String(2), nullable=True, comment='Preferred country code')
    show_country_posts = Column(Boolean, default=True, comment='Show posts from preferred country')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="settings")
