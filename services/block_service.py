from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models.block import Block
from models.user import User
from schemas.block import BlockCreate, BlockStatus

class BlockService:
    """Service for handling user blocking functionality."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def block_user(
        self, 
        blocker_id: int, 
        blocked_id: int
    ) -> Block:
        """
        Block a user.
        
        Args:
            blocker_id: ID of the user who is blocking
            blocked_id: ID of the user being blocked
            
        Returns:
            The created Block record
        """
        if blocker_id == blocked_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot block yourself"
            )
            
        # Check if already blocked
        existing_block = self.db.query(Block).filter(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id
        ).first()
        
        if existing_block:
            return existing_block
            
        # Check if users exist
        blocker = self.db.query(User).filter(User.id == blocker_id).first()
        blocked = self.db.query(User).filter(User.id == blocked_id).first()
        
        if not blocker or not blocked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Create the block
        block = Block(
            blocker_id=blocker_id,
            blocked_id=blocked_id
        )
        
        self.db.add(block)
        self.db.commit()
        self.db.refresh(block)
        
        return block
    
    async def unblock_user(
        self, 
        blocker_id: int, 
        blocked_id: int
    ) -> bool:
        """
        Unblock a user.
        
        Args:
            blocker_id: ID of the user who is unblocking
            blocked_id: ID of the user being unblocked
            
        Returns:
            bool: True if unblocked, False if no block existed
        """
        block = self.db.query(Block).filter(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id
        ).first()
        
        if not block:
            return False
            
        self.db.delete(block)
        self.db.commit()
        return True
    
    async def check_block_status(
        self, 
        user1_id: int, 
        user2_id: int
    ) -> bool:
        """
        Check if there is a block between two users in either direction.
        
        Args:
            user1_id: First user ID
            user2_id: Second user ID
            
        Returns:
            bool: True if either user has blocked the other
        """
        if user1_id == user2_id:
            return False
            
        return self.db.query(Block).filter(
            ((Block.blocker_id == user1_id) & (Block.blocked_id == user2_id)) |
            ((Block.blocker_id == user2_id) & (Block.blocked_id == user1_id))
        ).first() is not None
    
    async def get_block_status(
        self, 
        blocker_id: int, 
        blocked_id: int
    ) -> BlockStatus:
        """
        Get the block status between two users.
        
        Args:
            blocker_id: ID of the potential blocker
            blocked_id: ID of the potentially blocked user
            
        Returns:
            BlockStatus with is_blocked and blocked_at fields
        """
        block = self.db.query(Block).filter(
            Block.blocker_id == blocker_id,
            Block.blocked_id == blocked_id
        ).first()
        
        return BlockStatus(
            is_blocked=block is not None,
            blocked_at=block.created_at if block else None
        )
    
    async def get_blocked_users(
        self, 
        user_id: int
    ) -> List[int]:
        """
        Get a list of user IDs that the given user has blocked.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of blocked user IDs
        """
        blocks = self.db.query(Block).filter(
            Block.blocker_id == user_id
        ).all()
        
        return [block.blocked_id for block in blocks]
    
    async def get_blocked_by_users(
        self, 
        user_id: int
    ) -> List[int]:
        """
        Get a list of user IDs who have blocked the given user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of user IDs who have blocked this user
        """
        blocks = self.db.query(Block).filter(
            Block.blocked_id == user_id
        ).all()
        
        return [block.blocker_id for block in blocks]
