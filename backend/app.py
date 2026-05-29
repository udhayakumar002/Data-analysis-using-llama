from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from rag_service import rag_service
from flask_socketio import SocketIO, emit, join_room, leave_room
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from llm_agent import run_langgraph_analytics
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import os
import json
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import pandas as pd
import io
import math
import time
import traceback
import random
import base64
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
import shutil
import zipfile
from typing import List

# PDF report imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Optional: for writing to MySQL via pandas
try:
    from sqlalchemy import create_engine
    import pymysql  # required by SQLAlchemy URL
    SQLALCHEMY_AVAILABLE = True
except Exception:
    SQLALCHEMY_AVAILABLE = False

load_dotenv(".env.example")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/revenue_lens')
MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'revenue_lens')

# Connect to MongoDB
try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DB_NAME]
    print("✓ Connected to MongoDB")
except Exception as e:
    print(f"✗ Failed to connect to MongoDB: {e}")
    db = None

# Initialize collections AFTER db connection
if db is not None:
    users_collection = db['users']
    rooms_collection = db['rooms']
    messages_collection = db['messages']
    private_messages_collection = db['private_messages']
    otp_collection = db['otps']
    manual_requests_collection = db['manual_requests']
    auto_transforms_collection = db['auto_transforms']
    user_databases_collection = db['user_databases']
    terms_collection = db['terms_and_conditions']
    # after user_databases_collection
    report_history_collection = db['report_history']
    # Create indexes
    try:
        users_collection.create_index('email', unique=True)
        users_collection.create_index('username', unique=True)
        print("✓ Created unique indexes on users.email and users.username")
        
        # Index for efficient private message queries
        private_messages_collection.create_index([('participants', 1), ('timestamp', -1)])
        private_messages_collection.create_index('timestamp', expireAfterSeconds=2592000)  # 30 days TTL
        print("✓ Created indexes on private_messages collection")
    except Exception as e:
        print(f"Note: Index creation: {e}")
else:
    users_collection = None
    rooms_collection = None
    messages_collection = None
    private_messages_collection = None
    otp_collection = None
    manual_requests_collection = None
    auto_transforms_collection = None
    user_databases_collection = None
    terms_collection = None
    report_history_collection = None

active_users = {}

def serialize_doc(doc):
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc

def serialize_docs(docs):
    return [serialize_doc(doc) for doc in docs]

def generate_jwt_token(user_id):
    payload = {
        'user_id': str(user_id),
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except:
        return None

def get_current_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    try:
        token = auth_header.split(' ')[1]
        user_id = verify_jwt_token(token)
        if user_id:
            return users_collection.find_one({'_id': ObjectId(user_id)})
    except:
        pass
    return None

def generate_otp(length: int = 6) -> str:
    return ''.join(str(random.randint(0, 9)) for _ in range(length))

def send_otp_email(recipient_email: str, otp: str) -> None:
    """Send OTP email using basic SMTP settings from environment variables.

    Required env vars (add to your .env):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
    """
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("SMTP_FROM", user)

    if not host or not user or not password or not from_addr:
        print("[WARN] SMTP not configured; skipping real email send. OTP:", otp)
        return

    subject = "Your OTP Code"
    body = f"Your OTP code is: {otp}"

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = recipient_email

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)



@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if db is None or users_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required'}), 400
    
    user = users_collection.find_one({'email': email})
    
    if not user or not check_password_hash(user.get('password', ''), password):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    
    token = generate_jwt_token(user['_id'])
    
    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': str(user['_id']),
            'email': user['email'],
            'name': user['name'],
            'role': user.get('role', 'user')
        }
    }), 200

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if db is None or users_collection is None or otp_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields required'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
    
    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        return jsonify({'success': False, 'message': 'Email already registered'}), 400
    
    base_username = (email or "").split("@")[0]
    username = base_username.lower()

    # By default every new signup is a normal user; you can promote to admin in DB later
    role = 'user'

    # Generate OTP and store temp user data waiting for verification
    otp = generate_otp()
    temp_user = {
        'name': name,
        'email': email,
        'username': username,
        'password': generate_password_hash(password),
        'role': role,
        'createdAt': datetime.now()
    }

    # Upsert OTP record for this email
    otp_doc = {
        'email': email,
        'otp': otp,
        'temp_user': temp_user,
        'createdAt': datetime.now(),
        'expiresAt': datetime.utcnow() + timedelta(minutes=10)
    }
    otp_collection.update_one({'email': email}, {'$set': otp_doc}, upsert=True)

    try:
        send_otp_email(email, otp)
    except Exception as e:
        print('Failed to send OTP email:', str(e))
        return jsonify({'success': False, 'message': 'Failed to send OTP email'}), 500

    return jsonify({
        'success': True,
        'message': 'OTP sent to your email. Please verify to complete signup.'
    }), 200

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if db is None or users_collection is None or otp_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP are required'}), 400

    doc = otp_collection.find_one({'email': email})
    if not doc or doc.get('otp') != otp:
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

    expires_at = doc.get('expiresAt')
    if expires_at and expires_at < datetime.utcnow():
        return jsonify({'success': False, 'message': 'OTP expired'}), 400

    temp_user = doc.get('temp_user') or {}
    if not temp_user:
        return jsonify({'success': False, 'message': 'No pending signup for this email'}), 400

    # Ensure user does not already exist
    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        return jsonify({'success': False, 'message': 'Email already registered'}), 400

    # Create final user
    user = temp_user
    user['_id'] = ObjectId()
    if 'role' not in user:
        user['role'] = 'user'
    users_collection.insert_one(user)

    # Remove OTP record
    otp_collection.delete_one({'email': email})

    token = generate_jwt_token(user['_id'])

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': str(user['_id']),
            'email': user['email'],
            'name': user['name'],
            'role': user.get('role', 'user')
        }
    }), 201

@app.route('/api/chat/rooms', methods=['GET'])
def get_user_rooms():
    if db is None or rooms_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    user_id = str(current_user['_id'])
    rooms = list(rooms_collection.find({'members': user_id}))
    
    return jsonify({
        'success': True,
        'rooms': serialize_docs(rooms)
    }), 200

@app.route('/api/chat/rooms', methods=['POST'])
def create_room():
    if db is None or rooms_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'message': 'Room name is required'}), 400
    
    room_code = ''.join(str(uuid.uuid4()).split('-')[0:2]).upper()[:6]
    creator_id = str(current_user['_id'])
    
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

