# Revenue Lens Backend

A Flask-based backend server with WebSocket support for real-time chat functionality and MongoDB persistence.

## Features

- **Authentication**: JWT-based login/signup with unique usernames
- **Group Chat**: Real-time chat rooms with message persistence
- **Private Messaging**: Direct messages between users with username tagging
- **MongoDB Integration**: All messages and user data persisted in MongoDB
- **WebSocket Support**: Real-time message delivery
- **User Management**: Unique username validation and user search
- **Room Management**: Create, join, and manage chat rooms with unique codes

## Setup

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone the repository** (if applicable)

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Create a .env file** (copy from .env.example):
   ```bash
   cp .env.example .env
   ```

6. **Update .env with your configuration** (optional for development)

### Running the Server

```bash
python app.py
```

The server will start on `http://localhost:5000`

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login user
- `POST /api/auth/signup` - Register new user

### File Management
- `POST /api/files/upload` - Upload a file
- `GET /api/files/<file_id>/transform` - Get transformed file data

### Reports
- `POST /api/reports/generate` - Generate a new report
- `GET /api/reports/<report_id>` - Get report details
- `GET /api/reports` - Get all reports

### Chat Rooms
- `GET /api/chat/rooms` - Get all user's rooms
- `POST /api/chat/rooms` - Create a new room
- `GET /api/chat/rooms/<room_id>` - Get room details
- `POST /api/chat/rooms/join` - Join a room by code

## WebSocket Events

### Client → Server
- `connect` - Establish WebSocket connection
- `join_room` - Join a chat room
- `leave_room` - Leave a chat room
- `send_message` - Send a message to a room

### Server → Client
- `connected` - Connection established
- `message` - New message received
- `user_joined` - User joined the room
- `user_left` - User left the room
- `room_users` - List of users in room
- `error` - Error occurred

## Example WebSocket Usage

```javascript
// Connect
const socket = io('http://localhost:5000', {
  query: { userId: 'user-123' }
});

// Join room
socket.emit('join_room', { roomId: 'room-456' });

// Send message
socket.emit('send_message', {
  roomId: 'room-456',
  text: 'Hello!',
  sender: 'John'
});

// Listen for messages
socket.on('message', (data) => {
  console.log(`${data.sender}: ${data.text}`);
});
```

## Project Structure

```
backend/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
└── README.md          # This file
```

## Notes

- This is a development server with in-memory storage
- For production, implement:
  - Database (PostgreSQL, MongoDB, etc.)
  - Authentication with JWT tokens
  - Message persistence
  - User management
  - Error logging and monitoring

## Troubleshooting

### Port already in use
Change the port in `app.py`:
```python
socketio.run(app, debug=True, host='0.0.0.0', port=5001)
```

### CORS errors
Update `CORS_ORIGINS` in `.env` file

### WebSocket connection issues
Ensure the frontend is connecting to the correct WebSocket URL

## License

MIT
