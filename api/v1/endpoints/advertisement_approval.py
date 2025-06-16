from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from schemas.advertisement_approval import AdvertisementApproval
from services.advertisement_service import AdvertisementService
from models.user import User
from database import get_db

router = APIRouter(
    prefix="/advertisements",
    tags=["advertisement-approval"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/approve",
    response_model=AdvertisementApproval,
    summary="Approve or reject an advertisement",
    description="Only kaxorovorif6@gmail.com can approve advertisements."
)
async def approve_advertisement(
    approval_data: AdvertisementApproval,
    db: Session = Depends(get_db)
):
    """
    Approve or reject an advertisement.
    
    Only kaxorovorif6@gmail.com can approve advertisements.
    
    - **ad_id**: ID of the advertisement to approve/reject
    - **user_id**: ID of the user approving the advertisement
    - **is_approved**: Whether to approve (True) or reject (False) the advertisement
    """
    try:
        # Get the user by ID
        user = db.query(User).filter(User.id == approval_data.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {approval_data.user_id} not found"
            )

        # Check if the user has the correct email
        if user.email != "kaxorovorif6@gmail.com":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only kaxorovorif6@gmail.com can approve advertisements"
            )

        service = AdvertisementService(db)
        return await service.approve_advertisement(
            ad_id=approval_data.ad_id,
            approver_email=user.email,
            is_approved=approval_data.is_approved
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving advertisement: {str(e)}"
        )