@app.route('/api/chat/rooms/<room_id>', methods=['DELETE'])
def delete_room(room_id):
    if db is None or rooms_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        room = rooms_collection.find_one({'_id': ObjectId(room_id)})
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404
        
        # Optional: Only allow creator to delete
        # user_id = str(current_user['_id'])
        # if room.get('creatorId') != user_id:
        #     return jsonify({'success': False, 'message': 'Only the room creator can delete this room'}), 403
        
        # Delete all messages in the room
        messages_collection.delete_many({'roomId': room_id})
        
        # Delete the room
        rooms_collection.delete_one({'_id': ObjectId(room_id)})
        
        return jsonify({
            'success': True,
            'message': 'Room deleted successfully'
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/chat/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    if db is None or messages_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        room = rooms_collection.find_one({'_id': ObjectId(room_id)})
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404
        
        user_id = str(current_user['_id'])
        if user_id not in room.get('members', []):
            return jsonify({'success': False, 'message': 'Not a member of this room'}), 403
        
        messages = list(messages_collection.find({'roomId': room_id}).sort('timestamp', 1))
        
        room_data = serialize_doc(room)
        room_data['isCreator'] = room.get('creatorId') == user_id
        
        return jsonify({
            'success': True,
            'room': room_data,
            'messages': serialize_docs(messages)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/chat/rooms/join', methods=['POST'])
def join_room_by_code():
    if db is None or rooms_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    code = data.get('code', '').upper()
    
    room = rooms_collection.find_one({'code': code})
    
    if not room:
        return jsonify({'success': False, 'message': 'Room not found'}), 404
    
    user_id = str(current_user['_id'])
    if user_id not in room.get('members', []):
        rooms_collection.update_one(
            {'_id': room['_id']},
            {'$push': {'members': user_id}, '$set': {'updatedAt': datetime.now()}}
        )
    
    room_data = serialize_doc(room)
    room_data['isCreator'] = room.get('creatorId') == user_id
    
    return jsonify({
        'success': True,
        'room': room_data
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    db_status = 'connected' if db is not None else 'disconnected'
    return jsonify({
        'status': 'healthy',
        'database': db_status
    }), 200

@app.route('/api/legal/terms', methods=['GET'])
def get_terms():
    if db is None or terms_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    try:
        doc = terms_collection.find_one({'is_active': True}, sort=[('effective_date', -1)])
        if not doc:
            return jsonify({'success': False, 'message': 'Terms not found'}), 404

        doc['_id'] = str(doc['_id'])
        return jsonify({'success': True, 'terms': doc}), 200
    except Exception as e:
        print('Error fetching terms:', e)
        return jsonify({'success': False, 'message': 'Failed to load terms'}), 500
@app.route('/api/report-history/my', methods=['GET'])
def list_my_report_history():
    if db is None or report_history_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    user_id = str(current_user['_id'])
    docs = list(report_history_collection.find({'userId': user_id}).sort('generatedAt', -1))
    print(docs)
    return jsonify({'success': True, 'items': serialize_docs(docs)}), 200



# ================= Generate Report API =================
ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}

def _allowed_file(filename: str) -> bool:
    filename = (filename or '').lower()
    return any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS)

@app.route('/api/connect-db', methods=['POST'])
def connect_db():
    data = request.get_json(silent=True) or {}
    host = data.get('host', 'localhost')
    user = data.get('user')
    password = data.get('password', '')
    database_name = data.get('database')
    port = int(data.get('port', 3306))

    if not user or not database_name:
        return jsonify({'success': False, 'error': 'user and database are required'}), 400

    try:
        import mysql.connector
        conn = mysql.connector.connect(host=host, user=user, password=password, database=database_name, port=port)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'schema': {'existing_tables': tables}}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-files', methods=['POST'])
def upload_files():
    try:
        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'error': 'No files provided (expected key "files")'}), 400

        db_cfg_raw = request.form.get('dbConfig')
        db_cfg = None
        if db_cfg_raw:
            try:
                db_cfg = json.loads(db_cfg_raw)
            except Exception:
                return jsonify({'success': False, 'error': 'dbConfig must be valid JSON'}), 400

        # default local MySQL config for admin-side DB
        host = 'localhost'
        root_user = os.environ.get('LOCAL_MYSQL_USER', 'root')
        root_password = os.environ.get('LOCAL_MYSQL_PASSWORD', '')
        port = int(os.environ.get('LOCAL_MYSQL_PORT', 3306))

        # CASE 1: user gave full dbConfig (use their own DB)
        if db_cfg and db_cfg.get('user') and db_cfg.get('database'):
            user = db_cfg['user']
            password = db_cfg.get('password', '')
            database_name = db_cfg['database']

        # CASE 2: no usable dbConfig -> create per-user test DB
        else:
            current_user = get_current_user()
            if not current_user:
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401

            user_id_str = str(current_user['_id'])

            # decide next db name for this user: test01, test02, ...
            if user_databases_collection is None:
                return jsonify({'success': False, 'error': 'Database mapping collection not available'}), 500

            count = user_databases_collection.count_documents({
                'userId': user_id_str,
                'source': 'files',
            })
            index = count + 1
            database_name = f"test{index:02d}"

            import mysql.connector
            try:
                conn = mysql.connector.connect(
                    host=host,
                    user=root_user,
                    password=root_password,
                    port=port,
                )
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
                cursor.close()
                conn.close()
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to create local database: {str(e)}'}), 500

            # store mapping in Mongo so admin can see later
            user_databases_collection.insert_one({
                'userId': user_id_str,
                'dbName': database_name,
                'source': 'files',
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow(),
            })

            # for imports we use local admin MySQL
            user = root_user
            password = root_password

        if not SQLALCHEMY_AVAILABLE:
            return jsonify({'success': False, 'error': 'SQLAlchemy+pymysql is required on server to import data'}), 500

        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database_name}"
        engine = create_engine(url, pool_pre_ping=True)

        processed = 0
        table_errors = {}
        for storage in files:
            filename = secure_filename(storage.filename or '')
            if not filename:
                continue
            if not _allowed_file(filename):
                table_errors[filename] = 'Unsupported file type'
                continue

            table_name = os.path.splitext(os.path.basename(filename))[0]
            try:
                content = storage.read()
                if filename.lower().endswith('.csv'):
                    df = pd.read_csv(io.BytesIO(content))
                else:
                    df = pd.read_excel(io.BytesIO(content))

                df.to_sql(table_name, engine, if_exists='replace', index=False)
                processed += 1
            except Exception as e:
                table_errors[filename] = str(e)
                continue

        if processed == 0:
            return jsonify({
                'success': False,
                'error': 'No valid files imported into MySQL',
                'details': table_errors
            }), 400

        try:
            schema = _fetch_mysql_schema({
                'host': host,
                'user': user,
                'password': password,
                'database': database_name,
                'port': port,
            })
        except Exception as e:
            return jsonify({
                'success': True,
                'warning': f'Imported {processed} files but failed to fetch schema: {str(e)}',
                'processed_files': processed
            }), 200

        return jsonify({
            'success': True,
            'processed_files': processed,
            'schema': schema,
            'errors': table_errors,
            'databaseName': database_name,
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/chat/init', methods=['POST'])
def initialize_rag():
    """Initialize the RAG system."""
    success, message = rag_service.initialize_rag()
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message}), 400

