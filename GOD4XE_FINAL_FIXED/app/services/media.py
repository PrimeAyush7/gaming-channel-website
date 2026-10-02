import os
import uuid
import datetime
from pathlib import Path
from PIL import Image
import io
from app.config import (
    UPLOAD_DIR,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
)
from app.database import get_db

def dict_from_row(row):
    if not row:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            d[k] = str(v)
    return d

def is_valid_image(content: bytes, ext: str) -> bool:
    """Validates that file content actually matches an image format."""
    if ext == "svg":
        try:
            head = content[:1024].decode('utf-8', errors='ignore').lower()
            return "<svg" in head
        except Exception:
            return False

    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
        return True
    except Exception:
        return False

def upload_to_cloudinary(content: bytes, filename: str, folder: str = "god4xe") -> str:
    """
    Direct HTTPS multipart upload to Cloudinary using standard library.
    Returns secure_url on success, or None on failure/not configured.
    """
    if not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
        return None

    try:
        import hashlib
        import time
        import json
        import urllib.request

        ts = str(int(time.time()))
        to_sign = f"folder={folder}&timestamp={ts}{CLOUDINARY_API_SECRET}"
        signature = hashlib.sha1(to_sign.encode("utf-8")).hexdigest()

        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()

        def add_field(name, value):
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body.extend(f"{value}\r\n".encode("utf-8"))

        add_field("api_key", CLOUDINARY_API_KEY)
        add_field("timestamp", ts)
        add_field("folder", folder)
        add_field("signature", signature)

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("secure_url") or data.get("url")
    except Exception as e:
        print(f"[CLOUDINARY FALLBACK] Upload failed ({e}), defaulting to local disk.")
        return None

def save_media_file(filename: str, content: bytes, mime_type: str) -> tuple[dict, str]:
    if len(content) > MAX_UPLOAD_SIZE:
        return None, f"File size exceeds limit of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."

    raw_ext = Path(filename).suffix.lstrip(".").lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        return None, f"File extension '{raw_ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

    if not is_valid_image(content, raw_ext):
        return None, "File content is not a valid image or is corrupted."

    safe_name = f"{uuid.uuid4().hex}.{raw_ext}"
    target_path = UPLOAD_DIR / safe_name

    with open(target_path, "wb") as f:
        f.write(content)

    # Cloudinary persistence with automatic fallback to local disk
    cloud_url = upload_to_cloudinary(content, safe_name, folder="god4xe_media")
    public_url = cloud_url if cloud_url else f"/static/uploads/{safe_name}"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO media (filename, original_name, mime_type, file_size, url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (safe_name, filename, mime_type or f"image/{raw_ext}", len(content), public_url))
        res = cursor.fetchone()
        media_id = res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]
        cursor.execute("SELECT * FROM media WHERE id = %s;", (media_id,))
        record = dict_from_row(cursor.fetchone())
        return record, None

def get_all_media(limit: int = 50):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media ORDER BY id DESC LIMIT %s;", (limit,))
        return [dict_from_row(r) for r in cursor.fetchall()]

def delete_media(media_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM media WHERE id = %s;", (media_id,))
        row = cursor.fetchone()
        if row:
            filename = row["filename"]
            file_path = UPLOAD_DIR / filename
            if file_path.exists():
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            cursor.execute("DELETE FROM media WHERE id = %s;", (media_id,))
            return True
        return False

def download_and_save_remote_image(url: str) -> str:
    """
    Downloads an external image (e.g. Discord CDN, Blogger, external hotlink) and saves it locally
    so it becomes a permanent local upload and never fails due to expiry or bot blocks.
    Returns the permanent public URL (e.g. /static/uploads/uuid.png) or the original url if failed.
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return url
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = resp.read()
                if len(data) > 100:
                    clean_path = url.split("?")[0].rstrip("/")
                    raw_ext = clean_path.split(".")[-1].lower() if "." in clean_path else "png"
                    if raw_ext not in ALLOWED_EXTENSIONS or len(raw_ext) > 5:
                        raw_ext = "png"
                    record, err = save_media_file(f"remote_import.{raw_ext}", data, f"image/{raw_ext}")
                    if record and record.get("url"):
                        return record["url"]
    except Exception as e:
        print(f"[REMOTE IMAGE IMPORT FAILED] {e}")
    return url
