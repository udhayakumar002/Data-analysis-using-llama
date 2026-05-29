{{ ... }}

# Collections
users_collection = db['users'] if db is not None else None
rooms_collection = db['rooms'] if db is not None else None
messages_collection = db['messages'] if db is not None else None

{{ ... }}

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not db is not None:
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
    """Signup endpoint"""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if db is not None:
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

{{ ... }}