@app.route('/api/chat/ask', methods=['POST'])
def ask_question():
    """Ask a question to the RAG system."""
    data = request.get_json()
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({"error": "Question is required"}), 400
    
    response = rag_service.query(question)
    return jsonify(response)

@app.route('/api/generate-insight', methods=['POST'])
def generate_insight():
    data = request.get_json(silent=True) or {}
    query_text = (data.get('query') or '').strip()
    db_cfg = data.get('dbConfig') or {}

    if not query_text:
        return jsonify({'success': False, 'error': 'query is required'}), 400

    # Decide which DB credentials to use
    source = data.get('source')  # 'user_db' or 'uploaded_files'

    if source == 'uploaded_files':
        # Use local MySQL credentials from environment for the imported test DB
        host = 'localhost'
        user = os.environ.get('LOCAL_MYSQL_USER', 'root')
        password = os.environ.get('LOCAL_MYSQL_PASSWORD', '')
        database_name = data.get('databaseName') or (db_cfg.get('database') if isinstance(db_cfg, dict) else None)
        port = int(os.environ.get('LOCAL_MYSQL_PORT', 3306))
    else:
        # User's own DB
        host = db_cfg.get('host', 'localhost')
        user = db_cfg.get('user')
        password = db_cfg.get('password', '')
        database_name = db_cfg.get('database')
        port = int(db_cfg.get('port', 3306))

    if not user or not database_name:
        return jsonify({'success': False, 'error': 'dbConfig must include user and database'}), 400

    mysql_config = {
        "host": host,
        "user": user,
        "password": password,
        "database": database_name,
        "port": port,
    }

    try:
        result = run_langgraph_analytics(mysql_config, query_text)

        # If the agent returned an explicit error dict, surface it as 500 for the UI
        if isinstance(result, dict) and result.get('error'):
            return jsonify(result), 500

        # Otherwise return the full analytics payload for the frontend
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/summary', methods=['GET'])
def admin_summary():
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    if db is None or users_collection is None or rooms_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    users_cursor = users_collection.find({})
    users_stats = []

    for user in users_cursor:
        user_id_str = str(user.get('_id'))
        chatroom_count = rooms_collection.count_documents({'members': user_id_str})

        # Sum revenue from paid manual requests
        total_revenue = 0.0
        if manual_requests_collection is not None:
            paid_requests = manual_requests_collection.find({
                'userId': user_id_str,
                'paymentStatus': 'paid',
            })
            for req in paid_requests:
                try:
                    total_revenue += float(req.get('bidAmount') or 0)
                except (TypeError, ValueError):
                    pass

        stats = {
            'id': user_id_str,
            'name': user.get('name'),
            'email': user.get('email'),
            'role': user.get('role', 'user'),
            'chatroomCount': chatroom_count,
            'reportCount': 0,
            'revenue': round(total_revenue, 2),
        }
        users_stats.append(stats)

    return jsonify({'success': True, 'users': users_stats}), 200

def collect_charts(viz_data: dict) -> list:
    """
    Collect and format charts from visualization data.
    
    Args:
        viz_data: Dictionary containing visualization data
        
    Returns:
        List of formatted chart objects
    """
    charts = []
    
    if not viz_data:
        return charts
        
    try:
        # Handle different chart types
        for chart_type, chart_info in viz_data.items():
            if not chart_info:
                continue
                
            if isinstance(chart_info, dict):
                # Single chart
                if 'image' in chart_info:
                    charts.append({
                        'type': chart_type,
                        'image': chart_info.get('image', ''),
                        'title': chart_info.get('title', chart_type.replace('_', ' ').title()),
                        'description': chart_info.get('description', '')
                    })
            elif isinstance(chart_info, list):
                # Multiple charts of the same type
                for idx, chart in enumerate(chart_info):
                    if isinstance(chart, dict) and 'image' in chart:
                        charts.append({
                            'type': f"{chart_type}_{idx + 1}",
                            'image': chart.get('image', ''),
                            'title': chart.get('title', f"{chart_type.replace('_', ' ').title()} {idx + 1}"),
                            'description': chart.get('description', '')
                        })
                        
    except Exception as e:
        print(f"Error collecting charts: {str(e)}")
        
    return charts
    return charts
