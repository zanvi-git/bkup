import os
import datetime
import hashlib
import json
import shutil
import time
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from models import db, User

load_dotenv()

app = Flask(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, '..', 'uploads')
CHUNKS_FOLDER = os.path.join(UPLOAD_FOLDER, '.chunks')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHUNKS_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHUNKS_FOLDER'] = CHUNKS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(SCRIPT_DIR, 'backup_system.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CHUNK_RETENTION_HOURS'] = 24

db.init_app(app)
jwt = JWTManager(app)

with app.app_context():
    db.create_all()



def get_file_metadata(filepath):
    stat = os.stat(filepath)
    return {
        "filename": os.path.basename(filepath),
        "size_bytes": stat.st_size,
        "size_human": format_bytes(stat.st_size),
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
    }

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_user_upload_folder(username):
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(username))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_chunk_directory(file_id, username):
    file_id = secure_filename(file_id)
    user_chunks_folder = os.path.join(app.config['CHUNKS_FOLDER'], secure_filename(username))
    chunk_dir = os.path.join(user_chunks_folder, file_id)
    os.makedirs(chunk_dir, exist_ok=True)
    return chunk_dir

def get_metadata_path(file_id, username):
    chunk_dir = get_chunk_directory(file_id, username)
    return os.path.join(chunk_dir, 'metadata.json')

def save_chunk_metadata(file_id, filename, category, total_chunks, username):
    metadata = {
        'filename': filename,
        'category': category,
        'total_chunks': total_chunks,
        'upload_start_time': time.time(),
        'username': username
    }
    metadata_path = get_metadata_path(file_id, username)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f)

def load_chunk_metadata(file_id, username):
    metadata_path = get_metadata_path(file_id, username)
    if not os.path.exists(metadata_path):
        return None
    with open(metadata_path, 'r') as f:
        return json.load(f)

def save_chunk(file_id, chunk_index, chunk_data, expected_checksum, username):
    actual_checksum = hashlib.sha256(chunk_data).hexdigest()
    
    if actual_checksum != expected_checksum:
        return False, f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
    
    # Quota check
    user = User.query.filter_by(username=username).first()
    if user.used_bytes + len(chunk_data) > user.quota_bytes:
        return False, "Quota exceeded"
    
    chunk_dir = get_chunk_directory(file_id, username)
    chunk_path = os.path.join(chunk_dir, f'chunk_{chunk_index}.part')
    
    # If chunk already exists, we need to subtract its size from used_bytes first to avoid double counting if re-uploading
    if os.path.exists(chunk_path):
        user.used_bytes -= os.path.getsize(chunk_path)

    with open(chunk_path, 'wb') as f:
        f.write(chunk_data)
    
    user.used_bytes += len(chunk_data)
    db.session.commit()
    
    return True, actual_checksum

def get_received_chunks(file_id, username):
    chunk_dir = get_chunk_directory(file_id, username)
    if not os.path.exists(chunk_dir):
        return []
    
    chunks = []
    for filename in os.listdir(chunk_dir):
        if filename.startswith('chunk_') and filename.endswith('.part'):
            try:
                chunk_index = int(filename.replace('chunk_', '').replace('.part', ''))
                chunks.append(chunk_index)
            except ValueError:
                continue
    
    return sorted(chunks)

def merge_chunks(file_id, total_chunks, final_filename, category, username):
    chunk_dir = get_chunk_directory(file_id, username)
    
    received_chunks = get_received_chunks(file_id, username)
    expected_chunks = list(range(total_chunks))
    
    if received_chunks != expected_chunks:
        missing = set(expected_chunks) - set(received_chunks)
        return False, f"Missing chunks: {sorted(missing)}"
    
    user_upload_folder = get_user_upload_folder(username)
    category_path = os.path.join(user_upload_folder, secure_filename(category))
    os.makedirs(category_path, exist_ok=True)
    
    final_path = os.path.join(category_path, secure_filename(final_filename))
    
    with open(final_path, 'wb') as outfile:
        for i in range(total_chunks):
            chunk_path = os.path.join(chunk_dir, f'chunk_{i}.part')
            with open(chunk_path, 'rb') as infile:
                shutil.copyfileobj(infile, outfile)
    
    shutil.rmtree(chunk_dir)
    
    return True, final_path

def cleanup_old_chunks():
    if not os.path.exists(app.config['CHUNKS_FOLDER']):
        return 0
    
    retention_seconds = app.config['CHUNK_RETENTION_HOURS'] * 3600
    current_time = time.time()
    cleaned_count = 0
    
    for username in os.listdir(app.config['CHUNKS_FOLDER']):
        user_chunks_dir = os.path.join(app.config['CHUNKS_FOLDER'], username)
        if not os.path.isdir(user_chunks_dir):
            continue
            
        for file_id in os.listdir(user_chunks_dir):
            chunk_dir = os.path.join(user_chunks_dir, file_id)
            if not os.path.isdir(chunk_dir):
                continue
            
            metadata_path = os.path.join(chunk_dir, 'metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                upload_start_time = metadata.get('upload_start_time', 0)
                
                if current_time - upload_start_time > retention_seconds:
                    shutil.rmtree(chunk_dir)
                    cleaned_count += 1
    
    return cleaned_count

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "User already exists"}), 400
    
    new_user = User(username=data['username'])
    new_user.set_password(data['password'])
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Invalid username or password"}), 401
    
    access_token = create_access_token(identity=user.username)
    return jsonify({
        "access_token": access_token,
        "user": user.to_dict()
    }), 200

@app.route('/status/me', methods=['GET'])
@jwt_required()
def get_user_status():
    username = get_jwt_identity()
    user = User.query.filter_by(username=username).first()
    return jsonify(user.to_dict()), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "upload_folder": UPLOAD_FOLDER}), 200

# Simple upload endpoint is disabled. Use /upload/chunked instead.

@app.route('/upload/chunked', methods=['POST'])
@jwt_required()
def upload_chunk():
    username = get_jwt_identity()
    required_fields = ['chunk', 'filename', 'chunk_index', 'total_chunks', 'file_id', 'checksum']
    
    if 'chunk' not in request.files:
        return jsonify({"error": "No chunk file provided"}), 400
    
    for field in ['filename', 'chunk_index', 'total_chunks', 'file_id', 'checksum']:
        if field not in request.form:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    chunk_file = request.files['chunk']
    filename = request.form['filename']
    chunk_index = int(request.form['chunk_index'])
    total_chunks = int(request.form['total_chunks'])
    file_id = request.form['file_id']
    checksum = request.form['checksum']
    category = request.form.get('category', 'general')
    
    if chunk_index < 0 or chunk_index >= total_chunks:
        return jsonify({"error": f"Invalid chunk_index: {chunk_index} (total_chunks: {total_chunks})"}), 400
    
    chunk_data = chunk_file.read()
    
    metadata = load_chunk_metadata(file_id, username)
    if metadata is None:
        save_chunk_metadata(file_id, filename, category, total_chunks, username)
    
    success, result = save_chunk(file_id, chunk_index, chunk_data, checksum, username)
    
    if not success:
        return jsonify({"error": result}), 400
    
    received_chunks = get_received_chunks(file_id, username)
    
    return jsonify({
        "message": f"Chunk {chunk_index}/{total_chunks - 1} uploaded successfully",
        "chunk_index": chunk_index,
        "received_chunks": received_chunks,
        "total_chunks": total_chunks,
        "progress": f"{len(received_chunks)}/{total_chunks}",
        "complete": len(received_chunks) == total_chunks
    }), 200

@app.route('/upload/status/<file_id>', methods=['GET'])
@jwt_required()
def upload_status(file_id):
    username = get_jwt_identity()
    metadata = load_chunk_metadata(file_id, username)
    
    if metadata is None:
        return jsonify({
            "exists": False,
            "received_chunks": [],
            "total_chunks": 0
        }), 200
    
    received_chunks = get_received_chunks(file_id, username)
    
    return jsonify({
        "exists": True,
        "filename": metadata['filename'],
        "category": metadata['category'],
        "total_chunks": metadata['total_chunks'],
        "received_chunks": received_chunks,
        "progress": f"{len(received_chunks)}/{metadata['total_chunks']}",
        "complete": len(received_chunks) == metadata['total_chunks']
    }), 200

