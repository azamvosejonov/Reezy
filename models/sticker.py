from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base

class Sticker(Base):
    """Sticker model for storing sticker information"""
    __tablename__ = 'stickers'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    image_url = Column(String(500), nullable=False)
    is_animated = Column(Boolean, default=False)
    price = Column(Integer, default=10)  # Price in coins (default 10 coins)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user_stickers = relationship("UserSticker", back_populates="sticker")

class UserSticker(Base):
    """Association table for user's owned stickers"""
    __tablename__ = 'user_stickers'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    sticker_id = Column(Integer, ForeignKey('stickers.id'), nullable=False)
    obtained_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # None means permanent
    
    # Relationships
    sticker = relationship("Sticker", back_populates="user_stickers")
    user = relationship("User", back_populates="stickers")

class UserCoin(Base):
    """User's coin balance and transaction history"""
    __tablename__ = 'user_coins'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    balance = Column(Integer, default=0, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="coin_balance")

class CoinTransaction(Base):
    """Transaction history for user coins"""
    __tablename__ = 'coin_transactions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Integer, nullable=False)  # Can be positive (earned) or negative (spent)
    description = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="coin_transactions")
