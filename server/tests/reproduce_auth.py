import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5000"
# Use the key from .env if available, otherwise default
API_KEY = os.getenv('API_KEY', 'test-api-key-1234')

def test_endpoint(name, method, path, headers=None, data=None, files=None):
    url = f"{BASE_URL}{path}"
    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers)
        elif method == 'POST':
            resp = requests.post(url, headers=headers, data=data, files=files)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=headers)
        
        print(f"Testing {name} ({path}): Status {resp.status_code}")
        return resp
    except Exception as e:
        print(f"Error testing {name}: {e}")
        return None

def reproduce():
    print(f"--- Reproducing Auth Issue ---")
    print(f"Expected API_KEY: {API_KEY}")

    bad_headers = {'X-API-Key': 'WRONG-KEY'}
    good_headers = {'X-API-Key': API_KEY}

    # 1. Test a route that is currently protected (/delete) with a WRONG key
    print(f"\n1. Testing /delete with WRONG key:")
    test_endpoint("Delete (Wrong Key)", 'DELETE', '/delete/test/test', headers=bad_headers)

    # 2. Test a route that is currently UNPROTECTED (/files) with a WRONG key
    print(f"\n2. Testing /files with WRONG key (expected to pass currently):")
    test_endpoint("List Files (Wrong Key)", 'GET', '/files', headers=bad_headers)

    # 3. Test /health (should stay public)
    print(f"\n3. Testing /health (Public):")
    test_endpoint("Health", 'GET', '/health')

if __name__ == "__main__":
    reproduce()
