import os
import uuid
import datetime
from pathlib import Path
from PIL import Image
import io
from app.config import UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS
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


def save_media_file(filename: str, content: bytes, mime_type: str) -> tuple[dict, str]:
    """Validate an image and persist its binary content in PostgreSQL.

    Render's local filesystem is ephemeral, so the database copy is authoritative.
    A local compatibility copy is still attempted for existing /static/uploads URLs,
    but the generated public URL always points at the persistent /media/{id} route.
    """
    if len(content) > MAX_UPLOAD_SIZE:
        return None, f"File size exceeds limit of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."

    raw_ext = Path(filename).suffix.lstrip(".").lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        return None, f"File extension '{raw_ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

    if not is_valid_image(content, raw_ext):
        return None, "File content is not a valid image or is corrupted."

    safe_name = f"{uuid.uuid4().hex}.{raw_ext}"
    mime = mime_type or f"image/{raw_ext}"

    # Persist the bytes first. This is the authoritative copy that survives
    # Render restarts/redeploys/spin-downs.
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO media (filename, original_name, mime_type, file_size, url, data)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (safe_name, filename, mime, len(content), "", content))
        res = cursor.fetchone()
        media_id = res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]
        public_url = f"/media/{media_id}"
        cursor.execute("UPDATE media SET url = %s WHERE id = %s;", (public_url, media_id))
        cursor.execute("SELECT * FROM media WHERE id = %s;", (media_id,))
        record = dict_from_row(cursor.fetchone())

    # Keep a local compatibility copy where possible. Never depend on this copy
    # for serving newly uploaded media.
    try:
        target_path = UPLOAD_DIR / safe_name
        with open(target_path, "wb") as f:
            f.write(content)
    except OSError:
        pass

    return record, None


def get_all_media(limit: int = 50):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, original_name, mime_type, file_size, url, created_at FROM media ORDER BY id DESC LIMIT %s;", (limit,))
        return [dict_from_row(r) for r in cursor.fetchall()]


def get_media_content(media_id: int):
    """Return persistent media bytes + metadata for the public media endpoint."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, mime_type, data FROM media WHERE id = %s;", (media_id,))
        row = cursor.fetchone()
        if not row or row["data"] is None:
            return None
        return {
            "id": row["id"],
            "mime_type": row["mime_type"],
            "data": bytes(row["data"]),
        }


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
