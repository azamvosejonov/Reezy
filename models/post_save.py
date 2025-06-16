import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING

from database import Base

# Import for type checking to avoid circular imports
if TYPE_CHECKING:
    from .user import User
    from .post import Post

class PostSave(Base):
    __tablename__ = 'post_saves'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    saved_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships - using string-based references to avoid circular imports
    owner = relationship(
        "User",
        back_populates="saves",
        doc="User who saved the post"
    )
    
    post = relationship(
        "Post",
        back_populates="saves",
        doc="Post that was saved"
    )

    __table_args__ = (UniqueConstraint('owner_id', 'post_id', name='_user_post_save_uc'),)
