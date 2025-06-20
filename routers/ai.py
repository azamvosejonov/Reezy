"""
AI Content Moderation Module
Provides AI-powered content moderation for user-generated content.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# In-memory storage for premium users (in production, use a database)
premium_users: Dict[str, dict] = {}
ALLOWED_EMAIL = "kaxorovorif6@gmail.com"
PREMIUM_DURATION_DAYS = 30  # 1 month premium duration
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import current_user

from database import get_db
from models import User
from services.ai_usage_service import AIUsageService
from services.user_service import UserService
# Authentication is not required for AI endpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    responses={404: {"description": "Not found"}},
)

# In-memory cache for banned words (in a real app, this would be in a database)
BANNED_WORDS = {
    'badword1', 'badword2', 'inappropriate', 'spam',
    'scam', 'hate', 'violence', 'harassment'
}

# Pydantic models
class ModerationRequest(BaseModel):
    text: str

class ModerationResponse(BaseModel):
    is_appropriate: bool
    reason: Optional[str] = None
    score: float
    found_terms: Optional[List[str]] = None

class SubscriptionRequest(BaseModel):
    email: str

class UserSubscription(BaseModel):
    user_id: str
    email: str
    is_premium: bool
    premium_since: Optional[datetime]
    premium_until: Optional[datetime]
    daily_limit: int = 1000
    remaining_uses: int = 1000

class SubscriptionResponse(BaseModel):
    is_premium: bool
    daily_limit: int
    remaining_uses: int
    premium_expires_at: Optional[str]
    message: Optional[str] = None

def moderate_text(text: str) -> Dict[str, Any]:
    """
    Analyze text for inappropriate content.
    
    Args:
        text: The text to analyze
        
    Returns:
        Dict containing:
        - is_appropriate: bool - Whether the content is appropriate
        - reason: str - Reason for flagging (if any)
        - score: float - Confidence score (0-1)
    """
    if not text or not isinstance(text, str):
        return {
            'is_appropriate': False,
            'reason': 'Empty or invalid text',
            'score': 0.0
        }
    
    # Convert to lowercase for case-insensitive matching
    text_lower = text.lower()
    
    # Check for banned words
    found_words = [word for word in BANNED_WORDS if word in text_lower]
    
    if found_words:
        return {
            'is_appropriate': False,
            'reason': f'Found inappropriate content: {found_words}',
            'score': 0.9,
            'found_terms': found_words
        }
    
    # Check for excessive caps (shouting)
    if len(text) > 10 and sum(1 for c in text if c.isupper()) / len(text) > 0.7:
        return {
            'is_appropriate': False,
            'reason': 'Excessive use of capital letters',
            'score': 0.6
        }
    
    # Check for excessive repetition
    if any(text_lower.count(word * 3) > 0 for word in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']):
        return {
            'is_appropriate': False,
            'reason': 'Excessive character repetition',
            'score': 0.7
        }
    
    # If all checks pass
    return {
        'is_appropriate': True,
        'reason': 'Content appears appropriate',
        'score': 1.0
    }

@router.post("/moderate", response_model=ModerationResponse)
async def moderate_content(
    request: ModerationRequest
):
    """
    Moderate content using AI.
    
    Args:
        request: Content moderation request
        
    Returns:
        ModerationResponse: Content moderation result
    """
    # Process moderation without user authentication or usage tracking
    result = moderate_text(request.text)
    
    return ModerationResponse(
        is_appropriate=result['is_appropriate'],
        reason=result.get('reason'),
        score=result['score'],
        found_terms=result.get('found_terms')
    )

@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe_to_premium(
    email: str,
    user_id: str,
):
    """
    Subscribe to premium AI service.
    Only allows subscription for the specific email address.
    
    Args:
        email: User's email address
        user_id: User's unique ID
        
    Returns:
        SubscriptionResponse: Subscription status
    """
    if email.lower() != ALLOWED_EMAIL:
        raise HTTPException(
            status_code=403,
            detail="Premium subscription is not available for this email address"
        )
    
    # Check if user already has premium
    if user_id in premium_users:
        return {
            "is_premium": True,
            "daily_limit": premium_users[user_id]['daily_limit'],
            "remaining_uses": premium_users[user_id]['remaining_uses'],
            "premium_expires_at": premium_users[user_id]['premium_until'].isoformat() if premium_users[user_id]['premium_until'] else None,
            "message": "You already have an active premium subscription"
        }
    
    # Add new premium user
    premium_until = datetime.utcnow() + timedelta(days=PREMIUM_DURATION_DAYS)
    premium_users[user_id] = {
        'email': email,
        'is_premium': True,
        'premium_since': datetime.utcnow(),
        'premium_until': premium_until,
        'daily_limit': 1000,
        'remaining_uses': 1000
    }
    
    return {
        "is_premium": True,
        "daily_limit": 1000,
        "remaining_uses": 1000,
        "premium_expires_at": premium_until.isoformat(),
        "message": "Premium subscription activated successfully!"
    }

@router.post("/verify", response_model=SubscriptionResponse)
async def verify_premium_subscription():
    """
    Verify premium subscription.
    
    Returns:
        SubscriptionResponse: Subscription status
    """
    # In a real app, you would verify the subscription with a payment provider
    # For testing, we'll return a default response
    return {
        "is_premium": False,
        "daily_limit": 10,
        "remaining_uses": 10,
        "premium_expires_at": None
    }

@router.get("/status/{user_id}", response_model=SubscriptionResponse)
async def get_subscription_status(user_id: str):
    """
    Get current subscription status for a user.
    
    Args:
        user_id: User's unique ID
        
    Returns:
        SubscriptionResponse: Current subscription status
    """
    user = premium_users.get(user_id)
    if not user or not user['is_premium']:
        return {
            "is_premium": False,
            "daily_limit": 10,
            "remaining_uses": 10,
            "premium_expires_at": None,
            "message": "No active premium subscription found"
        }
    
    # Check if premium has expired
    if user['premium_until'] and user['premium_until'] < datetime.utcnow():
        user['is_premium'] = False
        return {
            "is_premium": False,
            "daily_limit": 10,
            "remaining_uses": 10,
            "premium_expires_at": None,
            "message": "Your premium subscription has expired"
        }
    
    return {
        "is_premium": True,
        "daily_limit": user['daily_limit'],
        "remaining_uses": user['remaining_uses'],
        "premium_expires_at": user['premium_until'].isoformat(),
        "message": "Active premium subscription"
    }

@router.get("/premium-users", response_model=List[Dict])
async def list_premium_users():
    """
    List all premium users.
    
    Returns:
        List of premium users with their subscription details
    """
    current_time = datetime.utcnow()
    active_users = []
    
    for user_id, user_data in premium_users.items():
        if user_data['is_premium'] and (not user_data['premium_until'] or user_data['premium_until'] > current_time):
            active_users.append({
                "user_id": user_id,
                "email": user_data['email'],
                "premium_since": user_data['premium_since'].isoformat(),
                "premium_until": user_data['premium_until'].isoformat() if user_data['premium_until'] else None,
                "days_remaining": (user_data['premium_until'] - current_time).days if user_data['premium_until'] else None
            })
    
    return active_users
