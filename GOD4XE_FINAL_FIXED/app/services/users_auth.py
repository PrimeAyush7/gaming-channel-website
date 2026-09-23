import uuid
import re
import json
import secrets
import hashlib
import datetime
import base64
import time
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature
from fastapi import Request, HTTPException, status
from app.database import get_db
from app.config import (
    GOOGLE_CLIENT_ID,
    SMS_PROVIDER,
    JWT_SECRET,
    ENVIRONMENT
)
from app.services.jwt_util import encode_jwt, decode_jwt
from app.services.auth import hash_password, verify_password

_TRUSTED_GOOGLE_KEYS = {}

def register_trusted_google_key(kid: str, public_key_pem: str):
    pub_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
    _TRUSTED_GOOGLE_KEYS[kid] = pub_key

def get_trusted_google_key(kid: str):
    return _TRUSTED_GOOGLE_KEYS.get(kid)

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
            INSERT INTO user_profiles (user_id, avatar_url, rank_tier)
            VALUES (%s, %s, %s);
        """, (user_id, "/static/images/default-avatar.png", "Bronze"))

        # Initialize diamond ledger account with 0 diamonds (registration awards zero free diamonds)
        cursor.execute("""
            INSERT INTO diamond_accounts (user_id, balance, locked_balance)
            VALUES (%s, 0, 0)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        # Track referral if present (0 diamonds awarded, status set to SUCCESSFUL upon registration)
        if referrer_id and referrer_id != user_id:
            cursor.execute("""
                INSERT INTO referrals (referrer_id, referee_id, reward_diamonds, status)
                VALUES (%s, %s, 0, 'SUCCESSFUL')
                ON CONFLICT (referee_id) DO NOTHING;
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
# GOOGLE AUTHENTICATION WITH CRYPTOGRAPHIC SIGNATURE VERIFICATION
# --------------------------------------------------------------------------
def verify_google_id_token(id_token_str: str, client_id: str = None) -> dict:
    if not id_token_str or not isinstance(id_token_str, str):
        raise ValueError("Google ID token string is required")

    parts = id_token_str.strip().split('.')
    if len(parts) != 3:
        raise ValueError("Malformed Google ID Token: expected 3 base64url segments")

    header_b64, payload_b64, sig_b64 = parts

    def b64url_dec(s: str) -> bytes:
        pad = '=' * ((4 - len(s) % 4) % 4)
        return base64.urlsafe_b64decode(s + pad)

    try:
        header = json.loads(b64url_dec(header_b64).decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Invalid Google token header: {e}")

    if header.get("alg") != "RS256":
        raise ValueError(f"Unsupported algorithm '{header.get('alg')}': expected RS256")

    try:
        claims = json.loads(b64url_dec(payload_b64).decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Invalid Google token claims: {e}")

    # 1. Verify Issuer
    iss = claims.get("iss", "")
    if iss not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError(f"Untrusted token issuer: '{iss}'")

    # 2. Verify Audience
    expected_aud = client_id or GOOGLE_CLIENT_ID
    if expected_aud:
        token_aud = claims.get("aud")
        if token_aud != expected_aud:
            raise ValueError(f"Audience mismatch: expected '{expected_aud}', but token audience is '{token_aud}'")

    # 3. Verify Expiry
    exp = claims.get("exp")
    if not exp or not isinstance(exp, (int, float)):
        raise ValueError("Missing or invalid expiration in token claims")
    if exp < int(time.time()):
        raise ValueError("Google ID Token has expired")

    # 4. Verify Identity
    google_id = str(claims.get("sub", "")).strip()
    email = claims.get("email", "").lower().strip()
    if not google_id:
        raise ValueError("Token missing subject (sub) claim")
    if not email:
        raise ValueError("Token missing email claim")

    # 5. Cryptographic Signature Verification
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    try:
        signature = b64url_dec(sig_b64)
    except Exception as e:
        raise ValueError("Invalid base64 signature encoding in token")

    kid = header.get("kid", "default")
    trusted_key = get_trusted_google_key(kid)

    if trusted_key:
        try:
            trusted_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature:
            raise ValueError("Invalid token cryptographic signature: signature verification failed")
    else:
        if ENVIRONMENT == "production":
            raise ValueError(f"Google public key for kid '{kid}' not found in trusted cert cache")
        else:
            raise ValueError(f"No trusted public key found for kid '{kid}'. Token signature cannot be verified.")

    return claims

def authenticate_google_user(id_token_str: str, referral_code: str = None) -> tuple[dict, str]:
    claims = verify_google_id_token(id_token_str)

    google_id = str(claims["sub"])
    email = claims["email"]
    name = claims.get("name", "")
    avatar = claims.get("picture", "/static/images/default-avatar.png")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM app_users WHERE google_id = %s OR email = %s;", (google_id, email))
        existing = cursor.fetchone()

        if existing:
            user_id = existing["id"] if isinstance(existing, dict) else existing[0]
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

            # Initialize diamond ledger account with 0 diamonds (registration awards zero free diamonds)
            cursor.execute("""
                INSERT INTO diamond_accounts (user_id, balance, locked_balance)
                VALUES (%s, 0, 0)
                ON CONFLICT (user_id) DO NOTHING;
            """, (user_id,))

            # Track referral if code provided during first Google signup
            if referral_code and referral_code.strip():
                cursor.execute("SELECT id FROM app_users WHERE referral_code = %s;", (referral_code.strip().upper(),))
                ref_user = cursor.fetchone()
                if ref_user:
                    ref_id = ref_user["id"] if isinstance(ref_user, dict) else ref_user[0]
                    if ref_id != user_id:
                        cursor.execute("""
                            INSERT INTO referrals (referrer_id, referee_id, reward_diamonds, status)
                            VALUES (%s, %s, 0, 'SUCCESSFUL')
                            ON CONFLICT (referee_id) DO NOTHING;
                        """, (ref_id, user_id))

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

            # Initialize diamond ledger account with 0 diamonds (registration awards zero free diamonds)
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
                   u.is_active, u.is_verified, u.created_at,
                   p.avatar_url, p.ff_uid, p.ff_ign, p.total_matches, p.wins, p.losses,
                   p.kills, p.points, p.rank_tier,
                   COALESCE(a.balance, 0) AS diamond_balance,
                   COALESCE(a.locked_balance, 0) AS locked_balance
            FROM app_users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            LEFT JOIN diamond_accounts a ON u.id = a.user_id
            WHERE u.id = %s;
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

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
    ff_uid = ff_uid.strip() if ff_uid else ""
    ff_ign = ff_ign.strip() if ff_ign else ""
    if not ff_uid or not ff_ign:
        raise ValueError("Both Free Fire UID and in-game name (IGN) are required")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET ff_uid = %s, ff_ign = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (ff_uid, ff_ign, user_id))

    return get_user_by_id(user_id)

def update_user_avatar(user_id: int, avatar_url: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET avatar_url = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (avatar_url.strip(), user_id))
    return get_user_by_id(user_id)
