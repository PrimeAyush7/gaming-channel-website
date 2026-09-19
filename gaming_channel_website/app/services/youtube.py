import re
from app.database import get_db

YOUTUBE_REGEX = re.compile(
    r'(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
)

def extract_youtube_id(input_str: str) -> str:
    """Extracts a valid 11-character YouTube ID from a URL or returns the ID if valid."""
    if not input_str:
        return ""
    input_str = input_str.strip()
    match = YOUTUBE_REGEX.search(input_str)
    if match:
        return match.group(1)
    # Check if the string itself is a 11-char ID
    if re.fullmatch(r'[a-zA-Z0-9_-]{11}', input_str):
        return input_str
    return ""

def get_featured_video():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM youtube_videos
            WHERE is_featured = 1
            ORDER BY sort_order ASC, id DESC
            LIMIT 1;
        """)
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM youtube_videos ORDER BY sort_order ASC, id DESC LIMIT 1;")
            row = cursor.fetchone()
        return dict(row) if row else None

def get_all_videos(limit: int = 20):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM youtube_videos
            ORDER BY is_featured DESC, sort_order ASC, id DESC
            LIMIT ?;
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def add_video(title: str, youtube_input: str, is_featured: bool = False, sort_order: int = 0):
    yt_id = extract_youtube_id(youtube_input)
    if not yt_id:
        return None, "Invalid YouTube URL or Video ID provided."
    
    with get_db() as conn:
        cursor = conn.cursor()
        if is_featured:
            cursor.execute("UPDATE youtube_videos SET is_featured = 0;")
        cursor.execute("""
            INSERT INTO youtube_videos (title, youtube_id, is_featured, sort_order)
            VALUES (?, ?, ?, ?);
        """, (title.strip(), yt_id, 1 if is_featured else 0, sort_order))
        return cursor.lastrowid, None

def update_video(video_id: int, title: str, youtube_input: str, is_featured: bool = False, sort_order: int = 0):
    yt_id = extract_youtube_id(youtube_input)
    if not yt_id:
        return False, "Invalid YouTube URL or Video ID provided."
    with get_db() as conn:
        cursor = conn.cursor()
        if is_featured:
            cursor.execute("UPDATE youtube_videos SET is_featured = 0 WHERE id != ?;", (video_id,))
        cursor.execute("""
            UPDATE youtube_videos
            SET title = ?, youtube_id = ?, is_featured = ?, sort_order = ?
            WHERE id = ?;
        """, (title.strip(), yt_id, 1 if is_featured else 0, sort_order, video_id))
        return True, None

def delete_video(video_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM youtube_videos WHERE id = ?;", (video_id,))
