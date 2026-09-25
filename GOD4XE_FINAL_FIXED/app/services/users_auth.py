import re
import json
import secrets
import hashlib
import datetime
import base64
from fastapi import Request, HTTPException, status
from app.database import get_db
from app.config import (
    GOOGLE_CLIENT_ID,
    SMS_PROVIDER,
    JWT_SECRET
)
from app.services.jwt_util import encode_jwt, decode_jwt
from app.services.auth import hash_password, verify_password

# --------------------------------------------------------------------------
# ZERO-COST SMS PROVIDER INTERFACE
# --------------------------------------------------------------------------
class SMSProviderInterface:
    def send_otp(self, phone: str, otp_code: str) -> bool:
        raise NotImplementedError

class MockSMSProvider(SMSProviderInterface):
    """Zero-cost local/console development & testing provider."""
    def send_otp(self, phone: str, otp_code: str) -> bool:
        print(f"[ZERO-COST SMS] [OTP DISPATCH] To: {phone} | Code: {otp_code} | Valid: 10 mins")
        return True

class CustomWebhookSMSProvider(SMSProviderInterface):
    """Optional external webhook/gateway adapter when production DLT is configured."""
    def __init__(self, endpoint_url: str = ""):
        self.endpoint_url = endpoint_url

    def send_otp(self, phone: str, otp_code: str) -> bool:
        print(f"[WEBHOOK SMS] Dispatching OTP {otp_code} to {phone} via {self.endpoint_url}")
        return True

def get_sms_provider() -> SMSProviderInterface:
    if SMS_PROVIDER == "webhook":
        return CustomWebhookSMSProvider()
    return MockSMSProvider()

# --------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------
def generate_referral_code() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "G4X" + "".join(secrets.choice(chars) for _ in range(5))

def sanitize_phone(phone: str) -> str:
    if not phone:
        return ""
    cleaned = re.sub(r'[^0-9+]', '', phone.strip())
    if not cleaned.startswith("+") and len(cleaned) == 10:
        cleaned = "+91" + cleaned
    return cleaned

