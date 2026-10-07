import os
import uuid
import datetime
from pathlib import Path
from PIL import Image
import io
import psycopg2
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

def optimize_image_if_needed(content: bytes, raw_ext: str) -> tuple[bytes, str, str]:
    """
    Optimizes large phone/camera images: resizes if > 1600px, compresses quality 85.
    Returns (optimized_bytes, new_ext, new_mime).
    """
    if raw_ext in ("svg", "gif", "pdf"):
        mime = "image/svg+xml" if raw_ext == "svg" else ("image/gif" if raw_ext == "gif" else "application/pdf")
        return content, raw_ext, mime
    try:
        image = Image.open(io.BytesIO(content))
        has_transparency = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)

        # Resize if dimensions exceed 1600px
        max_dim = 1600
        if image.width > max_dim or image.height > max_dim:
            image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        out_buf = io.BytesIO()
        if raw_ext in ("png", "webp") and has_transparency:
            image.save(out_buf, format="PNG", optimize=True)
            return out_buf.getvalue(), "png", "image/png"
        else:
            # Convert to standard RGB JPEG for 80% smaller size and universal browser compatibility
            rgb_im = image.convert("RGB")
            rgb_im.save(out_buf, format="JPEG", quality=85, optimize=True)
            return out_buf.getvalue(), "jpg", "image/jpeg"
    except Exception as e:
        print(f"[IMAGE OPTIMIZE FALLBACK] {e}")
        return content, raw_ext, f"image/{raw_ext}"

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
        print(f"[CLOUDINARY FALLBACK] Upload failed ({e}), defaulting to local disk / DB.")
        return None

def save_media_file(filename: str, content: bytes, mime_type: str) -> tuple[dict, str]:
    if len(content) > MAX_UPLOAD_SIZE:
        return None, f"File size exceeds limit of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."

    raw_ext = Path(filename).suffix.lstrip(".").lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        return None, f"File extension '{raw_ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

    if not is_valid_image(content, raw_ext):
        return None, "File content is not a valid image or is corrupted."

    # Optimize and compress large images to save space and speed up loading
    final_content, final_ext, final_mime = optimize_image_if_needed(content, raw_ext)

    safe_name = f"{uuid.uuid4().hex}.{final_ext}"
    target_path = UPLOAD_DIR / safe_name

    # 1. Save to local disk cache
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(final_content)
    except Exception as e:
        print(f"[LOCAL DISK WRITE ERROR] {e}")

    # 2. Cloudinary persistence if configured
    cloud_url = upload_to_cloudinary(final_content, safe_name, folder="god4xe_media")
    public_url = cloud_url if cloud_url else f"/static/uploads/{safe_name}"

    # 3. Store raw bytes directly in PostgreSQL (BYTEA) so Render reboots never lose images!
    binary_data = psycopg2.Binary(final_content) if final_content else None

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO media (filename, original_name, mime_type, file_size, url, file_data)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (safe_name, filename, final_mime or mime_type or f"image/{final_ext}", len(final_content), public_url, binary_data))
        except Exception:
            # Fallback if file_data column is not yet present
            conn.rollback()
            cursor.execute("""
                INSERT INTO media (filename, original_name, mime_type, file_size, url)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (safe_name, filename, final_mime or mime_type or f"image/{final_ext}", len(final_content), public_url))

        res = cursor.fetchone()
        media_id = res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]
        cursor.execute("SELECT id, filename, original_name, mime_type, file_size, url, created_at FROM media WHERE id = %s;", (media_id,))
        record = dict_from_row(cursor.fetchone())
        return record, None

def get_media_bytes_by_filename(filename: str) -> dict:
    """
    Retrieves image data from PostgreSQL persistent storage when local disk cache is wiped by Render reboot.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename, mime_type, file_data FROM media WHERE filename = %s;", (filename,))
            row = cursor.fetchone()
            if row and row.get("file_data"):
                return {
                    "filename": row["filename"],
                    "mime_type": row["mime_type"],
                    "file_data": bytes(row["file_data"])
                }
    except Exception as e:
        print(f"[GET MEDIA BYTES ERROR] {e}")
    return None

def get_all_media(limit: int = 50):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, original_name, mime_type, file_size, url, created_at FROM media ORDER BY id DESC LIMIT %s;", (limit,))
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
    Downloads an external image (e.g. Discord CDN, Blogger, Base64 data URL) and saves it locally
    and into PostgreSQL so it becomes permanent and never expires due to Discord 24hr token expiry or bot blocks.
    Returns the permanent public URL (e.g. /static/uploads/uuid.jpg) or the original url if failed.
    """
    if not url:
        return url
    url = url.strip()

    # Handle Base64 Data URI
    if url.startswith("data:image/") and ";base64," in url:
        try:
            import base64
            header, b64_data = url.split(";base64,", 1)
            mime_part = header.replace("data:", "").strip()
            raw_ext = mime_part.split("/")[-1].lower() if "/" in mime_part else "png"
            if raw_ext not in ALLOWED_EXTENSIONS:
                raw_ext = "png"
            raw_bytes = base64.b64decode(b64_data)
            record, err = save_media_file(f"upload_{uuid.uuid4().hex[:8]}.{raw_ext}", raw_bytes, mime_part)
            if record and record.get("url"):
                return record["url"]
        except Exception as e:
            print(f"[DATA URI DECODE FAILED] {e}")
            return url

    if not (url.startswith("http://") or url.startswith("https://")):
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
        with urllib.request.urlopen(req, timeout=12) as resp:
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
