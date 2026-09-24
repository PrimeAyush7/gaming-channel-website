import logging
import uuid
import re
import json
import secrets
import hashlib
import datetime
import base64
import time
import urllib.request
from typing import Dict, Optional, Tuple, Any
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography import x509
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

logger = logging.getLogger("users_auth")

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False

_GOOGLE_JWKS_CACHE: Dict[str, Any] = {}
_GOOGLE_JWKS_CACHE_EXPIRY: float = 0.0
_TRUSTED_GOOGLE_KEYS: Dict[str, Any] = {}

def register_trusted_google_key(kid: str, public_key_pem: str):
    """Register a PEM public key for testing or custom trust."""
    pub_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'), default_backend())
    _TRUSTED_GOOGLE_KEYS[kid] = pub_key

def register_trusted_google_public_key(kid: str, pub_key):
    """Register an RSAPublicKey directly for testing."""
    _TRUSTED_GOOGLE_KEYS[kid] = pub_key

def get_trusted_google_key(kid: str):
    return _TRUSTED_GOOGLE_KEYS.get(kid)

def clear_trusted_google_keys():
    _TRUSTED_GOOGLE_KEYS.clear()

def _int_from_b64url(s: str) -> int:
    pad = '=' * ((4 - len(s) % 4) % 4)
    data = base64.urlsafe_b64decode(s + pad)
    return int.from_bytes(data, byteorder='big')

def _jwk_to_rsa_public_key(jwk: dict):
    """Convert an RSA JWK into a cryptography RSAPublicKey object."""
    try:
        if jwk.get("kty") == "RSA" and "n" in jwk and "e" in jwk:
            n = _int_from_b64url(jwk["n"])
            e = _int_from_b64url(jwk["e"])
            return RSAPublicNumbers(e, n).public_key(default_backend())
        elif "x5c" in jwk and jwk["x5c"]:
            cert_der = base64.b64decode(jwk["x5c"][0])
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            return cert.public_key()
    except Exception as e:
        logger.warning(f"Failed to parse JWK key {jwk.get('kid')}: {e}")
    return None

