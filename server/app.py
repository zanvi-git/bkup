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
app.config['API_KEY'] = os.getenv('API_KEY', 'default-secret-key-change-me')
app.config['CHUNK_RETENTION_HOURS'] = 24

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != app.config['API_KEY']:
            return jsonify({"error": "Unauthorized: Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

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

def get_chunk_directory(file_id):
    file_id = secure_filename(file_id)
    chunk_dir = os.path.join(app.config['CHUNKS_FOLDER'], file_id)
    os.makedirs(chunk_dir, exist_ok=True)
    return chunk_dir

def get_metadata_path(file_id):
    chunk_dir = get_chunk_directory(file_id)
    return os.path.join(chunk_dir, 'metadata.json')

def save_chunk_metadata(file_id, filename, category, total_chunks):
    metadata = {
        'filename': filename,
        'category': category,
        'total_chunks': total_chunks,
        'upload_start_time': time.time()
    }
    metadata_path = get_metadata_path(file_id)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f)

def load_chunk_metadata(file_id):
    metadata_path = get_metadata_path(file_id)
    if not os.path.exists(metadata_path):
        return None
    with open(metadata_path, 'r') as f:
        return json.load(f)

def save_chunk(file_id, chunk_index, chunk_data, expected_checksum):
    actual_checksum = hashlib.sha256(chunk_data).hexdigest()
    
    if actual_checksum != expected_checksum:
        return False, f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
    
    chunk_dir = get_chunk_directory(file_id)
    chunk_path = os.path.join(chunk_dir, f'chunk_{chunk_index}.part')
    
    with open(chunk_path, 'wb') as f:
        f.write(chunk_data)
    
    return True, actual_checksum

def get_received_chunks(file_id):
    chunk_dir = get_chunk_directory(file_id)
    if not os.path.exists(chunk_dir):
        return []
    
    chunks = []
    for filename in os.listdir(chunk_dir):
        if filename.startswith('chunk_') and filename.endswith('.part'):
            chunk_index = int(filename.replace('chunk_', '').replace('.part', ''))
            chunks.append(chunk_index)
    
    return sorted(chunks)

def merge_chunks(file_id, total_chunks, final_filename, category):
    chunk_dir = get_chunk_directory(file_id)
    
    received_chunks = get_received_chunks(file_id)
    expected_chunks = list(range(total_chunks))
    
    if received_chunks != expected_chunks:
        missing = set(expected_chunks) - set(received_chunks)
        return False, f"Missing chunks: {sorted(missing)}"
    
    category_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(category))
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
    
    for file_id in os.listdir(app.config['CHUNKS_FOLDER']):
        chunk_dir = os.path.join(app.config['CHUNKS_FOLDER'], file_id)
        if not os.path.isdir(chunk_dir):
            continue
        
        metadata_path = get_metadata_path(file_id)
        if os.path.exists(metadata_path):
            metadata = load_chunk_metadata(file_id)
            upload_start_time = metadata.get('upload_start_time', 0)
            
            if current_time - upload_start_time > retention_seconds:
                shutil.rmtree(chunk_dir)
                cleaned_count += 1
    
    return cleaned_count

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "upload_folder": UPLOAD_FOLDER}), 200

# Simple upload endpoint is disabled. Use /upload/chunked instead.

@app.route('/upload/chunked', methods=['POST'])
@require_api_key
def upload_chunk():
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
    
    metadata = load_chunk_metadata(file_id)
    if metadata is None:
        save_chunk_metadata(file_id, filename, category, total_chunks)
    
    success, result = save_chunk(file_id, chunk_index, chunk_data, checksum)
    
    if not success:
        return jsonify({"error": result}), 400
    
    received_chunks = get_received_chunks(file_id)
    
    return jsonify({
        "message": f"Chunk {chunk_index}/{total_chunks - 1} uploaded successfully",
        "chunk_index": chunk_index,
        "received_chunks": received_chunks,
        "total_chunks": total_chunks,
        "progress": f"{len(received_chunks)}/{total_chunks}",
        "complete": len(received_chunks) == total_chunks
    }), 200

@app.route('/upload/status/<file_id>', methods=['GET'])
@require_api_key
def upload_status(file_id):
    metadata = load_chunk_metadata(file_id)
    
    if metadata is None:
        return jsonify({
            "exists": False,
            "received_chunks": [],
            "total_chunks": 0
        }), 200
    
    received_chunks = get_received_chunks(file_id)
    
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
@require_api_key
def merge_upload(file_id):
    metadata = load_chunk_metadata(file_id)
    
    if metadata is None:
        return jsonify({"error": "Upload not found"}), 404
    
    success, result = merge_chunks(
        file_id,
        metadata['total_chunks'],
        metadata['filename'],
        metadata['category']
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
@require_api_key
def cleanup_chunks():
    cleaned_count = cleanup_old_chunks()
    return jsonify({
        "message": f"Cleaned up {cleaned_count} incomplete upload(s)",
        "count": cleaned_count
    }), 200

@app.route('/files', methods=['GET'])
@require_api_key
def list_files():
    category = request.args.get('category')
    
    if category:
        category = secure_filename(category)
        category_path = os.path.join(app.config['UPLOAD_FOLDER'], category)
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
        for category_name in os.listdir(app.config['UPLOAD_FOLDER']):
            category_path = os.path.join(app.config['UPLOAD_FOLDER'], category_name)
            if os.path.isdir(category_path):
                for filename in os.listdir(category_path):
                    filepath = os.path.join(category_path, filename)
                    if os.path.isfile(filepath):
                        metadata = get_file_metadata(filepath)
                        metadata['category'] = category_name
                        all_files.append(metadata)
        
        return jsonify({"files": all_files, "total": len(all_files)}), 200

@app.route('/categories', methods=['GET'])
@require_api_key
def list_categories():
    categories = []
    for item in os.listdir(app.config['UPLOAD_FOLDER']):
        item_path = os.path.join(app.config['UPLOAD_FOLDER'], item)
        if os.path.isdir(item_path):
            file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
            categories.append({
                "name": item,
                "file_count": file_count
            })
    
    return jsonify({"categories": categories, "total": len(categories)}), 200

@app.route('/download/<category>/<filename>', methods=['GET'])
@require_api_key
def download_file(category, filename):
    category = secure_filename(category)
    filename = secure_filename(filename)
    category_path = os.path.join(app.config['UPLOAD_FOLDER'], category)
    
    if not os.path.exists(os.path.join(category_path, filename)):
        return jsonify({"error": "File not found"}), 404
    
    return send_from_directory(category_path, filename, as_attachment=True)

@app.route('/metadata/<category>/<filename>', methods=['GET'])
@require_api_key
def file_metadata(category, filename):
    category = secure_filename(category)
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], category, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    
    metadata = get_file_metadata(filepath)
    metadata['category'] = category
    
    return jsonify(metadata), 200

@app.route('/delete/<category>/<filename>', methods=['DELETE'])
@require_api_key
def delete_file(category, filename):
    category = secure_filename(category)
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], category, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    
    os.remove(filepath)
    
    category_path = os.path.join(app.config['UPLOAD_FOLDER'], category)
    if os.path.exists(category_path) and not os.listdir(category_path):
        os.rmdir(category_path)
    
    return jsonify({"message": f"File {filename} deleted successfully"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