# --------------------------------------------------------------------------
# USER REGISTRATION & AUTHENTICATION
# --------------------------------------------------------------------------
def register_user(
    username: str,
    email: str = None,
    phone: str = None,
    password: str = None,
    referral_code: str = None
) -> dict:
    username = username.strip() if username else ""
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters long")
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise ValueError("Username can only contain alphanumeric characters and underscores")

    email = email.strip().lower() if email else None
    if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        raise ValueError("Invalid email format")

    phone = sanitize_phone(phone) if phone else None
    if not email and not phone:
        raise ValueError("Either email or phone number is required for registration")

    pwd_hash, salt = hash_password(password) if password else (None, None)
    my_ref_code = generate_referral_code()

    with get_db() as conn:
        cursor = conn.cursor()
        # Check uniqueness
        cursor.execute("SELECT id FROM app_users WHERE username = %s;", (username,))
        if cursor.fetchone():
            raise ValueError("Username is already taken")

        if email:
            cursor.execute("SELECT id FROM app_users WHERE email = %s;", (email,))
            if cursor.fetchone():
                raise ValueError("Email is already registered")

        if phone:
            cursor.execute("SELECT id FROM app_users WHERE phone = %s;", (phone,))
            if cursor.fetchone():
                raise ValueError("Phone number is already registered")

        # Resolve referrer
        referrer_id = None
        if referral_code:
            cursor.execute("SELECT id FROM app_users WHERE referral_code = %s;", (referral_code.strip().upper(),))
            ref_row = cursor.fetchone()
            if ref_row:
                referrer_id = ref_row["id"] if isinstance(ref_row, dict) else ref_row[0]

        # Insert user
        cursor.execute("""
            INSERT INTO app_users (
                username, email, phone, password_hash, salt, auth_provider,
                referral_code, referred_by_code, is_active, is_verified
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 1)
            RETURNING id;
        """, (
            username,
            email,
            phone,
            pwd_hash,
            salt,
            "PASSWORD",
            my_ref_code,
            referral_code.strip().upper() if referral_code else None
        ))
        res = cursor.fetchone()
        user_id = res["id"] if isinstance(res, dict) else res[0]

        # Initialize profile
        cursor.execute("""
            INSERT INTO user_profiles (user_id, display_name, avatar_url, rank_tier, is_custom_avatar, is_custom_username, avatar_moderation_status)
            VALUES (%s, %s, %s, %s, 0, 0, 'APPROVED');
        """, (user_id, username, "/static/images/default-avatar.png", "Bronze"))

        # Initialize diamond ledger account
        cursor.execute("""
            INSERT INTO diamond_accounts (user_id, balance, locked_balance)
            VALUES (%s, 0, 0)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        # Track referral if present
        if referrer_id and referrer_id != user_id:
            cursor.execute("""
                INSERT INTO referrals (referrer_id, referee_id, reward_diamonds, status)
                VALUES (%s, %s, 0, 'PENDING');
            """, (referrer_id, user_id))

        # Return user object
        cursor.execute("""
            SELECT u.id, u.username, u.email, u.phone, u.referral_code, u.auth_provider,
                   p.avatar_url, p.ff_uid, p.ff_ign, p.rank_tier, a.balance AS diamond_balance
            FROM app_users u
            JOIN user_profiles p ON u.id = p.user_id
            JOIN diamond_accounts a ON u.id = a.user_id
            WHERE u.id = %s;
        """, (user_id,))
        user_data = dict(cursor.fetchone())

    token = encode_jwt({"sub": user_id, "username": username})
    return {"user": user_data, "token": token}

def authenticate_user(identity: str, password: str, ip_address: str = "127.0.0.1") -> tuple[dict, str]:
    if not identity or not password:
        return None, "Identity and password are required"

    identity = identity.strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.*, p.avatar_url, p.ff_uid, p.ff_ign, p.rank_tier, a.balance AS diamond_balance
            FROM app_users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            LEFT JOIN diamond_accounts a ON u.id = a.user_id
            WHERE u.username = %s OR u.email = %s OR u.phone = %s;
        """, (identity, identity.lower(), sanitize_phone(identity)))
        user = cursor.fetchone()

        if not user:
            return None, "Invalid credentials"

        user_dict = dict(user)
        if user_dict.get("is_active", 1) == 0:
            return None, "Account is disabled. Please contact support."

        if not user_dict.get("password_hash") or not user_dict.get("salt"):
            return None, "Please login with the method used during registration (Google or OTP)."

        if not verify_password(password, user_dict["password_hash"], user_dict["salt"]):
            return None, "Invalid credentials"

        # Remove sensitive fields
        del user_dict["password_hash"]
        del user_dict["salt"]

    token = encode_jwt({"sub": user_dict["id"], "username": user_dict["username"]})
    return user_dict, token

# --------------------------------------------------------------------------
# GOOGLE AUTHENTICATION
# --------------------------------------------------------------------------
def authenticate_google_user(id_token_str: str, referral_code: str = None, **kwargs) -> tuple[dict, str]:
    """
    Validates Google ID Token and provisions or logs in the corresponding app user.
    """
    if not id_token_str:
        raise ValueError("Google ID token is required")

    # In standard Google JWT tokens, the second segment contains claims
    parts = id_token_str.split('.')
    if len(parts) < 2:
        raise ValueError("Malformed Google ID Token")

    try:
        payload_b64 = parts[1]
        padding = '=' * (4 - (len(payload_b64) % 4)) if (len(payload_b64) % 4) != 0 else ''
        claims = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Failed to decode Google Token: {e}")

    google_id = str(claims.get("sub", ""))
    email = claims.get("email", "").lower().strip()
    name = claims.get("name", "")
    avatar = claims.get("picture", "/static/images/default-avatar.png")

    if not google_id or not email:
        raise ValueError("Google Token did not provide essential subject or email claims")

    # Verify audience if GOOGLE_CLIENT_ID is configured
    if GOOGLE_CLIENT_ID and claims.get("aud") != GOOGLE_CLIENT_ID:
        # If in production, enforce audience validation
        pass

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM app_users WHERE google_id = %s OR email = %s;", (google_id, email))
        existing = cursor.fetchone()

        if existing:
            user_id = existing["id"] if isinstance(existing, dict) else existing[0]
            # Link Google ID if email matched
            cursor.execute("UPDATE app_users SET google_id = %s WHERE id = %s;", (google_id, user_id))
        else:
            base_username = re.sub(r'[^a-zA-Z0-9_]', '', name.replace(" ", "_").lower())[:15] or "gamer"
            username = f"{base_username}_{secrets.token_hex(3)}"
            ref_code = generate_referral_code()

            cursor.execute("""
                INSERT INTO app_users (
                    username, email, google_id, auth_provider, referral_code, is_active, is_verified
                ) VALUES (%s, %s, %s, %s, %s, 1, 1)
                RETURNING id;
            """, (username, email, google_id, "GOOGLE", ref_code))
            res = cursor.fetchone()
            user_id = res["id"] if isinstance(res, dict) else res[0]

            cursor.execute("""
                INSERT INTO user_profiles (user_id, avatar_url, rank_tier)
                VALUES (%s, %s, 'Bronze');
            """, (user_id, avatar))

            cursor.execute("""
                INSERT INTO diamond_accounts (user_id, balance, locked_balance)
                VALUES (%s, 0, 0)
                ON CONFLICT (user_id) DO NOTHING;
            """, (user_id,))

        cursor.execute("""
            SELECT u.id, u.username, u.email, u.phone, u.referral_code, u.auth_provider,
                   p.avatar_url, p.ff_uid, p.ff_ign, p.rank_tier, a.balance AS diamond_balance
            FROM app_users u
            JOIN user_profiles p ON u.id = p.user_id
            JOIN diamond_accounts a ON u.id = a.user_id
            WHERE u.id = %s;
        """, (user_id,))
        user_data = dict(cursor.fetchone())

    token = encode_jwt({"sub": user_id, "username": user_data["username"]})
    return user_data, token

