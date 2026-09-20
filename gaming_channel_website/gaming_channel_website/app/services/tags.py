import re
from app.database import get_db

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text or "tag"

def get_all_tags():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, COUNT(pt.post_id) AS post_count
            FROM tags t
            LEFT JOIN post_tags pt ON t.id = pt.tag_id
            GROUP BY t.id
            ORDER BY post_count DESC, t.name ASC;
        """)
        return [dict(row) for row in cursor.fetchall()]

def get_tag_by_slug(slug: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tags WHERE slug = %s;", (slug.strip().lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_or_create_tag(name: str):
    name = name.strip()
    slug = slugify(name)
    if not name:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE slug = %s;", (slug,))
        row = cursor.fetchone()
        if row:
            return row["id"] if isinstance(row, dict) or hasattr(row, "__getitem__") else row[0]
        cursor.execute("INSERT INTO tags (name, slug) VALUES (%s, %s) RETURNING id;", (name, slug))
        res = cursor.fetchone()
        return res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]

def set_post_tags(post_id: int, tags_input: str):
    """Parses comma-separated tag string and links them to the post."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM post_tags WHERE post_id = %s;", (post_id,))

        if not tags_input:
            return

        tag_items = [t.strip() for t in tags_input.split(",") if t.strip()]
        for tag_name in tag_items:
            tag_slug = slugify(tag_name)
            cursor.execute("SELECT id FROM tags WHERE slug = %s;", (tag_slug,))
            row = cursor.fetchone()
            if row:
                tag_id = row["id"] if isinstance(row, dict) or hasattr(row, "__getitem__") else row[0]
            else:
                cursor.execute("INSERT INTO tags (name, slug) VALUES (%s, %s) RETURNING id;", (tag_name.upper(), tag_slug))
                res = cursor.fetchone()
                tag_id = res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]

            cursor.execute("""
                INSERT INTO post_tags (post_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (post_id, tag_id))

def get_tags_for_post(post_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*
            FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            WHERE pt.post_id = %s
            ORDER BY t.name ASC;
        """, (post_id,))
        return [dict(row) for row in cursor.fetchall()]

def delete_tag(tag_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tags WHERE id = %s;", (tag_id,))
