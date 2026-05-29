import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './ChatRooms.css';

const ChatRooms = () => {
  const [activeTab, setActiveTab] = useState('list');
  const [rooms, setRooms] = useState([]);
  const [joinCode, setJoinCode] = useState('');
  const [roomName, setRoomName] = useState('');
  const [roomDescription, setRoomDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      navigate('/login');
      return;
    }
    fetchUserRooms();
  }, []);

  const fetchUserRooms = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:5000/api/chat/rooms', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success) {
        setRooms(data.rooms);
      } else {
        setError(data.message || 'Failed to fetch rooms');
      }
    } catch (err) {
      setError('Failed to fetch rooms');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRoom = async (e) => {
    e.preventDefault();
    if (!roomName.trim()) {
      setError('Room name is required');
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:5000/api/chat/rooms', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ name: roomName, description: roomDescription })
      });
      const newRoom = await response.json();

      if (newRoom.success) {
        setRooms([...rooms, newRoom.room]);
        setRoomName('');
        setRoomDescription('');
        setActiveTab('list');
        setError('');
        alert(`Room created! Code: ${newRoom.room.code}`);
      } else {
        setError(newRoom.message || 'Failed to create room');
      }
    } catch (err) {
      setError('Failed to create room');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleJoinRoom = async (e) => {
    e.preventDefault();
    if (!joinCode.trim()) {
      setError('Room code is required');
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:5000/api/chat/rooms/join', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ code: joinCode.toUpperCase() })
      });
      const room = await response.json();

      if (room.success) {
        setJoinCode('');
        setActiveTab('list');
        setError('');
        alert(`Joined room: ${room.room.name}`);
        fetchUserRooms();
      } else {
        setError(room.message || 'Failed to join room');
      }
    } catch (err) {
      setError('Failed to join room');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRoom = async (roomId, roomName) => {
    if (!window.confirm(`Are you sure you want to delete "${roomName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch(`http://localhost:5000/api/chat/rooms/${roomId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await response.json();

      if (data.success) {
        setRooms(rooms.filter(room => room._id !== roomId));
        setError('');
        alert('Room deleted successfully');
      } else {
        setError(data.message || 'Failed to delete room');
      }
    } catch (err) {
      setError('Failed to delete room');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEnterRoom = (roomId) => {
    navigate(`/chat/${roomId}`);
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');

  return (
    <div className="chat-rooms-container">
      <div className="chat-rooms-header">
        <button className="btn-back" onClick={() => navigate('/dashboard')}>← Back</button>
        <h1>Chat Rooms</h1>
        <div className="header-right">
          <span className="user-name">👤 {currentUser.name}</span>
          <button className="btn-logout" onClick={handleLogout}>Logout</button>
        </div>
      </div>

      <div className="chat-rooms-content">
        <div className="tabs">
          <button
            className={`tab-btn ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            My Rooms
          </button>
          <button
            className={`tab-btn ${activeTab === 'join' ? 'active' : ''}`}
            onClick={() => setActiveTab('join')}
          >
            Join Room
          </button>
          <button
            className={`tab-btn ${activeTab === 'create' ? 'active' : ''}`}
            onClick={() => setActiveTab('create')}
          >
            Create Room
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        {activeTab === 'list' && (
          <div className="tab-content">
            <h2>Your Chat Rooms</h2>
            {loading ? (
              <p className="loading">Loading rooms...</p>
            ) : rooms.length === 0 ? (
              <p className="empty-state">No rooms yet. Create or join one!</p>
            ) : (
              <div className="rooms-grid">
                {rooms.map(room => (
                  <div key={room._id} className="room-card">
                    <button
                      className="btn-delete-room"
                      onClick={() => handleDeleteRoom(room._id, room.name)}
                      title="Delete room"
                    >
                      Delete
                    </button>
                    <div className="room-info">
                      <h3>{room.name}</h3>
                      <p>{room.description}</p>
                      <div className="room-meta">
                        <span className="members">👥 {room.members?.length || 0} members</span>
                        {room.creatorId === currentUser.id && (
                          <span className="code-badge">Code: {room.code}</span>
                        )}
                      </div>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleEnterRoom(room._id)}
                    >
                      Enter Room
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'join' && (
          <div className="tab-content">
            <h2>Join a Room</h2>
            <form onSubmit={handleJoinRoom} className="form-container">
              <div className="form-group">
                <label>Room Code</label>
                <input
                  type="text"
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  placeholder="Enter room code (e.g., ABC123)"
                  maxLength="6"
                />
              </div>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? 'Joining...' : 'Join Room'}
              </button>
            </form>
          </div>
        )}

        {activeTab === 'create' && (
          <div className="tab-content">
            <h2>Create a New Room</h2>
            <form onSubmit={handleCreateRoom} className="form-container">
              <div className="form-group">
                <label>Room Name</label>
                <input
                  type="text"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  placeholder="Enter room name"
                  required
                />
              </div>
              <div className="form-group">
                <label>Description (Optional)</label>
                <textarea
                  value={roomDescription}
                  onChange={(e) => setRoomDescription(e.target.value)}
                  placeholder="Enter room description"
                  rows="4"
                />
              </div>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create Room'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatRooms;