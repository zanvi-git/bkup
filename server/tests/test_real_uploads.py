import os
import sys
from upload_client import ChunkedUploadClient
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5000"
API_KEY = os.getenv('API_KEY', 'test-api-key-12345')

def upload_real_files():
    # Files are in the parent directory
    parent_dir = os.path.join(os.getcwd(), '..')
    files_to_upload = [
        (os.path.join(parent_dir, "pic.jpg"), "photos"),
        (os.path.join(parent_dir, "vid.mp4"), "videos")
    ]
    
    client = ChunkedUploadClient(BASE_URL, API_KEY, chunk_size=4 * 1024 * 1024)
    
    for filepath, category in files_to_upload:
        if not os.path.exists(filepath):
            print(f"Error: File not found at {filepath}")
            continue
            
        print(f"\n--- Uploading {os.path.basename(filepath)} to {category} ---")
        try:
            result = client.upload_file(filepath, category=category)
            print(f"Success: {result['message']}")
            if 'metadata' in result:
                meta = result['metadata']
                print(f"Metadata: Size={meta['size_human']}, Category={meta['category']}")
        except Exception as e:
            print(f"Failed to upload {os.path.basename(filepath)}: {e}")

if __name__ == "__main__":
    upload_real_files()
