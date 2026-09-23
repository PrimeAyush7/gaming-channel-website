import datetime
from app.database import get_db

def dict_from_row(row):
    if not row:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            d[k] = str(v)
    return d

def record_event(event_type: str, target_id: int = None, page_path: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO analytics_events (event_type, target_id, page_path)
            VALUES (%s, %s, %s);
        """, (event_type, target_id, page_path))

def get_dashboard_stats():
    with get_db() as conn:
        cursor = conn.cursor()

        # Posts counts
        cursor.execute("SELECT COUNT(*) FROM posts;")
        row = cursor.fetchone()
        total_posts = row[0] if row else 0

        cursor.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1;")
        row = cursor.fetchone()
        published_posts = row[0] if row else 0

        draft_posts = total_posts - published_posts

        # Sections count
        cursor.execute("SELECT COUNT(*) FROM sections;")
        row = cursor.fetchone()
        total_sections = row[0] if row else 0

        # Tags count
        cursor.execute("SELECT COUNT(*) FROM tags;")
        row = cursor.fetchone()
        total_tags = row[0] if row else 0

        # Total views
        cursor.execute("SELECT COALESCE(SUM(view_count), 0) FROM posts;")
        row = cursor.fetchone()
        total_post_views = row[0] if row else 0

        # Total downloads
        cursor.execute("SELECT COALESCE(SUM(download_count), 0) FROM posts;")
        row = cursor.fetchone()
        total_downloads = row[0] if row else 0

        # YouTube clicks
        cursor.execute("SELECT COUNT(*) FROM analytics_events WHERE event_type = 'youtube_click';")
        row = cursor.fetchone()
        youtube_clicks = row[0] if row else 0

        # Recent events
        cursor.execute("""
            SELECT event_type, target_id, page_path, created_at
            FROM analytics_events
            ORDER BY id DESC
            LIMIT 10;
        """)
        recent_events = [dict_from_row(r) for r in cursor.fetchall()]

        # Top 5 most viewed posts
        cursor.execute("""
            SELECT id, title, slug, view_count, download_count
            FROM posts
            WHERE is_published = 1
            ORDER BY view_count DESC, id DESC
            LIMIT 5;
        """)
        top_posts = [dict_from_row(r) for r in cursor.fetchall()]

        return {
            "total_posts": total_posts,
            "published_posts": published_posts,
            "draft_posts": draft_posts,
            "total_sections": total_sections,
            "total_tags": total_tags,
            "total_post_views": total_post_views,
            "total_downloads": total_downloads,
            "youtube_clicks": youtube_clicks,
            "recent_events": recent_events,
            "top_posts": top_posts
        }