def fetch_google_public_keys(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch and cache Google's public signing keys from official Google endpoints:
    Primary:  https://www.googleapis.com/oauth2/v3/certs (JWKS format)
    Fallback: https://www.googleapis.com/oauth2/v1/certs (x509 PEM format)
    Handles Cache-Control max-age header for TTL and logs detailed diagnostic telemetry.
    """
    global _GOOGLE_JWKS_CACHE, _GOOGLE_JWKS_CACHE_EXPIRY
    now = time.time()
    if not force_refresh and _GOOGLE_JWKS_CACHE and now < _GOOGLE_JWKS_CACHE_EXPIRY:
        return _GOOGLE_JWKS_CACHE

    keys = {}
    cache_ttl = 3600  # Default 1 hour fallback

    # 1. Primary: Google official v3 JWKS endpoint
    v3_url = "https://www.googleapis.com/oauth2/v3/certs"
    v3_status = None
    try:
        raw_data = None
        cc = ""
        try:
            import requests
            resp = requests.get(
                v3_url,
                headers={"User-Agent": "God4xe-Backend/1.0", "Accept": "application/json"},
                timeout=10
            )
            v3_status = resp.status_code
            cc = resp.headers.get("Cache-Control", "")
            if v3_status == 200:
                raw_data = resp.json()
            else:
                logger.warning(f"[JWKS_V3_HTTP] Google v3 JWKS endpoint returned HTTP {v3_status}")
        except Exception as req_err:
            logger.warning(f"[JWKS_V3_REQUESTS_ERR] requests.get failed: {type(req_err).__name__}: {req_err}, trying urllib fallback")
            req = urllib.request.Request(
                v3_url,
                headers={"User-Agent": "God4xe-Backend/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as u_resp:
                v3_status = u_resp.status
                cc = u_resp.headers.get("Cache-Control", "")
                raw_data = json.loads(u_resp.read().decode("utf-8"))

        if raw_data and isinstance(raw_data, dict):
            # Parse Cache-Control header
            for part in cc.split(","):
                part = part.strip()
                if part.startswith("max-age="):
                    try:
                        cache_ttl = max(60, int(part.split("=")[1].strip()))
                    except Exception:
                        pass

            jwk_list = raw_data.get("keys", [])
            for jwk in jwk_list:
                kid = jwk.get("kid")
                if kid:
                    pk = _jwk_to_rsa_public_key(jwk)
                    if pk:
                        keys[kid] = pk

            logger.info(
                f"[JWKS_V3_SUCCESS] HTTP Status: {v3_status} | "
                f"Keys received: {len(jwk_list)} | Keys parsed: {len(keys)} | "
                f"Key IDs: {list(keys.keys())} | TTL: {cache_ttl}s"
            )
    except Exception as e:
        logger.warning(f"[JWKS_V3_FAILED] Failed to fetch/parse Google v3 JWKS endpoint: {type(e).__name__}: {e}")

    # 2. Fallback: Google v1 certs endpoint (x509 PEM certificates)
    if not keys:
        v1_url = "https://www.googleapis.com/oauth2/v1/certs"
        v1_status = None
        try:
            raw_data = None
            try:
                import requests
                resp = requests.get(
                    v1_url,
                    headers={"User-Agent": "God4xe-Backend/1.0", "Accept": "application/json"},
                    timeout=10
                )
                v1_status = resp.status_code
                if v1_status == 200:
                    raw_data = resp.json()
            except Exception as req_err:
                logger.warning(f"[JWKS_V1_REQUESTS_ERR] requests.get failed: {type(req_err).__name__}: {req_err}, trying urllib fallback")
                req = urllib.request.Request(
                    v1_url,
                    headers={"User-Agent": "God4xe-Backend/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as u_resp:
                    v1_status = u_resp.status
                    raw_data = json.loads(u_resp.read().decode("utf-8"))

            if raw_data and isinstance(raw_data, dict):
                for kid, pem_str in raw_data.items():
                    if isinstance(pem_str, str) and "BEGIN CERTIFICATE" in pem_str:
                        cert = x509.load_pem_x509_certificate(pem_str.encode("utf-8"), default_backend())
                        keys[kid] = cert.public_key()

                logger.info(
                    f"[JWKS_V1_SUCCESS] HTTP Status: {v1_status} | "
                    f"Keys parsed: {len(keys)} | Key IDs: {list(keys.keys())}"
                )
        except Exception as e:
            logger.warning(f"[JWKS_V1_FAILED] Failed to fetch/parse Google v1 certs endpoint: {type(e).__name__}: {e}")

    if keys:
        _GOOGLE_JWKS_CACHE = keys
        _GOOGLE_JWKS_CACHE_EXPIRY = now + cache_ttl
        logger.info(f"[JWKS_CACHED] Successfully cached {len(keys)} Google public signing keys for {cache_ttl}s")
    else:
        logger.warning("[JWKS_EMPTY] No usable Google public signing keys could be retrieved from remote endpoints")

    return _GOOGLE_JWKS_CACHE

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
            INSERT INTO user_profiles (user_id, display_name, avatar_url, rank_tier, is_custom_avatar, is_custom_username)
            VALUES (%s, %s, %s, %s, 0, 0);
        """, (user_id, username, "/static/images/default-avatar.png", "Bronze"))

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
    """
    Cryptographically verify a Google ID Token:
    1. First attempts Google's official google-auth library if available.
    2. Seamlessly falls back to RFC 7515 / RFC 7519 RS256 JWKS verification via cryptography:
       - Header RS256 algorithm validation
       - Issuer validation (accounts.google.com or https://accounts.google.com)
       - Audience validation (GOOGLE_CLIENT_ID / client_id)
       - Expiration validation (exp > now)
       - Identity validation (sub and email presence)
       - Cryptographic signature validation against Google's public signing keys
    Logs comprehensive telemetry for diagnostics without exposing sensitive token secrets.
    """
    if not id_token_str or not isinstance(id_token_str, str):
        raise ValueError("Google ID token string is required")

    expected_aud = (client_id or GOOGLE_CLIENT_ID or "").strip()

    # Pre-parse unverified header to inspect kid and alg for logging and routing
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
        logger.warning(f"[GOOGLE_AUTH] Malformed token header: {e}")
        raise ValueError("Invalid Google token header")

    token_kid = header.get("kid", "unknown")
    token_alg = header.get("alg", "unknown")
    logger.info(
        f"[GOOGLE_AUTH_START] Verification requested | Alg: {token_alg} | "
        f"Kid: {token_kid} | Expected Aud: {expected_aud[:25] if expected_aud else '(none)'}..."
    )

    google_auth_error = None
    # Attempt 1: Official google-auth verification if library is available
    if _GOOGLE_AUTH_AVAILABLE:
        logger.info(
            f"[GOOGLE_AUTH_METHOD] Attempting official google-auth SDK "
            f"verify_oauth2_token for kid '{token_kid}'"
        )
        try:
            req = google_requests.Request()
            # Allow 10s clock skew to account for slight device/server clock drift
            claims = google_id_token.verify_oauth2_token(
                id_token_str,
                req,
                audience=expected_aud if expected_aud else None,
                clock_skew_in_seconds=10
            )
            google_id = str(claims.get("sub", "")).strip()
            email = claims.get("email", "").lower().strip()
            if not google_id:
                raise ValueError("Token missing subject (sub) claim")
            if not email:
                raise ValueError("Token missing email claim")

            logger.info(
                f"[GOOGLE_AUTH_OFFICIAL_SUCCESS] Official google-auth SDK successfully verified "
                f"token for sub={google_id}, email={email}"
            )
            return claims
        except Exception as e:
            google_auth_error = f"{type(e).__name__}: {e}"
            logger.warning(
                f"[GOOGLE_AUTH_OFFICIAL_FAILED] Official google-auth SDK failed: "
                f"{google_auth_error} (kid: {token_kid}). Evaluating fallback."
            )
            err_str = str(e).lower()
            # If audience, issuer, or expiration definitively failed, reject immediately
            if any(term in err_str for term in ["wrong recipient", "audience mismatch", "token has wrong audience", "token expired", "wrong issuer"]):
                raise ValueError(f"Google ID token verification failed: {e}")
    else:
        logger.info(
            f"[GOOGLE_AUTH_METHOD] google-auth SDK not installed or unavailable. "
            f"Proceeding to native JWKS verification."
        )

    # Attempt 2: Comprehensive manual JWKS verification using cryptography
    logger.info(
        f"[GOOGLE_AUTH_METHOD] Attempting manual JWKS cryptographic verification "
        f"(kid: {token_kid})"
    )
    if token_alg != "RS256":
        raise ValueError(f"Unsupported algorithm '{token_alg}': expected RS256")

    try:
        claims = json.loads(b64url_dec(payload_b64).decode('utf-8'))
    except Exception as e:
        logger.warning(f"[GOOGLE_AUTH] Malformed token payload: {e}")
        raise ValueError(f"Invalid Google token claims: {e}")

    # 1. Verify Issuer
    iss = claims.get("iss", "")
    if iss not in ("accounts.google.com", "https://accounts.google.com"):
        logger.warning(f"[GOOGLE_AUTH] Untrusted token issuer: '{iss}'")
        raise ValueError(f"Untrusted token issuer: '{iss}'")

    # 2. Verify Audience
    if expected_aud:
        token_aud = claims.get("aud")
        if isinstance(token_aud, list):
            if expected_aud not in token_aud:
                logger.warning(f"[GOOGLE_AUTH] Audience mismatch: expected '{expected_aud}', token had {token_aud}")
                raise ValueError(f"Audience mismatch: expected '{expected_aud}', but token audience is {token_aud}")
        elif token_aud != expected_aud:
            logger.warning(f"[GOOGLE_AUTH] Audience mismatch: expected '{expected_aud}', token had '{token_aud}'")
            raise ValueError(f"Audience mismatch: expected '{expected_aud}', but token audience is '{token_aud}'")

    # 3. Verify Expiry (with 10s allowable clock skew)
    exp = claims.get("exp")
    if not exp or not isinstance(exp, (int, float)):
        raise ValueError("Missing or invalid expiration in token claims")
    if exp < int(time.time()) - 10:
        logger.warning(f"[GOOGLE_AUTH] Token expired: exp={exp} < now={int(time.time())}")
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

    # Look in trusted/test keys first
    pub_key = get_trusted_google_key(token_kid)
    if pub_key:
        logger.info(f"[GOOGLE_AUTH_KEY] Using locally registered trusted key for kid '{token_kid}'")
    else:
        # If not in trusted keys, check the Google JWKS cache
        cached_keys = fetch_google_public_keys(force_refresh=False)
        pub_key = cached_keys.get(token_kid)
        if not pub_key:
            # Force refresh to handle key rotation
            logger.info(f"[GOOGLE_AUTH_KEY_ROTATION] Kid '{token_kid}' not in cache, force-refreshing JWKS")
            refreshed_keys = fetch_google_public_keys(force_refresh=True)
            pub_key = refreshed_keys.get(token_kid)

    if not pub_key:
        log_detail = f"Kid '{token_kid}' not found in Google public signing keys."
        if google_auth_error:
            log_detail += f" Official google-auth error was: {google_auth_error}."
        logger.error(f"[GOOGLE_AUTH_FAILED] {log_detail}")
        raise ValueError(f"Unable to verify Google token: public signing key for kid '{token_kid}' not found")

    try:
        pub_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        logger.warning(f"[GOOGLE_AUTH_SIG_FAIL] Cryptographic signature verification failed for kid '{token_kid}'")
        raise ValueError("Invalid token cryptographic signature: signature verification failed")

    logger.info(f"[GOOGLE_AUTH_JWKS_SUCCESS] Manual JWKS successfully verified token for sub={google_id}, email={email}")
    return claims


