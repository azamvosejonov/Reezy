import { api } from './api';

const callService = {
  // Initialize a new call
  async initiateCall(calleeId, callType = 'video') {
    try {
      const response = await api.post('/calls/initiate', {
        receiver_id: calleeId,
        call_type: callType
      });
      return response.data;
    } catch (error) {
      console.error('Error initiating call:', error);
      throw error;
    }
  },
  
  // Answer an incoming call
  async answerCall(callId) {
    try {
      const response = await api.post(`/calls/${callId}/answer`);
      return response.data;
    } catch (error) {
      console.error('Error answering call:', error);
      throw error;
    }
  },
  
  // Reject an incoming call
  async rejectCall(callId) {
    try {
      const response = await api.post(`/calls/${callId}/reject`);
      return response.data;
    } catch (error) {
      console.error('Error rejecting call:', error);
      throw error;
    }
  },
  
  // End an ongoing call
  async endCall(callId) {
    try {
      const response = await api.post(`/calls/${callId}/end`);
      return response.data;
    } catch (error) {
      console.error('Error ending call:', error);
      throw error;
    }
  },
  
  // Get call details
  async getCall(callId) {
    try {
      const response = await api.get(`/calls/${callId}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching call details:', error);
      throw error;
    }
  },
  
  // Get call history
  async getCallHistory(limit = 20, offset = 0) {
    try {
      const response = await api.get('/calls/history', {
        params: { limit, offset }
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching call history:', error);
      throw error;
    }
  },
  
  // Get missed calls
  async getMissedCalls(limit = 20, offset = 0) {
    try {
      const response = await api.get('/calls/missed', {
        params: { limit, offset }
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching missed calls:', error);
      throw error;
    }
  },
  
  // Get call participants
  async getCallParticipants(callId) {
    try {
      const response = await api.get(`/calls/${callId}/participants`);
      return response.data;
    } catch (error) {
      console.error('Error fetching call participants:', error);
      throw error;
    }
  },
  
  // Send a signal to a call participant
  async sendSignal(callId, receiverId, signal) {
    try {
      const response = await api.post(`/calls/${callId}/signal`, {
        receiver_id: receiverId,
        signal: signal
      });
      return response.data;
    } catch (error) {
      console.error('Error sending signal:', error);
      throw error;
    }
  }
};

export default callService;
