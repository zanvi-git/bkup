import requests
import os

BASE_URL = "http://localhost:5000"

def test_auth_logic():
    print(f"Testing with key from test_server.py: test-api-key-12345")
    headers = {'X-API-Key': 'test-api-key-12345'}
    resp = requests.delete(f"{BASE_URL}/delete/test/test", headers=headers)
    print(f"Status Code: {resp.status_code}")
    if resp.status_code != 404: # expect 404 if auth passes but file missing
        print(f"Body: {resp.json()}")

    print(f"\nTesting /files with incorrect key: WRONG-KEY")
    headers = {'X-API-Key': 'WRONG-KEY'}
    resp = requests.get(f"{BASE_URL}/files", headers=headers)
    print(f"Status Code: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Success! (This is bad if auth should be required)")

if __name__ == "__main__":
    test_auth_logic()
