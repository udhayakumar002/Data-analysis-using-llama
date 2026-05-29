import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import io from 'socket.io-client';
import './Chat.css';

const Chat = () => {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [roomInfo, setRoomInfo] = useState(null);
  const [users, setUsers] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSuggestions, setMentionSuggestions] = useState([]);
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(-1);
  const [privateRecipient, setPrivateRecipient] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const socketRef = useRef(null);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      navigate('/login');
      return;
    }
    
    fetchRoomInfo();
    connectSocket();

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, [roomId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchRoomInfo = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(`http://localhost:5000/api/chat/rooms/${roomId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await response.json();
      
      if (data.success) {
        setRoomInfo(data.room);
        setMessages(data.messages || []);
      } else {
        console.error('Failed to fetch room:', data.message);
      }
    } catch (err) {
      console.error('Failed to fetch room info:', err);
    } finally {
      setLoading(false);
    }
  };

  const connectSocket = () => {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const token = localStorage.getItem('authToken');
      
      socketRef.current = io('http://localhost:5000', {
        auth: { token },
        query: { userId: user.id }
      });

      socketRef.current.on('connect', () => {
        console.log('Socket connected');
        setIsConnected(true);
        
        socketRef.current.emit('join_room', { 
          roomId,
          userId: user.id 
        });
      });

      socketRef.current.on('message', (data) => {
        setMessages(prev => [...prev, {
          id: data.id,
          userId: data.userId,
          userName: data.userName,
          text: data.text,
          timestamp: new Date(data.timestamp).toLocaleTimeString()
        }]);
      });

      socketRef.current.on('user_joined', (data) => {
        setMessages(prev => [...prev, {
          id: Date.now(),
          sender: 'System',
          text: `${data.userName} joined the room`,
          timestamp: new Date().toLocaleTimeString(),
          isSystem: true
        }]);
      });

      socketRef.current.on('user_left', (data) => {
        setMessages(prev => [...prev, {
          id: Date.now(),
          sender: 'System',
          text: `${data.userName} left the room`,
          timestamp: new Date().toLocaleTimeString(),
          isSystem: true
        }]);
      });

      socketRef.current.on('room_users', (data) => {
        setUsers(data.users || []);
      });

      socketRef.current.on('disconnect', () => {
        console.log('Socket disconnected');
        setIsConnected(false);
      });

      socketRef.current.on('error', (error) => {
        console.error('Socket error:', error);
      });
    } catch (err) {
      console.error('Socket connection failed:', err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !isConnected) return;

    const user = JSON.parse(localStorage.getItem('user') || '{}');
    
    socketRef.current.emit('send_message', {
      roomId,
      text: inputMessage,
      userId: user.id,
      userName: user.name
    });

    setInputMessage('');
  };

  const handleLeaveRoom = () => {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    socketRef.current.emit('leave_room', { 
      roomId,
      userId: user.id 
    });
    navigate('/chat-rooms');
  };

  if (loading) {
    return <div className="chat-loading">Loading chat room...</div>;
  }

  if (!roomInfo) {
    return <div className="chat-loading">Room not found</div>;
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="header-info">
          <button className="btn-back" onClick={handleLeaveRoom}>← Back</button>
          <div>
            <h1>{roomInfo.name}</h1>
            <p>{roomInfo.description}</p>
          </div>
        </div>
        <div className="connection-status">
          <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      <div className="chat-main">
        <div className="chat-messages">
          <div className="messages-list">
            {messages.length === 0 ? (
              <div className="no-messages">
                <p>No messages yet. Start the conversation!</p>
              </div>
            ) : (
              messages.map(msg => (
                <div
                  key={msg.id}
                  className={`message ${msg.isSystem ? 'system-message' : 'user-message'}`}
                >
                  {!msg.isSystem && (
                    <div className="message-sender">{msg.userName}</div>
                  )}
                  <div className={`message-content ${msg.isSystem ? 'system' : ''}`}>
                    {msg.text}
                  </div>
                  <div className="message-time">{msg.timestamp}</div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="chat-sidebar">
          <div className="users-section">
            <h3>Members ({users.length})</h3>
            <div className="users-list">
              {users.map(user => (
                <div key={user.id} className="user-item">
                  <span className="user-avatar">{user.name?.charAt(0).toUpperCase() || 'U'}</span>
                  <span className="user-name">{user.name || 'Unknown'}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="chat-input-area">
        <form onSubmit={handleSendMessage} className="message-form">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type a message..."
            disabled={!isConnected}
            className="message-input"
          />
          <button
            type="submit"
            disabled={!isConnected || !inputMessage.trim()}
            className="btn btn-send"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
};

export default Chat;
