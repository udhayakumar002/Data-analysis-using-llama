# MongoDB Setup Guide for Revenue Lens

This guide will help you set up MongoDB and migrate from the in-memory backend to the MongoDB-backed backend.

## Prerequisites

- MongoDB installed locally or MongoDB Atlas account (cloud)
- Python 3.8+
- Backend dependencies installed

## Option 1: Local MongoDB Installation

### Windows

1. **Download MongoDB Community Edition**
   - Visit: https://www.mongodb.com/try/download/community
   - Download the Windows installer

2. **Install MongoDB**
   - Run the installer
   - Choose "Install MongoDB as a Service"
   - Default installation path: `C:\Program Files\MongoDB\Server\`

3. **Start MongoDB Service**
   ```bash
   # MongoDB should start automatically
   # Or manually start it:
   net start MongoDB
   ```

4. **Verify Installation**
   ```bash
   mongosh
   # You should see the MongoDB shell prompt
   ```

### macOS

```bash
# Using Homebrew
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

### Linux (Ubuntu/Debian)

```bash
# Add MongoDB repository
curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

# Install
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl start mongod
```

## Option 2: MongoDB Atlas (Cloud)

1. **Create Account**
   - Go to: https://www.mongodb.com/cloud/atlas
   - Sign up for free account

2. **Create Cluster**
   - Click "Create a Deployment"
   - Choose "Free" tier
   - Select region closest to you
   - Click "Create Cluster"

3. **Get Connection String**
   - Click "Connect"
   - Choose "Drivers"
   - Copy the connection string
   - Replace `<password>` with your database password

## Backend Migration

### Step 1: Install MongoDB Driver

```bash
cd backend
pip install pymongo==4.4.1
```

### Step 2: Update .env File

Create `.env` file in backend directory:

**For Local MongoDB:**
```
MONGODB_URI=mongodb://localhost:27017/revenue_lens
MONGODB_DB_NAME=revenue_lens
```

**For MongoDB Atlas:**
```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/revenue_lens?retryWrites=true&w=majority
MONGODB_DB_NAME=revenue_lens
```

### Step 3: Replace app.py

The new MongoDB-integrated backend is in `app_mongodb.py`:

```bash
# Backup old app
mv app.py app_old.py

# Use new MongoDB version
mv app_mongodb.py app.py
```

### Step 4: Update Chat Handlers

The chat routes and WebSocket handlers are now in `chat_handlers.py`. Update `app.py` to include:

```python
from chat_handlers import setup_chat_routes, setup_websocket_handlers

# After creating collections, add:
collections = {
    'rooms': rooms_collection,
    'messages': messages_collection
}

setup_chat_routes(app, collections, active_users)
setup_websocket_handlers(socketio, collections, active_users)
```

### Step 5: Start Backend

```bash
python app.py
```

You should see:
```
✓ Connected to MongoDB
==================================================
Revenue Lens Backend Server
==================================================
Environment: development
Database: mongodb://localhost:27017/revenue_lens
==================================================
```

## Database Schema

### Users Collection
```json
{
  "_id": ObjectId,
  "email": "user@example.com",
  "name": "John Doe",
  "createdAt": ISODate
}
```

### Rooms Collection
```json
{
  "_id": ObjectId,
  "name": "General",
  "description": "General discussion",
  "code": "ABC123",
  "creatorId": "user-id",
  "members": ["user-id-1", "user-id-2"],
  "createdAt": ISODate,
  "updatedAt": ISODate
}
```

### Messages Collection
```json
{
  "_id": ObjectId,
  "roomId": "room-id",
  "sender": "John Doe",
  "text": "Hello everyone!",
  "timestamp": ISODate
}
```

## Verify MongoDB Connection

### Using MongoDB Shell

```bash
# Connect to MongoDB
mongosh

# Show databases
show dbs

# Use revenue_lens database
use revenue_lens

# Show collections
show collections

# View rooms
db.rooms.find()

# View messages
db.messages.find()

# View users
db.users.find()
```

## Troubleshooting

### MongoDB Connection Failed

**Error:** `Connection refused`

**Solution:**
- Ensure MongoDB service is running
- Check MongoDB URI in `.env`
- For local: `mongodb://localhost:27017/revenue_lens`
- For Atlas: Verify connection string and IP whitelist

### Database Not Found

**Error:** `database not found`

**Solution:**
- MongoDB creates database automatically on first write
- Create a room to initialize database
- Check database name in `.env`

### Authentication Failed (Atlas)

**Error:** `authentication failed`

**Solution:**
- Verify username and password in connection string
- Check IP whitelist in MongoDB Atlas
- Add your IP: https://cloud.mongodb.com/v2

### Port Already in Use

**Error:** `Address already in use`

**Solution:**
- Change port in `.env`: `PORT=5001`
- Or kill process: `lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9`

## Data Persistence Features

### Rooms
- ✅ Persist across server restarts
- ✅ Track creator ID
- ✅ Store room code for joining
- ✅ Maintain member list

### Messages
- ✅ Persist all messages
- ✅ Retrieve message history
- ✅ Timestamp tracking
- ✅ Sender information

### Users
- ✅ Store user profiles
- ✅ Track creation date
- ✅ Email-based lookup

## Next Steps

1. **Indexes**: Add MongoDB indexes for better performance
   ```javascript
   db.rooms.createIndex({ "code": 1 })
   db.messages.createIndex({ "roomId": 1, "timestamp": 1 })
   db.users.createIndex({ "email": 1 })
   ```

2. **Backups**: Set up MongoDB backups
   - Use MongoDB Atlas automated backups
   - Or use `mongodump` for local backups

3. **Authentication**: Implement proper user authentication
   - Add password hashing (bcrypt)
   - Implement JWT tokens
   - Add user roles and permissions

4. **Monitoring**: Set up monitoring
   - MongoDB Atlas monitoring
   - Application logging
   - Error tracking

## Production Checklist

- [ ] MongoDB Atlas cluster created
- [ ] Connection string configured
- [ ] IP whitelist updated
- [ ] Database backups enabled
- [ ] Indexes created
- [ ] Authentication implemented
- [ ] Error logging configured
- [ ] Performance monitoring enabled

## Support

For MongoDB help:
- Official Docs: https://docs.mongodb.com/
- MongoDB Atlas: https://www.mongodb.com/cloud/atlas
- Community: https://www.mongodb.com/community/forum
