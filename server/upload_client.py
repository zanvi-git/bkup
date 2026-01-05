import os
import hashlib
import requests
import time
import uuid
from typing import Callable, Optional

class ChunkedUploadClient:
    def __init__(self, base_url: str, chunk_size: int = 4 * 1024 * 1024):
        self.base_url = base_url.rstrip('/')
        self.chunk_size = chunk_size
        self.session = requests.Session()
        self.access_token = None
    
    def set_token(self, token: str):
        self.access_token = token
        self.session.headers['Authorization'] = f'Bearer {self.access_token}'

    def register(self, username, password):
        response = self.session.post(f"{self.base_url}/register", json={
            "username": username,
            "password": password
        })
        response.raise_for_status()
        return response.json()

    def login(self, username, password):
        response = self.session.post(f"{self.base_url}/login", json={
            "username": username,
            "password": password
        })
        response.raise_for_status()
        data = response.json()
        self.set_token(data['access_token'])
        return data
    
    def upload_file(
        self,
        filepath: str,
        category: str = 'general',
        file_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> dict:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if file_id is None:
            file_id = f"{uuid.uuid4().hex}_{int(time.time())}"
        
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        print(f"Uploading {filename} ({self._format_bytes(file_size)}) in {total_chunks} chunk(s)")
        
        received_chunks = self._check_resume(file_id)
        if received_chunks:
            print(f"Resuming upload: {len(received_chunks)}/{total_chunks} chunks already uploaded")
        
        with open(filepath, 'rb') as f:
            for chunk_index in range(total_chunks):
                if chunk_index in received_chunks:
                    if progress_callback:
                        progress_callback(chunk_index, total_chunks, (chunk_index + 1) / total_chunks * 100)
                    continue
                
                f.seek(chunk_index * self.chunk_size)
                chunk_data = f.read(self.chunk_size)
                
                checksum = self._calculate_checksum(chunk_data)
                
                self._upload_chunk_with_retry(
                    chunk_data=chunk_data,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    file_id=file_id,
                    filename=filename,
                    category=category,
                    checksum=checksum
                )
                
                if progress_callback:
                    progress_callback(chunk_index, total_chunks, (chunk_index + 1) / total_chunks * 100)
                
                print(f"  Uploaded chunk {chunk_index + 1}/{total_chunks} ({self._format_bytes(len(chunk_data))})")
        
        print(f"Merging {total_chunks} chunks...")
        response = self._merge_file(file_id)
        
        print(f"Upload complete: {response['message']}")
        return response
    
    def _check_resume(self, file_id: str) -> list:
        try:
            response = self.session.get(f"{self.base_url}/upload/status/{file_id}")
            response.raise_for_status()
            data = response.json()
            
            if data.get('exists'):
                return data.get('received_chunks', [])
            
            return []
        except requests.RequestException:
            return []
    
    def _upload_chunk_with_retry(
        self,
        chunk_data: bytes,
        chunk_index: int,
        total_chunks: int,
        file_id: str,
        filename: str,
        category: str,
        checksum: str,
        max_retries: int = 3
    ):
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                files = {'chunk': (f'chunk_{chunk_index}', chunk_data)}
                data = {
                    'filename': filename,
                    'chunk_index': chunk_index,
                    'total_chunks': total_chunks,
                    'file_id': file_id,
                    'category': category,
                    'checksum': checksum
                }
                
                response = self.session.post(
                    f"{self.base_url}/upload/chunked",
                    files=files,
                    data=data,
                    timeout=60
                )
                response.raise_for_status()
                
                return response.json()
            
            except requests.RequestException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  Retry {attempt + 1}/{max_retries} after {wait_time}s due to: {e}")
                    time.sleep(wait_time)
        
        raise last_exception
    
    def _merge_file(self, file_id: str) -> dict:
        response = self.session.post(f"{self.base_url}/upload/merge/{file_id}")
        response.raise_for_status()
        return response.json()
    
    def _calculate_checksum(self, chunk_data: bytes) -> str:
        return hashlib.sha256(chunk_data).hexdigest()
    
    def _format_bytes(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

if __name__ == '__main__':
    client = ChunkedUploadClient(
        base_url="http://localhost:5000",
        api_key="test-api-key-12345",
        chunk_size=4 * 1024 * 1024
    )
    
    def on_progress(chunk_index, total_chunks, percentage):
        print(f"Progress: {percentage:.1f}% ({chunk_index + 1}/{total_chunks} chunks)")
    
    try:
        result = client.upload_file(
            filepath="test_large_file.bin",
            category="videos",
            progress_callback=on_progress
        )
        print(f"Success: {result}")
    except Exception as e:
        print(f"Upload failed: {e}")