@app.route('/api/download-full-report', methods=['POST'])
def download_full_report():
    try:
        current_user = get_current_user()
        user_id = str(current_user['_id']) if current_user else None
        payload = request.get_json(silent=True) or {}
        results = payload.get('results', [])
        data_source_type = payload.get('dataSourceType')  # 'user_db' or 'uploaded_files'
        database_name = payload.get('databaseName')       # e.g. 'mydb' or 'test01'

        if db is not None and report_history_collection is not None and user_id:
            try:
                report_history_collection.insert_one({
                    'userId': user_id,
                    'resultsCount': len(results),
                    'generatedAt': datetime.utcnow(),
                    'dataSourceType': data_source_type,
                    'databaseName': database_name,
                })
            except Exception as e:
                print('Failed to store report history:', e)

        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph('AI Insights Report', styles['Title']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
        story.append(Spacer(1, 12))

        for idx, item in enumerate(results, 1):
            insight = item.get('insight', {}) or {}
            
            # Query Section
            story.append(Paragraph(f'Query {idx}', styles['Heading2']))
            story.append(Paragraph(item.get('query', 'N/A'), styles['Normal']))
            story.append(Spacer(1, 8))

            # SQL Query
            sql_text = insight.get('sql_query') or insight.get('sql') or ''
            if sql_text:
                story.append(Paragraph('SQL Query', styles['Heading3']))
                formatted_sql = sql_text.replace('\n', '<br/>').replace(' ', '&nbsp;')
                story.append(Paragraph(f'<font name="Courier" size="8">{formatted_sql}</font>', styles['Normal']))
                story.append(Spacer(1, 8))

            # Key Findings
            key_findings = insight.get('key_findings') or insight.get('summary') or []
            if key_findings:
                story.append(Paragraph('Key Findings', styles['Heading3']))
                if isinstance(key_findings, str):
                    story.append(Paragraph(key_findings, styles['Normal']))
                else:
                    for point in key_findings:
                        story.append(Paragraph(f'• {point}', styles['Normal']))
                story.append(Spacer(1, 8))

            # Risk Factors
            risk_factors = insight.get('risk_factors') or insight.get('risks') or []
            if risk_factors:
                story.append(Paragraph('Risk Factors', styles['Heading3']))
                if isinstance(risk_factors, str):
                    story.append(Paragraph(risk_factors, styles['Normal']))
                else:
                    for risk in risk_factors:
                        story.append(Paragraph(f'• {risk}', styles['Normal']))
                story.append(Spacer(1, 8))

            # Recommendations
            recommendations = insight.get('recommendations') or insight.get('strategy') or []
            if recommendations:
                story.append(Paragraph('Recommendations', styles['Heading3']))
                if isinstance(recommendations, str):
                    story.append(Paragraph(recommendations, styles['Normal']))
                else:
                    for rec in recommendations:
                        story.append(Paragraph(f'• {rec}', styles['Normal']))
                story.append(Spacer(1, 8))

            # Visualizations
            viz = insight.get('visualizations') or {}
            print("Visualizations data structure:", json.dumps(viz, indent=2))
            charts = collect_charts(viz)  # Reuse existing chart collection logic
            if charts:
                story.append(Paragraph('Visualizations', styles['Heading3']))
                for chart in charts:
                    try:
                        img_str = chart['image']
                        if isinstance(img_str, str) and 'base64,' in img_str:
                            img_str = img_str.split('base64,', 1)[-1]
                        img_bytes = base64.b64decode(img_str)
                        img_buf = io.BytesIO(img_bytes)
                        img = Image(img_buf, width=400, height=200)
                        story.append(img)
                        story.append(Spacer(1, 12))
                    except Exception:
                        continue

            # Data Preview
            data_rows = insight.get('data') or []
            columns = insight.get('columns') or []
            if isinstance(data_rows, list) and data_rows and isinstance(data_rows[0], dict):
                preview_rows = data_rows[:10]
                table_data = [columns] if columns else [list(preview_rows[0].keys())]
                for row in preview_rows:
                    table_data.append([str(row.get(col, '')) for col in table_data[0]])

                story.append(Paragraph('Data Preview', styles['Heading3']))
                tbl = Table(table_data, hAlign='LEFT')
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 12))

        doc.build(story)
        pdf_buf.seek(0)
        return send_file(
            pdf_buf,
            as_attachment=True,
            download_name=f'AI_Insights_Report_{int(time.time())}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500
@app.route('/api/azure/upload-folder', methods=['POST'])
def upload_folder_to_azure():
    """Upload folder to Azure Data Lake"""
    # Implementation for uploading files to Azure Data Lake
    pass

@app.route('/api/databricks/transform', methods=['POST'])
def trigger_databricks_transform():
    """Trigger Databricks transformation job"""
    # Implementation for triggering Databricks job
    pass

@app.route('/api/databricks/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get Databricks job status"""
    # Implementation for checking job status
    pass

@app.route('/api/azure/list-files', methods=['POST'])
def list_azure_files():
    """List files in Azure Data Lake folder"""
    # Implementation for listing files
    pass

@app.route('/api/azure/download-file', methods=['POST'])
def download_azure_file():
    """Download single file from Azure"""
    # Implementation for downloading file
    pass

@app.route('/api/azure/download-folder', methods=['POST'])
def download_azure_folder():
    """Download folder as ZIP from Azure"""
    # Implementation for downloading folder as ZIP
    pass

# ============ Manual Bid-based Transform Requests ============
MANUAL_REQUESTS_DIR = Path("manual_requests")
MANUAL_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_manual_dirs(request_id: str):
    base = MANUAL_REQUESTS_DIR / request_id
    input_dir = base / "input"
    arch_dir = base / "architecture"
    result_dir = base / "result"
    for d in [input_dir, arch_dir, result_dir]:
        d.mkdir(parents=True, exist_ok=True)
    return base, input_dir, arch_dir, result_dir


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle general chat with the AI assistant."""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    chat_history = data.get('history', [])
    
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    
    try:
        # Initialize LLM if not already done
        llm = get_cached_llm()
        
        # Create a prompt for general chat
        prompt = ChatPromptTemplate.from_template("""
        You are RevenueLens AI Assistant, a helpful assistant for the RevenueLens platform.
        Help users with general questions, navigation, and provide information about the application.
        
        Current conversation:
        {history}
        
        User: {input}
        Assistant:""")
        
        # Create a simple chain for general chat
        chain = (
            {
                "input": RunnablePassthrough(),
                "history": lambda x: "\n".join(x.get("history", []))
            }
            | prompt
            | llm
            | StrOutputParser()
        )
        
        # Get response
        response = chain.invoke({
            "input": user_message,
            "history": chat_history
        })
        
        return jsonify({
            "response": response,
            "type": "general_chat"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/manual-requests', methods=['POST'])
def create_manual_request():
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    # Block new manual requests if user has any unpaid manual request
    existing_unpaid = manual_requests_collection.find_one({
        'userId': str(current_user['_id']),
        'paymentStatus': {'$ne': 'paid'},
    })
    if existing_unpaid:
        return jsonify({
            'success': False,
            'message': 'You already have a manual request pending or unpaid. Please complete payment before creating a new manual request.'
        }), 400

    bid_amount_raw = request.form.get('bidAmount')
    architecture_mode = request.form.get('architectureMode', 'default')

    if not bid_amount_raw:
        return jsonify({'success': False, 'message': 'bidAmount is required'}), 400

    try:
        bid_amount = float(bid_amount_raw)
    except ValueError:
        return jsonify({'success': False, 'message': 'bidAmount must be a number'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'success': False, 'message': 'At least one data file is required'}), 400

    arch_file = request.files.get('architectureFile') if architecture_mode == 'custom' else None
    
    if architecture_mode == 'custom' and not arch_file:
        return jsonify({'success': False, 'message': 'Custom architecture file is required'}), 400
    
    if architecture_mode == 'default' and arch_file:
        return jsonify({'success': False, 'message': 'Custom architecture file is not allowed in default mode'}), 400

    now = datetime.utcnow()
    doc = {
        'userId': str(current_user['_id']),
        'userEmail': current_user.get('email'),
        'bidAmount': bid_amount,
        'status': 'pending',
        'paymentStatus': 'unpaid',
        'createdAt': now,
        'updatedAt': now,
        'files': [],
        'architecture': {
            'mode': architecture_mode,
            'originalName': arch_file.filename if arch_file else None,
            'storedPath': None,
        },
        'resultFile': None,
    }

    result = manual_requests_collection.insert_one(doc)
    request_id = str(result.inserted_id)

    base_dir, input_dir, arch_dir, result_dir = _ensure_manual_dirs(request_id)

    saved_files = []
    for f in files:
        filename = secure_filename(f.filename or '')
        if not filename:
            continue
        dest = input_dir / filename
        with open(dest, 'wb') as buf:
            shutil.copyfileobj(f.stream, buf)
        saved_files.append({
            'originalName': f.filename,
            'storedPath': str(dest),
        })

    arch_info = doc['architecture']
    if arch_file:
        arch_name = secure_filename(arch_file.filename or '')
        if arch_name:
            arch_dest = arch_dir / arch_name
            with open(arch_dest, 'wb') as buf:
                shutil.copyfileobj(arch_file.stream, buf)
            arch_info['storedPath'] = str(arch_dest)

    manual_requests_collection.update_one(
        {'_id': result.inserted_id},
        {'$set': {
            'files': saved_files,
            'architecture': arch_info,
            'updatedAt': datetime.utcnow(),
        }}
    )

    return jsonify({'success': True, 'requestId': request_id}), 201


@app.route('/api/manual-requests/my', methods=['GET'])
def list_my_manual_requests():
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    user_id = str(current_user['_id'])
    docs = list(manual_requests_collection.find({'userId': user_id}).sort('createdAt', -1))
    return jsonify({'success': True, 'requests': serialize_docs(docs)}), 200


@app.route('/api/manual-requests/<request_id>', methods=['GET'])
def get_manual_request(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    user_id = str(current_user['_id'])
    if user_id != doc.get('userId') and current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    return jsonify({'success': True, 'request': serialize_doc(doc)}), 200


@app.route('/api/manual-requests/<request_id>/download-result', methods=['GET'])
def download_manual_result(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    user_id = str(current_user['_id'])
    if user_id != doc.get('userId'):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    if doc.get('paymentStatus') != 'paid':
        return jsonify({'success': False, 'message': 'Payment required before download'}), 403

    result_info = doc.get('resultFile') or {}
    path_str = result_info.get('storedPath')
    if not path_str or not os.path.exists(path_str):
        return jsonify({'success': False, 'message': 'Result file not available'}), 404

    return send_file(
        path_str, 
        as_attachment=True, 
        download_name=result_info.get('originalName') or 'transformed_result.zip'
    )


@app.route("/api/auto-transforms/my", methods=["GET"])
def list_my_auto_transforms():
    if db is None or auto_transforms_collection is None:
        return jsonify({"success": False, "message": "Database not connected"}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    user_id_str = str(current_user["_id"])
    docs = list(
        auto_transforms_collection.find({"userId": user_id_str}).sort(
            "createdAt", -1
        )
    )
    return jsonify({"success": True, "items": serialize_docs(docs)}), 200




@app.route("/api/admin/auto-transforms", methods=["GET"])
def admin_list_auto_transforms():
    if db is None or auto_transforms_collection is None:
        return jsonify({"success": False, "message": "Database not connected"}), 500

    current_user = get_current_user()
    if not current_user or current_user.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden"}), 403

    docs = list(auto_transforms_collection.find({}).sort("createdAt", -1))
    return jsonify({"success": True, "items": serialize_docs(docs)}), 200


@app.route("/api/auto-transforms/<auto_id>/pay", methods=["POST"])
def pay_for_auto_transform(auto_id):
    if db is None or auto_transforms_collection is None:
        return jsonify({"success": False, "message": "Database not connected"}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        doc = auto_transforms_collection.find_one({"_id": ObjectId(auto_id)})
    except Exception:
        return jsonify({"success": False, "message": "Invalid id"}), 400

    if not doc:
        return jsonify({"success": False, "message": "Not found"}), 404

    # only owner can pay
    if str(current_user["_id"]) != doc.get("userId"):
        return jsonify({"success": False, "message": "Forbidden"}), 403

    if doc.get("paymentStatus") == "paid":
        return jsonify({"success": True}), 200

    auto_transforms_collection.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "paymentStatus": "paid",
                "updatedAt": datetime.utcnow(),
                "paidAt": datetime.utcnow(),
            }
        },
    )
    return jsonify({"success": True}), 200

@app.route('/api/manual-requests/<request_id>/cancel', methods=['POST'])
def cancel_manual_request(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    user_id = str(current_user['_id'])
    if user_id != doc.get('userId'):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    # Only allow cancel while pending (before admin accepts/rejects)
    if doc.get('status') != 'pending':
        return jsonify({'success': False, 'message': 'Only pending requests can be cancelled'}), 400

    manual_requests_collection.update_one(
        {'_id': doc['_id']},
        {'$set': {
            'status': 'cancelled',
            'paymentStatus': 'cancelled',
            'updatedAt': datetime.utcnow(),
        }}
    )

    return jsonify({'success': True}), 200


@app.route('/api/admin/manual-requests', methods=['GET'])
def admin_list_manual_requests():
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    docs = list(manual_requests_collection.find({}).sort('createdAt', -1))
    return jsonify({'success': True, 'requests': serialize_docs(docs)}), 200


@app.route('/api/admin/manual-requests/<request_id>/status', methods=['POST'])
def admin_update_manual_status(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status not in ['accepted', 'rejected']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    manual_requests_collection.update_one(
        {'_id': doc['_id']},
        {'$set': {'status': new_status, 'updatedAt': datetime.utcnow()}}
    )

    return jsonify({'success': True}), 200


@app.route('/api/admin/manual-requests/<request_id>/bid', methods=['POST'])
def admin_update_manual_bid(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    new_bid = data.get('bidAmount')
    if new_bid is None:
        return jsonify({'success': False, 'message': 'bidAmount is required'}), 400

    try:
        bid_float = float(new_bid)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'bidAmount must be a number'}), 400

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    manual_requests_collection.update_one(
    {'_id': doc['_id']},
    {'$set': {
        'paymentStatus': 'paid',
        'status': 'completed',
        'updatedAt': datetime.utcnow(),
    }}
)

    return jsonify({'success': True}), 200

@app.route('/api/admin/manual-requests/<request_id>/architecture', methods=['GET'])
def admin_download_manual_architecture(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    arch = (doc.get('architecture') or {})
    path_str = arch.get('storedPath')
    original_name = arch.get('originalName') or 'architecture_file'

    if not path_str or not os.path.exists(path_str):
        return jsonify({'success': False, 'message': 'Architecture file not available'}), 404

    return send_file(path_str, as_attachment=False, download_name=original_name)


@app.route('/api/admin/manual-requests/<request_id>/download-input', methods=['GET'])
def admin_download_manual_input(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    # Get input folder for this request
    base_dir, input_dir, arch_dir, result_dir = _ensure_manual_dirs(request_id)

    if not input_dir.exists():
        return jsonify({'success': False, 'message': 'Input files not found'}), 404

    # Zip the input files in memory
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_info in doc.get('files', []):
            path_str = file_info.get('storedPath')
            original_name = file_info.get('originalName') or 'file'
            if path_str and os.path.exists(path_str):
                zf.write(path_str, arcname=original_name)
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name=f'manual_request_{request_id}_input.zip',
        mimetype='application/zip',
    )

@app.route('/api/admin/manual-requests/<request_id>/upload-result', methods=['POST'])
def admin_upload_manual_result(request_id):
    if db is None or manual_requests_collection is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500

    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        doc = manual_requests_collection.find_one({'_id': ObjectId(request_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid request id'}), 400

    if not doc:
        return jsonify({'success': False, 'message': 'Request not found'}), 404

    result_file = request.files.get('resultFile')
    if not result_file:
        return jsonify({'success': False, 'message': 'resultFile is required'}), 400

    base_dir, input_dir, arch_dir, result_dir = _ensure_manual_dirs(request_id)

    filename = secure_filename(result_file.filename or 'transformed_result.zip')
    dest = result_dir / filename
    with open(dest, 'wb') as buf:
        shutil.copyfileobj(result_file.stream, buf)

    manual_requests_collection.update_one(
        {'_id': doc['_id']},
        {'$set': {
            'resultFile': {
                'originalName': result_file.filename,
                'storedPath': str(dest),
            },
            'status': 'ready_for_payment',
            'updatedAt': datetime.utcnow(),
        }}
    )

    return jsonify({'success': True}), 200


# ============ Automatic Medallion Transform Pipeline ============
BASE_DIR = Path("medallion_data")
BRONZE_DIR = BASE_DIR / "bronze"
SILVER_DIR = BASE_DIR / "silver"
GOLD_DIR = BASE_DIR / "gold"

for d in [BRONZE_DIR, SILVER_DIR, GOLD_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class MedallionPipeline:
    """Handles the complete medallion architecture pipeline (bronze -> silver -> gold)."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.bronze_path = BRONZE_DIR / session_id
        self.silver_path = SILVER_DIR / session_id
        self.gold_path = GOLD_DIR / session_id

        for path in [self.bronze_path, self.silver_path, self.gold_path]:
            path.mkdir(parents=True, exist_ok=True)

    def ingest_to_bronze(self, files: List):
        """Bronze layer: store raw data as-is."""
        ingested_files = []

        for storage in files:
            file = storage
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            file_path = self.bronze_path / filename

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.stream, buffer)

            ingested_files.append({
                "filename": filename,
                "original_name": file.filename,
                "path": str(file_path),
                "size": file_path.stat().st_size,
            })

        metadata = {
            "ingestion_time": datetime.now().isoformat(),
            "files": ingested_files,
            "layer": "bronze",
        }

        with open(self.bronze_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def process_to_silver(self) -> dict:
        """Silver layer: clean, validate, and standardize data."""
        processed_files = []

        for bronze_file in self.bronze_path.glob("*"):
            if bronze_file.name == "metadata.json":
                continue

            if bronze_file.suffix.lower() in [".csv", ".json", ".xlsx", ".xls"]:
                try:
                    if bronze_file.suffix.lower() == ".csv":
                        encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
                        df = None
                        for encoding in encodings:
                            try:
                                df = pd.read_csv(bronze_file, encoding=encoding)
                                break
                            except UnicodeDecodeError:
                                continue
                        if df is None:
                            raise Exception("Could not decode file with any supported encoding")
                    elif bronze_file.suffix.lower() == ".json":
                        with open(bronze_file, "r", encoding="utf-8", errors="ignore") as f:
                            df = pd.read_json(f)
                    elif bronze_file.suffix.lower() in [".xlsx", ".xls"]:
                        df = pd.read_excel(bronze_file)
                    else:
                        continue

                    original_rows = len(df)

                    # 1. Standardize column names
                    df.columns = (
                        df.columns.str.strip()
                        .str.lower()
                        .str.replace(" ", "_")
                        .str.replace(r"[^\w]", "_", regex=True)
                    )

                    # 2. Remove duplicate rows
                    df = df.drop_duplicates()

                    # 3. Handle missing values
                    numeric_cols = df.select_dtypes(include=["number"]).columns
                    for col in numeric_cols:
                        if df[col].isnull().any():
                            median_val = df[col].median()
                            if pd.notna(median_val):
                                df[col].fillna(median_val, inplace=True)
                            else:
                                df[col].fillna(0, inplace=True)

                    categorical_cols = df.select_dtypes(include=["object"]).columns
                    for col in categorical_cols:
                        if df[col].isnull().any():
                            mode_val = df[col].mode()
                            if len(mode_val) > 0:
                                df[col].fillna(mode_val[0], inplace=True)
                            else:
                                df[col].fillna("unknown", inplace=True)

                    # 4. Remove rows with all NaN values
                    df = df.dropna(how="all")

                    # 5. Strip whitespace from string columns
                    for col in categorical_cols:
                        if col in df.columns:
                            df[col] = df[col].astype(str).str.strip()

                    # 6. Remove columns with no variance
                    cols_before = len(df.columns)
                    constant_cols = [c for c in df.columns if df[c].nunique() == 1]
                    if constant_cols:
                        df = df.drop(columns=constant_cols)
                    cols_removed = cols_before - len(df.columns)

                    # Save cleaned data to silver layer as CSV for easy inspection
                    silver_filename = f"cleaned_{bronze_file.stem}.csv"
                    silver_path = self.silver_path / silver_filename
                    df.to_csv(silver_path, index=False)

                    processed_files.append({
                        "source_file": bronze_file.name,
                        "silver_file": silver_filename,
                        "original_rows": original_rows,
                        "processed_rows": len(df),
                        "removed_rows": original_rows - len(df),
                        "removed_columns": cols_removed,
                        "columns": list(df.columns),
                        "data_types": df.dtypes.astype(str).to_dict(),
                        "status": "success",
                    })
                except Exception as e:
                    processed_files.append({
                        "source_file": bronze_file.name,
                        "error": str(e),
                        "status": "failed",
                    })

        metadata = {
            "processing_time": datetime.now().isoformat(),
            "files": processed_files,
            "layer": "silver",
        }

        with open(self.silver_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def aggregate_to_gold(self) -> dict:
        """Gold layer: business-level aggregations and quality metrics."""
        gold_files = []

        # Iterate over cleaned CSVs in the silver layer
        for silver_file in self.silver_path.glob("cleaned_*.csv"):
            try:
                # Read cleaned data from silver layer (CSV)
                df = pd.read_csv(silver_file)

                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
                date_cols = [
                    col
                    for col in df.columns
                    if "date" in col.lower() or "time" in col.lower()
                ]

                for col in date_cols:
                    if col in df.columns:
                        try:
                            df[col] = pd.to_datetime(df[col], errors="coerce")
                        except Exception:
                            pass

                gold_df = df.copy()
                gold_df.insert(0, "record_id", range(1, len(gold_df) + 1))

                if categorical_cols and numeric_cols:
                    for cat_col in categorical_cols[:3]:
                        if cat_col in gold_df.columns:
                            count_map = gold_df[cat_col].value_counts().to_dict()
                            gold_df[f"{cat_col}_count"] = gold_df[cat_col].map(count_map)

                            first_numeric = numeric_cols[0]
                            mean_map = df.groupby(cat_col)[first_numeric].mean().to_dict()
                            gold_df[f"{cat_col}_avg_{first_numeric}"] = gold_df[cat_col].map(mean_map)

                if numeric_cols:
                    main_numeric = numeric_cols[0]
                    gold_df[f"{main_numeric}_rank"] = gold_df[main_numeric].rank(
                        ascending=False, method="dense"
                    ).astype(int)
                    gold_df[f"{main_numeric}_percentile"] = (
                        gold_df[main_numeric].rank(pct=True) * 100
                    ).round(2)
                    gold_df[f"{main_numeric}_cumsum"] = gold_df[main_numeric].cumsum()
                    mean_val = gold_df[main_numeric].mean()
                    gold_df[f"{main_numeric}_deviation"] = (
                        gold_df[main_numeric] - mean_val
                    ).round(2)

                if categorical_cols:
                    main_cat = categorical_cols[0]
                    if main_cat in gold_df.columns:
                        top_categories = (
                            gold_df[main_cat].value_counts().head(5).index.tolist()
                        )
                        gold_df[f"{main_cat}_is_top5"] = gold_df[main_cat].isin(
                            top_categories
                        )

                for date_col in date_cols:
                    if (
                        date_col in gold_df.columns
                        and pd.api.types.is_datetime64_any_dtype(gold_df[date_col])
                    ):
                        gold_df[f"{date_col}_year"] = gold_df[date_col].dt.year
                        gold_df[f"{date_col}_month"] = gold_df[date_col].dt.month
                        gold_df[f"{date_col}_quarter"] = gold_df[date_col].dt.quarter
                        gold_df[f"{date_col}_day_of_week"] = gold_df[date_col].dt.dayofweek
                        gold_df[f"{date_col}_day_name"] = gold_df[date_col].dt.day_name()

                if len(numeric_cols) >= 2:
                    col1, col2 = numeric_cols[0], numeric_cols[1]
                    gold_df[f"{col1}_to_{col2}_ratio"] = (
                        gold_df[col1] / gold_df[col2].replace(0, 1)
                    ).round(4)

                if numeric_cols:
                    for num_col in numeric_cols[:2]:
                        Q1 = gold_df[num_col].quantile(0.25)
                        Q3 = gold_df[num_col].quantile(0.75)
                        IQR = Q3 - Q1
                        gold_df[f"{num_col}_is_outlier"] = (
                            (gold_df[num_col] < (Q1 - 1.5 * IQR))
                            | (gold_df[num_col] > (Q3 + 1.5 * IQR))
                        )

                gold_df["row_completeness"] = (
                    1 - gold_df.isnull().sum(axis=1) / len(gold_df.columns)
                ) * 100
                gold_df["has_missing_values"] = gold_df.isnull().any(axis=1)
                gold_df["load_timestamp"] = datetime.now().isoformat()
                gold_df["data_quality_score"] = gold_df["row_completeness"].round(2)

                base_name = silver_file.stem.replace("cleaned_", "")
                gold_filename = f"{base_name}_gold.csv"
                gold_path = self.gold_path / gold_filename
                gold_df.to_csv(gold_path, index=False)

                total_rows = len(gold_df)
                complete_rows = len(gold_df[gold_df["row_completeness"] == 100])
                outlier_count = sum(
                    [
                        gold_df[col].sum()
                        for col in gold_df.columns
                        if col.endswith("_is_outlier")
                    ]
                )

                gold_files.append({
                    "source_file": silver_file.name,
                    "gold_file": gold_filename,
                    "rows": total_rows,
                    "columns": len(gold_df.columns),
                    "complete_rows": complete_rows,
                    "rows_with_missing": total_rows - complete_rows,
                    "outliers_detected": int(outlier_count),
                    "avg_data_quality": round(
                        gold_df["data_quality_score"].mean(), 2
                    ),
                    "column_names": list(gold_df.columns),
                    "status": "success",
                })

            except Exception as e:
                gold_files.append({
                    "source_file": silver_file.name,
                    "error": str(e),
                    "status": "failed",
                })

        metadata = {
            "aggregation_time": datetime.now().isoformat(),
            "files": gold_files,
            "layer": "gold",
        }

        with open(self.gold_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def create_zip_package(self) -> Path:
        """Create a zip file containing all layers for this session."""
        zip_filename = f"medallion_output_{self.session_id}.zip"
        zip_path = BASE_DIR / zip_filename

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for layer_name, base_path in [
                ("bronze", self.bronze_path),
                ("silver", self.silver_path),
                ("gold", self.gold_path),
            ]:
                for file in base_path.rglob("*"):
                    if file.is_file():
                        arcname = f"{layer_name}/{file.relative_to(base_path)}"
                        zipf.write(file, arcname)

        return zip_path
@app.route("/api/auto-transforms/<auto_id>/download-zip", methods=["GET"])
def download_auto_zip(auto_id):
    if db is None or auto_transforms_collection is None:
        return jsonify({"success": False, "message": "Database not connected"}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        doc = auto_transforms_collection.find_one({"_id": ObjectId(auto_id)})
    except Exception:
        return jsonify({"success": False, "message": "Invalid id"}), 400

    if not doc:
        return jsonify({"success": False, "message": "Not found"}), 404

    # only owner can download
    if str(current_user["_id"]) != doc.get("userId"):
        return jsonify({"success": False, "message": "Forbidden"}), 403

    if doc.get("paymentStatus") != "paid":
        return jsonify({"success": False, "message": "Payment required before download"}), 403

    zip_path = doc.get("zipPath")
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"success": False, "message": "Result file not available"}), 404

    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"auto_transform_{auto_id}.zip",
        mimetype="application/zip",
    )

@app.route("/api/transform/automatic", methods=["POST"])
def automatic_transform():
    """Automatic medallion-style transformation for uploaded files.

    Expects form-data with multiple `files` fields. Returns a ZIP containing
    bronze/silver/gold outputs for this session.
    """
    if db is None or auto_transforms_collection is None or users_collection is None:
        return jsonify({"success": False, "message": "Database not connected"}), 500

    current_user = get_current_user()
    if not current_user:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    user_id_str = str(current_user["_id"])
    user_email = current_user.get("email")

    # Block if user has any unpaid automatic transform
    existing_unpaid_auto = auto_transforms_collection.find_one(
        {"userId": user_id_str, "paymentStatus": {"$ne": "paid"}}
    )
    if existing_unpaid_auto:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "You already have an automatic transformation unpaid. Please complete payment before starting a new one.",
                }
            ),
            400,
        )

    files = request.files.getlist("files")
    if not files:
        return jsonify({"success": False, "message": "No files uploaded"}), 400

    # Compute total size from uploads
    total_size_bytes = 0
    safe_files = []
    for storage in files:
        file_obj = storage
        # get size: content_length or read into memory
        size = getattr(file_obj, "content_length", None) or 0
        if size == 0:
            # fallback: read into bytes
            file_bytes = file_obj.read()
            size = len(file_bytes)
            # reset stream for pipeline
            from io import BytesIO

            file_obj.stream = BytesIO(file_bytes)
        total_size_bytes += size
        safe_files.append(file_obj)

    size_mb = total_size_bytes / (1024 * 1024)

    # For each 0.1 MB, price increases by 10
    steps = math.ceil(size_mb / 0.01) if size_mb > 0 else 1
    price = steps * 10.0

    # Ensure minimum of 10 even for very tiny files
    if price < 10.0:
        price = 10.0

    session_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Log auto transform record
    auto_doc = {
        "userId": user_id_str,
        "userEmail": user_email,
        "sessionId": session_id,
        "sizeBytes": total_size_bytes,
        "sizeMb": size_mb,
        "price": float(f"{price:.2f}"),
        "status": "completed",  # automatic run completes immediately
        "paymentStatus": "unpaid",
        "createdAt": now,
        "updatedAt": now,
    }
    result = auto_transforms_collection.insert_one(auto_doc)
    auto_id = str(result.inserted_id)

    try:
        pipeline = MedallionPipeline(session_id)

        bronze_metadata = pipeline.ingest_to_bronze(safe_files)
        silver_metadata = pipeline.process_to_silver()
        gold_metadata = pipeline.aggregate_to_gold()
        zip_path = pipeline.create_zip_package()
        auto_transforms_collection.update_one(
            {"_id": result.inserted_id},
            {
                "$set": {
                    "zipPath": str(zip_path),
                    "updatedAt": datetime.utcnow(),
                }
    },
)

        return jsonify({
            "success": True,
            "autoId": auto_id,
            "price": auto_doc["price"],
            "sessionId": session_id,
        }), 200

    except Exception as e:
        return (
            jsonify({"success": False, "message": f"Pipeline error: {str(e)}"}),
            500,
        )


