from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from schemas.block import Block, BlockCreate, BlockStatus
from services.block_service import BlockService
from models import User
from database import SessionLocal
# from routers.advertisements import get_current_user # Temporarily disabled


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(tags=["blocks"])
logger = logging.getLogger(__name__)

# WARNING: Authentication has been temporarily disabled on these endpoints for testing.
# This is insecure and should not be used in production.
# A hardcoded user ID (e.g., 1) is used instead of the authenticated user.

@router.post("/", response_model=Block, status_code=status.HTTP_201_CREATED)
async def block_user(
    block_data: BlockCreate,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Temporarily disabled
):
    """
    Block a user.
    
    - **blocked_id**: ID of the user to block
    """
    try:
        service = BlockService(db)
        # Using a hardcoded user ID (1) for testing.
        return await service.block_user(
            blocker_id=1, 
            blocked_id=block_data.blocked_id
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error blocking user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while blocking the user"
        )

@router.delete("/{blocked_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    blocked_id: int,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Temporarily disabled
):
    """
    Unblock a user.
    
    - **blocked_id**: ID of the user to unblock
    """
    try:
        service = BlockService(db)
        # Using a hardcoded user ID (1) for testing.
        unblocked = await service.unblock_user(
            blocker_id=1,
            blocked_id=blocked_id
        )
        
        if not unblocked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block relationship not found"
            )
            
        return None
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error unblocking user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unblocking the user"
        )

@router.get("/status/{user_id}", response_model=BlockStatus)
async def get_block_status(
    user_id: int,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Temporarily disabled
):
    """
    Check if current user has blocked another user.
    
    - **user_id**: ID of the user to check block status with
    """
    try:
        service = BlockService(db)
        # Using a hardcoded user ID (1) for testing.
        block_status = await service.get_block_status(
            blocker_id=1,
            blocked_id=user_id
        )
        # Return the BlockStatus object directly from the service
        return block_status
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error checking block status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while checking block status"
        )

@router.get("/blocked-users", response_model=List[int])
async def get_blocked_users(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Temporarily disabled
):
    """
    Get a list of user IDs that the current user has blocked.
    """
    try:
        service = BlockService(db)
        # Using a hardcoded user ID (1) for testing.
        return await service.get_blocked_users(user_id=1)
    except Exception as e:
        logger.error(f"Error getting blocked users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching blocked users"
        )

@router.get("/blocked-by-users", response_model=List[int])
async def get_blocked_by_users(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Temporarily disabled
):
    """
    Get a list of user IDs who have blocked the current user.
    """
    try:
        service = BlockService(db)
        # Using a hardcoded user ID (1) for testing.
        return await service.get_blocked_by_users(user_id=1)
    except Exception as e:
        logger.error(f"Error getting users who blocked current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching users who blocked you"
        )
