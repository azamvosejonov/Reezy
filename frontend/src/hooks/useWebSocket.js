import { useEffect, useRef, useCallback } from 'react';
import { webSocketService } from '../services/websocket.service';

export function useWebSocket() {
  const messageHandlers = useRef(new Map());

  // Register message handlers
  const onMessage = useCallback((type, handler) => {
    // Remove existing handler if it exists
    const cleanup = webSocketService.onMessage(type, handler);
    
    // Store cleanup function
    if (!messageHandlers.current.has(type)) {
      messageHandlers.current.set(type, new Set());
    }
    messageHandlers.current.get(type).add(cleanup);
    
    // Return cleanup function
    return cleanup;
  }, []);

  // Unregister all message handlers on unmount
  useEffect(() => {
    return () => {
      // Clean up all registered handlers
      messageHandlers.current.forEach((cleanups, type) => {
        cleanups.forEach(cleanup => cleanup());
      });
      messageHandlers.current.clear();
    };
  }, []);

  // Send message through WebSocket
  const sendMessage = useCallback(async (type, data = {}) => {
    try {
      await webSocketService.sendMessage(type, data);
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(async () => {
    try {
      await webSocketService.connect();
      return true;
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      return false;
    }
  }, []);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    webSocketService.disconnect();
  }, []);

  // Check connection status
  const isConnected = useCallback(() => {
    return webSocketService.isConnected;
  }, []);

  // Call-specific methods
  const joinCall = useCallback(async (callId) => {
    return sendMessage('join_call', { call_id: callId });
  }, [sendMessage]);

  const leaveCall = useCallback(async (callId) => {
    return sendMessage('leave_call', { call_id: callId });
  }, [sendMessage]);

  const sendSignal = useCallback(async (receiverId, callId, signal) => {
    return sendMessage('call_signal', {
      receiver_id: receiverId,
      call_id: callId,
      signal
    });
  }, [sendMessage]);

  return {
    onMessage,
    sendMessage,
    connect,
    disconnect,
    isConnected,
    joinCall,
    leaveCall,
    sendSignal
  };
}

// Hook specifically for call functionality
export function useCallWebSocket(callId, callbacks = {}) {
  const {
    onSignal,
    onUserJoined,
    onUserLeft,
    onCallEnded,
    onError
  } = callbacks;

  const { onMessage, ...rest } = useWebSocket();

  // Register call-specific message handlers
  useEffect(() => {
    const cleanupFns = [];

    if (onSignal) {
      cleanupFns.push(
        onMessage('call_signal', (message) => {
          if (message.call_id === callId) {
            onSignal(message);
          }
        })
      );
    }

    if (onUserJoined) {
      cleanupFns.push(
        onMessage('user_joined', (message) => {
          if (message.call_id === callId) {
            onUserJoined(message.user_id);
          }
        })
      );
    }

    if (onUserLeft) {
      cleanupFns.push(
        onMessage('user_left', (message) => {
          if (message.call_id === callId) {
            onUserLeft(message.user_id);
          }
        })
      );
    }

    if (onCallEnded) {
      cleanupFns.push(
        onMessage('call_ended', (message) => {
          if (message.call_id === callId) {
            onCallEnded(message);
          }
        })
      );
    }

    if (onError) {
      cleanupFns.push(
        onMessage('error', (message) => {
          if (!callId || message.call_id === callId) {
            onError(message);
          }
        })
      );
    }

    // Join the call when the component mounts
    if (callId) {
      rest.joinCall(callId).catch(error => {
        console.error('Failed to join call:', error);
        onError?.({ error: 'Failed to join call' });
      });
    }

    // Clean up on unmount
    return () => {
      cleanupFns.forEach(cleanup => cleanup?.());
      if (callId) {
        rest.leaveCall(callId).catch(console.error);
      }
    };
  }, [callId, onSignal, onUserJoined, onUserLeft, onCallEnded, onError, onMessage, rest]);

  return rest;
}
