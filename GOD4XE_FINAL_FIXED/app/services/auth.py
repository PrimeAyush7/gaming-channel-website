import os
import json
import hashlib
import secrets
import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from app.database import get_db
from app.config import (
    ROLE_SUPER_ADMIN,
    ROLE_TOURNAMENT_ADMIN,
    ROLE_FINANCE_ADMIN,
    ROLE_SUPPORT_ADMIN,
    ALL_ADMIN_ROLES
)

HASH_ITERATIONS = 100_000

def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        HASH_ITERATIONS
    )
    return dk.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        HASH_ITERATIONS
    )
    return secrets.compare_digest(dk.hex(), password_hash)

def check_login_rate_limit(ip_address: str) -> bool:
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login_attempts WHERE ip_address = %s;", (ip_address,))

def log_admin_action(
    admin_id: int,
    admin_username: str,
    role: str,
    action: str,
    resource: str,
    resource_id: str,
    ip_address: str,
    user_agent: str = None,
    before_state: dict = None,
    after_state: dict = None
):
    before_json = json.dumps(before_state, default=str) if before_state else None
    after_json = json.dumps(after_state, default=str) if after_state else None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_audit_logs (
                admin_id, admin_username, role, action, resource,
                resource_id, ip_address, user_agent, before_state, after_state
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            admin_id,
            admin_username,
            role,
            action,
            resource,
            str(resource_id) if resource_id is not None else None,
            ip_address or "127.0.0.1",
            user_agent,
            before_json,
            after_json
        ))

def create_admin_user(username: str, password: str) -> int:
    return create_admin_with_role(username, password, ROLE_SUPER_ADMIN)

def create_admin_with_role(username: str, password: str, role: str = ROLE_SUPER_ADMIN, email: str = None) -> int:
    if role not in ALL_ADMIN_ROLES:
        role = ROLE_SUPER_ADMIN
    pwd_hash, salt = hash_password(password)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admins (username, password_hash, salt, role, email, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            RETURNING id;
        """, (username.strip(), pwd_hash, salt, role, email))
        res = cursor.fetchone()
        return res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]

def list_admins():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, email, COALESCE(role, 'SUPER_ADMIN') AS role,
                   is_active, created_at, last_login
            FROM admins
            ORDER BY id ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

def update_admin_role(admin_id: int, new_role: str):
    if new_role not in ALL_ADMIN_ROLES:
        raise ValueError("Invalid admin role")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE admins SET role = %s WHERE id = %s;", (new_role, admin_id))

def update_admin_status(admin_id: int, is_active: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE admins SET is_active = %s WHERE id = %s;", (1 if is_active else 0, admin_id))

def delete_admin(admin_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE id = %s;", (admin_id,))

def get_audit_logs(limit: int = 100, offset: int = 0, resource: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        if resource:
            cursor.execute("""
                SELECT * FROM admin_audit_logs
                WHERE resource = %s
                ORDER BY id DESC LIMIT %s OFFSET %s;
            """, (resource, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM admin_audit_logs
                ORDER BY id DESC LIMIT %s OFFSET %s;
            """, (limit, offset))
        return [dict(r) for r in cursor.fetchall()]

def authenticate_admin(username: str, password: str, ip_address: str = "127.0.0.1"):
    if not check_login_rate_limit(ip_address):
        return None, "Too many failed attempts. Please try again in 15 minutes."

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE username = %s;", (username.strip(),))
        admin = cursor.fetchone()

        if not admin:
            record_failed_login(ip_address)
            return None, "Invalid username or password."

        admin_dict = dict(admin)
        if admin_dict.get("is_active", 1) == 0:
            return None, "This admin account has been deactivated."

        if not verify_password(password, admin["password_hash"], admin["salt"]):
            record_failed_login(ip_address)
            return None, "Invalid username or password."

        reset_failed_login(ip_address)
        cursor.execute("UPDATE admins SET last_login = CURRENT_TIMESTAMP WHERE id = %s;", (admin["id"],))
        
        if not admin_dict.get("role"):
            admin_dict["role"] = ROLE_SUPER_ADMIN
            
        return admin_dict, None

def create_session(admin_id: int) -> tuple[str, str]:
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
    session_id = request.cookies.get("nexus_session")
    if not session_id:
        return None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, s.csrf_token, s.expires_at, a.id AS admin_id, a.username,
                   COALESCE(a.role, 'SUPER_ADMIN') AS role, a.email, COALESCE(a.is_active, 1) AS is_active
            FROM sessions s
            JOIN admins a ON s.admin_id = a.id
            WHERE s.session_id = %s;
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        admin_dict = dict(row)
        if admin_dict.get("is_active", 1) == 0:
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

        return admin_dict

def delete_session(session_id: str):
    if not session_id:
        return
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = %s;", (session_id,))

def verify_csrf(request: Request, submitted_token: str, session_csrf_token: str) -> bool:
    if not submitted_token or not session_csrf_token:
        return False
    return secrets.compare_digest(submitted_token, session_csrf_token)

def has_role_permission(current_role: str, allowed_roles: list[str]) -> bool:
    if current_role == ROLE_SUPER_ADMIN:
        return True
    return current_role in allowed_roles

def bootstrap_admin_from_env() -> bool:
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
            return False

        pwd_hash, salt = hash_password(password)
        cursor.execute("""
            INSERT INTO admins (username, password_hash, salt, role, is_active)
            VALUES (%s, %s, %s, %s, 1);
        """, (username, pwd_hash, salt, ROLE_SUPER_ADMIN))
        print(f"[BOOTSTRAP] Initial super admin '{username}' provisioned safely from environment.")
        return True
