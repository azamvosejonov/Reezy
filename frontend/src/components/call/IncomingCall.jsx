import React, { useState, useEffect } from 'react';
import { Modal, Button, Spinner } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { callService } from '../../services/call.service';
import { useAuth } from '../../contexts/AuthContext';
import { webSocketService } from '../../services/websocket.service';

const IncomingCall = ({ call, onDismiss }) => {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const [isAnswering, setIsAnswering] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [caller, setCaller] = useState(null);
  const [error, setError] = useState('');
  
  // Extract caller information
  useEffect(() => {
    if (call) {
      // In a real app, you would fetch the caller's details here
      setCaller({
        id: call.caller_id,
        name: `User ${call.caller_id}`,
        avatar: `https://ui-avatars.com/api/?name=User+${call.caller_id}&background=random`
      });
      
      // Auto-reject after 30 seconds if not answered
      const timeoutId = setTimeout(() => {
        if (!isAnswering) {
          handleReject();
        }
      }, 30000);
      
      return () => clearTimeout(timeoutId);
    }
  }, [call]);
  
  const handleAnswer = async () => {
    if (!call || isAnswering) return;
    
    try {
      setIsAnswering(true);
      setError('');
      
      // Answer the call
      await callService.answerCall(call.id);
      
      // Navigate to the call interface
      navigate(`/calls/${call.id}`);
      
      // Notify parent to close the notification
      onDismiss();
    } catch (error) {
      console.error('Error answering call:', error);
      setError('Failed to answer the call. Please try again.');
      setIsAnswering(false);
    }
  };
  
  const handleReject = async () => {
    if (!call || isRejecting) return;
    
    try {
      setIsRejecting(true);
      setError('');
      
      // Reject the call
      await callService.rejectCall(call.id);
      
      // Notify parent to close the notification
      onDismiss();
    } catch (error) {
      console.error('Error rejecting call:', error);
      setError('Failed to reject the call. Please try again.');
      setIsRejecting(false);
    }
  };
  
  if (!call || !caller) return null;
  
  return (
    <Modal 
      show={!!call} 
      onHide={handleReject}
      centered
      backdrop="static"
      keyboard={false}
      className="incoming-call-modal"
    >
      <Modal.Body className="text-center p-4">
        <div className="mb-4">
          <img 
            src={caller.avatar} 
            alt={caller.name}
            className="rounded-circle mb-3"
            style={{ width: '120px', height: '120px', objectFit: 'cover' }}
          />
          <h4>Incoming {call.call_type} Call</h4>
          <p className="text-muted">{caller.name} is calling you</p>
        </div>
        
        {error && (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        )}
        
        <div className="d-flex justify-content-center gap-3">
          <Button 
            variant="danger" 
            size="lg" 
            className="rounded-circle"
            style={{ width: '60px', height: '60px' }}
            onClick={handleReject}
            disabled={isRejecting || isAnswering}
          >
            {isRejecting ? (
              <Spinner animation="border" size="sm" />
            ) : (
              <i className="bi bi-telephone-x-fill fs-4"></i>
            )}
          </Button>
          
          <Button 
            variant="success" 
            size="lg" 
            className="rounded-circle"
            style={{ width: '60px', height: '60px' }}
            onClick={handleAnswer}
            disabled={isAnswering || isRejecting}
          >
            {isAnswering ? (
              <Spinner animation="border" size="sm" />
            ) : (
              <i className="bi bi-telephone-fill fs-4"></i>
            )}
          </Button>
        </div>
      </Modal.Body>
    </Modal>
  );
};

export default IncomingCall;
