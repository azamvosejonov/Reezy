from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from config import settings
from database import Base

class AIUsage(Base):
    """Model for tracking AI usage limits and subscriptions."""
    __tablename__ = 'ai_usage'
    __table_args__ = {'schema': settings.SQLALCHEMY_DB_TABLE_PREFIX.rstrip('_') if settings.SQLALCHEMY_DB_TABLE_PREFIX else None}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    is_premium = Column(Boolean, default=False)
    premium_expires_at = Column(DateTime, nullable=True)
    daily_limit = Column(Integer, default=10)
    current_month_limit = Column(Integer, default=0)
    last_reset_date = Column(DateTime, nullable=True)
    premium_verification_email = Column(String(100), nullable=True)
    is_premium_verified = Column(Boolean, default=False)

    user = relationship("User", back_populates="ai_usage", uselist=False)

    def __repr__(self):
        return f"<AIUsage(id={self.id}, user_id={self.user_id}, is_premium={self.is_premium})>"