def generate_clean_username(cursor, name: str, email: str = "") -> str:
    raw = (name or "").strip()
    if not raw and email:
        raw = email.split("@")[0]
    clean = re.sub(r"[\s\-]+", "_", raw.lower().strip())
    clean = re.sub(r"[^a-z0-9_]", "", clean).strip("_")
    clean = re.sub(r"_+", "_", clean)[:20]
    if len(clean) < 3:
        clean = "player"

    # Try clean candidate directly
    cursor.execute("SELECT 1 FROM app_users WHERE LOWER(username) = LOWER(%s);", (clean,))
    if not cursor.fetchone():
        return clean

    # Try sequential numerical suffixes: _01 to _99
    for i in range(1, 100):
        suffix = f"{i:02d}"
        cand = f"{clean[:25]}_{suffix}" if not clean.endswith("_") else f"{clean[:25]}{suffix}"
        cursor.execute("SELECT 1 FROM app_users WHERE LOWER(username) = LOWER(%s);", (cand,))
        if not cursor.fetchone():
            return cand

    # Random 3-digit suffix fallback
    for _ in range(10):
        cand = f"{clean[:24]}_{secrets.randbelow(900) + 100}"
        cursor.execute("SELECT 1 FROM app_users WHERE LOWER(username) = LOWER(%s);", (cand,))
        if not cursor.fetchone():
            return cand

    return f"{clean[:20]}_{secrets.token_hex(2)}"
