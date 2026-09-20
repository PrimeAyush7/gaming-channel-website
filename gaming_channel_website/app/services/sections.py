import re
from app.database import get_db

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text or "section"

def get_all_sections(only_nav: bool = False):
    with get_db() as conn:
        cursor = conn.cursor()
        if only_nav:
            cursor.execute("""
                SELECT * FROM sections
                WHERE is_nav_visible = 1
                ORDER BY sort_order ASC, name ASC;
            """)
        else:
            cursor.execute("""
                SELECT * FROM sections
                ORDER BY sort_order ASC, id ASC;
            """)
        return [dict(row) for row in cursor.fetchall()]

def get_section_by_id(section_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sections WHERE id = %s;", (section_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_section_by_slug(slug: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sections WHERE slug = %s;", (slug.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_section(name: str, slug: str, description: str = "", icon: str = "🎮", is_nav_visible: bool = True, sort_order: int = 0):
    name = name.strip()
    slug = slugify(slug if slug else name)
    with get_db() as conn:
        cursor = conn.cursor()
        # Ensure unique slug
        cursor.execute("SELECT id FROM sections WHERE slug = %s;", (slug,))
        if cursor.fetchone():
            count = 1
            orig_slug = slug
            while True:
                slug = f"{orig_slug}-{count}"
                cursor.execute("SELECT id FROM sections WHERE slug = %s;", (slug,))
                if not cursor.fetchone():
                    break
                count += 1

        cursor.execute("""
            INSERT INTO sections (name, slug, description, icon, is_nav_visible, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (name, slug, description.strip(), icon.strip() or "🎮", 1 if is_nav_visible else 0, sort_order))
        res = cursor.fetchone()
        return res["id"] if isinstance(res, dict) or hasattr(res, "__getitem__") else res[0]

def update_section(section_id: int, name: str, slug: str, description: str = "", icon: str = "🎮", is_nav_visible: bool = True, sort_order: int = 0):
    name = name.strip()
    slug = slugify(slug if slug else name)
    with get_db() as conn:
        cursor = conn.cursor()
        # Check collision with other sections
        cursor.execute("SELECT id FROM sections WHERE slug = %s AND id != %s;", (slug, section_id))
        if cursor.fetchone():
            slug = f"{slug}-{section_id}"

        cursor.execute("""
            UPDATE sections
            SET name = %s, slug = %s, description = %s, icon = %s, is_nav_visible = %s, sort_order = %s
            WHERE id = %s;
        """, (name, slug, description.strip(), icon.strip() or "🎮", 1 if is_nav_visible else 0, sort_order, section_id))

def delete_section(section_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sections WHERE id = %s;", (section_id,))
