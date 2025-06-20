from pydantic import BaseModel
from typing import Optional

class BaseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