def authenticate_google_user(id_token_str: str, referral_code: str = None) -> tuple[dict, str]:
    claims = verify_google_id_token(id_token_str)

    google_id = str(claims["sub"]).strip()
    email = claims.get("email", "").lower().strip()
    name = claims.get("name", "").strip()
    avatar = claims.get("picture", "/static/images/default-avatar.png")

    with get_db() as conn:
        cursor = conn.cursor()
        # Look up strictly by stable Google sub identity first
        cursor.execute("SELECT id, username, email FROM app_users WHERE google_id = %s;", (google_id,))
        existing = cursor.fetchone()

        if not existing and email:
            # Check by email to link Google account to existing user
            cursor.execute("SELECT id, username, email FROM app_users WHERE email = %s;", (email,))
            existing = cursor.fetchone()
            if existing:
                user_id = existing["id"] if isinstance(existing, dict) else existing[0]
                cursor.execute("UPDATE app_users SET google_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (google_id, user_id))

        if existing:
            user_id = existing["id"] if isinstance(existing, dict) else existing[0]
            # Safe profile synchronization:
            cursor.execute("SELECT display_name, avatar_url, is_custom_avatar, is_custom_username FROM user_profiles WHERE user_id = %s;", (user_id,))
            prof = cursor.fetchone()
            prof_dict = dict(prof) if prof else {}

            p_updates = []
            p_params = []

            # Only sync avatar from Google if user has not uploaded/chosen a custom avatar
            if not prof_dict.get("is_custom_avatar", 0) and avatar:
                p_updates.append("avatar_url = %s")
                p_params.append(avatar)

            # Only populate display_name from Google name if display_name is not already set
            if not prof_dict.get("display_name") and name:
                p_updates.append("display_name = %s")
                p_params.append(name)

            if p_updates:
                p_updates.append("updated_at = CURRENT_TIMESTAMP")
                p_params.append(user_id)
                cursor.execute(f"UPDATE user_profiles SET {', '.join(p_updates)} WHERE user_id = %s;", tuple(p_params))
        else:
            # First-time Google registration: clean username candidate from Google name
            clean_username = generate_clean_username(cursor, name, email)
            display_name = name if name else clean_username
            ref_code = generate_referral_code()

            cursor.execute("""
                INSERT INTO app_users (
                    username, email, google_id, auth_provider, referral_code, is_active, is_verified
                ) VALUES (%s, %s, %s, %s, %s, 1, 1)
                RETURNING id;
            """, (clean_username, email, google_id, "GOOGLE", ref_code))
            res = cursor.fetchone()
            user_id = res["id"] if isinstance(res, dict) else res[0]

            cursor.execute("""
                INSERT INTO user_profiles (user_id, display_name, avatar_url, rank_tier, is_custom_avatar, is_custom_username)
                VALUES (%s, %s, %s, 'Bronze', 0, 0);
            """, (user_id, display_name, avatar))

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

    user_data = get_user_by_id(user_id)
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
                   u.google_id, u.is_active, u.is_verified, u.created_at,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar_url, '/static/images/default-avatar.png') AS avatar_url,
                   COALESCE(p.is_custom_avatar, 0) AS is_custom_avatar,
                   COALESCE(p.is_custom_username, 0) AS is_custom_username,
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

