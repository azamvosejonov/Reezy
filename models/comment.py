import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)

    owner = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")
