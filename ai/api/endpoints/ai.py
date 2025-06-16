from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from pydantic import BaseModel
from datetime import datetime

from ai.services.ai_service import AIService

router = APIRouter()

# Initialize AI service with rate limiting (e.g., 60 requests per minute)
ai_service = AIService(rate_limit_per_minute=60)

class TextGenerationRequest(BaseModel):
    prompt: str
    max_tokens: int = 100
    temperature: float = 0.7

class SentimentAnalysisRequest(BaseModel):
    text: str

@router.post("/generate")
async def generate_text(request: TextGenerationRequest) -> Dict[str, Any]:
    """
    Generate text using the AI model with rate limiting.
    
    Args:
        request: Text generation parameters
        
    Returns:
        Generated text and metadata
    """
    return await ai_service.generate_text(
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )

@router.post("/analyze-sentiment")
async def analyze_sentiment(request: SentimentAnalysisRequest) -> Dict[str, Any]:
    """
    Analyze sentiment of the given text with rate limiting.
    
    Args:
        request: Text to analyze
        
    Returns:
        Sentiment analysis results
    """
    return await ai_service.analyze_sentiment(text=request.text)

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for the AI service.
    
    Returns:
        Service status and timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "AI Service"
    }
