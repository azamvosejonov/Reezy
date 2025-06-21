import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import SessionLocal
from models.user import User
from routers.auth import get_current_user, get_optional_current_user
from schemas.user import UserResponse, UserUpdate, PublicUserResponse
from services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        print(f"Database error: {e}")
        raise
    finally:
        db.close()




@router.get("/{user_id}", response_model=PublicUserResponse)
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a user's public profile.
    
    - **user_id**: ID of the user to retrieve
    - Returns: Public user information based on privacy settings and permissions
    """
    try:
        service = UserService(db)
        current_user_id = current_user.id if current_user else None
        
        # Get user with proper permission checks
        user = await service.get_user_by_id(
            user_id=user_id,
            current_user_id=current_user_id
        )
        
        # The service will handle privacy and block checks
        # Just return the user data as is since the service has already handled permissions
        return user
        
    except HTTPException as he:
        # Re-raise HTTP exceptions with their original status codes
        raise he
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the user profile"
        )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the current user's profile.
    
    - **user_data**: Updated user data
    """
    try:
        service = UserService(db)
        updated_user = await service.update_user(
            user_id=current_user.id,
            user_data=user_data
        )
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating your profile"
        )

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Delete the current user's account."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    try:
        service = UserService(db)
        success = await service.delete_user(current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return None
    except Exception as e:
        logger.error(f"Error deleting user account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting your account"
        )
