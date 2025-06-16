import json
import logging
from typing import Dict, Set, Optional, List, Any
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from calls.services.call_service import CallService
from calls.models.call import Call, CallStatus

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # call_id -> Set[user_id]
        self.active_calls: Dict[int, Set[int]] = {}
        # user_id -> call_id
        self.user_call_map: Dict[int, int] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Handle new WebSocket connection."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected")
    
    def disconnect(self, user_id: int):
        """Handle WebSocket disconnection."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            
        # Clean up call state if user was in a call
        if user_id in self.user_call_map:
            call_id = self.user_call_map[user_id]
            if call_id in self.active_calls:
                self.active_calls[call_id].discard(user_id)
                if not self.active_calls[call_id]:
                    del self.active_calls[call_id]
            del self.user_call_map[user_id]
            
        logger.info(f"User {user_id} disconnected")
    
    async def handle_message(self, db: Session, user_id: int, data: dict):
        """Handle incoming WebSocket message."""
        message_type = data.get("type")
        
        if message_type == "call_signal":
            await self._handle_call_signal(db, user_id, data)
        elif message_type == "join_call":
            await self._handle_join_call(db, user_id, data)
        elif message_type == "leave_call":
            await self._handle_leave_call(db, user_id, data)
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    async def _handle_call_signal(self, db: Session, sender_id: int, data: dict):
        """Handle WebRTC signaling messages between clients."""
        call_id = data.get("call_id")
        receiver_id = data.get("receiver_id")
        signal = data.get("signal", {})
        
        if not call_id or not receiver_id:
            logger.warning("Missing call_id or receiver_id in call_signal")
            return
        
        # Verify sender is part of the call
        call_service = CallService(db)
        try:
            call = call_service.get_call(call_id, sender_id)
        except ValueError:
            logger.warning(f"User {sender_id} not authorized for call {call_id}")
            return
        
        # Verify receiver is part of the call
        if receiver_id not in [call.caller_id, call.receiver_id]:
            logger.warning(f"Receiver {receiver_id} not part of call {call_id}")
            return
        
        # Forward the signal to the receiver
        await self._send_to_user(receiver_id, {
            "type": "call_signal",
            "call_id": call_id,
            "sender_id": sender_id,
            "signal": signal
        })
    
    async def _handle_join_call(self, db: Session, user_id: int, data: dict):
        """Handle a user joining a call."""
        call_id = data.get("call_id")
        if not call_id:
            logger.warning("Missing call_id in join_call")
            return
        
        call_service = CallService(db)
        try:
            call = call_service.get_call(call_id, user_id)
            
            # Add user to the call
            if call_id not in self.active_calls:
                self.active_calls[call_id] = set()
            self.active_calls[call_id].add(user_id)
            self.user_call_map[user_id] = call_id
            
            # Notify other participants
            for participant_id in self.active_calls[call_id]:
                if participant_id != user_id:
                    await self._send_to_user(participant_id, {
                        "type": "user_joined",
                        "call_id": call_id,
                        "user_id": user_id
                    })
        except ValueError:
            logger.warning(f"User {user_id} not authorized to join call {call_id}")
    
    async def _handle_leave_call(self, db: Session, user_id: int, data: dict):
        """Handle a user leaving a call."""
        call_id = data.get("call_id")
        if not call_id:
            logger.warning("Missing call_id in leave_call")
            return
        
        # Remove user from call state
        if call_id in self.active_calls and user_id in self.active_calls[call_id]:
            self.active_calls[call_id].discard(user_id)
            if not self.active_calls[call_id]:
                del self.active_calls[call_id]
        
        if user_id in self.user_call_map:
            del self.user_call_map[user_id]
        
        # Notify other participants
        if call_id in self.active_calls:
            for participant_id in self.active_calls[call_id]:
                await self._send_to_user(participant_id, {
                    "type": "user_left",
                    "call_id": call_id,
                    "user_id": user_id
                })
    
    async def _send_to_user(self, user_id: int, message: dict):
        """Send a message to a specific user."""
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                self.disconnect(user_id)
    
    async def notify_call_status_change(
        self, 
        call_id: int, 
        status: str,
        initiator_id: Optional[int] = None
    ):
        """Notify all participants of a call status change."""
        if call_id not in self.active_calls:
            return
            
        for user_id in self.active_calls[call_id]:
            if user_id != initiator_id:  # Don't notify the user who initiated the change
                await self._send_to_user(user_id, {
                    "type": "call_status_changed",
                    "call_id": call_id,
                    "status": status
                })
    
    def get_call_participants(self, call_id: int) -> List[int]:
        """Get list of user IDs currently in a call."""
        return list(self.active_calls.get(call_id, set()))

# Global instance of the connection manager
connection_manager = ConnectionManager()
