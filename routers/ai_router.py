from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, Literal, List, Union
from pydantic import BaseModel, Field
from datetime import datetime

# Import AI services
from ai.services.ai_service import AIService
from ai.api.endpoints.ai import TextGenerationRequest

# Create router
router = APIRouter(
    prefix="/api/ai",
    tags=["AI Services"],
    responses={404: {"description": "Not found"}},
)

# Initialize AI service with rate limiting
ai_service = AIService(rate_limit_per_minute=60)

class Message(BaseModel):
    """A message in a conversation."""
    role: Literal['system', 'user', 'assistant']
    content: str

class AIModelRequest(TextGenerationRequest):
    """Request model for AI text generation."""
    model: Literal['gemini'] = 'gemini'  # Only Gemini is supported now

class Recommendation(BaseModel):
    """A recommendation from the ad analysis."""
    type: str
    message: str
    confidence: float = Field(..., ge=0.0, le=1.0)

class AdAnalysisData(BaseModel):
    """Ad analysis data model."""
    analysis_timestamp: datetime
    source: str
    recommendations: List[Recommendation]

class AdAnalysisResponse(BaseModel):
    """Response model for ad analysis API."""
    status: Literal['success', 'error']
    data: Optional[AdAnalysisData] = None
    message: str
    error: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

@router.post("/generate", summary="Generate text using AI")
async def generate_text(request: AIModelRequest):
    """
    Generate text using the specified AI model with rate limiting.
    
    Args:
        prompt: The input prompt for text generation (if messages is None)
        max_tokens: Maximum number of tokens to generate (default: 100)
        temperature: Controls randomness (0.0 to 1.0, default: 0.7)
        model: Which AI model to use ('gemini' or 'grok')
        system_prompt: Optional system message to set AI behavior (Grok only)
        messages: Optional conversation history (Grok only)
        
    Returns:
        Generated text and metadata
    """
    try:
        return await ai_service.generate_text(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating text with {request.model}: {str(e)}"
        )

@router.get("/ad/analyze", response_model=AdAnalysisResponse, summary="Analyze an ad")
async def analyze_ad(
    title: str,
    description: Optional[str] = None,
    target_audience: Optional[str] = None
):
    """
    Analyze an advertisement for optimization recommendations.
    
    Args:
        title: The ad title to analyze
        description: Optional ad description
        target_audience: Optional target audience description
        
    Returns:
        Analysis results with optimization recommendations
    """
    try:
        # This is a mock implementation - replace with actual analysis logic
        recommendations = []
        
        # Example recommendation
        if len(title) < 15:
            recommendations.append({
                "type": "title_optimization",
                "message": "Consider making the title more descriptive (15+ characters)",
                "confidence": 0.75
            })
        
        # Add more analysis logic here...
        
        return {
            "status": "success",
            "data": {
                "analysis_timestamp": datetime.utcnow(),
                "source": "local_analysis",
                "recommendations": recommendations
            },
            "message": "Ad analysis completed successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Failed to analyze ad",
            "error": {"detail": str(e)}
        }

@router.get("/rate-limit", summary="Get current rate limit status")
async def get_rate_limit_status():
    """
    Get the current rate limit status.
    
    Returns:
        Current rate limit information including remaining requests and reset time
    """
    try:
        status = ai_service.get_rate_limit_status()
        return status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rate limit status: {str(e)}"
        )

@router.get("/health", status_code=200)
async def health_check():
    """
    Health check endpoint for the AI service.
    
    Returns:
        Service status and timestamp
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "ai"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )
