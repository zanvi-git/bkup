import os
import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, '..', 'uploads')  # One level up from server/ folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max limit
app.config['API_KEY'] = os.getenv('API_KEY', 'default-secret-key-change-me')

# Authentication decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != app.config['API_KEY']:
            return jsonify({"error": "Unauthorized: Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Helper function to get file metadata
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
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "upload_folder": UPLOAD_FOLDER}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Get category (default: 'general')
    category = request.form.get('category', 'general')
    category = secure_filename(category)
    
    # Create category folder
    category_path = os.path.join(app.config['UPLOAD_FOLDER'], category)
    os.makedirs(category_path, exist_ok=True)
    
    filename = secure_filename(file.filename)
    save_path = os.path.join(category_path, filename)
    file.save(save_path)
    
    # Get metadata
    metadata = get_file_metadata(save_path)
    metadata['category'] = category
    
    return jsonify({
        "message": f"File {filename} uploaded successfully",
        "metadata": metadata
    }), 201

@app.route('/files', methods=['GET'])
def list_files():
    category = request.args.get('category')
    
    if category:
        # List files in specific category
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
        # List all files with their categories
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
def download_file(category, filename):
    category = secure_filename(category)
    filename = secure_filename(filename)
    category_path = os.path.join(app.config['UPLOAD_FOLDER'], category)
    
    if not os.path.exists(os.path.join(category_path, filename)):
        return jsonify({"error": "File not found"}), 404
    
    return send_from_directory(category_path, filename, as_attachment=True)

@app.route('/metadata/<category>/<filename>', methods=['GET'])
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
    
    # Remove category folder if empty
    category_path = os.path.join(app.config['UPLOAD_FOLDER'], category)
    if os.path.exists(category_path) and not os.listdir(category_path):
        os.rmdir(category_path)
    
    return jsonify({"message": f"File {filename} deleted successfully"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
