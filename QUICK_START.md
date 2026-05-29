# Quick Start - MongoDB Integration

## TL;DR - Get Running in 5 Minutes

### 1. Install MongoDB (Windows)
```bash
# Download from: https://www.mongodb.com/try/download/community
# Run installer, choose "Install as Service"
# Verify: mongosh
```

### 2. Backend Setup
```bash
cd backend
pip install pymongo==4.4.1
```

### 3. Create .env
```bash
# backend/.env
MONGODB_URI=mongodb://localhost:27017/revenue_lens
MONGODB_DB_NAME=revenue_lens
```

### 4. Switch Backend
```bash
mv app.py app_old.py
mv app_mongodb.py app.py
```

### 5. Run Backend
```bash
python app.py
# Should show: ✓ Connected to MongoDB
```

### 6. Run Frontend (new terminal)
```bash
cd frontend
npm start
```

## What Changed

| Feature | Before | After |
|---------|--------|-------|
| Data Storage | In-memory (lost on restart) | MongoDB (persistent) |
| Rooms | Disappear on refresh | Persist forever |
| Messages | Lost on restart | Saved in database |
| Creator ID | Not tracked | Tracked in DB |
| Chat Icon | Small (60x60) | Large WhatsApp style (70x70) |

## Test It

1. **Create a room** → Refresh page → Room still there ✅
2. **Send message** → Refresh page → Message still there ✅
3. **Click chat icon** → Opens Chat Rooms page ✅

## Verify MongoDB

```bash
# Open MongoDB shell
mongosh

# Check database
use revenue_lens
show collections

# View rooms
db.rooms.find()

# View messages
db.messages.find()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Connection refused` | Start MongoDB: `net start MongoDB` |
| Rooms disappear | Check `.env` file, verify MongoDB running |
| Chat icon not visible | Restart frontend: `npm start` |
| `pymongo not found` | Run: `pip install pymongo==4.4.1` |

## Files Changed

```
✅ frontend/src/pages/ChatIcon.css (UPDATED)
✅ backend/app_mongodb.py (NEW)
✅ backend/chat_handlers.py (NEW)
✅ backend/requirements.txt (UPDATED)
✅ backend/.env.example (UPDATED)
```

## Next: MongoDB Atlas (Cloud)

Want to use cloud MongoDB instead of local?

1. Go to: https://www.mongodb.com/cloud/atlas
2. Create free account
3. Create cluster
4. Get connection string
5. Update `.env`:
   ```
   MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/revenue_lens
   ```

## Commands Reference

```bash
# Start MongoDB (Windows)
net start MongoDB

# Start MongoDB (macOS)
brew services start mongodb-community

# Connect to MongoDB
mongosh

# Backend
cd backend && python app.py

# Frontend
cd frontend && npm start

# Install dependencies
pip install -r requirements.txt
npm install
```

## Architecture

```
Frontend (React)
    ↓
API Routes (Flask)
    ↓
WebSocket (Socket.io)
    ↓
MongoDB (Persistent Storage)
```

## Features Working Now

- ✅ Create chat rooms
- ✅ Join rooms with code
- ✅ Send/receive messages
- ✅ See active members
- ✅ Room persistence
- ✅ Message history
- ✅ Creator tracking
- ✅ WhatsApp-style chat icon

## Need Help?

- **Setup Issues?** → See `MONGODB_SETUP.md`
- **General Setup?** → See `SETUP_GUIDE.md`
- **API Docs?** → See `backend/README.md`
- **All Updates?** → See `UPDATES_SUMMARY.md`

---

**Ready to go!** 🚀
