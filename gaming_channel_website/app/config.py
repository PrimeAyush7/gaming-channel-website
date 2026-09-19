import os
import sqlite3
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = APP_DIR / "static" / "uploads"

# Ensure essential directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "nexus-super-secret-key-" + secrets.token_hex(16))

# Database configuration: Native SQLite (Fast, zero-configuration, robust)
_env_db_path = os.getenv("DATABASE_PATH")
_env_db_url = os.getenv("DATABASE_URL")
if _env_db_path:
    DATABASE_PATH = _env_db_path
elif _env_db_url and _env_db_url.startswith("sqlite:///"):
    DATABASE_PATH = _env_db_url.replace("sqlite:///", "", 1)
else:
    _candidate = str(DATA_DIR / "site.db")
    try:
        _test_conn = sqlite3.connect(_candidate, timeout=1.0)
        _test_conn.execute("CREATE TABLE IF NOT EXISTS _fs_test (id INT);")
        _test_conn.close()
        DATABASE_PATH = _candidate
    except Exception:
        DATABASE_PATH = "/tmp/nexus_gaming.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
PORT = int(os.getenv("PORT", 8000))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 5 * 1024 * 1024))  # 5 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