@socketio.on('disconnect')
def handle_disconnect():
    for user_id, user in list(active_users.items()):
        if user['socketId'] == request.sid:
            del active_users[user_id]
            print(f' User {user_id} disconnected')
            break

@socketio.on('join_room')
def handle_join_room(data):
    if db is None or users_collection is None:
        emit('error', {'message': 'Database not connected'})
        return
    
    room_id = data.get('roomId')
    user_id = data.get('userId')
    
    try:
        room = rooms_collection.find_one({'_id': ObjectId(room_id)})
        if not room:
            emit('error', {'message': 'Room not found'})
            return
        
        join_room(room_id)
        
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            emit('user_joined', {
                'userId': user_id,
                'userName': user.get('name', 'Unknown'),
                'roomId': room_id
            }, room=room_id)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('send_message')
def handle_send_message(data):
    if db is None or messages_collection is None or users_collection is None:
        emit('error', {'message': 'Database not connected'})
        return

    room_id = data.get('roomId')
    user_id = data.get('userId')
    text = (data.get('text') or '').strip()

    if not room_id or not user_id or not text:
        emit('error', {'message': 'Invalid message payload'})
        return

    try:
        # Verify user and room exist
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        room = rooms_collection.find_one({'_id': ObjectId(room_id)})
        if not user or not room:
            emit('error', {'message': 'Invalid room or user'})
            return

        # Persist message
        msg_doc = {
            'roomId': room_id,
            'userId': str(user['_id']),
            'userName': user.get('name', 'Unknown'),
            'text': text,
            'timestamp': datetime.utcnow()
        }
        result = messages_collection.insert_one(msg_doc)
        msg_doc['_id'] = str(result.inserted_id)

        # Broadcast to all clients in the room (including sender)
        emit('message', {
            'id': msg_doc['_id'],
            'roomId': room_id,
            'userId': msg_doc['userId'],
            'userName': msg_doc['userName'],
            'text': msg_doc['text'],
            'timestamp': msg_doc['timestamp'].isoformat() + 'Z'
        }, room=room_id)

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('leave_room')
def handle_leave_room(data):
    room_id = data.get('roomId')
    user_id = data.get('userId')
    if not room_id or not user_id:
        return

    leave_room(room_id)

    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        user_name = user.get('name', 'Unknown') if user else 'Unknown'
        emit('user_left', {
            'userId': user_id,
            'userName': user_name,
            'roomId': room_id
        }, room=room_id)
    except Exception as e:
        emit('error', {'message': str(e)})