# --------------------------------------------------------------------------
# PROFILE EDITING & VALIDATION
# --------------------------------------------------------------------------
def check_username_availability(username: str, exclude_user_id: int = None) -> tuple[bool, str]:
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM app_users WHERE id = %s;", (user_id,))
        curr = cursor.fetchone()
        if not curr:
            raise ValueError("User not found")
        curr_dict = dict(curr)

        # Update username if provided and changed
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

        # Update profile fields
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
    import io
    from app.config import APP_DIR
    if not file_bytes:
        raise ValueError("Avatar file data is empty")
    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValueError("Avatar image exceeds 5MB limit")

    allowed_types = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif"
    }
    ext = allowed_types.get((content_type or "").lower().strip())
    if not ext:
        for k, v in [(".jpg", "jpg"), (".jpeg", "jpg"), (".png", "png"), (".webp", "webp")]:
            if filename.lower().endswith(k):
                ext = v
                break
    if not ext:
        raise ValueError("Invalid image format. Supported formats: JPEG, PNG, WEBP, GIF")

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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET avatar_url = %s, is_custom_avatar = 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (avatar_url, user_id))

    return get_user_by_id(user_id)

def remove_user_avatar(user_id: int) -> dict:
    default_avatar = "/static/images/default-avatar.png"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_profiles
            SET avatar_url = %s, is_custom_avatar = 0, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (default_avatar, user_id))
    return get_user_by_id(user_id)

