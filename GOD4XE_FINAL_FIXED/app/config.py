import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = APP_DIR / "static" / "uploads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "god4xe-super-secret-key-" + secrets.token_hex(16))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
PORT = int(os.getenv("PORT", 8000))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL and ENVIRONMENT == "production":
    raise RuntimeError(
        "CRITICAL: DATABASE_URL environment variable is missing in production. "
        "Please configure your Render PostgreSQL instance connection string."
    )

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg", "pdf"}

JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = int(os.getenv("JWT_EXPIRATION_DAYS", 30))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "mock").strip().lower()
WITHDRAWALS_ENABLED = os.getenv("WITHDRAWALS_ENABLED", "false").strip().lower() in ("true", "1")

ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_TOURNAMENT_ADMIN = "TOURNAMENT_ADMIN"
ROLE_FINANCE_ADMIN = "FINANCE_ADMIN"
ROLE_SUPPORT_ADMIN = "SUPPORT_ADMIN"

ALL_ADMIN_ROLES = [
    ROLE_SUPER_ADMIN,
    ROLE_TOURNAMENT_ADMIN,
    ROLE_FINANCE_ADMIN,
    ROLE_SUPPORT_ADMIN
]
