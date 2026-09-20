import os
import hashlib
import secrets
import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from app.database import get_db

HASH_ITERATIONS = 100_000

def hash_password(password: str) -> tuple[str, str]:
    """Generates salt and hashes password with PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        HASH_ITERATIONS
    )
    return dk.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verifies password in constant time."""
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        HASH_ITERATIONS
    )
    return secrets.compare_digest(dk.hex(), password_hash)

def check_login_rate_limit(ip_address: str) -> bool:
    """Returns True if request is allowed, False if IP is temporarily locked out."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT attempts, last_attempt FROM login_attempts WHERE ip_address = %s;", (ip_address,))
        row = cursor.fetchone()
        if not row:
            return True
        attempts = row["attempts"]
        last_attempt_val = row["last_attempt"]
        try:
            if isinstance(last_attempt_val, (datetime.datetime, datetime.date)):
                last_attempt = last_attempt_val
            else:
                last_attempt = datetime.datetime.fromisoformat(str(last_attempt_val).replace("Z", ""))
        except Exception:
            last_attempt = datetime.datetime.utcnow()

        if (datetime.datetime.utcnow() - last_attempt).total_seconds() > 900:
            cursor.execute("DELETE FROM login_attempts WHERE ip_address = %s;", (ip_address,))
            return True
        if attempts >= 5:
            return False
        return True

def record_failed_login(ip_address: str):
    """Increments failed login counter for IP."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO login_attempts (ip_address, attempts, last_attempt)
            VALUES (%s, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(ip_address) DO UPDATE SET
                attempts = login_attempts.attempts + 1,
                last_attempt = CURRENT_TIMESTAMP;
        """, (ip_address,))

def reset_failed_login(ip_address: str):
    """Resets failed login counter upon successful authentication."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login_attempts WHERE ip_address = %s;", (ip_address,))

def create_admin_user(username: str, password: str) -> int:
    """Creates a new admin user in the database."""
    pwd_hash, salt = hash_password(password)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admins (username, password_hash, salt)
            VALUES (%s, %s, %s)
            RETURNING id;
        """, (username.strip(), pwd_hash, salt))
        res = cursor.fetchone()
        return res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]

def authenticate_admin(username: str, password: str, ip_address: str = "127.0.0.1"):
    """Authenticates admin and returns admin record or None."""
    if not check_login_rate_limit(ip_address):
        return None, "Too many failed attempts. Please try again in 15 minutes."

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE username = %s;", (username.strip(),))
        admin = cursor.fetchone()

        if not admin:
            record_failed_login(ip_address)
            return None, "Invalid username or password."

        if not verify_password(password, admin["password_hash"], admin["salt"]):
            record_failed_login(ip_address)
            return None, "Invalid username or password."

        reset_failed_login(ip_address)
        cursor.execute("UPDATE admins SET last_login = CURRENT_TIMESTAMP WHERE id = %s;", (admin["id"],))
        return dict(admin), None

def create_session(admin_id: int) -> tuple[str, str]:
    """Generates session_id and csrf_token, saving them into DB."""
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (session_id, admin_id, csrf_token, expires_at)
            VALUES (%s, %s, %s, %s);
        """, (session_id, admin_id, csrf_token, expires_at.isoformat()))

    return session_id, csrf_token

def get_current_admin(request: Request):
    """Retrieves authenticated admin and session info from cookie."""
    session_id = request.cookies.get("nexus_session")
    if not session_id:
        return None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, s.csrf_token, s.expires_at, a.id AS admin_id, a.username
            FROM sessions s
            JOIN admins a ON s.admin_id = a.id
            WHERE s.session_id = %s;
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        try:
            expires_at = row["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.datetime.fromisoformat(expires_at.replace("Z", ""))
            if datetime.datetime.utcnow() > expires_at:
                cursor.execute("DELETE FROM sessions WHERE session_id = %s;", (session_id,))
                return None
        except Exception:
            pass

        return dict(row)

def delete_session(session_id: str):
    """Logs out by removing session from DB."""
    if not session_id:
        return
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = %s;", (session_id,))

def verify_csrf(request: Request, submitted_token: str, session_csrf_token: str) -> bool:
    """Verifies CSRF token matching in constant time."""
    if not submitted_token or not session_csrf_token:
        return False
    return secrets.compare_digest(submitted_token, session_csrf_token)

def bootstrap_admin_from_env() -> bool:
    """
    Bootstraps the initial administrator from environment variables if no admin exists.
    Supports ADMIN_USERNAME, ADMIN_PASSWORD (and optional ADMIN_NAME).
    NEVER overwrites an existing admin.
    NEVER logs or displays the admin password.
    """
    username = os.getenv("ADMIN_USERNAME") or os.getenv("ADMIN_NAME")
    password = os.getenv("ADMIN_PASSWORD")

    if not username or not password:
        return False

    username = username.strip()
    if not username or not password:
        return False

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM admins;")
        row = cursor.fetchone()
        count = row[0] if row else 0
        if count > 0:
            # An admin already exists! NEVER overwrite existing admin accounts.
            return False

        pwd_hash, salt = hash_password(password)
        cursor.execute("""
            INSERT INTO admins (username, password_hash, salt)
            VALUES (%s, %s, %s);
        """, (username, pwd_hash, salt))
        print(f"[BOOTSTRAP] Initial admin user '{username}' provisioned safely from environment.")
        return True
