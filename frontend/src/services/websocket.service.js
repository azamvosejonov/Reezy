import { getAccessToken } from './auth.service';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.messageHandlers = new Map();
    this.connectionPromise = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1 second delay
    this.isConnected = false;
  }

  async connect() {
    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      try {
        // Use wss:// for production, ws:// for development
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsUrl = `${protocol}${window.location.host}/api/calls/ws`;
        
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
          console.log('WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          resolve();
        };

        this.socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.socket.onclose = (event) => {
          console.log('WebSocket disconnected', event);
          this.isConnected = false;
          this.connectionPromise = null;
          this.handleReconnect();
        };

        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.isConnected = false;
          this.connectionPromise = null;
          reject(error);
        };
      } catch (error) {
        console.error('WebSocket connection error:', error);
        reject(error);
      }
    });

    return this.connectionPromise;
  }

  handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    console.log(`Attempting to reconnect in ${delay}ms...`);
    
    setTimeout(() => {
      this.connect().catch(console.error);
    }, delay);
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.isConnected = false;
      this.connectionPromise = null;
    }
  }

  handleMessage(message) {
    const { type } = message;
    const handlers = this.messageHandlers.get(type) || [];
    
    handlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error(`Error in handler for message type ${type}:`, error);
      }
    });
  }

  onMessage(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type).push(handler);
    
    // Return unsubscribe function
    return () => this.offMessage(type, handler);
  }

  offMessage(type, handler) {
    if (!this.messageHandlers.has(type)) return;
    
    const handlers = this.messageHandlers.get(type);
    const index = handlers.indexOf(handler);
    if (index !== -1) {
      handlers.splice(index, 1);
    }
    
    if (handlers.length === 0) {
      this.messageHandlers.delete(type);
    }
  }

  async sendMessage(type, data = {}) {
    if (!this.isConnected) {
      await this.connect();
    }
    
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ type, ...data });
      this.socket.send(message);
    } else {
      console.error('WebSocket is not connected');
      throw new Error('WebSocket is not connected');
    }
  }

  // Specific call-related methods
  async joinCall(callId) {
    await this.sendMessage('join_call', { call_id: callId });
  }

  async leaveCall(callId) {
    await this.sendMessage('leave_call', { call_id: callId });
  }

  async sendSignal(receiverId, callId, signal) {
    await this.sendMessage('call_signal', {
      receiver_id: receiverId,
      call_id: callId,
      signal
    });
  }
}

// Singleton instance
export const webSocketService = new WebSocketService();

// Auto-connect when imported
webSocketService.connect().catch(console.error);

// Export for direct usage
export default webSocketService;