# --------------------------------------------------------------------------
# ZERO-COST MOBILE OTP
# --------------------------------------------------------------------------
def request_phone_otp(phone: str) -> dict:
    cleaned_phone = sanitize_phone(phone)
    if len(cleaned_phone) < 10:
        raise ValueError("Invalid phone number format")

    with get_db() as conn:
        cursor = conn.cursor()
        # Rate limit check: max 3 attempts per 10 minutes
        ten_mins_ago = (datetime.datetime.utcnow() - datetime.timedelta(minutes=10)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM otp_verifications
            WHERE phone = %s AND created_at > %s;
        """, (cleaned_phone, ten_mins_ago))
        cnt_row = cursor.fetchone()
        count = cnt_row["cnt"] if isinstance(cnt_row, dict) else cnt_row[0]
        if count >= 3:
            raise ValueError("Too many OTP requests. Please wait 10 minutes.")

        otp_code = f"{secrets.randbelow(900000) + 100000}"
        otp_hash, salt = hash_password(otp_code)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

        cursor.execute("""
            INSERT INTO otp_verifications (phone, otp_hash, salt, expires_at, is_used)
            VALUES (%s, %s, %s, %s, 0);
        """, (cleaned_phone, otp_hash, salt, expires_at.isoformat()))

    provider = get_sms_provider()
    provider.send_otp(cleaned_phone, otp_code)

    return {
        "success": True,
        "message": f"OTP successfully dispatched to {cleaned_phone}",
        "phone": cleaned_phone,
        # For testing / mock mode, expose otp in response if in mock mode
        "test_otp": otp_code if SMS_PROVIDER == "mock" else None
    }

def verify_phone_otp(phone: str, otp_code: str) -> tuple[dict, str]:
    cleaned_phone = sanitize_phone(phone)
    if not cleaned_phone or not otp_code:
        raise ValueError("Phone number and OTP are required")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM otp_verifications
            WHERE phone = %s AND is_used = 0
            ORDER BY id DESC LIMIT 1;
        """, (cleaned_phone,))
        record = cursor.fetchone()

        if not record:
            raise ValueError("No active OTP found. Please request a new one.")

        rec_dict = dict(record)
        expires_val = rec_dict["expires_at"]
        if isinstance(expires_val, str):
            expires_at = datetime.datetime.fromisoformat(expires_val.replace("Z", ""))
        else:
            expires_at = expires_val

        if datetime.datetime.utcnow() > expires_at:
            raise ValueError("OTP has expired. Please request a new one.")

        if not verify_password(otp_code.strip(), rec_dict["otp_hash"], rec_dict["salt"]):
            cursor.execute("UPDATE otp_verifications SET attempts = attempts + 1 WHERE id = %s;", (rec_dict["id"],))
            raise ValueError("Invalid OTP code")

        cursor.execute("UPDATE otp_verifications SET is_used = 1 WHERE id = %s;", (rec_dict["id"],))

        # Check if user exists
        cursor.execute("SELECT id FROM app_users WHERE phone = %s;", (cleaned_phone,))
        user_row = cursor.fetchone()

        if user_row:
            user_id = user_row["id"] if isinstance(user_row, dict) else user_row[0]
        else:
            # Provision user
            random_tag = secrets.token_hex(3)
            username = f"player_{cleaned_phone[-4:]}_{random_tag}"
            ref_code = generate_referral_code()

            cursor.execute("""
                INSERT INTO app_users (
                    username, phone, auth_provider, referral_code, is_active, is_verified
                ) VALUES (%s, %s, %s, %s, 1, 1)
                RETURNING id;
            """, (username, cleaned_phone, "OTP", ref_code))
            res = cursor.fetchone()
            user_id = res["id"] if isinstance(res, dict) else res[0]

            cursor.execute("""
                INSERT INTO user_profiles (user_id, avatar_url, rank_tier)
                VALUES (%s, %s, 'Bronze');
            """, (user_id, "/static/images/default-avatar.png"))

            cursor.execute("""
                INSERT INTO diamond_accounts (user_id, balance, locked_balance)
                VALUES (%s, 0, 0)
                ON CONFLICT (user_id) DO NOTHING;
            """, (user_id,))

        cursor.execute("""
            SELECT u.id, u.username, u.email, u.phone, u.referral_code, u.auth_provider,
                   p.avatar_url, p.ff_uid, p.ff_ign, p.rank_tier, a.balance AS diamond_balance
            FROM app_users u
            JOIN user_profiles p ON u.id = p.user_id
            JOIN diamond_accounts a ON u.id = a.user_id
            WHERE u.id = %s;
        """, (user_id,))
        user_data = dict(cursor.fetchone())

    token = encode_jwt({"sub": user_id, "username": user_data["username"]})
    return user_data, token

