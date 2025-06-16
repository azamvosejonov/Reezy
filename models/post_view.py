import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base

class PostView(Base):
    __tablename__ = 'post_views'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    viewed_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="views")
    post = relationship("Post", back_populates="views")
