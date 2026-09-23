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
    if len(content) > MAX_UPLOAD_SIZE:
        return None, f"File size exceeds limit of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB."

    raw_ext = Path(filename).suffix.lstrip(".").lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        return None, f"File extension '{raw_ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

    if not is_valid_image(content, raw_ext):
        return None, "File content is not a valid image or is corrupted."

    # Generate safe random filename to prevent collisions and path traversal
    safe_name = f"{uuid.uuid4().hex}.{raw_ext}"
    target_path = UPLOAD_DIR / safe_name

    with open(target_path, "wb") as f:
        f.write(content)

    public_url = f"/static/uploads/{safe_name}"

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
