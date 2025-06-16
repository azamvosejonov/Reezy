import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from openai import OpenAI

class GrokService:
    """Service for interacting with the Grok AI API using the official OpenAI client."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Grok service with an optional API key."""
        self.api_key = api_key or os.getenv('XAI_API_KEY') or os.getenv('GROK_API_KEY')
        if not self.api_key:
            raise ValueError("XAI_API_KEY or GROK_API_KEY environment variable is required")
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self.model_name = "grok-3"
    
    async def generate_text(
        self, 
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate text using the Grok API via OpenAI client.
        
        Args:
            prompt: Input prompt for the AI (if messages is None)
            max_tokens: Maximum number of tokens to generate
            temperature: Controls randomness (0.0 to 1.0)
            system_prompt: Optional system message to set behavior
            messages: Optional list of message objects with role and content
            
        Returns:
            Dictionary containing the generated text and metadata
        """
        try:
            # Prepare messages
            message_list = []
            
            # Add system message if provided
            if system_prompt:
                message_list.append({"role": "system", "content": system_prompt})
                
            # Add existing messages or create a new user message from prompt
            if messages:
                message_list.extend(messages)
            else:
                message_list.append({"role": "user", "content": prompt})
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=message_list,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # Extract the response
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                return {
                    "text": content,
                    "model": self.model_name,
                    "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No response from Grok API"
                )
                    
        except Exception as e:
            error_detail = str(e)
            if "quota" in error_detail.lower() or "limit" in error_detail.lower():
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif "authentication" in error_detail.lower():
                status_code = status.HTTP_401_UNAUTHORIZED
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                
            raise HTTPException(
                status_code=status_code,
                detail=f"Grok API error: {error_detail}"
            )
