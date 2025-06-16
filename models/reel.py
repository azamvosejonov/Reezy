import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class Reel(Base):
    __tablename__ = 'reels'
    id = Column(Integer, primary_key=True, index=True)
    caption = Column(Text, nullable=True)
    media_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    owner = relationship("User", back_populates="reels")
    comments = relationship("ReelComment", back_populates="reel", cascade="all, delete-orphan")
    likes = relationship("ReelLike", back_populates="reel", cascade="all, delete-orphan")

class ReelLike(Base):
    __tablename__ = 'reel_likes'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    reel_id = Column(Integer, ForeignKey('reels.id'), nullable=False)

    owner = relationship("User", back_populates="reel_likes")
    reel = relationship("Reel", back_populates="likes")

class ReelComment(Base):
    __tablename__ = 'reel_comments'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    reel_id = Column(Integer, ForeignKey('reels.id'), nullable=False)

    owner = relationship("User", back_populates="reel_comments")
    reel = relationship("Reel", back_populates="comments")
