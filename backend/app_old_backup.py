from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/revenue_lens')
MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'revenue_lens')

try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DB_NAME]
    print("✓ Connected to MongoDB")
except Exception as e:
    print(f"✗ Failed to connect to MongoDB: {e}")
    db = None

users_collection = db['users'] if db is not None else None
rooms_collection = db['rooms'] if db is not None else None
messages_collection = db['messages'] if db is not None else None

active_users = {}

def serialize_doc(doc):
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc

def serialize_docs(docs):
    return [serialize_doc(doc) for doc in docs]

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    if email and password:
        user = users_collection.find_one({'email': email})
        if not user:
            user = {
                '_id': ObjectId(),
                'email': email,
                'name': email.split('@')[0],
                'createdAt': datetime.now()
            }
            users_collection.insert_one(user)
        
        return jsonify({
            'success': True,
            'token': 'mock-jwt-token-' + str(uuid.uuid4()),
            'user': {
                'id': str(user['_id']),
                'email': user['email'],
                'name': user['name']
            }
        }), 200
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    if name and email and password:
        existing_user = users_collection.find_one({'email': email})
        if existing_user:
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        user = {
            '_id': ObjectId(),
            'email': email,
            'name': name,
            'createdAt': datetime.now()
        }
        users_collection.insert_one(user)
        
        return jsonify({
            'success': True,
            'token': 'mock-jwt-token-' + str(uuid.uuid4()),
            'user': {
                'id': str(user['_id']),
                'email': user['email'],
                'name': user['name']
            }
        }), 201
    
    return jsonify({'success': False, 'message': 'Invalid data'}), 400

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    file_id = str(uuid.uuid4())
    return jsonify({
        'success': True,
        'fileId': file_id,
        'fileName': file.filename,
        'message': 'File uploaded successfully'
    }), 200

@app.route('/api/files/<file_id>/transform', methods=['GET'])
def get_transformed_data(file_id):
    return jsonify({
        'success': True,
        'fileId': file_id,
        'transformedData': {
            'rows': 100,
            'columns': 10,
            'summary': 'Data transformation completed'
        }
    }), 200

@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    report_id = str(uuid.uuid4())
    return jsonify({
        'success': True,
        'reportId': report_id,
        'status': 'completed',
        'generatedAt': datetime.now().isoformat(),
        'message': 'Report generated successfully'
    }), 200

@app.route('/api/reports/<report_id>', methods=['GET'])
def get_report(report_id):
    return jsonify({
        'success': True,
        'reportId': report_id,
        'status': 'completed',
        'data': {}
    }), 200

@app.route('/api/reports', methods=['GET'])
def get_all_reports():
    return jsonify({
        'success': True,
        'reports': []
    }), 200

@app.route('/api/chat/rooms', methods=['GET'])
def get_user_rooms():
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    rooms = list(rooms_collection.find())
    return jsonify({
        'success': True,
        'rooms': serialize_docs(rooms)
    }), 200

@app.route('/api/chat/rooms', methods=['POST'])
def create_room():
    if db is None:
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
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    try:
        room = rooms_collection.find_one({'_id': ObjectId(room_id)})
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404
        
        messages = list(messages_collection.find({'roomId': room_id}).sort('timestamp', 1))
        
        return jsonify({
            'success': True,
            'room': serialize_doc(room),
            'messages': serialize_docs(messages)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/chat/rooms/join', methods=['POST'])
def join_room_by_code():
    if db is None:
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

@app.route('/health', methods=['GET'])
def health_check():
    db_status = 'connected' if db is not None else 'disconnected'
    return jsonify({
        'status': 'healthy',
        'database': db_status
    }), 200

@socketio.on('connect')
def handle_connect():
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
    for user_id, user in list(active_users.items()):
        if user['socketId'] == request.sid:
            del active_users[user_id]
            print(f'✓ User {user_id} disconnected')
            break

@socketio.on('join_room')
def handle_join_room(data):
    if db is None:
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
    if db is None:
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

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("Revenue Lens Backend Server")
    print("=" * 50)
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Database: {MONGODB_URI}")
    print("=" * 50)
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
