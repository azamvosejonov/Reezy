import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCallWebSocket } from '../../hooks/useWebSocket';
import { useAuth } from '../../contexts/AuthContext';
import { callService } from '../../services/api';
import { Button, Card, Container, Row, Col, Spinner, Alert } from 'react-bootstrap';

const CallInterface = () => {
  const { callId } = useParams();
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  
  const [call, setCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState({});
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [participants, setParticipants] = useState([]);
  
  const localVideoRef = useRef();
  const remoteVideosRef = useRef({});
  const peerConnections = useRef({});
  
  // Fetch call details
  useEffect(() => {
    const fetchCallDetails = async () => {
      try {
        const callData = await callService.getCall(callId);
        setCall(callData);
        setParticipants(callData.participants || []);
      } catch (err) {
        setError('Failed to load call details');
        console.error('Error fetching call details:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchCallDetails();
  }, [callId]);
  
  // Handle WebSocket messages
  const handleSignal = async (message) => {
    try {
      const { sender_id, signal } = message;
      
      if (signal.type === 'offer') {
        await handleOffer(sender_id, signal);
      } else if (signal.type === 'answer') {
        await handleAnswer(sender_id, signal);
      } else if (signal.type === 'candidate') {
        await handleCandidate(sender_id, signal);
      }
    } catch (err) {
      console.error('Error handling signal:', err);
    }
  };
  
  const handleUserJoined = (userId) => {
    setParticipants(prev => [...prev, { id: userId }]);
    // Initiate peer connection when a new user joins
    createPeerConnection(userId);
  };
  
  const handleUserLeft = (userId) => {
    setParticipants(prev => prev.filter(p => p.id !== userId));
    // Clean up peer connection
    if (peerConnections.current[userId]) {
      peerConnections.current[userId].close();
      delete peerConnections.current[userId];
    }
    
    // Remove remote stream
    setRemoteStreams(prev => {
      const newStreams = { ...prev };
      delete newStreams[userId];
      return newStreams;
    });
  };
  
  const handleCallEnded = () => {
    // Clean up and navigate away
    endCall();
    navigate('/calls');
  };
  
  const handleError = (error) => {
    setError(error.message || 'An error occurred during the call');
    console.error('Call error:', error);
  };
  
  // Initialize WebSocket connection
  const { sendSignal } = useCallWebSocket(callId, {
    onSignal: handleSignal,
    onUserJoined: handleUserJoined,
    onUserLeft: handleUserLeft,
    onCallEnded: handleCallEnded,
    onError: handleError
  });
  
  // Initialize media stream
  useEffect(() => {
    const initMedia = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: true
        });
        
        setLocalStream(stream);
        
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }
        
        // Initialize peer connections for existing participants
        participants.forEach(participant => {
          if (participant.id !== currentUser.id) {
            createPeerConnection(participant.id);
          }
        });
        
      } catch (err) {
        setError('Could not access camera/microphone');
        console.error('Error accessing media devices:', err);
      }
    };
    
    initMedia();
    
    // Clean up on unmount
    return () => {
      if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
      }
      
      // Close all peer connections
      Object.values(peerConnections.current).forEach(pc => pc.close());
      peerConnections.current = {};
    };
  }, []);
  
  // Create a new peer connection
  const createPeerConnection = (userId) => {
    if (peerConnections.current[userId]) {
      return; // Connection already exists
    }
    
    const configuration = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        // Add your TURN server configuration here if needed
      ]
    };
    
    const pc = new RTCPeerConnection(configuration);
    peerConnections.current[userId] = pc;
    
    // Add local stream to peer connection
    if (localStream) {
      localStream.getTracks().forEach(track => {
        pc.addTrack(track, localStream);
      });
    }
    
    // Handle remote stream
    pc.ontrack = (event) => {
      setRemoteStreams(prev => ({
        ...prev,
        [userId]: event.streams[0]
      }));
    };
    
    // Handle ICE candidates
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal(userId, callId, {
          type: 'candidate',
          candidate: event.candidate
        });
      }
    };
    
    // Handle connection state changes
    pc.onconnectionstatechange = () => {
      console.log(`Connection state with ${userId}:`, pc.connectionState);
      
      if (pc.connectionState === 'disconnected' || 
          pc.connectionState === 'failed' || 
          pc.connectionState === 'closed') {
        handleUserLeft(userId);
      }
    };
    
    // If we're the one initiating the call, create an offer
    if (call?.caller_id === currentUser.id) {
      createAndSendOffer(userId);
    }
  };
  
  // Create and send an offer
  const createAndSendOffer = async (userId) => {
    try {
      const pc = peerConnections.current[userId];
      if (!pc) return;
      
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      
      sendSignal(userId, callId, {
        type: 'offer',
        sdp: pc.localDescription
      });
    } catch (err) {
      console.error('Error creating/sending offer:', err);
    }
  };
  
  // Handle incoming offer
  const handleOffer = async (userId, offer) => {
    try {
      const pc = peerConnections.current[userId] || createPeerConnection(userId);
      
      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      
      sendSignal(userId, callId, {
        type: 'answer',
        sdp: pc.localDescription
      });
    } catch (err) {
      console.error('Error handling offer:', err);
    }
  };
  
  // Handle incoming answer
  const handleAnswer = async (userId, answer) => {
    try {
      const pc = peerConnections.current[userId];
      if (!pc) return;
      
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err) {
      console.error('Error handling answer:', err);
    }
  };
  
  // Handle ICE candidates
  const handleCandidate = async (userId, candidate) => {
    try {
      const pc = peerConnections.current[userId];
      if (!pc) return;
      
      await pc.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (err) {
      console.error('Error handling ICE candidate:', err);
    }
  };
  
  // Toggle mute
  const toggleMute = () => {
    if (localStream) {
      localStream.getAudioTracks().forEach(track => {
        track.enabled = !track.enabled;
      });
      setIsMuted(!isMuted);
    }
  };
  
  // Toggle video
  const toggleVideo = () => {
    if (localStream) {
      localStream.getVideoTracks().forEach(track => {
        track.enabled = !track.enabled;
      });
      setIsVideoOff(!isVideoOff);
    }
  };
  
  // End the call
  const endCall = async () => {
    try {
      await callService.endCall(callId);
    } catch (err) {
      console.error('Error ending call:', err);
    } finally {
      // Clean up
      if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
      }
      
      Object.values(peerConnections.current).forEach(pc => pc.close());
      peerConnections.current = {};
      
      navigate('/calls');
    }
  };
  
  if (loading) {
    return (
      <Container className="d-flex justify-content-center align-items-center" style={{ height: '100vh' }}>
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading call...</span>
        </Spinner>
      </Container>
    );
  }
  
  if (error) {
    return (
      <Container className="mt-5">
        <Alert variant="danger">
          {error}
          <div className="mt-2">
            <Button variant="outline-danger" onClick={() => window.location.reload()}>
              Try Again
            </Button>
          </div>
        </Alert>
      </Container>
    );
  }
  
  return (
    <Container fluid className="p-0" style={{ height: '100vh', overflow: 'hidden' }}>
      <Row className="g-0 h-100">
        {/* Main video area */}
        <Col md={9} className="bg-dark position-relative" style={{ height: '100%' }}>
          <div className="position-absolute w-100 h-100 d-flex flex-wrap justify-content-center align-items-center">
            {participants.length === 0 ? (
              <div className="text-white text-center">
                <h3>Waiting for participants to join...</h3>
              </div>
            ) : (
              participants.map(participant => (
                <div 
                  key={participant.id} 
                  className="position-relative m-2"
                  style={{ width: '45%', height: '45%' }}
                >
                  <video
                    ref={ref => remoteVideosRef.current[participant.id] = ref}
                    autoPlay
                    playsInline
                    className="h-100 w-100 bg-secondary"
                    style={{ objectFit: 'cover' }}
                  />
                  <div className="position-absolute bottom-0 start-0 text-white p-2 bg-dark bg-opacity-50 w-100">
                    {participant.id === currentUser.id ? 'You' : `User ${participant.id}`}
                  </div>
                </div>
              ))
            )}
          </div>
        </Col>
        
        {/* Sidebar */}
        <Col md={3} className="bg-light p-3" style={{ height: '100%', overflowY: 'auto' }}>
          <h4>Call Details</h4>
          <hr />
          
          <div className="mb-4">
            <h6>Participants ({participants.length})</h6>
            <div className="list-group">
              {participants.map(participant => (
                <div key={participant.id} className="list-group-item">
                  {participant.id === currentUser.id ? 'You' : `User ${participant.id}`}
                </div>
              ))}
            </div>
          </div>
          
          <div className="mb-4">
            <h6>Your Video</h6>
            <div className="position-relative" style={{ height: '150px' }}>
              <video
                ref={localVideoRef}
                autoPlay
                muted
                playsInline
                className="w-100 h-100 bg-secondary"
                style={{ objectFit: 'cover' }}
              />
            </div>
          </div>
          
          <div className="d-flex justify-content-center gap-2 mb-3">
            <Button 
              variant={isMuted ? 'danger' : 'outline-secondary'}
              onClick={toggleMute}
              title={isMuted ? 'Unmute' : 'Mute'}
            >
              <i className={`bi bi-mic${isMuted ? '-mute' : ''}-fill`}></i>
            </Button>
            
            <Button 
              variant={isVideoOff ? 'danger' : 'outline-secondary'}
              onClick={toggleVideo}
              title={isVideoOff ? 'Turn on video' : 'Turn off video'}
            >
              <i className={`bi bi-camera-video${isVideoOff ? '-off' : ''}-fill`}></i>
            </Button>
            
            <Button 
              variant="danger" 
              onClick={endCall}
              title="End call"
            >
              <i className="bi bi-telephone-x-fill"></i>
            </Button>
          </div>
          
          <div className="mt-auto">
            <Button 
              variant="outline-secondary" 
              size="sm" 
              className="w-100"
              onClick={() => navigator.clipboard.writeText(window.location.href)}
            >
              <i className="bi bi-link-45deg me-2"></i>
              Copy call link
            </Button>
          </div>
        </Col>
      </Row>
    </Container>
  );
};

export default CallInterface;
