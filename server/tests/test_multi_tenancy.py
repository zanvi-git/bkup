import requests
import os
import time
import hashlib
import uuid
import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from upload_client import ChunkedUploadClient

BASE_URL = "http://localhost:5000"

class TestMultiTenancy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_a = ChunkedUploadClient(BASE_URL, chunk_size=1024*1024)
        cls.user_a = f"user_a_{uuid.uuid4().hex[:8]}"
        cls.pass_a = "password123"
        cls.client_a.register(cls.user_a, cls.pass_a)
        cls.client_a.login(cls.user_a, cls.pass_a)

        cls.client_b = ChunkedUploadClient(BASE_URL, chunk_size=1024*1024)
        cls.user_b = f"user_b_{uuid.uuid4().hex[:8]}"
        cls.pass_b = "password456"
        cls.client_b.register(cls.user_b, cls.pass_b)
        cls.client_b.login(cls.user_b, cls.pass_b)

    def test_user_isolation(self):
       
        filename = "secret_a.txt"
        with open(filename, "w") as f:
            f.write("User A's private content")
        
        self.client_a.upload_file(filename, category="private")
        files_b = self.client_b.session.get(f"{BASE_URL}/files").json()
        filenames_b = [f['filename'] for f in files_b.get('files', [])]
        self.assertNotIn(filename, filenames_b)

      
        resp = self.client_b.session.get(f"{BASE_URL}/download/private/{filename}")
        self.assertEqual(resp.status_code, 404)

        if os.path.exists(filename):
            os.remove(filename)

    def test_same_filename_collision(self):
        # Both users upload a file with the same name
        filename = "shared_name.txt"
        
        with open(filename, "w") as f:
            f.write("Content A")
        self.client_a.upload_file(filename, category="general")
        
        with open(filename, "w") as f:
            f.write("Content B")
        self.client_b.upload_file(filename, category="general")

       
        resp_a = self.client_a.session.get(f"{BASE_URL}/download/general/{filename}")
        self.assertEqual(resp_a.text, "Content A")

        
        resp_b = self.client_b.session.get(f"{BASE_URL}/download/general/{filename}")
        self.assertEqual(resp_b.text, "Content B")

        if os.path.exists(filename):
            os.remove(filename)

    def test_quota_enforcement(self):
        #create a fake qouta and try exceeding it
        username = self.user_a
        status_before = self.client_a.session.get(f"{BASE_URL}/status/me").json()
        used_before = status_before['used_bytes']

        filename = "quota_test.bin"
        size = 2 * 1024 * 1024 # 2MB
        with open(filename, "wb") as f:
            f.write(os.urandom(size))
        
        self.client_a.upload_file(filename, category="quota_test")
        
        status_after = self.client_a.session.get(f"{BASE_URL}/status/me").json()
        self.assertEqual(status_after['used_bytes'], used_before + size)

        # Delete and check quota again
        self.client_a.session.delete(f"{BASE_URL}/delete/quota_test/{filename}")
        status_final = self.client_a.session.get(f"{BASE_URL}/status/me").json()
        self.assertEqual(status_final['used_bytes'], used_before)

        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    unittest.main()
