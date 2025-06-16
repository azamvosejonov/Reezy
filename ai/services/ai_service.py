import asyncio
import os
import tempfile
import time
import json
import aiohttp
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from dotenv import load_dotenv
from gtts import gTTS

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

# Gemini API configuration
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MODEL_NAME = "gemini-2.0-flash"

class AIService:
    """
    Service for handling AI-related operations with rate limiting.
    """
    
    def __init__(self, rate_limit_per_minute: int = 60):
        """
        Initialize the AI service with rate limiting.
        
        Args:
            rate_limit_per_minute: Number of allowed requests per minute
        """
        self.rate_limit = rate_limit_per_minute
        self.request_timestamps = []
        self.last_reset = datetime.now()
        
    def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        now = datetime.now()
        
        # Reset counters if a minute has passed
        if now - self.last_reset > timedelta(minutes=1):
            self.request_timestamps = []
            self.last_reset = now
        
        # Remove old timestamps (older than 1 minute)
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if now - ts < timedelta(minutes=1)
        ]
        
        # Check if we've hit the rate limit
        remaining = max(0, self.rate_limit - len(self.request_timestamps))
        if remaining <= 0:
            reset_time = (self.last_reset + timedelta(minutes=1)).strftime('%H:%M:%S')
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "remaining": 0,
                    "reset_at": reset_time
                }
            )
    
    def _track_api_usage(self):
        """Track API usage and update rate limit counters."""
        now = datetime.now()
        self.request_timestamps.append(now)
        
    def get_rate_limit_status(self):
        """Get current rate limit status."""
        now = datetime.now()
        
        # Clean up old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if now - ts < timedelta(minutes=1)
        ]
        
        remaining = max(0, self.rate_limit - len(self.request_timestamps))
        reset_time = (self.last_reset + timedelta(minutes=1)).strftime('%H:%M:%S')
        
        return {
            "limit": self.rate_limit,
            "remaining": remaining,
            "reset_at": reset_time
        }
    
    async def _handle_quota_error(self, error: Exception) -> Dict[str, Any]:
        """Handle quota exceeded errors with a friendly response."""
        return {
            "error": "API quota exceeded",
            "message": "The API quota has been exceeded. Please try again later.",
            "status_code": 429,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _make_gemini_request(self, prompt: str, max_tokens: int = 100, temperature: float = 0.7) -> Dict[str, Any]:
        """Make a request to the Gemini API"""
        headers = {
            'Content-Type': 'application/json',
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                    headers=headers,
                    json=payload
                ) as response:
                    response_data = await response.json()
                    if response.status != 200:
                        error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                        if 'quota' in error_msg.lower() or '429' in str(response.status):
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="API quota exceeded"
                            )
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Gemini API error: {error_msg}"
                        )
                    
                    # Track successful API usage
                    self._track_api_usage()
                    return response_data
                    
        except aiohttp.ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to connect to Gemini API: {str(e)}"
            )
    
    async def generate_text(
        self, 
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate text using Google's Gemini 2.0 Flash model with fallback for quota limits.
        
        Args:
            prompt: Input prompt for the AI
            max_tokens: Maximum number of tokens to generate
            temperature: Controls randomness (0.0 to 1.0)
            
        Returns:
            Dictionary containing the generated text and metadata
        """
        self._check_rate_limit()
        
        try:
            response_data = await self._make_gemini_request(prompt, max_tokens, temperature)
            
            # Extract the generated text from the response
            try:
                generated_text = response_data['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError) as e:
                generated_text = "I couldn't generate a response at the moment."
            
            return {
                "text": generated_text,
                "tokens_used": len(generated_text.split()),
                "model": MODEL_NAME,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except HTTPException as http_err:
            return await self._handle_quota_error(http_err)
        except Exception as e:
            return await self._handle_quota_error(e)
            
    async def generate_voice_response(
        self,
        text: str,
        language: str = 'en',
        slow: bool = False
    ) -> Tuple[bytes, str]:
        """
        Convert text to speech using gTTS.
        
        Args:
            text: Text to convert to speech
            language: Language code (e.g., 'en', 'ru', 'uz')
            slow: Whether to speak slowly
            
        Returns:
            Tuple of (audio_data, content_type)
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                temp_path = fp.name
            
            # Generate speech
            tts = gTTS(text=text, lang=language, slow=slow)
            tts.save(temp_path)
            
            # Read the file
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
                
            # Clean up
            os.unlink(temp_path)
            
            return audio_data, 'audio/mpeg'
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate voice response: {str(e)}"
            )
