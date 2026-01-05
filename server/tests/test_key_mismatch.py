import requests

BASE_URL = "http://localhost:5000"

def test_key(key):
    headers = {'X-API-Key': key}
    resp = requests.delete(f"{BASE_URL}/delete/test/test", headers=headers)
    print(f"Key: [{key}] -> Status: {resp.status_code}")

if __name__ == "__main__":
    # Test with the key that should work
    test_key("test-api-key-1234")
    # Test with the key that I thought worked
    test_key("test-api-key-12345")
    # Test with a definitely wrong key
    test_key("WRONG")