@app.route('/upload/merge/<file_id>', methods=['POST'])
@jwt_required()
def merge_upload(file_id):
    username = get_jwt_identity()
    metadata = load_chunk_metadata(file_id, username)
    
    if metadata is None:
        return jsonify({"error": "Upload not found"}), 404
    
    success, result = merge_chunks(
        file_id,
        metadata['total_chunks'],
        metadata['filename'],
        metadata['category'],
        username
    )
    
    if not success:
        return jsonify({"error": result}), 400
    
    file_metadata = get_file_metadata(result)
    file_metadata['category'] = metadata['category']
    
    return jsonify({
        "message": f"File {metadata['filename']} merged successfully",
        "metadata": file_metadata
    }), 201

@app.route('/upload/cleanup', methods=['POST'])
@jwt_required()
def cleanup_chunks():
    cleaned_count = cleanup_old_chunks()
    return jsonify({
        "message": f"Cleaned up {cleaned_count} incomplete upload(s)",
        "count": cleaned_count
    }), 200

@app.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    username = get_jwt_identity()
    category = request.args.get('category')
    user_upload_folder = get_user_upload_folder(username)
    
    if category:
        category = secure_filename(category)
        category_path = os.path.join(user_upload_folder, category)
        if not os.path.exists(category_path):
            return jsonify({"error": "Category not found"}), 404
        
        files = []
        for filename in os.listdir(category_path):
            filepath = os.path.join(category_path, filename)
            if os.path.isfile(filepath):
                metadata = get_file_metadata(filepath)
                metadata['category'] = category
                files.append(metadata)
        
        return jsonify({"category": category, "files": files}), 200
    else:
        all_files = []
        for category_name in os.listdir(user_upload_folder):
            category_path = os.path.join(user_upload_folder, category_name)
            if os.path.isdir(category_path):
                for filename in os.listdir(category_path):
                    filepath = os.path.join(category_path, filename)
                    if os.path.isfile(filepath):
                        metadata = get_file_metadata(filepath)
                        metadata['category'] = category_name
                        all_files.append(metadata)
        
        return jsonify({"files": all_files, "total": len(all_files)}), 200

@app.route('/categories', methods=['GET'])
@jwt_required()
def list_categories():
    username = get_jwt_identity()
    user_upload_folder = get_user_upload_folder(username)
    
    categories = []
    if os.path.exists(user_upload_folder):
        for item in os.listdir(user_upload_folder):
            item_path = os.path.join(user_upload_folder, item)
            if os.path.isdir(item_path):
                file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                categories.append({
                    "name": item,
                    "file_count": file_count
                })
    
    return jsonify({"categories": categories, "total": len(categories)}), 200

@app.route('/download/<category>/<filename>', methods=['GET'])
@jwt_required()
def download_file(category, filename):
    username = get_jwt_identity()
    category = secure_filename(category)
    filename = secure_filename(filename)
    user_upload_folder = get_user_upload_folder(username)
    category_path = os.path.join(user_upload_folder, category)
    
    if not os.path.exists(os.path.join(category_path, filename)):
        return jsonify({"error": "File not found"}), 404
    
    return send_from_directory(category_path, filename, as_attachment=True)

@app.route('/metadata/<category>/<filename>', methods=['GET'])
@jwt_required()
def file_metadata(category, filename):
    username = get_jwt_identity()
    category = secure_filename(category)
    filename = secure_filename(filename)
    user_upload_folder = get_user_upload_folder(username)
    filepath = os.path.join(user_upload_folder, category, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    
    metadata = get_file_metadata(filepath)
    metadata['category'] = category
    
    return jsonify(metadata), 200

@app.route('/delete/<category>/<filename>', methods=['DELETE'])
@jwt_required()
def delete_file(category, filename):
    username = get_jwt_identity()
    category = secure_filename(category)
    filename = secure_filename(filename)
    user_upload_folder = get_user_upload_folder(username)
    filepath = os.path.join(user_upload_folder, category, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    
    file_size = os.path.getsize(filepath)
    os.remove(filepath)
    
    # Update quota
    user = User.query.filter_by(username=username).first()
    user.used_bytes = max(0, user.used_bytes - file_size)
    db.session.commit()
    
    category_path = os.path.join(user_upload_folder, category)
    if os.path.exists(category_path) and not os.listdir(category_path):
        os.rmdir(category_path)
    
    return jsonify({"message": f"File {filename} deleted successfully"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
