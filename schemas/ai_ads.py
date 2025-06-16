"""
Pydantic models for AI Ad Optimization API
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AIAdAnalysisRequest(BaseModel):
    """Request model for ad analysis"""
    title: str = Field(..., description="The title of the ad")
    description: str = Field(..., description="The description of the ad")
    target_audience: str = Field("General", description="Target audience description")
    performance_metrics: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional performance metrics like click-through rate, impressions, etc."
    )
    additional_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Any additional context about the ad or campaign"
    )

class Recommendation(BaseModel):
    """A single recommendation from the AI analysis"""
    type: str = Field(..., description="Type of recommendation")
    message: str = Field(..., description="The recommendation message")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    suggested_title: Optional[str] = Field(None, description="Suggested title if applicable")
    suggested_description: Optional[str] = Field(None, description="Suggested description if applicable")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class AIAdOptimizationResponse(BaseModel):
    """Response model for ad analysis"""
    analysis_id: str = Field(..., description="Unique ID for this analysis")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the analysis was performed")
    status: str = Field("success", description="Analysis status")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in the analysis")
    recommendations: List[Recommendation] = Field(..., description="List of recommendations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional analysis metadata")

class AdOptimizationRequest(BaseModel):
    """Request model for ad copy optimization"""
    original_title: str = Field(..., description="Original ad title")
    original_description: str = Field(..., description="Original ad description")
    target_audience: str = Field(..., description="Target audience description")
    tone: Optional[str] = Field("professional", description="Desired tone for the optimized copy")
    max_length: Optional[int] = Field(100, description="Maximum length for the optimized copy")
    keywords: Optional[List[str]] = Field(None, description="Keywords to include in the optimized copy")

class AdOptimizationResponse(BaseModel):
    """Response model for ad copy optimization"""
    original_title: str = Field(..., description="Original ad title")
    optimized_title: str = Field(..., description="Optimized ad title")
    optimized_description: str = Field(..., description="Optimized ad description")
    optimization_score: float = Field(..., ge=0.0, le=1.0, description="Optimization quality score")
    improvements: List[str] = Field(..., description="List of improvements made")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the optimization was performed")
