"""
AI Content Moderation Module
Provides AI-powered content moderation for user-generated content.
"""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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
