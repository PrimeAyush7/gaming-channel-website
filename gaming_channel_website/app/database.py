from contextlib import contextmanager
import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from app.config import DATABASE_URL

_pg_pool = None

def get_connection_pool():
    global _pg_pool
    if _pg_pool is None or getattr(_pg_pool, "closed", False):
        if not DATABASE_URL:
            raise RuntimeError(
                "CRITICAL: DATABASE_URL is not configured. Please provide a valid PostgreSQL connection string."
            )
        try:
            _pg_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=15,
                dsn=DATABASE_URL,
                cursor_factory=DictCursor
            )
        except Exception as e:
            raise RuntimeError(f"CRITICAL: Failed to initialize PostgreSQL connection pool: {e}") from e
    return _pg_pool

@contextmanager
def get_db():
    p = get_connection_pool()
    conn = p.getconn()
    try:
        if getattr(conn, "closed", 0) != 0:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        yield conn
        conn.commit()
    except Exception:
        if getattr(conn, "closed", 0) == 0:
            conn.rollback()
        raise
    finally:
        if getattr(conn, "closed", 0) == 0:
            p.putconn(conn)

def init_db():
    """Initialize PostgreSQL database tables, indexes, and default seed configurations."""
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Admins
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                salt VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );
        """)

        # 2. Sessions (Secure Session Management)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
                csrf_token VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Dynamic Sections / Categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                slug VARCHAR(200) UNIQUE NOT NULL,
                description TEXT,
                icon VARCHAR(50) DEFAULT '🎮',
                is_nav_visible INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Tags
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Posts / Articles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                title VARCHAR(300) NOT NULL,
                slug VARCHAR(300) UNIQUE NOT NULL,
                summary TEXT,
                content TEXT NOT NULL,
                thumbnail_url TEXT,
                youtube_video_id VARCHAR(100),
                download_url TEXT,
                download_label VARCHAR(100) DEFAULT 'DOWNLOAD FILE',
                section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
                is_published INTEGER DEFAULT 1,
                is_featured INTEGER DEFAULT 0,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seo_title VARCHAR(300),
                seo_description TEXT,
                view_count INTEGER DEFAULT 0,
                download_count INTEGER DEFAULT 0
            );
        """)

        # 6. Post Tags Relation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_tags (
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (post_id, tag_id)
            );
        """)

        # 7. YouTube Videos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS youtube_videos (
                id SERIAL PRIMARY KEY,
                title VARCHAR(300) NOT NULL,
                youtube_id VARCHAR(100) NOT NULL,
                is_featured INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Media Library
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                original_name VARCHAR(255) NOT NULL,
                mime_type VARCHAR(100) NOT NULL,
                file_size BIGINT NOT NULL,
                url TEXT NOT NULL,
                data BYTEA,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 9. Site Settings (Key/Value configuration)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT
            );
        """)

        # 10. Ad Settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_enabled INTEGER DEFAULT 0,
                client_id VARCHAR(100) DEFAULT '',
                slot_home_top VARCHAR(100) DEFAULT '',
                slot_home_bottom VARCHAR(100) DEFAULT '',
                slot_post_top VARCHAR(100) DEFAULT '',
                slot_post_bottom VARCHAR(100) DEFAULT '',
                slot_sidebar VARCHAR(100) DEFAULT '',
                custom_ads_txt TEXT DEFAULT ''
            );
        """)

        # 11. First-Party Analytics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                target_id INTEGER,
                page_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 12. Rate limiting tracking for login attempts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                ip_address VARCHAR(100) PRIMARY KEY,
                attempts INTEGER DEFAULT 1,
                last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Application initialization metadata. This lets us distinguish a genuinely
        # fresh database from an existing database whose user-managed sections were
        # intentionally deleted.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_metadata (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT
            );
        """)

        # Media migration for existing installations.
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'media'
              AND column_name = 'data';
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE media ADD COLUMN data BYTEA;")

        # PostgreSQL Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(is_published, published_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_slug ON sections(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_nav ON sections(is_nav_visible, sort_order);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_slug ON tags(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type, created_at);")

        # Initialize Default Settings (including all social channels)
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
            "footer_text": "© 2026 GOD4XE. All rights reserved. Powered by GOD4XE Engine.",
            "seo_keywords": "gaming, configs, game updates, sensitivity, guides, gaming channel",
            "robots_txt": "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nSitemap: /sitemap.xml",
        }
        for k, v in default_settings.items():
            cursor.execute("""
                INSERT INTO site_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING;
            """, (k, v))

        # Default Ad Settings row
        cursor.execute("""
            INSERT INTO ad_settings (id, is_enabled, client_id, custom_ads_txt)
            VALUES (1, 0, '', '# Google AdSense ads.txt configuration\n# google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0')
            ON CONFLICT (id) DO NOTHING;
        """)

        # Default Dynamic Sections
        # Seed only once on a genuinely fresh database. After that, sections are
        # fully admin-managed and deleting one must remain permanent across restarts.
        cursor.execute("SELECT value FROM app_metadata WHERE key = %s;", ("default_sections_seeded",))
        sections_seed_marker = cursor.fetchone()
        if not sections_seed_marker:
            cursor.execute("SELECT COUNT(*) AS count FROM sections;")
            section_count_row = cursor.fetchone()
            section_count = section_count_row["count"] if isinstance(section_count_row, dict) or hasattr(section_count_row, "__getitem__") else section_count_row[0]

            if int(section_count or 0) == 0:
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
                for sec in default_sections:
                    cursor.execute("""
                        INSERT INTO sections (name, slug, description, icon, is_nav_visible, sort_order)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (slug) DO NOTHING;
                    """, sec)

            # Whether the database was empty or already had user-managed sections,
            # mark initialization complete so this block can never reseed later.
            cursor.execute("""
                INSERT INTO app_metadata (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING;
            """, ("default_sections_seeded", "1"))

        # Default Tags
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
        for tag in default_tags:
            cursor.execute("""
                INSERT INTO tags (name, slug)
                VALUES (%s, %s)
                ON CONFLICT (slug) DO NOTHING;
            """, tag)
