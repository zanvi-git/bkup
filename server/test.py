import requests
import os
import time
import hashlib
import uuid
from upload_client import ChunkedUploadClient

BASE_URL = "http://localhost:5000"
API_KEY = "test-api-key-12345"

def create_test_file(filename, size_mb):
    size_bytes = size_mb * 1024 * 1024
    with open(filename, 'wb') as f:
        chunk_size = 1024 * 1024
        remaining = size_bytes
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            f.write(os.urandom(write_size))
            remaining -= write_size
    return filename

def test_health():
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print(f"[PASS] Health check: {response.json()}")
            return True
        else:
            print(f"[FAIL] Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Health check exception: {e}")
        return False

def test_upload_with_category():
    test_files = [
        ("test_photo.txt", "photos", "This is a test photo file."),
        ("test_doc.txt", "documents", "This is a test document."),
        ("test_video.txt", "videos", "This is a test video file."),
        ("test_general.txt", "general", "This is a general file.")
    ]
    
    for filename, category, content in test_files:
        with open(filename, 'w') as f:
            f.write(content)
        
        try:
            client = ChunkedUploadClient(BASE_URL, API_KEY, chunk_size=1024) # Use small chunks for small test files
            result = client.upload_file(filename, category=category)
            
            if result and 'metadata' in result:
                print(f"[PASS] Upload {filename} to category '{category}': {result['message']}")
            else:
                print(f"[FAIL] Upload {filename} failed: {result}")
                return False
        except Exception as e:
            print(f"[FAIL] Upload {filename} exception: {e}")
            return False
        finally:
            if os.path.exists(filename):
                os.remove(filename)
    
    return True

def test_list_files():
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/files", headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'files' in data:
                total = data.get('total', len(data['files']))
                print(f"[PASS] List all files: Found {total} files")
                for file_info in data['files'][:5]:
                    print(f"  - {file_info['category']}/{file_info['filename']} ({file_info['size_human']})")
                return True
            else:
                print(f"[FAIL] Unexpected response format: {data}")
                return False
        else:
            print(f"[FAIL] List files failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] List files exception: {e}")
        return False

def test_list_files_by_category():
    category = "photos"
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/files?category={category}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"[PASS] List files in '{category}': Found {len(data['files'])} files")
            return True
        else:
            print(f"[FAIL] List files by category failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] List files by category exception: {e}")
        return False

def test_list_categories():
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/categories", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"[PASS] List categories: Found {data['total']} categories")
            for cat in data['categories']:
                print(f"  - {cat['name']}: {cat['file_count']} files")
            return True
        else:
            print(f"[FAIL] List categories failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] List categories exception: {e}")
        return False

def test_metadata():
    category = "photos"
    filename = "test_photo.txt"
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/metadata/{category}/{filename}", headers=headers)
        if response.status_code == 200:
            metadata = response.json()
            print(f"[PASS] Get metadata for {category}/{filename}:")
            print(f"  Size: {metadata['size_human']}, Modified: {metadata['modified']}")
            return True
        else:
            print(f"[FAIL] Get metadata failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Get metadata exception: {e}")
        return False

def test_download():
    category = "documents"
    filename = "test_doc.txt"
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/download/{category}/{filename}", headers=headers)
        if response.status_code == 200:
            print(f"[PASS] Download {category}/{filename}: {len(response.content)} bytes")
            return True
        else:
            print(f"[FAIL] Download failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Download exception: {e}")
        return False

def test_delete_without_auth():
    category = "videos"
    filename = "test_video.txt"
    try:
        response = requests.delete(f"{BASE_URL}/delete/{category}/{filename}")
        if response.status_code == 401:
            print(f"[PASS] Delete without auth correctly rejected: {response.json()['error']}")
            return True
        else:
            print(f"[FAIL] Delete without auth should have failed with 401")
            return False
    except Exception as e:
        print(f"[FAIL] Delete without auth exception: {e}")
        return False

def test_delete_with_auth():
    category = "videos"
    filename = "test_video.txt"
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.delete(f"{BASE_URL}/delete/{category}/{filename}", headers=headers)
        if response.status_code == 200:
            print(f"[PASS] Delete with auth: {response.json()['message']}")
            return True
        else:
            print(f"[FAIL] Delete with auth failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Delete with auth exception: {e}")
        return False

def test_chunked_upload_small_file():
    filename = "test_small_chunked.bin"
    try:
        create_test_file(filename, 1)
        
        client = ChunkedUploadClient(BASE_URL, API_KEY, chunk_size=4 * 1024 * 1024)
        result = client.upload_file(filename, category="test_chunked")
        
        if result and 'metadata' in result:
            print(f"[PASS] Small file chunked upload: {result['message']}")
            return True
        else:
            print(f"[FAIL] Small file chunked upload failed: {result}")
            return False
    except Exception as e:
        print(f"[FAIL] Small file chunked upload exception: {e}")
        return False
    finally:
        if os.path.exists(filename):
            os.remove(filename)