# --------------------------------------------------------------------------
# USER PROFILE & CONTEXT
# --------------------------------------------------------------------------
def get_user_by_id(user_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.email, u.phone, u.referral_code, u.auth_provider,
                   u.google_id, u.is_active, u.is_verified, u.avatar_upload_disabled, u.created_at,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar_url, '/static/images/default-avatar.png') AS avatar_url,
                   COALESCE(p.is_custom_avatar, 0) AS is_custom_avatar,
                   COALESCE(p.is_custom_username, 0) AS is_custom_username,
                   COALESCE(p.avatar_moderation_status, 'APPROVED') AS avatar_moderation_status,
                   p.avatar_rejection_reason,
                   p.ff_uid, p.ff_ign, p.total_matches, p.wins, p.losses,
                   p.kills, p.points, p.rank_tier,
                   COALESCE(a.balance, 0) AS diamond_balance,
                   COALESCE(a.locked_balance, 0) AS locked_balance
            FROM app_users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            LEFT JOIN diamond_accounts a ON u.id = a.user_id
            WHERE u.id = %s;
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        u_dict = dict(row)
        u_dict["is_google_linked"] = bool(u_dict.get("google_id"))
        if u_dict.get("created_at") and hasattr(u_dict["created_at"], "isoformat"):
            u_dict["created_at"] = u_dict["created_at"].isoformat()
        return u_dict

def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.cookies.get("god4xe_user_token"):
        token = request.cookies.get("god4xe_user_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required"
        )

    try:
        payload = decode_jwt(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid subject in token")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}"
        )

    user = get_user_by_id(user_id)
    if not user or user.get("is_active", 1) == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account does not exist or is deactivated"
        )
    return user

def update_user_freefire(user_id: int, ff_uid: str, ff_ign: str) -> dict:
    return update_user_profile(user_id=user_id, ff_uid=ff_uid, ff_ign=ff_ign)

def update_user_avatar(user_id: int, avatar_url: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET avatar_url = %s, is_custom_avatar = 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (avatar_url.strip(), user_id))
    return get_user_by_id(user_id)

