from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage (replace with database in production)
rooms = {}
users = {}
messages = {}

# ==================== Authentication Routes ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    # TODO: Implement actual authentication with database
    if email and password:
        return jsonify({
            'success': True,
            'token': 'mock-jwt-token-' + str(uuid.uuid4()),
            'user': {
                'id': str(uuid.uuid4()),
                'email': email,
                'name': email.split('@')[0]
            }
        }), 200
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Signup endpoint"""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    # TODO: Implement actual user registration with database
    if name and email and password:
        return jsonify({
            'success': True,
            'token': 'mock-jwt-token-' + str(uuid.uuid4()),
            'user': {
                'id': str(uuid.uuid4()),
                'email': email,
                'name': name
            }
        }), 201
    
    return jsonify({'success': False, 'message': 'Invalid data'}), 400


# ==================== File Upload Routes ====================

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """File upload endpoint"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    # TODO: Process file and return transformed data
    file_id = str(uuid.uuid4())
    return jsonify({
        'success': True,
        'fileId': file_id,
        'fileName': file.filename,
        'message': 'File uploaded successfully'
    }), 200


@app.route('/api/files/<file_id>/transform', methods=['GET'])
def get_transformed_data(file_id):
    """Get transformed file data"""
    # TODO: Implement actual data transformation
    return jsonify({
        'success': True,
        'fileId': file_id,
        'transformedData': {
            'rows': 100,
            'columns': 10,
            'summary': 'Data transformation completed'
        }
    }), 200


# ==================== Report Routes ====================

@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """Generate report"""
    # TODO: Implement actual report generation
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
    """Get report details"""
    # TODO: Fetch report from database
    return jsonify({
        'success': True,
        'reportId': report_id,
        'status': 'completed',
        'data': {}
    }), 200


@app.route('/api/reports', methods=['GET'])
def get_all_reports():
    """Get all reports"""
    # TODO: Fetch all reports from database
    return jsonify({
        'success': True,
        'reports': []
    }), 200


# ==================== Chat Routes ====================

@app.route('/api/chat/rooms', methods=['GET'])
def get_user_rooms():
    """Get all rooms for the user"""
    # TODO: Get user from auth token and fetch their rooms
    return jsonify({
        'success': True,
        'rooms': list(rooms.values())
    }), 200


@app.route('/api/chat/rooms', methods=['POST'])
def create_room():
    """Create a new chat room"""
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'message': 'Room name is required'}), 400
    
    room_id = str(uuid.uuid4())
    room_code = ''.join(str(uuid.uuid4()).split('-')[0:2]).upper()[:6]
    
    rooms[room_id] = {
        'id': room_id,
        'name': name,
        'description': description,
        'code': room_code,
        'members': [],
        'createdAt': datetime.now().isoformat()
    }
    
    messages[room_id] = []
    
    return jsonify({
        'success': True,
        'room': rooms[room_id]
    }), 201


@app.route('/api/chat/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    """Get room details"""
    if room_id not in rooms:
        return jsonify({'success': False, 'message': 'Room not found'}), 404
    
    return jsonify({
        'success': True,
        'room': rooms[room_id],
        'messages': messages.get(room_id, [])
    }), 200


@app.route('/api/chat/rooms/join', methods=['POST'])
def join_room_by_code():
    """Join a room using room code"""
    data = request.get_json()
    code = data.get('code', '').upper()
    
    # Find room by code
    room = next((r for r in rooms.values() if r['code'] == code), None)
    
    if not room:
        return jsonify({'success': False, 'message': 'Room not found'}), 404
    
    return jsonify({
        'success': True,
        'room': room
    }), 200


# ==================== WebSocket Events ====================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    user_id = request.args.get('userId')
    users[user_id] = {
        'id': user_id,
        'name': f'User-{user_id[:8]}',
        'socketId': request.sid,
        'connectedAt': datetime.now().isoformat()
    }
    print(f'User {user_id} connected')
    emit('connected', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    # Find and remove user
    for user_id, user in list(users.items()):
        if user['socketId'] == request.sid:
            del users[user_id]
            print(f'User {user_id} disconnected')
            break


@socketio.on('join_room')
def handle_join_room(data):
    """Handle user joining a room"""
    room_id = data.get('roomId')
    user_id = request.args.get('userId')
    
    if room_id not in rooms:
        emit('error', {'message': 'Room not found'})
        return
    
    join_room(room_id)
    
    # Add user to room
    if user_id in users:
        user = users[user_id]
        if user not in rooms[room_id]['members']:
            rooms[room_id]['members'].append(user)
        
        # Notify others
        emit('user_joined', {
            'user': user,
            'roomId': room_id
        }, room=room_id)
        
        # Send room users to all in room
        emit('room_users', {
            'users': rooms[room_id]['members']
        }, room=room_id)


@socketio.on('leave_room')
def handle_leave_room(data):
    """Handle user leaving a room"""
    room_id = data.get('roomId')
    user_id = request.args.get('userId')
    
    leave_room(room_id)
    
    if room_id in rooms and user_id in users:
        user = users[user_id]
        rooms[room_id]['members'] = [m for m in rooms[room_id]['members'] if m['id'] != user_id]
        
        emit('user_left', {
            'userId': user_id,
            'userName': user['name'],
            'roomId': room_id
        }, room=room_id)


@socketio.on('send_message')
def handle_send_message(data):
    """Handle message sending"""
    room_id = data.get('roomId')
    text = data.get('text')
    sender = data.get('sender')
    
    if not room_id or not text:
        emit('error', {'message': 'Invalid message data'})
        return
    
    message = {
        'id': str(uuid.uuid4()),
        'roomId': room_id,
        'sender': sender,
        'text': text,
        'timestamp': datetime.now().isoformat()
    }
    
    # Store message
    if room_id not in messages:
        messages[room_id] = []
    messages[room_id].append(message)
    
    # Broadcast to room
    emit('message', message, room=room_id)


# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500


# ==================== Health Check ====================

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
