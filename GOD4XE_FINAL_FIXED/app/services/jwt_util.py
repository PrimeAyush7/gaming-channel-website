import hmac
import hashlib
import base64
import json
import time
from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_DAYS

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4)) if (len(data) % 4) != 0 else ''
    return base64.urlsafe_b64decode(data + padding)

def encode_jwt(payload: dict, secret: str = JWT_SECRET, expires_in_days: int = JWT_EXPIRATION_DAYS) -> str:
    now = int(time.time())
    full_payload = {
        "iat": now,
        "exp": now + (expires_in_days * 86400),
        **payload
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _b64url_encode(json.dumps(full_payload, separators=(',', ':')).encode('utf-8'))
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    sig = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_jwt(token: str, secret: str = JWT_SECRET) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT structure")
    header_b64, payload_b64, sig_b64 = parts
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    expected_sig = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid signature")
    payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
    if "exp" in payload and payload["exp"] < int(time.time()):
        raise ValueError("Token has expired")
    return payload