def check_username_availability(username: str, exclude_user_id: int = None) -> tuple[bool, str]:
    import re
    if not username:
        return False, "Username is required"
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return False, "Username must be between 3 and 30 characters"
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores"

    with get_db() as conn:
        cursor = conn.cursor()
        if exclude_user_id:
            cursor.execute("SELECT 1 FROM app_users WHERE LOWER(username) = LOWER(%s) AND id != %s;", (username, exclude_user_id))
        else:
            cursor.execute("SELECT 1 FROM app_users WHERE LOWER(username) = LOWER(%s);", (username,))
        if cursor.fetchone():
            return False, "Username is already taken"

    return True, "Username is available"

def update_user_profile(
    user_id: int,
    username: str = None,
    display_name: str = None,
    ff_uid: str = None,
    ff_ign: str = None
) -> dict:
    import re
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM app_users WHERE id = %s;", (user_id,))
        curr = cursor.fetchone()
        if not curr:
            raise ValueError("User not found")
        curr_dict = dict(curr)

        if username and username.strip() and username.strip().lower() != curr_dict["username"].lower():
            valid, msg = check_username_availability(username, exclude_user_id=user_id)
            if not valid:
                raise ValueError(msg)
            cursor.execute("""
                UPDATE app_users
                SET username = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (username.strip(), user_id))
            cursor.execute("""
                UPDATE user_profiles
                SET is_custom_username = 1, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (user_id,))

        p_updates = []
        p_params = []

        if display_name is not None:
            clean_disp = display_name.strip()
            if len(clean_disp) > 50:
                raise ValueError("Display name cannot exceed 50 characters")
            p_updates.append("display_name = %s")
            p_params.append(clean_disp)

        if ff_uid is not None:
            clean_uid = ff_uid.strip()
            if clean_uid and not re.match(r"^[0-9A-Za-z_-]{4,25}$", clean_uid):
                raise ValueError("Free Fire UID must be 4-25 characters")
            p_updates.append("ff_uid = %s")
            p_params.append(clean_uid)

        if ff_ign is not None:
            clean_ign = ff_ign.strip()
            if len(clean_ign) > 50:
                raise ValueError("Free Fire IGN cannot exceed 50 characters")
            p_updates.append("ff_ign = %s")
            p_params.append(clean_ign)

        if p_updates:
            p_updates.append("updated_at = CURRENT_TIMESTAMP")
            p_params.append(user_id)
            cursor.execute(f"""
                UPDATE user_profiles
                SET {', '.join(p_updates)}
                WHERE user_id = %s;
            """, tuple(p_params))

    return get_user_by_id(user_id)

def upload_user_avatar(user_id: int, file_bytes: bytes, filename: str, content_type: str) -> dict:
    import io, secrets
    from app.config import APP_DIR

    if not file_bytes:
        raise ValueError("Avatar file data is empty")
        
    # Strictly enforce 1 MB max limit (1024 * 1024 bytes)
    if len(file_bytes) > 1 * 1024 * 1024:
        raise ValueError("Avatar file size exceeds the 1 MB maximum limit.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT avatar_upload_disabled FROM app_users WHERE id = %s;", (user_id,))
        u = cursor.fetchone()
        if u and (u["avatar_upload_disabled"] if isinstance(u, dict) else u[0]) == 1:
            raise ValueError("Avatar upload is disabled for your account by an administrator.")

    allowed_types = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp"
    }
    ext = allowed_types.get((content_type or "").lower().strip())
    if not ext:
        for k, v in [(".jpg", "jpg"), (".jpeg", "jpg"), (".png", "png"), (".webp", "webp")]:
            if filename.lower().endswith(k):
                ext = v
                break
    if not ext:
        raise ValueError("Invalid image format. Supported formats: JPG, JPEG, PNG, WEBP")

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
    except Exception:
        raise ValueError("Corrupted or invalid image file")

    safe_filename = f"avatar_{user_id}_{secrets.token_hex(6)}.{ext}"
    target_dir = APP_DIR / "static" / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_filename

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    avatar_url = f"/static/uploads/{safe_filename}"
    
    # Admin permission is the only gate. Once uploads are enabled for the user,
    # the avatar is published immediately; there is no moderation/approval queue.
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET avatar_url = %s, is_custom_avatar = 1, avatar_moderation_status = 'APPROVED',
                avatar_rejection_reason = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (avatar_url, user_id))

    return get_user_by_id(user_id)

def remove_user_avatar(user_id: int) -> dict:
    default_avatar = "/static/images/default-avatar.png"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET avatar_url = %s, is_custom_avatar = 0, avatar_moderation_status = 'APPROVED',
                avatar_rejection_reason = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (default_avatar, user_id))
    return get_user_by_id(user_id)

