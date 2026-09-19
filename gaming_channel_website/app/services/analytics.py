from app.database import get_db

def record_event(event_type: str, target_id: int = None, page_path: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO analytics_events (event_type, target_id, page_path)
            VALUES (?, ?, ?);
        """, (event_type, target_id, page_path))

def get_dashboard_stats():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Posts counts
        cursor.execute("SELECT COUNT(*) FROM posts;")
        total_posts = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1;")
        published_posts = cursor.fetchone()[0]

        draft_posts = total_posts - published_posts

        # Sections count
        cursor.execute("SELECT COUNT(*) FROM sections;")
        total_sections = cursor.fetchone()[0]

        # Tags count
        cursor.execute("SELECT COUNT(*) FROM tags;")
        total_tags = cursor.fetchone()[0]

        # Total views
        cursor.execute("SELECT COALESCE(SUM(view_count), 0) FROM posts;")
        total_post_views = cursor.fetchone()[0]

        # Total downloads
        cursor.execute("SELECT COALESCE(SUM(download_count), 0) FROM posts;")
        total_downloads = cursor.fetchone()[0]

        # YouTube clicks
        cursor.execute("SELECT COUNT(*) FROM analytics_events WHERE event_type = 'youtube_click';")
        youtube_clicks = cursor.fetchone()[0]

        # Recent events
        cursor.execute("""
            SELECT event_type, target_id, page_path, created_at
            FROM analytics_events
            ORDER BY id DESC
            LIMIT 10;
        """)
        recent_events = [dict(r) for r in cursor.fetchall()]

        # Top 5 most viewed posts
        cursor.execute("""
            SELECT id, title, slug, view_count, download_count
            FROM posts
            WHERE is_published = 1
            ORDER BY view_count DESC, id DESC
            LIMIT 5;
        """)
        top_posts = [dict(r) for r in cursor.fetchall()]

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