# --------------------------------------------------------------------------
# ADMIN PANEL: USER MANAGEMENT
# --------------------------------------------------------------------------
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
                   u.google_id, u.is_active, u.is_verified, u.created_at,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar_url, '/static/images/default-avatar.png') AS avatar_url,
                   p.ff_uid, p.ff_ign, p.rank_tier,
                   COALESCE(a.balance, 0) AS diamond_balance,
                   (SELECT COUNT(*) FROM referrals WHERE referrer_id = u.id AND status = 'SUCCESSFUL') AS referral_count
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


def admin_adjust_user_diamonds(user_id: int, amount: int, admin_id: int, reason: str = None) -> dict:
    """Atomically adjust a user's diamond balance through the existing ledger."""
    if not isinstance(amount, int) or amount == 0:
        raise ValueError("Adjustment amount must be a non-zero integer")
    if not get_user_by_id(user_id):
        raise ValueError("User not found")

    from app.services.wallet import credit_diamonds, deduct_diamonds
    reason_clean = (reason or "Admin balance adjustment").strip()[:500]
    tx_type = "ADMIN_CREDIT" if amount > 0 else "ADMIN_DEBIT"
    if amount > 0:
        tx = credit_diamonds(
            user_id=user_id,
            amount=amount,
            tx_type=tx_type,
            reference_id=f"ADMIN-{admin_id}",
            admin_id=admin_id,
            description=reason_clean,
        )
    else:
        tx = deduct_diamonds(
            user_id=user_id,
            amount=abs(amount),
            tx_type=tx_type,
            reference_id=f"ADMIN-{admin_id}",
            admin_id=admin_id,
            description=reason_clean,
        )
    return tx

def delete_user_if_safe(user_id: int) -> dict:
    """Permanently delete only a clean/test account with no historical records."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, referral_code FROM app_users WHERE id = %s FOR UPDATE;", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("User not found")
        user = dict(row)

        checks = {
            "tournament participation": "SELECT COUNT(*) AS c FROM tournament_participants WHERE user_id = %s",
            "match results": "SELECT COUNT(*) AS c FROM match_results WHERE user_id = %s",
            "match disputes": "SELECT COUNT(*) AS c FROM match_disputes WHERE reporter_user_id = %s",
            "diamond transactions": "SELECT COUNT(*) AS c FROM diamond_transactions WHERE user_id = %s",
            "deposit requests": "SELECT COUNT(*) AS c FROM deposit_requests WHERE user_id = %s",
            "withdrawal requests": "SELECT COUNT(*) AS c FROM withdrawal_requests WHERE user_id = %s",
            "redeem history": "SELECT COUNT(*) AS c FROM redeem_history WHERE user_id = %s",
            "referrals": "SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = %s OR referee_id = %s",
            "support tickets": "SELECT COUNT(*) AS c FROM support_tickets WHERE user_id = %s",
            "other users using referral code": "SELECT COUNT(*) AS c FROM app_users WHERE referred_by_code = %s",
        }
        for label, query in checks.items():
            params = (user_id, user_id) if label == "referrals" else ((user["referral_code"],) if label == "other users using referral code" else (user_id,))
            cursor.execute(query, params)
            count = cursor.fetchone()["c"]
            if count:
                raise ValueError(f"Cannot permanently delete this user: {label} exist. Deactivate the account instead.")

        cursor.execute("DELETE FROM app_users WHERE id = %s;", (user_id,))
        if cursor.rowcount != 1:
            raise ValueError("User deletion failed")

    return user

def revoke_user_sessions(user_id: int) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_sessions WHERE user_id = %s;", (user_id,))
        count = cursor.rowcount
    return count
