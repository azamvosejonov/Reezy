from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class LiveStream(Base):
    __tablename__ = 'livestreams'

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default='active')  # active, ended
    viewer_count = Column(Integer, default=0)
    saved_post_id = Column(Integer, ForeignKey('posts.id'), nullable=True)

    host = relationship('User', back_populates='livestreams')
    likes = relationship('LiveStreamLike', back_populates='livestream', cascade='all, delete-orphan')
    comments = relationship('LiveStreamComment', back_populates='livestream', cascade='all, delete-orphan')

class LiveStreamLike(Base):
    __tablename__ = 'livestream_likes'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    livestream_id = Column(Integer, ForeignKey('livestreams.id'), nullable=False)

    user = relationship('User')
    livestream = relationship('LiveStream', back_populates='likes')

class LiveStreamComment(Base):
    __tablename__ = 'livestream_comments'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    livestream_id = Column(Integer, ForeignKey('livestreams.id'), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User')
    livestream = relationship('LiveStream', back_populates='comments')
