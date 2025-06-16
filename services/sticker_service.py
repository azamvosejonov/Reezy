from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import logging

from models.sticker import Sticker, UserSticker, UserCoin, CoinTransaction
from models.user import User

logger = logging.getLogger(__name__)

class StickerService:
    """Service for handling sticker and coin operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_available_stickers(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all available stickers that the user can purchase."""
        # Get all stickers that user doesn't own or has expired
        owned_sticker_ids = [us.sticker_id for us in 
                           self.db.query(UserSticker.sticker_id)
                           .filter(UserSticker.user_id == user_id,
                                  (UserSticker.expires_at.is_(None) | 
                                   (UserSticker.expires_at > datetime.utcnow()))
                                 )
                           .all()]
        
        query = self.db.query(Sticker)
        if owned_sticker_ids:
            query = query.filter(~Sticker.id.in_(owned_sticker_ids))
            
        return [{
            'id': sticker.id,
            'name': sticker.name,
            'image_url': sticker.image_url,
            'is_animated': sticker.is_animated,
            'price': sticker.price,
            'is_premium': sticker.is_premium
        } for sticker in query.all()]
    
    def get_user_stickers(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all stickers owned by the user."""
        user_stickers = (self.db.query(UserSticker)
                        .join(Sticker)
                        .filter(UserSticker.user_id == user_id,
                               (UserSticker.expires_at.is_(None) | 
                                (UserSticker.expires_at > datetime.utcnow()))
                              )
                        .all())
        
        return [{
            'id': us.sticker.id,
            'name': us.sticker.name,
            'image_url': us.sticker.image_url,
            'is_animated': us.sticker.is_animated,
            'obtained_at': us.obtained_at,
            'expires_at': us.expires_at,
            'is_premium': us.sticker.is_premium
        } for us in user_stickers]
    
    def purchase_sticker(self, user_id: int, sticker_id: int) -> Dict[str, Any]:
        """Purchase a sticker with coins."""
        # Start transaction
        try:
            # Get user's coin balance
            user_coin = (self.db.query(UserCoin)
                        .filter(UserCoin.user_id == user_id)
                        .with_for_update()  # Lock the row for update
                        .first())
            
            if not user_coin:
                user_coin = UserCoin(user_id=user_id, balance=0)
                self.db.add(user_coin)
            
            # Get sticker details
            sticker = self.db.query(Sticker).filter(Sticker.id == sticker_id).first()
            if not sticker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Sticker not found"
                )
            
            # Check if user already has this sticker
            existing = (self.db.query(UserSticker)
                      .filter(UserSticker.user_id == user_id,
                             UserSticker.sticker_id == sticker_id,
                             (UserSticker.expires_at.is_(None) | 
                              (UserSticker.expires_at > datetime.utcnow()))
                            )
                      .first())
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You already own this sticker"
                )
            
            # Check if user has enough coins
            if user_coin.balance < sticker.price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Not enough coins to purchase this sticker"
                )
            
            # Deduct coins
            user_coin.balance -= sticker.price
            
            # Add transaction record
            transaction = CoinTransaction(
                user_id=user_id,
                amount=-sticker.price,
                description=f"Purchased sticker: {sticker.name}"
            )
            self.db.add(transaction)
            
            # Add sticker to user's collection
            expires_at = None
            if sticker.is_premium:
                expires_at = datetime.utcnow() + timedelta(days=60)  # 2 months for premium stickers
                
            user_sticker = UserSticker(
                user_id=user_id,
                sticker_id=sticker_id,
                expires_at=expires_at
            )
            self.db.add(user_sticker)
            
            self.db.commit()
            
            return {
                'success': True,
                'balance': user_coin.balance,
                'sticker': {
                    'id': sticker.id,
                    'name': sticker.name,
                    'image_url': sticker.image_url,
                    'is_animated': sticker.is_animated,
                    'expires_at': expires_at
                }
            }
            
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error purchasing sticker: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing your purchase"
            )
    
    def add_coins(self, user_id: int, amount: int, description: str) -> Dict[str, Any]:
        """Add coins to user's balance."""
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
            
        try:
            # Get or create user's coin balance
            user_coin = (self.db.query(UserCoin)
                        .filter(UserCoin.user_id == user_id)
                        .with_for_update()  # Lock the row for update
                        .first())
            
            if not user_coin:
                user_coin = UserCoin(user_id=user_id, balance=0)
                self.db.add(user_coin)
            
            # Update balance
            user_coin.balance += amount
            
            # Add transaction record
            transaction = CoinTransaction(
                user_id=user_id,
                amount=amount,
                description=description
            )
            self.db.add(transaction)
            
            self.db.commit()
            
            return {
                'success': True,
                'new_balance': user_coin.balance,
                'added_amount': amount
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding coins: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating your coin balance"
            )
    
    def get_coin_balance(self, user_id: int) -> Dict[str, Any]:
        """Get user's coin balance and recent transactions."""
        try:
            # Get user's coin balance
            user_coin = (self.db.query(UserCoin)
                        .filter(UserCoin.user_id == user_id)
                        .first())
            
            if not user_coin:
                return {
                    'balance': 0,
                    'transactions': []
                }
            
            # Get recent transactions (last 10)
            transactions = (self.db.query(CoinTransaction)
                          .filter(CoinTransaction.user_id == user_id)
                          .order_by(CoinTransaction.created_at.desc())
                          .limit(10)
                          .all())
            
            return {
                'balance': user_coin.balance,
                'transactions': [{
                    'id': t.id,
                    'amount': t.amount,
                    'description': t.description,
                    'created_at': t.created_at
                } for t in transactions]
            }
            
        except Exception as e:
            logger.error(f"Error getting coin balance: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving your coin balance"
            )

    def reward_for_post(self, user_id: int) -> Dict[str, Any]:
        """Reward user with 1 coin for creating a post."""
        return self.add_coins(
            user_id=user_id,
            amount=1,
            description="Reward for creating a post"
        )
    
    def create_premium_sticker(self, name: str, image_url: str, is_animated: bool = True, price: int = 10) -> Dict[str, Any]:
        """Create a new premium sticker."""
        try:
            sticker = Sticker(
                name=name,
                image_url=image_url,
                is_animated=is_animated,
                price=price,
                is_premium=True
            )
            self.db.add(sticker)
            self.db.commit()
            
            return {
                'success': True,
                'sticker': {
                    'id': sticker.id,
                    'name': sticker.name,
                    'image_url': sticker.image_url,
                    'is_animated': sticker.is_animated,
                    'price': sticker.price,
                    'is_premium': sticker.is_premium
                }
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating premium sticker: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while creating the sticker"
            )
