from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from calls.schemas.call import (
    Call, CallCreate, CallUpdate,
    CallTokenResponse, CallSignal, CallWithParticipants
)
from calls.services.call_service import CallService
from calls.services.websocket_manager import connection_manager
from models import User
from database import get_db
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/initiate")
async def initiate_call(
    call_data: CallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initiate a new call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use authenticated user's ID as the caller
        call = await call_service.initiate_call(current_user.id, call_data)
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{call_id}/answer", response_model=Call)
async def answer_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Answer an incoming call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use authenticated user's ID to answer the call
        call = call_service.answer_call(call_id, current_user.id)
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{call_id}/reject", response_model=Call)
async def reject_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reject an incoming call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use authenticated user's ID to reject the call
        call = call_service.reject_call(call_id, current_user.id)
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{call_id}/end", response_model=Call)
async def end_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    End an ongoing call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use authenticated user's ID to end the call
        call = call_service.end_call(call_id, current_user.id)
        # Notify other participants
        await connection_manager.notify_call_status_change(
            call_id,
            "call_ended",
            initiator_id=current_user.id
        )
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history", response_model=List[Call])
async def get_call_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get call history without authentication.
    Returns all calls (consider adding filters if needed).
    """
    call_service = CallService(db)
    # Get calls where the user was either caller or participant
    return call_service.get_user_calls(current_user.id, limit, offset)

@router.get("/missed", response_model=List[Call])
async def get_missed_calls(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get missed calls without authentication.
    Returns all missed calls (consider adding filters if needed).
    """
    call_service = CallService(db)
    # Get calls where the user was receiver and call was missed (rejected or ended without answer)
    calls = call_service.get_user_calls(current_user.id, limit, offset)

    # Filter missed calls (where user was receiver and call was rejected or ended without answer)
    missed_calls = []
    for call in calls:
        if (call.receiver_id == current_user.id and
            (call.status == "rejected" or (call.status == "completed" and not call.start_time))):
            missed_calls.append(call)

    return missed_calls

@router.get("/{call_id}", response_model=CallWithParticipants)
async def get_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get call details without authentication.
    """
    call_service = CallService(db)
    try:
        # Get call and check if user is a participant
        call = call_service.get_call(call_id, current_user.id)
        
        # Check if user is either caller or receiver
        if call.caller_id != current_user.id and call.receiver_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not a participant in this call")
            
        return call
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    WebSocket endpoint for real-time call signaling.
    No authentication required.
    """
    # Accept WebSocket connection with authentication
    await websocket.accept()
    
    # Use authenticated user's ID
    user_id = current_user.id
    
    # Accept the WebSocket connection
    await websocket.accept()
    
    # Connect the user to the WebSocket manager
    await connection_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive and handle messages
            data = await websocket.receive_json()
            await connection_manager.handle_message(db, user_id, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(user_id)
        raise

@router.post("/{call_id}/signal", status_code=status.HTTP_200_OK)
async def send_signal(
    call_id: int,
    signal_data: CallSignal,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a WebRTC signal to other call participants without authentication.
    """
    call_service = CallService(db)
    try:
        # Get call and check if user is a participant
        call = call_service.get_call(call_id, current_user.id)
        
        # Check if user is either caller or receiver
        if call.caller_id != current_user.id and call.receiver_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not a participant in this call")
            
        # Forward the signal to the connection manager
        await connection_manager.handle_message(db, current_user.id, {
            "type": "call_signal",
            "call_id": call_id,
            "receiver_id": signal_data.receiver_id,
            "signal": signal_data.data
        })
        
        return {"status": "signal_sent"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{call_id}/participants", response_model=List[int])
async def get_call_participants(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of user IDs currently in a call without authentication.
    """
    call_service = CallService(db)
    try:
        # Get call and check if user is a participant
        call = call_service.get_call(call_id, current_user.id)
        
        # Check if user is either caller or receiver
        if call.caller_id != current_user.id and call.receiver_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not a participant in this call")
            
        # Get call participants
        participants = call_service.get_call_participants(call_id)
        return participants
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
