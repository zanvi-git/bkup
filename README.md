# Phone Backup Cloud System

This is a backend service that serves as a receiver for data packages from clients(much like a cloud storage). It exposes a REST API to receive data. the data is received in chunks for pause/resume features.

## Features

- **Secured API**: All endpoints are protected via `X-API-Key` headers.
- **Unified Chunked Uploads**: Exclusive use of resumable, chunked uploads with SHA-256 checksum verification for high reliability.

---

## 📂 Project Structure

- **`/server`**: Flask-based Python backend. Handles file storage, chunk merging, metadata extraction, and authentication.
- **`/app`**: check out: https://github.com/zanvi-git/app
- **`/uploads`**: (Generated) Directory where the server stores uploaded files and temporary chunks.

---

## 🛠️ Getting Started

### 1. Server Setup
```bash
cd server
pip install -r requirements.txt
# Configure your .env file with API_KEY
python app.py
```
> [!NOTE]
> For production, the backend is expected at `https://bkup.onrender.com`.

## 2. Test Server
You can test the server using the `test.py` file. 
```bash
cd server
python test.py #make sure to change the base url and update api key
```
---

## Server Routes

1. /register - register a new user
2. /login - login as an existing user
3. /status/me - get user status
4. /health - ping server
5. /upload/chunked - upload files (must use the client-side script for uploading)
6. /upload/status/<file_id> - check file chunk/status
7. /upload/merge/<file_id> - merge chunks of file
8. /upload/cleanup - remove chunks of incomplete uploads
9. /files - check current user's files
10. /categories - file categories
11. /download/<category>/<filename> - download file from server
12. /metadata/<category>/<filename> - fetch file's metadata
13. /delete/<category>/<filename> - delete a file

With love.