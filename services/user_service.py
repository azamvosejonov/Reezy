from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, not_
from fastapi import HTTPException, status
import logging

from models.user import User
from models.block import Block
from schemas.user import UserResponse, UserUpdate, PublicUserResponse
from routers.auth import get_password_hash

logger = logging.getLogger(__name__)

class UserService:
    """Service for handling user-related operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def search_users(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        current_user_id: Optional[int] = None,
        exclude_blocked: bool = True
    ) -> List[dict]:
        """
        Search for users with optional query string.
        
        Args:
            query: Optional search query to filter users by username or full name
            limit: Maximum number of results to return
            offset: Number of results to skip for pagination
            current_user_id: Optional ID of the current user for permission checks
            exclude_blocked: Whether to exclude users who have blocked or been blocked by the current user
            
        Returns:
            List of user dictionaries matching the search criteria
        """
        try:
            # Start with base query for active users
            query_filters = [User.is_active == True]
            
            # Add search term filter if provided
            if query:
                search_term = f"%{query}%"
                query_filters.append(
                    or_(
                        User.username.ilike(search_term),
                        User.full_name.ilike(search_term)
                    )
                )
            
            # Exclude blocked users if requested and user is authenticated
            if exclude_blocked and current_user_id:
                blocked_users = self.db.query(Block.user2_id).filter(Block.user1_id == current_user_id)
                blocked_by = self.db.query(Block.user1_id).filter(Block.user2_id == current_user_id)
                query_filters.append(User.id.notin_(blocked_users.union(blocked_by).subquery()))
            
            # Execute query with pagination
            users = self.db.query(User).filter(*query_filters)\
                .order_by(User.username)\
                .offset(offset)\
                .limit(limit)\
                .all()
            
            # Convert to response dictionaries
            result = []
            for user in users:
                is_own_profile = current_user_id == user.id
                is_private = getattr(user, 'is_private', False)
                
                # For private profiles, only return basic info unless it's the user's own profile
                if is_private and not is_own_profile:
                    user_data = {
                        "id": user.id,
                        "username": user.username,
                        "is_private": True,
                        "profile_picture": user.profile_picture,
                        "is_verified": user.is_verified,
                        "created_at": user.created_at
                    }
                else:
                    # For public profiles or own profile, return full info
                    user_data = {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.full_name,
                        "bio": user.bio,
                        "profile_picture": user.profile_picture,
                        "is_verified": user.is_verified,
                        "is_private": is_private,
                        "created_at": user.created_at
                    }
                    # Only include email for the user's own profile
                    if is_own_profile:
                        user_data["email"] = user.email
                
                result.append(user_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching users: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while searching for users"
            )
    
    async def get_user_by_id(self, user_id: int, current_user_id: Optional[int] = None) -> dict:
        """
        Get a user by ID with proper permission checks.
        
        Args:
            user_id: ID of the user to retrieve
            current_user_id: Optional ID of the current user for permission checks
            
        Returns:
            dict: User data with appropriate fields based on permissions
            
        Raises:
            HTTPException: If user not found or access is denied
        """
        try:
            # Get the requested user
            user = self.db.query(User).filter(
                User.id == user_id,
                User.is_active == True
            ).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Foydalanuvchi topilmadi"
                )
            
            is_own_profile = current_user_id == user_id
            is_private = getattr(user, 'is_private', False)
            
            # Get block relationships in a single query for efficiency
            if current_user_id and not is_own_profile:
                block_relationship = self.db.query(Block).filter(
                    ((Block.blocker_id == user_id) & (Block.blocked_id == current_user_id)) |  # User blocked current user
                    ((Block.blocker_id == current_user_id) & (Block.blocked_id == user_id))  # Current user blocked user
                ).first()
                
                if block_relationship:
                    # Check who blocked whom
                    if block_relationship.blocker_id == user_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Ushbu profilga kirish taqiqlangan"
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Siz ushbu foydalanuvchini bloklagansiz"
                        )
            
            # Prepare base response data
            response_data = {
                "id": user.id,
                "username": user.username,
                "profile_picture": user.profile_picture,
                "is_verified": user.is_verified,
                "created_at": user.created_at,
                "is_private": is_private,
                "is_own_profile": is_own_profile
            }
            
            # Add additional fields based on privacy and ownership
            if is_own_profile or not is_private:
                response_data.update({
                    "full_name": user.full_name,
                    "bio": user.bio,
                })
                
                # Only include email for the user's own profile
                if is_own_profile:
                    response_data["email"] = user.email
            
            return response_data
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Foydalanuvchi ma'lumotlarini olishda xatolik yuz berdi"
            )

    async def update_user(
        self, 
        user_id: int, 
        user_data: UserUpdate
    ) -> Optional[UserResponse]:
        """
        Update a user's information.
        
        Args:
            user_id: ID of the user to update
            user_data: User data to update
            
        Returns:
            Updated UserResponse if successful, None otherwise
        """
        try:
            user = self.db.query(User).filter(
                User.id == user_id,
                User.is_active == True
            ).first()
            
            if not user:
                return None
            
            # Update fields if they are provided
            update_data = user_data.dict(exclude_unset=True)
            
            # Hash password if it's being updated
            if 'password' in update_data and update_data['password']:
                update_data['hashed_password'] = get_password_hash(update_data.pop('password'))
            
            # Update user fields
            for field, value in update_data.items():
                if hasattr(user, field) and field != 'id':
                    setattr(user, field, value)
            
            self.db.commit()
            self.db.refresh(user)
            
            return UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                bio=user.bio,
                profile_picture=user.profile_picture,
                is_verified=user.is_verified,
                created_at=user.created_at
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating the user"
            )
    
    async def delete_user(self, user_id: int) -> bool:
        """
        Soft delete a user by setting is_active to False.
        
        Args:
            user_id: ID of the user to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user = self.db.query(User).filter(
                User.id == user_id,
                User.is_active == True
            ).first()
            
            if not user:
                return False
            
            # Soft delete by setting is_active to False
            user.is_active = False
            self.db.commit()
            
            # TODO: Add cleanup tasks (e.g., revoke tokens, delete files, etc.)
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting user: {str(e)}")
            return False
