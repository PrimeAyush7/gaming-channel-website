from contextlib import contextmanager
import os
import re
from pathlib import Path
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from app.config import DATABASE_URL, BASE_DIR

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

def run_migrations(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(100) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    migrations_dir = BASE_DIR / "migrations"
    if not migrations_dir.exists():
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))
    for file_path in migration_files:
        version = file_path.name
        cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s;", (version,))
        if cursor.fetchone():
            continue

        sql_content = file_path.read_text(encoding="utf-8")
        statements = []
        current_stmt = []
        for line in sql_content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("--"):
                continue
            current_stmt.append(line)
            if line_str.endswith(";"):
                stmt = "\n".join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []
        if current_stmt:
            stmt = "\n".join(current_stmt).strip()
            if stmt:
                statements.append(stmt)

        for stmt in statements:
            try:
                cursor.execute(stmt)
            except Exception as ex:
                err_msg = str(ex).lower()
                if "syntax error" in err_msg and "add column if not exists" in stmt.lower():
                    clean_stmt = re.sub(r'ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS', 'ADD COLUMN', stmt, flags=re.IGNORECASE)
                    try:
                        cursor.execute(clean_stmt)
                    except Exception:
                        pass
                elif "duplicate column" in err_msg or "already exists" in err_msg:
                    pass
                else:
                    raise

        cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s);", (version,))

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        run_migrations(conn)

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
            "upi_id": "god4xe@upi",
            "upi_payee_name": "GOD4XE ESPORTS",
            "min_deposit_diamonds": "50",
            "deposit_instructions": "Pay via any UPI App (GPay, PhonePe, Paytm), enter UTR reference number and submit. Diamonds will be credited after admin review.",
            "withdrawals_enabled": "false"
        }
        for k, v in default_settings.items():
            cursor.execute("""
                INSERT INTO site_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING;
            """, (k, v))

        cursor.execute("""
            INSERT INTO ad_settings (id, is_enabled, client_id, custom_ads_txt)
            VALUES (1, 0, '', '# Google AdSense ads.txt configuration\ngoogle.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0')
            ON CONFLICT (id) DO NOTHING;
        """)

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
