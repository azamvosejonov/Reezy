from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PostViewResponse(BaseModel):
    id: int
    post_id: int
    owner_id: int
    created_at: datetime
    
    model_config = {
        "from_attributes": True
    }
