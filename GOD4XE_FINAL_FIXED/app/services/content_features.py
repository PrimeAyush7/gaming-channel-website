import datetime
from app.database import get_db

# --------------------------------------------------------------------------
# SMART NOTIFICATIONS
# --------------------------------------------------------------------------
def send_smart_notification(user_id: int, title: str, message: str, notif_type: str, action_url: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, action_url, is_read)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id, user_id, title, message, notification_type, action_url, is_read, created_at;
        """, (user_id, title, message, notif_type, action_url))
        row = cursor.fetchone()
        return dict(row) if row else None

# --------------------------------------------------------------------------
# LATEST UPDATES (HOME SCREEN)
# --------------------------------------------------------------------------
def list_latest_updates(only_published: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_published = 1" if only_published else ""
        cursor.execute(f"""
            SELECT id, heading, description, cover_image_url, youtube_video_url,
                   button_text, button_url, display_order, is_published, created_at
            FROM latest_updates
            {where}
            ORDER BY display_order ASC, id DESC;
        """)
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

def create_latest_update(heading: str, description: str, cover_image_url: str = None, youtube_video_url: str = None, button_text: str = None, button_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO latest_updates (heading, description, cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, heading, description, cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published, created_at;
        """, (heading.strip(), description.strip(), cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published))
        return dict(cursor.fetchone())

def update_latest_update(update_id: int, heading: str, description: str, cover_image_url: str = None, youtube_video_url: str = None, button_text: str = None, button_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE latest_updates
            SET heading = %s, description = %s, cover_image_url = %s, youtube_video_url = %s,
                button_text = %s, button_url = %s, display_order = %s, is_published = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, heading, description, cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published;
        """, (heading.strip(), description.strip(), cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published, update_id))
        return dict(cursor.fetchone())

def delete_latest_update(update_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM latest_updates WHERE id = %s;", (update_id,))
    return True

# --------------------------------------------------------------------------
# ANNOUNCEMENTS & ARENA MARQUEE
# --------------------------------------------------------------------------
def list_announcements(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_active = 1" if only_active else ""
        cursor.execute(f"""
            SELECT id, title, message, banner_url, type, display_order, is_active, created_at
            FROM announcements
            {where}
            ORDER BY display_order ASC, id DESC;
        """)
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

def create_announcement(title: str, message: str, banner_url: str = None, type: str = 'INFO', display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO announcements (title, message, banner_url, type, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, title, message, banner_url, type, display_order, is_active, created_at;
        """, (title.strip(), message.strip(), banner_url, type, display_order, is_active))
        return dict(cursor.fetchone())

def update_announcement(announcement_id: int, title: str, message: str, banner_url: str = None, type: str = 'INFO', display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE announcements
            SET title = %s, message = %s, banner_url = %s, type = %s, display_order = %s, is_active = %s
            WHERE id = %s
            RETURNING id, title, message, banner_url, type, display_order, is_active;
        """, (title.strip(), message.strip(), banner_url, type, display_order, is_active, announcement_id))
        return dict(cursor.fetchone())

def delete_announcement(announcement_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM announcements WHERE id = %s;", (announcement_id,))
    return True

# --------------------------------------------------------------------------
# COMMUNITIES (SOCIAL LINKS)
# --------------------------------------------------------------------------
def list_communities(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_active = 1" if only_active else ""
        cursor.execute(f"""
            SELECT id, platform, name, url, logo_url, display_order, is_active, created_at
            FROM communities
            {where}
            ORDER BY display_order ASC, id ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

def update_community(comm_id: int, platform: str, name: str, url: str, logo_url: str = None, display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE communities
            SET platform = %s, name = %s, url = %s, logo_url = %s, display_order = %s, is_active = %s
            WHERE id = %s
            RETURNING id, platform, name, url, logo_url, display_order, is_active;
        """, (platform.strip(), name.strip(), url.strip(), logo_url, display_order, is_active, comm_id))
        return dict(cursor.fetchone())

def create_community(platform: str, name: str, url: str, logo_url: str = None, display_order: int = 0) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO communities (platform, name, url, logo_url, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            RETURNING id, platform, name, url, logo_url, display_order, is_active;
        """, (platform.strip(), name.strip(), url.strip(), logo_url, display_order))
        return dict(cursor.fetchone())

def delete_community(comm_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM communities WHERE id = %s;", (comm_id,))
    return True

# --------------------------------------------------------------------------
# TUTORIALS / HOW TO PLAY
# --------------------------------------------------------------------------
def list_tutorials(only_published: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_published = 1" if only_published else ""
        cursor.execute(f"""
            SELECT id, title, slug, category, content, image_url, video_url, display_order, is_published, created_at
            FROM tutorials
            {where}
            ORDER BY display_order ASC, id ASC;
        """)
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

def get_tutorial_by_slug(slug: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tutorials WHERE slug = %s;", (slug.strip().lower(),))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        return d

def create_tutorial(title: str, slug: str, category: str, content: str, image_url: str = None, video_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tutorials (title, slug, category, content, image_url, video_url, display_order, is_published)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, title, slug, category, content, image_url, video_url, display_order, is_published, created_at;
        """, (title.strip(), slug.strip().lower(), category.strip().upper(), content.strip(), image_url, video_url, display_order, is_published))
        return dict(cursor.fetchone())

def update_tutorial(tut_id: int, title: str, slug: str, category: str, content: str, image_url: str = None, video_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tutorials
            SET title = %s, slug = %s, category = %s, content = %s, image_url = %s, video_url = %s, display_order = %s, is_published = %s
            WHERE id = %s
            RETURNING id, title, slug, category, content, image_url, video_url, display_order, is_published;
        """, (title.strip(), slug.strip().lower(), category.strip().upper(), content.strip(), image_url, video_url, display_order, is_published, tut_id))
        return dict(cursor.fetchone())

def delete_tutorial(tut_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tutorials WHERE id = %s;", (tut_id,))
    return True
