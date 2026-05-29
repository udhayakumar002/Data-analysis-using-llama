# This file contains chat-related routes and WebSocket handlers
# Import this in app_mongodb.py after defining socketio

from flask import request, jsonify
from flask_socketio import emit, join_room, leave_room
from bson.objectid import ObjectId
from datetime import datetime
import uuid

# These will be injected from main app
db = None
rooms_collection = None
messages_collection = None
active_users = {}

# ==================== Chat Routes ====================

def setup_chat_routes(app, collections, users_dict):
    """Setup chat routes"""
    global db, rooms_collection, messages_collection, active_users
    rooms_collection = collections['rooms']
    messages_collection = collections['messages']
    active_users = users_dict
    
    @app.route('/api/chat/rooms', methods=['GET'])
    def get_user_rooms():
        """Get all rooms"""
        if not rooms_collection:
            return jsonify({'success': False, 'message': 'Database not connected'}), 500
        
        rooms = list(rooms_collection.find())
        return jsonify({
            'success': True,
            'rooms': [serialize_doc(r) for r in rooms]
        }), 200
    
    @app.route('/api/chat/rooms', methods=['POST'])
    def create_room():
        """Create a new chat room"""
        if not rooms_collection:
            return jsonify({'success': False, 'message': 'Database not connected'}), 500
        
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        creator_id = data.get('creatorId', 'anonymous')
        
        if not name:
            return jsonify({'success': False, 'message': 'Room name is required'}), 400
        
        room_code = ''.join(str(uuid.uuid4()).split('-')[0:2]).upper()[:6]
        
        room = {
            'name': name,
            'description': description,
            'code': room_code,
            'creatorId': creator_id,
            'members': [creator_id],
            'createdAt': datetime.now(),
            'updatedAt': datetime.now()
        }
        
        result = rooms_collection.insert_one(room)
        room['_id'] = str(result.inserted_id)
        
        return jsonify({
            'success': True,
            'room': serialize_doc(room)
        }), 201
    
    @app.route('/api/chat/rooms/<room_id>', methods=['GET'])
    def get_room(room_id):
        """Get room details"""
        if not rooms_collection:
            return jsonify({'success': False, 'message': 'Database not connected'}), 500
        
        try:
            room = rooms_collection.find_one({'_id': ObjectId(room_id)})
            if not room:
                return jsonify({'success': False, 'message': 'Room not found'}), 404
            
            messages = list(messages_collection.find({'roomId': room_id}).sort('timestamp', 1))
            
            return jsonify({
                'success': True,
                'room': serialize_doc(room),
                'messages': [serialize_doc(m) for m in messages]
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
    
    @app.route('/api/chat/rooms/join', methods=['POST'])
    def join_room_by_code():
        """Join a room using room code"""
        if not rooms_collection:
            return jsonify({'success': False, 'message': 'Database not connected'}), 500
        
        data = request.get_json()
        code = data.get('code', '').upper()
        user_id = data.get('userId', 'anonymous')
        
        room = rooms_collection.find_one({'code': code})
        
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404
        
        if user_id not in room.get('members', []):
            rooms_collection.update_one(
                {'_id': room['_id']},
                {'$push': {'members': user_id}, '$set': {'updatedAt': datetime.now()}}
            )
        
        return jsonify({
            'success': True,
            'room': serialize_doc(room)
        }), 200


def setup_websocket_handlers(socketio, collections, users_dict):
    """Setup WebSocket handlers"""
    global rooms_collection, messages_collection, active_users
    rooms_collection = collections['rooms']
    messages_collection = collections['messages']
    active_users = users_dict
    
    @socketio.on('connect')
    def handle_connect():
        """Handle WebSocket connection"""
        user_id = request.args.get('userId', 'anonymous-' + str(uuid.uuid4())[:8])
        active_users[user_id] = {
            'id': user_id,
            'name': f'User-{user_id[:8]}',
            'socketId': request.sid,
            'connectedAt': datetime.now().isoformat()
        }
        print(f'✓ User {user_id} connected')
        emit('connected', {'message': 'Connected to server'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle WebSocket disconnection"""
        for user_id, user in list(active_users.items()):
            if user['socketId'] == request.sid:
                del active_users[user_id]
                print(f'✓ User {user_id} disconnected')
                break
    
    @socketio.on('join_room')
    def handle_join_room(data):
        """Handle user joining a room"""
        if not rooms_collection:
            emit('error', {'message': 'Database not connected'})
            return
        
        room_id = data.get('roomId')
        user_id = request.args.get('userId', 'anonymous')
        
        try:
            room = rooms_collection.find_one({'_id': ObjectId(room_id)})
            if not room:
                emit('error', {'message': 'Room not found'})
                return
            
            join_room(room_id)
            
            if user_id not in room.get('members', []):
                rooms_collection.update_one(
                    {'_id': ObjectId(room_id)},
                    {'$push': {'members': user_id}, '$set': {'updatedAt': datetime.now()}}
                )
            
            updated_room = rooms_collection.find_one({'_id': ObjectId(room_id)})
            
            if user_id in active_users:
                user = active_users[user_id]
                emit('user_joined', {
                    'user': user,
                    'roomId': room_id
                }, room=room_id)
            
            emit('room_users', {
                'users': [active_users.get(uid, {'id': uid, 'name': f'User-{uid[:8]}'}) 
                         for uid in updated_room.get('members', [])]
            }, room=room_id)
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('leave_room')
    def handle_leave_room(data):
        """Handle user leaving a room"""
        room_id = data.get('roomId')
        user_id = request.args.get('userId', 'anonymous')
        
        try:
            leave_room(room_id)
            
            if user_id in active_users:
                user = active_users[user_id]
                emit('user_left', {
                    'userId': user_id,
                    'userName': user['name'],
                    'roomId': room_id
                }, room=room_id)
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle message sending"""
        if not messages_collection:
            emit('error', {'message': 'Database not connected'})
            return
        
        room_id = data.get('roomId')
        text = data.get('text')
        sender = data.get('sender')
        
        if not room_id or not text:
            emit('error', {'message': 'Invalid message data'})
            return
        
        try:
            message = {
                'roomId': room_id,
                'sender': sender,
                'text': text,
                'timestamp': datetime.now()
            }
            
            result = messages_collection.insert_one(message)
            
            emit('message', {
                'id': str(result.inserted_id),
                'roomId': room_id,
                'sender': sender,
                'text': text,
                'timestamp': datetime.now().isoformat()
            }, room=room_id)
        except Exception as e:
            emit('error', {'message': str(e)})


def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc
