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

---

With love.