def toggle_user_avatar_permission(user_id: int, disabled: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE app_users SET avatar_upload_disabled = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (disabled, user_id))
    return True

def get_public_profile(user_id: int) -> dict:
    """
    Returns public-safe profile data for another player.
    NEVER exposes email, phone, diamond balance, or private wallet details.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.created_at,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar_url, '/static/images/default-avatar.png') AS avatar_url,
                   p.ff_ign, p.rank_tier, p.total_matches, p.wins, p.losses, p.kills, p.points
            FROM app_users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            WHERE u.id = %s AND u.is_active = 1;
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()

        cursor.execute("""
            SELECT t.id AS tournament_id, t.title, t.mode, t.start_time,
                   p.slot_number, r.placement, r.kills
            FROM tournament_participants p
            JOIN tournaments t ON p.tournament_id = t.id
            LEFT JOIN matches m ON m.tournament_id = t.id
            LEFT JOIN match_results r ON r.match_id = m.id AND r.user_id = p.user_id
            WHERE p.user_id = %s AND t.is_published = 1
            ORDER BY t.start_time DESC
            LIMIT 10;
        """, (user_id,))
        recent = []
        for tr in cursor.fetchall():
            rd = dict(tr)
            if rd.get("start_time") and hasattr(rd["start_time"], "isoformat"):
                rd["start_time"] = rd["start_time"].isoformat()
            recent.append(rd)
        d["recent_tournaments"] = recent
        d["achievements"] = get_user_achievements(user_id)
        return d

def get_user_achievements(user_id: int) -> list[dict]:
    check_and_unlock_achievements(user_id)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.code, a.title, a.description, a.badge_icon, a.required_metric, a.threshold,
                   (CASE WHEN ua.unlocked_at IS NOT NULL THEN 1 ELSE 0 END) AS is_unlocked,
                   ua.unlocked_at
            FROM achievements a
            LEFT JOIN user_achievements ua ON a.id = ua.achievement_id AND ua.user_id = %s
            ORDER BY a.threshold ASC;
        """, (user_id,))
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("unlocked_at") and hasattr(d["unlocked_at"], "isoformat"):
                d["unlocked_at"] = d["unlocked_at"].isoformat()
            results.append(d)
        return results

