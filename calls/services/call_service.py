from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
import uuid
import json

from calls.models.call import Call, CallParticipant, CallStatus, CallType
from calls.schemas.call import CallCreate, CallUpdate, CallParticipantCreate
from models import User
from services.block_service import BlockService


class CallService:
    """Service for handling call-related operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.block_service = BlockService(db)
    
    async def initiate_call(self, caller_id: int, call_data: CallCreate) -> Call:
        """
        Initiate a new call.
        """
        # Check if receiver exists
        receiver = self.db.query(User).filter(User.id == call_data.receiver_id).first()
        if not receiver:
            raise ValueError("Receiver not found")
            
        # Check if receiver is already in a call
        active_call = self.db.query(Call).filter(
            (Call.receiver_id == call_data.receiver_id) &
            (Call.status == "ringing")
        ).first()
        
        if active_call:
            raise ValueError("The receiver is already in a call")
            
        # Create new call
        call = Call(
            caller_id=caller_id,
            receiver_id=call_data.receiver_id,
            call_type=call_data.call_type,
            status=CallStatus.RINGING,
            call_sid=str(uuid.uuid4())
        )
        
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        
        # Add caller as participant
        self._add_participant(call.id, caller_id, is_caller=True)
        
        return call
    
    def answer_call(self, call_id: int, user_id: int) -> Call:
        """
        Answer an incoming call.
        
        Args:
            call_id: ID of the call to answer
            user_id: ID of the user answering the call
            
        Returns:
            The updated call object
        """
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if not call:
            raise ValueError("Call not found")
            
        if call.receiver_id != user_id:
            raise ValueError("You are not the intended receiver of this call")
            
        if call.status != CallStatus.RINGING:
            raise ValueError("Call is not in a state that can be answered")
            
        call.status = CallStatus.IN_PROGRESS
        call.start_time = datetime.utcnow()
        
        # Add receiver as participant
        self._add_participant(call.id, user_id, is_caller=False)
        
        self.db.commit()
        self.db.refresh(call)
        return call
    
    def end_call(self, call_id: int, user_id: int) -> Call:
        """
        End an ongoing call.
        
        Args:
            call_id: ID of the call to end
            user_id: ID of the user ending the call
            
        Returns:
            The ended call object
        """
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if not call:
            raise ValueError("Call not found")
            
        if user_id not in [call.caller_id, call.receiver_id]:
            raise ValueError("You are not a participant in this call")
            
        if call.status == CallStatus.COMPLETED:
            return call
            
        call.status = CallStatus.COMPLETED
        call.end_time = datetime.utcnow()
        
        if call.start_time:
            call.duration = int((call.end_time - call.start_time).total_seconds())
        
        # Update participant leave time
        participant = self.db.query(CallParticipant).filter(
            CallParticipant.call_id == call_id,
            CallParticipant.user_id == user_id
        ).first()
        
        if participant:
            participant.left_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(call)
        return call
    
    def reject_call(self, call_id: int, user_id: int) -> Call:
        """
        Reject an incoming or ongoing call.
        
        Args:
            call_id: ID of the call to reject
            user_id: ID of the user rejecting the call
            
        Returns:
            The updated call object
            
        Raises:
            ValueError: If call not found or user is not authorized
        """
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if not call:
            raise ValueError("Call not found")
            
        # Allow both caller and receiver to reject the call
        if user_id not in [call.caller_id, call.receiver_id]:
            raise ValueError("You are not a participant in this call")
            
        # If call is already completed, just return it
        if call.status == CallStatus.COMPLETED:
            return call
            
        # If call is already rejected, return it
        if call.status == CallStatus.REJECTED:
            return call
            
        # Update call status
        call.status = CallStatus.REJECTED
        call.end_time = datetime.utcnow()
        
        # Calculate duration if call was in progress
        if call.start_time and not call.duration:
            call.duration = int((call.end_time - call.start_time).total_seconds())
        
        # Ensure user is added as a participant and mark as left
        participant = self.db.query(CallParticipant).filter(
            CallParticipant.call_id == call_id,
            CallParticipant.user_id == user_id
        ).first()
        
        if not participant:
            participant = self._add_participant(call.id, user_id, is_caller=(user_id == call.caller_id))
            
        participant.left_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(call)
        return call
    
    def get_call(self, call_id: int, user_id: Optional[int] = None) -> Call:
        """
        Get call details by ID without access restrictions.
        
        Args:
            call_id: ID of the call to retrieve
            user_id: Optional user ID for backward compatibility
            
        Returns:
            The call object with participants
            
        Raises:
            ValueError: If call is not found
        """
        call = self.db.query(Call).filter(
            Call.id == call_id
        ).options(
            joinedload(Call.participants)
            .joinedload(CallParticipant.user)
        ).first()

    def get_user_calls(self, user_id: int, limit: int = 20, offset: int = 0) -> List[Call]:
        """
        Get calls where the user was either caller or participant.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of calls to return
            offset: Number of calls to skip
            
        Returns:
            List of calls where the user was a participant
        """
        return self.db.query(Call).filter(
            or_(
                Call.caller_id == user_id,
                Call.receiver_id == user_id
            )
        ).order_by(Call.created_at.desc()).limit(limit).offset(offset).all()
        
        if not call:
            raise ValueError("Call not found")
            
        return call
    
    def get_all_calls(self, limit: int = 20, offset: int = 0) -> List[Call]:
        """
        Get all calls with pagination.
        
        Args:
            limit: Maximum number of calls to return
            offset: Number of calls to skip
            
        Returns:
            List of call objects
        """
        return self.db.query(Call).order_by(
            Call.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def get_all_missed_calls(self, limit: int = 20, offset: int = 0) -> List[Call]:
        """
        Get all missed calls with pagination.
        
        Args:
            limit: Maximum number of calls to return
            offset: Number of calls to skip
            
        Returns:
            List of missed call objects
        """
        return self.db.query(Call).filter(
            Call.status == CallStatus.MISSED
        ).order_by(
            Call.created_at.desc()
        ).offset(offset).limit(limit).all()
        
    def get_user_calls(self, user_id: int, limit: int = 20, offset: int = 0) -> List[Call]:
        """
        Get call history for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of calls to return
            offset: Number of calls to skip
            
        Returns:
            List of call objects
        """
        return self.db.query(Call).filter(
            or_(
                Call.caller_id == user_id,
                Call.receiver_id == user_id
            )
        ).order_by(
            Call.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def update_call_participant(
        self, 
        call_id: int, 
        user_id: int, 
        update_data: Dict[str, Any]
    ) -> CallParticipant:
        """
        Update a call participant's status.
        
        Args:
            call_id: ID of the call
            user_id: ID of the participant to update
            update_data: Fields to update
            
        Returns:
            The updated participant object
        """
        participant = self.db.query(CallParticipant).filter(
            CallParticipant.call_id == call_id,
            CallParticipant.user_id == user_id
        ).first()
        
        if not participant:
            raise ValueError("Participant not found in this call")
            
        for key, value in update_data.items():
            setattr(participant, key, value)
            
        self.db.commit()
        self.db.refresh(participant)
        return participant
    
    def _add_participant(self, call_id: int, user_id: int, is_caller: bool) -> CallParticipant:
        """
        Add a participant to a call.
        
        Args:
            call_id: ID of the call
            user_id: ID of the user to add
            is_caller: Whether the user is the caller
            
        Returns:
            The created participant object
        """
        # Check if participant already exists
        participant = self.db.query(CallParticipant).filter(
            CallParticipant.call_id == call_id,
            CallParticipant.user_id == user_id
        ).first()
        
        if participant:
            return participant
            
        participant = CallParticipant(
            call_id=call_id,
            user_id=user_id,
            is_muted=False,
            is_video_on=False,
            joined_at=datetime.utcnow()
        )
        
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant
    
    def get_active_calls(self, user_id: int) -> List[Call]:
        """
        Get active calls for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of active call objects
        """
        return self.db.query(Call).filter(
            or_(
                Call.caller_id == user_id,
                Call.receiver_id == user_id
            ),
            Call.status == CallStatus.IN_PROGRESS
        ).all()
    
    def get_missed_calls(self, user_id: int, limit: int = 20, offset: int = 0) -> List[Call]:
        """
        Get missed calls for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of calls to return
            offset: Number of calls to skip
            
        Returns:
            List of missed call objects
        """
        return self.db.query(Call).filter(
            Call.receiver_id == user_id,
            Call.status == CallStatus.MISSED
        ).order_by(
            Call.start_time.desc()
        ).offset(offset).limit(limit).all()
