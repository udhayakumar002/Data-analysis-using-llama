# Revenue Lens - Complete Setup Guide

This guide will help you set up and run the entire Revenue Lens application with chat functionality.

## Project Structure

```
revenue_lens/
├── frontend/              # React frontend application
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.js
│   │   │   ├── Signup.js
│   │   │   ├── Dashboard.js
│   │   │   ├── ChatRooms.js
│   │   │   ├── Chat.js
│   │   │   └── *.css
│   │   ├── services/
│   │   │   ├── api.js
│   │   │   └── websocket.js
│   │   ├── App.js
│   │   └── App.css
│   ├── package.json
│   ├── .env.example
│   └── README.md
└── backend/               # Flask backend server
    ├── app.py
    ├── requirements.txt
    ├── .env.example
    └── README.md
```

## Prerequisites

- **Node.js** (v14+) and npm
- **Python** (3.8+) and pip
- **Git** (optional)

## Backend Setup

### Step 1: Navigate to backend directory

```bash
cd revenue_lens/backend
```

### Step 2: Create virtual environment

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Create .env file

```bash
cp .env.example .env
```

Edit `.env` and update values if needed (defaults work for development).

### Step 5: Run the backend server

```bash
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
 * WebSocket connected
```

**Keep this terminal open!**

## Frontend Setup

### Step 1: Open a new terminal and navigate to frontend

```bash
cd revenue_lens/frontend
```

### Step 2: Install dependencies

```bash
npm install
```

If you get any warnings, they're usually safe to ignore for development.

### Step 3: Create .env file

```bash
cp .env.example .env
```

The default values should work:
```
REACT_APP_API_URL=http://localhost:5000/api
REACT_APP_WS_URL=ws://localhost:5000/ws
REACT_APP_ENV=development
```

### Step 4: Start the development server

```bash
npm start
```

The app will automatically open at `http://localhost:3000`

## Running the Application

### Terminal 1 - Backend
```bash
cd revenue_lens/backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python app.py
```

### Terminal 2 - Frontend
```bash
cd revenue_lens/frontend
npm start
```

## Testing the Chat Feature

1. **Open the app** at `http://localhost:3000`
2. **Login** (use any email/password for demo)
3. **Navigate to Dashboard**
4. **Click the chat icon** (💬) at the bottom right
5. **Create a Room** or **Join a Room** with a code
6. **Enter the Room** and start chatting!

## Features Overview

### Authentication
- Login with email and password
- Sign up for new account
- Protected routes

### Dashboard
- File upload for analysis
- Report generation
- Chat icon button

### Chat Rooms
- Create new chat rooms
- Join existing rooms with code
- View all your rooms
- Room descriptions and member count

### Real-time Chat
- Send and receive messages instantly
- See active members in room
- System notifications for joins/leaves
- Connection status indicator

## API Endpoints

### Authentication
- `POST /api/auth/login`
- `POST /api/auth/signup`

### Chat
- `GET /api/chat/rooms` - Get user's rooms
- `POST /api/chat/rooms` - Create room
- `GET /api/chat/rooms/<id>` - Get room details
- `POST /api/chat/rooms/join` - Join room by code

### WebSocket Events
- `join_room` - Join a chat room
- `send_message` - Send message
- `leave_room` - Leave room
- `message` - Receive message
- `user_joined` - User joined notification
- `user_left` - User left notification

## Troubleshooting

### Backend won't start
- Check if port 5000 is in use: `lsof -i :5000` (macOS/Linux)
- Change port in `app.py` if needed
- Ensure Python 3.8+ is installed

### Frontend won't connect to backend
- Verify backend is running on `http://localhost:5000`
- Check `.env` file has correct `REACT_APP_API_URL`
- Clear browser cache and refresh

### WebSocket connection fails
- Ensure backend is running
- Check `REACT_APP_WS_URL` in `.env`
- Browser console should show connection attempts

### Port 3000 already in use
```bash
# Kill process on port 3000 (macOS/Linux)
lsof -i :3000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or change port in frontend
PORT=3001 npm start
```

## Development Tips

### Hot Reload
- Frontend automatically reloads on file changes
- Backend requires manual restart for Python changes

### Debugging
- Open browser DevTools (F12) to see console logs
- Backend logs appear in terminal

### Mock Data
- Login/signup accepts any email/password
- Chat rooms are stored in memory (lost on restart)
- For production, implement database

## Next Steps

1. **Connect to Database**: Replace in-memory storage with PostgreSQL/MongoDB
2. **Implement Authentication**: Add JWT tokens and proper user management
3. **Add Message Persistence**: Store messages in database
4. **Enhance UI**: Add more features and polish
5. **Deploy**: Use Docker, Heroku, AWS, etc.

## File Upload & Report Generation

These features are ready for backend implementation:

**File Upload:**
```javascript
// Frontend: src/pages/Dashboard.js
// Backend: app.py - /api/files/upload endpoint
```

**Report Generation:**
```javascript
// Frontend: src/pages/Dashboard.js
// Backend: app.py - /api/reports/generate endpoint
```

## Production Checklist

- [ ] Set `FLASK_ENV=production` in backend
- [ ] Update `SECRET_KEY` in backend `.env`
- [ ] Implement database
- [ ] Add JWT authentication
- [ ] Enable HTTPS
- [ ] Set up error logging
- [ ] Configure CORS properly
- [ ] Add rate limiting
- [ ] Test all features
- [ ] Deploy to hosting service

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review backend README.md
3. Check frontend console for errors
4. Verify all services are running

## License

MIT