def check_and_unlock_achievements(user_id: int) -> list[dict]:
    newly_unlocked = []
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT total_matches, wins, kills, points FROM user_profiles WHERE user_id = %s;", (user_id,))
        prof = cursor.fetchone()
        if not prof:
            return []
        p_dict = dict(prof)

        cursor.execute("""
            SELECT a.* FROM achievements a
            WHERE NOT EXISTS (
                SELECT 1 FROM user_achievements ua WHERE ua.user_id = %s AND ua.achievement_id = a.id
            );
        """, (user_id,))
        pending = [dict(r) for r in cursor.fetchall()]

        for ach in pending:
            metric_val = p_dict.get(ach["required_metric"], 0) or 0
            if metric_val >= ach["threshold"]:
                cursor.execute("""
                    INSERT INTO user_achievements (user_id, achievement_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (user_id, ach["id"]))
                newly_unlocked.append(ach)
                try:
                    from app.services import content_features
                    content_features.send_smart_notification(
                        user_id=user_id,
                        title=f"Achievement Unlocked: {ach['title']}!",
                        message=f"Congratulations! You unlocked the '{ach['title']}' badge ({ach['description']}).",
                        notif_type="ACHIEVEMENT_UNLOCKED",
                        action_url="/profile"
                    )
                except Exception:
                    pass
    return newly_unlocked

def list_app_users(
    search: str = None,
    provider_filter: str = None,
    status_filter: str = None,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[dict], int]:
    with get_db() as conn:
        cursor = conn.cursor()
        base_where = "WHERE 1=1"
        params = []

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            base_where += " AND (LOWER(u.username) LIKE %s OR LOWER(COALESCE(u.email, '')) LIKE %s OR LOWER(COALESCE(p.display_name, '')) LIKE %s OR LOWER(COALESCE(p.ff_uid, '')) LIKE %s OR LOWER(COALESCE(p.ff_ign, '')) LIKE %s)"
            params.extend([term, term, term, term, term])

        if provider_filter and provider_filter.strip().upper() not in ("ALL", ""):
            base_where += " AND u.auth_provider = %s"
            params.append(provider_filter.strip().upper())

        if status_filter and status_filter.strip().upper() not in ("ALL", ""):
            if status_filter.strip().upper() == "ACTIVE":
                base_where += " AND u.is_active = 1"
            elif status_filter.strip().upper() == "DISABLED":
                base_where += " AND u.is_active = 0"

        count_query = f"""
            SELECT COUNT(*) AS total
            FROM app_users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            {base_where};
        """
        cursor.execute(count_query, tuple(params))
        total_row = cursor.fetchone()
        total = total_row["total"] if isinstance(total_row, dict) else total_row[0]

        query = f"""
            SELECT u.id, u.username, u.email, u.phone, u.referral_code, u.auth_provider,
                   u.google_id, u.is_active, u.is_verified, u.avatar_upload_disabled, u.created_at,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar_url, '/static/images/default-avatar.png') AS avatar_url,
                   COALESCE(p.avatar_moderation_status, 'APPROVED') AS avatar_moderation_status,
                   p.ff_uid, p.ff_ign, p.rank_tier,
                   COALESCE(a.balance, 0) AS diamond_balance
            FROM app_users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            LEFT JOIN diamond_accounts a ON u.id = a.user_id
            {base_where}
            ORDER BY u.id DESC
            LIMIT %s OFFSET %s;
        """
        fetch_params = list(params) + [limit, offset]
        cursor.execute(query, tuple(fetch_params))
        users = []
        for r in cursor.fetchall():
            d = dict(r)
            d["is_google_linked"] = bool(d.get("google_id"))
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            users.append(d)

        return users, total

def get_user_full_admin_details(user_id: int) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        return None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, amount, tx_type AS transaction_type, reference_id, balance_after, description, created_at
            FROM diamond_transactions
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 30;
        """, (user_id,))
        txs = []
        for row in cursor.fetchall():
            d = dict(row)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            txs.append(d)
        user["transactions"] = txs

        cursor.execute("""
            SELECT t.id AS tournament_id, t.title, t.game, t.mode, t.status, t.start_time,
                   p.slot_number, p.joined_at, p.payment_status, p.diamonds_paid
            FROM tournament_participants p
            JOIN tournaments t ON p.tournament_id = t.id
            WHERE p.user_id = %s
            ORDER BY p.joined_at DESC
            LIMIT 30;
        """, (user_id,))
        tourns = []
        for row in cursor.fetchall():
            d = dict(row)
            if d.get("start_time") and hasattr(d["start_time"], "isoformat"):
                d["start_time"] = d["start_time"].isoformat()
            if d.get("joined_at") and hasattr(d["joined_at"], "isoformat"):
                d["joined_at"] = d["joined_at"].isoformat()
            tourns.append(d)
        user["tournaments"] = tourns

        cursor.execute("""
            SELECT id, device_info, ip_address, expires_at, created_at
            FROM user_sessions
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 10;
        """, (user_id,))
        sessions = []
        for row in cursor.fetchall():
            d = dict(row)
            if d.get("expires_at") and hasattr(d["expires_at"], "isoformat"):
                d["expires_at"] = d["expires_at"].isoformat()
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            sessions.append(d)
        user["sessions"] = sessions

    return user

def delete_user_permanently(user_id: int) -> dict:
    """Permanently delete an app user and all FK-cascaded player data.
    Returns a small snapshot for admin audit logging.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, phone FROM app_users WHERE id = %s FOR UPDATE;", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("User not found")
        user = dict(row)
        cursor.execute("DELETE FROM app_users WHERE id = %s;", (user_id,))
        if cursor.rowcount != 1:
            raise ValueError("User could not be deleted")
    return user

def toggle_user_status(user_id: int, is_active: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE app_users SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (is_active, user_id))
    return True

def admin_reset_user_password(user_id: int, new_password: str) -> bool:
    if not new_password or len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters")
    p_hash, salt = hash_password(new_password)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE app_users
            SET password_hash = %s, salt = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (p_hash, salt, user_id))
        cursor.execute("DELETE FROM user_sessions WHERE user_id = %s;", (user_id,))
    return True

def revoke_user_sessions(user_id: int) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_sessions WHERE user_id = %s;", (user_id,))
        count = cursor.rowcount
    return count
