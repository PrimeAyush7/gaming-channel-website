import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = APP_DIR / "static" / "uploads"

# Ensure essential directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "god4xe-super-secret-key-" + secrets.token_hex(16))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
PORT = int(os.getenv("PORT", 8000))

# PostgreSQL Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Normalize Render's postgres:// scheme to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# In production, fail with a clear useful error if DATABASE_URL is missing
if not DATABASE_URL and ENVIRONMENT == "production":
    raise RuntimeError(
        "CRITICAL: DATABASE_URL environment variable is missing in production. "
        "Please configure your Render PostgreSQL instance connection string."
    )

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 5 * 1024 * 1024))  # 5 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
