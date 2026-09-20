import sqlite3
from contextlib import contextmanager
from app.config import DATABASE_PATH

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = DELETE;")
    except Exception:
        pass
    return conn

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database tables with indexes and initial settings."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Admins
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );
        """)

        # 2. Sessions (Secure Session Management)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE
            );
        """)

        # 3. Dynamic Sections / Categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '🎮',
                is_nav_visible INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Tags
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Posts / Articles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                summary TEXT,
                content TEXT NOT NULL,
                thumbnail_url TEXT,
                youtube_video_id TEXT,
                download_url TEXT,
                download_label TEXT DEFAULT 'DOWNLOAD FILE',
                section_id INTEGER,
                is_published INTEGER DEFAULT 1,
                is_featured INTEGER DEFAULT 0,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seo_title TEXT,
                seo_description TEXT,
                view_count INTEGER DEFAULT 0,
                download_count INTEGER DEFAULT 0,
                FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL
            );
        """)

        # 6. Post Tags Relation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_tags (
                post_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, tag_id),
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );
        """)

        # 7. YouTube Videos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS youtube_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                youtube_id TEXT NOT NULL,
                is_featured INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
              "youtube_channel_url": "https://www.youtube.com/@channel",
      "instagram_url": "",
      "whatsapp_url": "",
      "telegram_url": "",
      "discord_url": "",
      "facebook_url": "",

        # 8. Media Library
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 9. Site Settings (Key/Value configuration)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        # 10. Ad Settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_enabled INTEGER DEFAULT 0,
                client_id TEXT DEFAULT '',
                slot_home_top TEXT DEFAULT '',
                slot_home_bottom TEXT DEFAULT '',
                slot_post_top TEXT DEFAULT '',
                slot_post_bottom TEXT DEFAULT '',
                slot_sidebar TEXT DEFAULT '',
                custom_ads_txt TEXT DEFAULT ''
            );
        """)

        # 11. First-Party Analytics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                target_id INTEGER,
                page_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 12. Rate limiting tracking for login attempts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                ip_address TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 1,
                last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(is_published, published_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_slug ON sections(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_nav ON sections(is_nav_visible, sort_order);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_slug ON tags(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type, created_at);")

       default_settings = {
    "site_name": "GOD4XE",
    "site_tagline": "Pro Gaming Guides, Configs & Updates",
    "site_description": "The ultimate hub for game updates, sensitivity configs, pro guides, and exclusive gaming content.",
    "logo_url": "/static/images/default-logo.svg",
    "favicon_url": "/static/images/favicon.svg",
    "youtube_channel_url": "https://www.youtube.com/@channel",
    "instagram_url": "",
    "whatsapp_url": "",
    "telegram_url": "",
    "discord_url": "",
    "facebook_url": "",
    "seo_keywords": "gaming, configs, game updates, sensitivity, guides, gaming channel",
    "footer_text": "© 2026 GOD4XE. All rights reserved.",
    "robots_txt": "User-agent: *\nAllow: /",
}
        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?);", (k, v))

        cursor.execute("""
            INSERT OR IGNORE INTO ad_settings (id, is_enabled, client_id, custom_ads_txt)
            VALUES (1, 0, '', '# Google AdSense ads.txt configuration\n# google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0');
        """)
        
        cursor.execute("SELECT COUNT(*) FROM sections;")
        if cursor.fetchone()[0] == 0:
            default_sections = [
                ("FREE STYLE COMBO", "free-style-combo", "Pro freestyle combinations, keybinds, and mechanical setups.", "⚡", 1, 1),
                ("OB50 UPDATE", "ob50-update", "OB50 patch notes, weapon balances, and tactical meta shifts.", "🔥", 1, 2),
                ("OB51 UPDATE", "ob51-update", "OB51 full changelog, new character skills, and ranked meta.", "🚀", 1, 3),
                ("OB52 UPDATE", "ob52-update", "OB52 next-gen mechanics and competitive tournaments.", "👑", 1, 4),
                ("CONFIG FILES", "config-files", "Optimized graphics configs, high FPS unlockers, and smoothness settings.", "⚙️", 1, 5),
                ("SENSITIVITY", "sensitivity", "Best DPI, HUD layouts, and one-tap headshot sensitivity guides.", "🎯", 1, 6),
                ("GUIDES", "guides", "In-depth tactical guides, ranked tips, and weapon mastery.", "📚", 1, 7),
                ("EVENTS", "events", "Upcoming esports tournaments, redeem events, and rewards.", "🏆", 1, 8),
            ]
            cursor.executemany("""
                INSERT INTO sections (name, slug, description, icon, is_nav_visible, sort_order)
                VALUES (?, ?, ?, ?, ?, ?);
            """, default_sections)

        cursor.execute("SELECT COUNT(*) FROM tags;")
        if cursor.fetchone()[0] == 0:
            default_tags = [
                ("OB52", "ob52"),
                ("CONFIG", "config"),
                ("SENSITIVITY", "sensitivity"),
                ("FREE FIRE", "free-fire"),
                ("UPDATE", "update"),
                ("GUIDE", "guide"),
                ("FPS BOOST", "fps-boost"),
                ("HEADSHOT", "headshot"),
            ]
            cursor.executemany("INSERT INTO tags (name, slug) VALUES (?, ?);", default_tags)
