from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship

from database import Base

# Import for type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .user import User  # noqa: F401

class SocialAccount(Base):
    __tablename__ = "social_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # e.g., 'google', 'github', 'facebook'
    provider_id = Column(String(255), nullable=False)  # User ID from the provider
    
    # Relationship - using string-based reference to avoid circular imports
    user = relationship(
        "User",
        back_populates="social_accounts"
    )
    
    def __repr__(self):
        return f"<SocialAccount {self.provider}:{self.provider_id}>"
