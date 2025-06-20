from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from models.ai_usage import AIUsage
from models.user import User

class AIUsageService:
    """Service for managing AI usage limits and subscriptions."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_usage(self, user_id: int) -> AIUsage:
        """Get or create AI usage record for a user."""
        usage = self.db.query(AIUsage).filter(AIUsage.user_id == user_id).first()
        if not usage:
            usage = AIUsage(user_id=user_id)
            self.db.add(usage)
            self.db.commit()
        return usage
    
    def check_usage_limit(self, user_id: int) -> bool:
        """Check if user has remaining AI usage quota."""
        usage = self.get_or_create_usage(user_id)
        
        # Check if premium subscription is valid
        if usage.is_premium:
            if usage.premium_expires_at and usage.premium_expires_at < datetime.utcnow():
                usage.is_premium = False
                usage.premium_expires_at = None
                self.db.commit()
            else:
                return True
        
        # Reset daily limit if needed
        if not usage.last_reset_date or usage.last_reset_date.date() != datetime.utcnow().date():
            usage.current_month_limit = 0
            usage.last_reset_date = datetime.utcnow()
            self.db.commit()
        
        return usage.current_month_limit < usage.daily_limit
    
    def increment_usage(self, user_id: int) -> None:
        """Increment AI usage counter for a user."""
        usage = self.get_or_create_usage(user_id)
        
        if not usage.is_premium and usage.current_month_limit >= usage.daily_limit:
            raise HTTPException(
                status_code=403,
                detail="Daily AI usage limit reached. Please subscribe to premium or wait until tomorrow."
            )
        
        usage.current_month_limit += 1
        self.db.commit()
    
    def subscribe_to_premium(self, user_id: int, email: str) -> None:
        """Subscribe user to premium and set verification email."""
        usage = self.get_or_create_usage(user_id)
        usage.is_premium = True
        usage.premium_expires_at = datetime.utcnow() + timedelta(days=30)
        usage.premium_verification_email = email
        usage.is_premium_verified = False
        self.db.commit()
    
    def verify_premium_subscription(self, user_id: int) -> None:
        """Verify premium subscription for a user."""
        usage = self.get_or_create_usage(user_id)
        
        if usage.premium_verification_email != "kaxorovorif6@gmail.com":
            raise HTTPException(
                status_code=403,
                detail="Invalid verification email"
            )
        
        usage.is_premium_verified = True
        usage.daily_limit = None  # Remove daily limit for verified premium users
        self.db.commit()
    
    def reset_limits(self, user_id: int) -> None:
        """Reset AI usage limits for a user."""
        usage = self.get_or_create_usage(user_id)
        usage.current_month_limit = 0
        usage.last_reset_date = datetime.utcnow()
        self.db.commit()