def _fetch_mysql_schema(db_cfg):
    import mysql.connector
    conn = mysql.connector.connect(host=db_cfg.get('host', 'localhost'), user=db_cfg.get('user'), password=db_cfg.get('password', ''), database=db_cfg.get('database'), port=int(db_cfg.get('port', 3306)))
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=%s ORDER BY TABLE_NAME", (db_cfg.get('database'),))
    tables = [r['TABLE_NAME'] for r in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_TYPE
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ORDINAL_POSITION
        """, (db_cfg.get('database'), t))
        cols = cur.fetchall()
        try:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM `{t}`")
            rc = cur.fetchone().get('cnt', 0)
        except Exception:
            rc = 0
        schema[t] = {
            'columns': [c['COLUMN_NAME'] for c in cols],
            'dtypes': {c['COLUMN_NAME']: c['DATA_TYPE'] for c in cols},
            'nullable': {c['COLUMN_NAME']: c['IS_NULLABLE'] for c in cols},
            'column_type': {c['COLUMN_NAME']: c['COLUMN_TYPE'] for c in cols},
            'row_count': int(rc)
        }
    cur.close()
    conn.close()
    return schema

@app.route('/api/get-schema', methods=['POST'])
def get_schema():
    data = request.get_json(silent=True) or {}
    db_cfg = data.get('dbConfig') or data
    host = db_cfg.get('host', 'localhost')
    user = db_cfg.get('user')
    password = db_cfg.get('password', '')
    database_name = db_cfg.get('database')
    port = int(db_cfg.get('port', 3306))
    if not user or not database_name:
        return jsonify({'success': False, 'error': 'dbConfig must include user and database'}), 400
    try:
        schema = _fetch_mysql_schema({'host': host, 'user': user, 'password': password, 'database': database_name, 'port': port})
        return jsonify({'success': True, 'schema': schema}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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