def test_chunked_upload_large_file():
    filename = "test_large_chunked.bin"
    try:
        create_test_file(filename, 12)
        
        client = ChunkedUploadClient(BASE_URL, API_KEY, chunk_size=4 * 1024 * 1024)
        result = client.upload_file(filename, category="test_chunked")
        
        if result and 'metadata' in result:
            print(f"[PASS] Large file chunked upload: {result['message']}")
            if result['metadata']['size_bytes'] == 12 * 1024 * 1024:
                print(f"  File size verified: {result['metadata']['size_human']}")
                return True
            else:
                print(f"[FAIL] File size mismatch: expected 12 MB, got {result['metadata']['size_human']}")
                return False
        else:
            print(f"[FAIL] Large file chunked upload failed: {result}")
            return False
    except Exception as e:
        print(f"[FAIL] Large file chunked upload exception: {e}")
        return False
    finally:
        if os.path.exists(filename):
            os.remove(filename)

def test_chunked_upload_resume():
    filename = "test_resume.bin"
    file_id = f"resume_test_{uuid.uuid4().hex}"
    
    try:
        create_test_file(filename, 8)
        chunk_size = 4 * 1024 * 1024
        
        with open(filename, 'rb') as f:
            chunk_data = f.read(chunk_size)
            checksum = hashlib.sha256(chunk_data).hexdigest()
            
            files = {'chunk': ('chunk_0', chunk_data)}
            data = {
                'filename': os.path.basename(filename),
                'chunk_index': 0,
                'total_chunks': 2,
                'file_id': file_id,
                'category': 'test_chunked',
                'checksum': checksum
            }
            
            headers = {'X-API-Key': API_KEY}
            response = requests.post(f"{BASE_URL}/upload/chunked", files=files, data=data, headers=headers)
            
            if response.status_code != 200:
                print(f"[FAIL] First chunk upload failed: {response.text}")
                return False
        
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/upload/status/{file_id}", headers=headers)
        if response.status_code == 200:
            status = response.json()
            if status['received_chunks'] == [0]:
                print(f"  Partial upload verified: {status['progress']}")
            else:
                print(f"[FAIL] Unexpected received chunks: {status['received_chunks']}")
                return False
        else:
            print(f"[FAIL] Status check failed: {response.text}")
            return False
        
        client = ChunkedUploadClient(BASE_URL, API_KEY, chunk_size=chunk_size)
        result = client.upload_file(filename, category="test_chunked", file_id=file_id)
        
        if result and 'metadata' in result:
            print(f"[PASS] Resume upload successful: {result['message']}")
            return True
        else:
            print(f"[FAIL] Resume upload failed: {result}")
            return False
    except Exception as e:
        print(f"[FAIL] Resume upload exception: {e}")
        return False
    finally:
        if os.path.exists(filename):
            os.remove(filename)

def test_upload_status_endpoint():
    try:
        file_id = "non_existent_upload"
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f"{BASE_URL}/upload/status/{file_id}", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if not data['exists'] and data['received_chunks'] == []:
                print(f"[PASS] Status endpoint for non-existent upload: {data}")
                return True
            else:
                print(f"[FAIL] Unexpected status response: {data}")
                return False
        else:
            print(f"[FAIL] Status endpoint failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Status endpoint exception: {e}")
        return False

def test_invalid_checksum():
    filename = "test_invalid_checksum.bin"
    try:
        create_test_file(filename, 1)
        
        with open(filename, 'rb') as f:
            chunk_data = f.read()
            wrong_checksum = "0" * 64
            
            files = {'chunk': ('chunk_0', chunk_data)}
            data = {
                'filename': os.path.basename(filename),
                'chunk_index': 0,
                'total_chunks': 1,
                'file_id': f"invalid_test_{uuid.uuid4().hex}",
                'category': 'test_chunked',
                'checksum': wrong_checksum
            }
            
            headers = {'X-API-Key': API_KEY}
            response = requests.post(f"{BASE_URL}/upload/chunked", files=files, data=data, headers=headers)
            
            if response.status_code == 400 and 'Checksum mismatch' in response.text:
                print(f"[PASS] Invalid checksum correctly rejected: {response.json()['error']}")
                return True
            else:
                print(f"[FAIL] Invalid checksum should have been rejected")
                return False
    except Exception as e:
        print(f"[FAIL] Invalid checksum test exception: {e}")
        return False
    finally:
        if os.path.exists(filename):
            os.remove(filename)

def test_cleanup_old_chunks():
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.post(f"{BASE_URL}/upload/cleanup", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"[PASS] Cleanup endpoint: {data['message']}")
            return True
        else:
            print(f"[FAIL] Cleanup endpoint failed: {response.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Cleanup endpoint exception: {e}")
        return False

def main():
    print("="*60)
    print("Flask Backup Server - Enhanced Features Test Suite")
    print("="*60)
    print("\nWaiting for server to be ready...")
    time.sleep(2)
    
    tests = [
        ("Health Check", test_health),
        ("Upload Files with Categories", test_upload_with_category),
        ("List All Files", test_list_files),
        ("List Files by Category", test_list_files_by_category),
        ("List Categories", test_list_categories),
        ("Get File Metadata", test_metadata),
        ("Download File", test_download),
        ("Delete Without Auth", test_delete_without_auth),
        ("Delete With Auth", test_delete_with_auth),
        ("Chunked Upload - Small File", test_chunked_upload_small_file),
        ("Chunked Upload - Large File", test_chunked_upload_large_file),
        ("Chunked Upload - Resume Capability", test_chunked_upload_resume),
        ("Upload Status Endpoint", test_upload_status_endpoint),
        ("Invalid Checksum Rejection", test_invalid_checksum),
        ("Cleanup Old Chunks", test_cleanup_old_chunks),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit(main())
