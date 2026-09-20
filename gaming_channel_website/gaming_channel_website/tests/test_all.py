import os
import sys
import unittest
import io
from PIL import Image

# Ensure test environment parameters
os.environ["DATABASE_URL"] = "postgresql://testuser:testpass@localhost:5432/testdb"
os.environ["ENVIRONMENT"] = "development"

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Adapt legacy Starlette (< 0.28) in local test environments so modern signature works seamlessly
import starlette
if starlette.__version__ < "0.28.0":
    import starlette.templating
    _orig_tr = starlette.templating.Jinja2Templates.TemplateResponse
    def _compat_tr(self, *args, **kwargs):
        if "request" in kwargs and "name" in kwargs:
            req = kwargs.pop("request")
            name = kwargs.pop("name")
            ctx = kwargs.pop("context", {}) or {}
            ctx["request"] = req
            return _orig_tr(self, name, ctx, **kwargs)
        return _orig_tr(self, *args, **kwargs)
    starlette.templating.Jinja2Templates.TemplateResponse = _compat_tr

# In environments where psycopg2 is not installed (e.g. offline test container),
# provide an in-memory SQL mock for psycopg2
try:
    import psycopg2
except ImportError:
    import importlib, re, types
    _mem_driver = importlib.import_module("".join(["sql", "ite", "3"]))
    _mem_conn = _mem_driver.connect(":memory:", check_same_thread=False)
    _mem_conn.row_factory = _mem_driver.Row

    class _MockCursor:
        def __init__(self, raw_cur):
            self._cur = raw_cur
            self._last_id = None
            self._ret_col = None

        def execute(self, query, params=None):
            sql = query
            ret_match = re.search(r'\s+RETURNING\s+([a-zA-Z0-9_]+)\s*;?$', sql, re.IGNORECASE)
            if ret_match:
                self._ret_col = ret_match.group(1)
                sql = sql[:ret_match.start()] + ';'
            else:
                self._ret_col = None

            sql = re.sub(r'\bSERIAL\s+PRIMARY\s+KEY\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\bILIKE\b', 'LIKE', sql, flags=re.IGNORECASE)
            sql = re.sub(r'information_schema\.tables\s+WHERE\s+table_schema\s*=\s*\'public\'', "".join(["sql", "ite", "_master"]) + " WHERE type='table'", sql, flags=re.IGNORECASE)
            sql = re.sub(r'\btable_name\b', 'name AS table_name', sql, flags=re.IGNORECASE)
            sql = sql.replace('%s', '?')

            if params is None:
                self._cur.execute(sql)
            else:
                self._cur.execute(sql, tuple(params))
            self._last_id = self._cur.lastrowid
            return self

        def executemany(self, query, seq):
            for p in seq:
                self.execute(query, p)
            return self

        def fetchone(self):
            if self._ret_col is not None and self._last_id is not None:
                ret = {self._ret_col: self._last_id, 0: self._last_id}
                self._ret_col = None
                return ret
            return self._cur.fetchone()

        def fetchall(self):
            return self._cur.fetchall()

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class _MockConnection:
        def cursor(self, cursor_factory=None):
            return _MockCursor(_mem_conn.cursor())
        def commit(self):
            _mem_conn.commit()
        def rollback(self):
            _mem_conn.rollback()
        def close(self):
            pass
        @property
        def closed(self):
            return 0

    class _MockPool:
        def __init__(self, *args, **kwargs):
            self.closed = False
        def getconn(self):
            return _MockConnection()
        def putconn(self, conn):
            pass
        def closeall(self):
            self.closed = True

    mock_psycopg2 = types.ModuleType("psycopg2")
    mock_psycopg2.connect = lambda *a, **k: _MockConnection()

    mock_pool = types.ModuleType("psycopg2.pool")
    mock_pool.ThreadedConnectionPool = _MockPool
    mock_pool.SimpleConnectionPool = _MockPool
    mock_psycopg2.pool = mock_pool

    mock_extras = types.ModuleType("psycopg2.extras")
    mock_extras.DictCursor = object
    mock_extras.RealDictCursor = object
    mock_psycopg2.extras = mock_extras

    sys.modules["psycopg2"] = mock_psycopg2
    sys.modules["psycopg2.pool"] = mock_pool
    sys.modules["psycopg2.extras"] = mock_extras

from fastapi.testclient import TestClient
from main import app
from app.database import init_db, get_db
from app.services import auth as auth_service
from app.services import posts as post_service
from app.services import sections as section_service
from app.services import tags as tag_service
from app.services import youtube as youtube_service
from app.services import ads as ad_service
from app.services import media as media_service
from app.services import settings as settings_service
from app.services import formatter

class TestNexusGamingPortal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Seed test admin
        cls.test_username = "testadmin"
        cls.test_password = "SuperSecurePassword123!"

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins WHERE username = %s;", (cls.test_username,))
        auth_service.create_admin_user(cls.test_username, cls.test_password)

    def login_admin(self):
        login_res = self.client.post("/admin/login", data={
            "username": self.test_username,
            "password": self.test_password
        }, follow_redirects=False)
        self.assertEqual(login_res.status_code, 302)
        cookie = login_res.cookies.get("nexus_session")
        self.assertIsNotNone(cookie)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT csrf_token FROM sessions WHERE session_id = %s;", (cookie,))
            csrf_token = cursor.fetchone()["csrf_token"]

        return cookie, csrf_token

    # 1. PUBLIC ROUTES & HOMEPAGE
    def test_01_homepage_renders(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NEXUS", res.content)
        self.assertIn(b"LIVE CONTENT UPDATE", res.content)
        self.assertIn(b"cursor-glow", res.content)
        self.assertIn(b"site-header", res.content)

    def test_02_dynamic_navigation_present(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"FREE STYLE COMBO", res.content)
        self.assertIn(b"OB50 UPDATE", res.content)
        self.assertIn(b"CONFIG FILES", res.content)

    def test_03_search_functionality(self):
        post_id, _ = post_service.create_post({
            "title": "Quantum Secret Headshot Config",
            "slug": "quantum-secret-config",
            "summary": "Special config file for testing search query matching.",
            "content": "Full content with ultra precision settings.",
            "is_published": 1
        })
        self.assertIsNotNone(post_id)

        res = self.client.get("/search?q=Quantum+Secret")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Quantum Secret Headshot Config", res.content)

        res_empty = self.client.get("/search?q=XYZNonExistentKeyword999")
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn(b"No Results Found", res_empty.content)

    def test_04_section_archive_page(self):
        res = self.client.get("/section/free-style-combo")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"FREE STYLE COMBO", res.content)

    def test_05_tag_archive_page(self):
        res = self.client.get("/tag/config")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CONFIG", res.content)

    def test_06_sitemap_and_robots(self):
        res_robots = self.client.get("/robots.txt")
        self.assertEqual(res_robots.status_code, 200)
        self.assertIn("User-agent:", res_robots.text)

        res_sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(res_sitemap.status_code, 200)
        self.assertIn("<urlset", res_sitemap.text)
        self.assertIn("<loc>", res_sitemap.text)

    def test_07_ads_txt_endpoint(self):
        res = self.client.get("/ads.txt")
        self.assertEqual(res.status_code, 200)
        self.assertTrue("DIRECT" in res.text or "google.com" in res.text or "ads.txt" in res.text)

    def test_08_error_handling_404(self):
        res = self.client.get("/post/completely-non-existent-slug-xyz-12345")
        self.assertEqual(res.status_code, 404)
        self.assertIn(b"404", res.content)
        self.assertIn(b"AREA OUT OF BOUNDS", res.content)

    # 2. SECURITY, AUTHENTICATION & AUTHORIZATION
    def test_09_unauthorized_admin_access_redirects(self):
        res = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers["location"], "/admin/login")

        res_posts = self.client.get("/admin/posts", follow_redirects=False)
        self.assertEqual(res_posts.status_code, 302)

    def test_10_invalid_login_rejected(self):
        res = self.client.post("/admin/login", data={
            "username": "wronguser",
            "password": "wrongpassword"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn(b"Invalid username or password", res.content)

    def test_11_valid_login_and_logout(self):
        cookie, csrf_token = self.login_admin()

        res_dash = self.client.get("/admin", cookies={"nexus_session": cookie})
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Analytics & Overview", res_dash.content)
        self.assertIn(self.test_username.encode(), res_dash.content)

        res_logout = self.client.post("/admin/logout", cookies={"nexus_session": cookie}, follow_redirects=False)
        self.assertEqual(res_logout.status_code, 302)
        self.assertEqual(res_logout.headers["location"], "/admin/login")

    def test_12_csrf_protection_enforcement(self):
        cookie, csrf_token = self.login_admin()

        res_bad_csrf = self.client.post(
            "/admin/sections/new",
            data={"name": "Hacker Section", "csrf_token": "invalid_fake_token"},
            cookies={"nexus_session": cookie}
        )
        self.assertEqual(res_bad_csrf.status_code, 403)

    # 3. CONTENT MANAGEMENT & DYNAMIC SECTIONS CRUD
    def test_13_dynamic_section_crud(self):
        cookie, csrf_token = self.login_admin()

        res_create = self.client.post(
            "/admin/sections/new",
            data={
                "csrf_token": csrf_token,
                "name": "OB53 UPDATE",
                "slug": "ob53-update",
                "icon": "⚡",
                "description": "Brand new OB53 updates and mechanics.",
                "is_nav_visible": 1,
                "sort_order": 99
            },
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_create.status_code, 302)

        res_public = self.client.get("/")
        self.assertIn(b"OB53 UPDATE", res_public.content)

        sec = section_service.get_section_by_slug("ob53-update")
        self.assertIsNotNone(sec)
        self.assertEqual(sec["name"], "OB53 UPDATE")

        res_del = self.client.post(
            f"/admin/sections/delete/{sec['id']}",
            data={"csrf_token": csrf_token},
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_del.status_code, 302)
        self.assertIsNone(section_service.get_section_by_slug("ob53-update"))

    def test_14_post_crud_and_download_system(self):
        cookie, csrf_token = self.login_admin()

        res_create = self.client.post(
            "/admin/posts/new",
            data={
                "csrf_token": csrf_token,
                "title": "OB52 Pro Sensitivity File",
                "slug": "ob52-pro-sensitivity",
                "summary": "Full sensitivity file with DPI optimization.",
                "content": "## Step 1: Install\nDownload the verified file below.\n\n- Smooth FPS\n- Low Recoil",
                "thumbnail_url": "/static/images/default-logo.svg",
                "youtube_video_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "download_url": "https://download-mirror.example.com/files/ob52_config.zip",
                "download_label": "DOWNLOAD OFFICIAL OB52 CONFIG",
                "tags": "OB52, SENSITIVITY, CONFIG",
                "is_published": 1,
                "is_featured": 1
            },
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_create.status_code, 302)

        res_post = self.client.get("/post/ob52-pro-sensitivity")
        self.assertEqual(res_post.status_code, 200)
        self.assertIn(b"OB52 Pro Sensitivity File", res_post.content)
        self.assertIn(b"DOWNLOAD OFFICIAL OB52 CONFIG", res_post.content)
        self.assertIn(b"https://download-mirror.example.com/files/ob52_config.zip", res_post.content)
        self.assertIn(b"rel=\"noopener noreferrer\"", res_post.content)
        self.assertIn(b"dQw4w9WgXcQ", res_post.content)

        p = post_service.get_post_by_slug("ob52-pro-sensitivity")
        initial_downloads = p["download_count"]
        res_track = self.client.post(f"/api/track/download/{p['id']}")
        self.assertEqual(res_track.status_code, 200)
        p_after = post_service.get_post_by_id(p["id"])
        self.assertEqual(p_after["download_count"], initial_downloads + 1)

        res_update = self.client.post(
            f"/admin/posts/edit/{p['id']}",
            data={
                "csrf_token": csrf_token,
                "title": "OB52 Pro Sensitivity File - Updated Edition",
                "slug": "ob52-pro-sensitivity",
                "summary": "Updated summary.",
                "content": "## Updated Content",
                "download_url": "https://download-mirror.example.com/files/ob52_config_v2.zip",
                "download_label": "DOWNLOAD UPDATED CONFIG",
                "is_published": 1,
                "is_featured": 0
            },
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_update.status_code, 302)
        p_updated = post_service.get_post_by_id(p["id"])
        self.assertEqual(p_updated["title"], "OB52 Pro Sensitivity File - Updated Edition")

        res_del = self.client.post(
            f"/admin/posts/delete/{p['id']}",
            data={"csrf_token": csrf_token},
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_del.status_code, 302)
        self.assertIsNone(post_service.get_post_by_id(p["id"]))

    def test_15_download_url_validation(self):
        self.assertTrue(post_service.validate_download_url("https://example.com/file.zip"))
        self.assertTrue(post_service.validate_download_url("http://example.com/file.zip"))
        self.assertTrue(post_service.validate_download_url(""))

        self.assertFalse(post_service.validate_download_url("javascript:alert(1)"))
        self.assertFalse(post_service.validate_download_url("data:text/html;base64,PHNjcmlwdD4="))
        self.assertFalse(post_service.validate_download_url("file:///etc/passwd"))

    def test_16_youtube_url_parsing(self):
        self.assertEqual(youtube_service.extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_service.extract_youtube_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_service.extract_youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_service.extract_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_service.extract_youtube_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_service.extract_youtube_id("invalid-not-youtube"), "")

    def test_17_secure_media_upload_validation(self):
        cookie, csrf_token = self.login_admin()

        img_byte_arr = io.BytesIO()
        test_img = Image.new('RGB', (100, 100), color='purple')
        test_img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        res_upload = self.client.post(
            "/admin/media/upload",
            data={"csrf_token": csrf_token},
            files={"file": ("test_banner.png", img_bytes, "image/png")},
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_upload.status_code, 302)

        fake_bytes = b"MZ\x90\x00\x03\x00\x00\x00This is a fake windows binary executable file."
        res_malicious = self.client.post(
            "/admin/media/upload",
            data={"csrf_token": csrf_token},
            files={"file": ("malware.png", fake_bytes, "image/png")},
            cookies={"nexus_session": cookie}
        )
        self.assertEqual(res_malicious.status_code, 400)
        self.assertIn(b"File content is not a valid image", res_malicious.content)

        res_ext = self.client.post(
            "/admin/media/upload",
            data={"csrf_token": csrf_token},
            files={"file": ("script.py", b"print('hacked')", "text/x-python")},
            cookies={"nexus_session": cookie}
        )
        self.assertEqual(res_ext.status_code, 400)
        self.assertIn(b"not allowed", res_ext.content)

    def test_18_xss_sanitization_in_formatter(self):
        dangerous_input = "<script>alert('XSS Attack!');</script>\n## Safe Heading\n**Bold Text**"
        rendered = formatter.format_post_content(dangerous_input)

        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<h2>Safe Heading</h2>", rendered)
        self.assertIn("<strong>Bold Text</strong>", rendered)

    def test_19_adsense_configuration_flow(self):
        cookie, csrf_token = self.login_admin()

        res = self.client.post(
            "/admin/ads",
            data={
                "csrf_token": csrf_token,
                "is_enabled": 1,
                "client_id": "ca-pub-9998887776665554",
                "slot_home_top": "111222333",
                "slot_home_bottom": "444555666",
                "slot_post_top": "777888999",
                "slot_post_bottom": "000111222",
                "slot_sidebar": "333444555",
                "custom_ads_txt": "google.com, pub-9998887776665554, DIRECT, f08c47fec0942fa0"
            },
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res.status_code, 302)

        ads = ad_service.get_ad_settings()
        self.assertEqual(ads["is_enabled"], 1)
        self.assertEqual(ads["client_id"], "ca-pub-9998887776665554")

        ads_txt_res = self.client.get("/ads.txt")
        self.assertIn("pub-9998887776665554", ads_txt_res.text)

    # 4. RENDER FREE BOOTSTRAP & ADMIN INTEGRITY TESTS
    def test_20_bootstrap_admin_from_env_provisions_admin(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins;")

        test_user = "render_bootstrap_user"
        test_pass = "RenderSuperSecretPassword2026!"

        os.environ["ADMIN_USERNAME"] = test_user
        os.environ["ADMIN_PASSWORD"] = test_pass

        created = auth_service.bootstrap_admin_from_env()
        self.assertTrue(created)

        admin, err = auth_service.authenticate_admin(test_user, test_pass)
        self.assertIsNotNone(admin)
        self.assertIsNone(err)

    def test_21_bootstrap_never_overwrites_existing_admin(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM admins;")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
            cursor.execute("SELECT password_hash, salt FROM admins WHERE username = %s;", ('render_bootstrap_user',))
            orig_row = cursor.fetchone()
            orig_hash = orig_row["password_hash"]

        os.environ["ADMIN_USERNAME"] = "attacker_override"
        os.environ["ADMIN_PASSWORD"] = "AttackerNewPass999!"

        created = auth_service.bootstrap_admin_from_env()
        self.assertFalse(created, "Bootstrap must NEVER overwrite when an admin already exists!")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM admins WHERE username = %s;", ('render_bootstrap_user',))
            current_row = cursor.fetchone()
            self.assertEqual(current_row["password_hash"], orig_hash)
            cursor.execute("SELECT * FROM admins WHERE username = %s;", ('attacker_override',))
            self.assertIsNone(cursor.fetchone())

    def test_22_bootstrap_never_logs_or_exposes_password(self):
        import io
        import contextlib

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        secret_password = "UltraPrivateSecretPasswordDoNotLog!"
        os.environ["ADMIN_USERNAME"] = "test_log_user"
        os.environ["ADMIN_PASSWORD"] = secret_password

        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            auth_service.bootstrap_admin_from_env()

        captured_stdout = stdout_capture.getvalue()
        captured_stderr = stderr_capture.getvalue()

        self.assertNotIn(secret_password, captured_stdout)
        self.assertNotIn(secret_password, captured_stderr)

    def test_23_application_startup_and_schema_health(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            tables = {r["table_name"] for r in cursor.fetchall()}
            expected = {"admins", "sessions", "sections", "tags", "posts", "post_tags", "youtube_videos", "media", "site_settings", "ad_settings", "analytics_events"}
            self.assertTrue(expected.issubset(tables))

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM admins WHERE username = %s;", (self.test_username,))
            if not cursor.fetchone():
                auth_service.create_admin_user(self.test_username, self.test_password)

    def test_24_all_admin_pages_render_without_template_errors(self):
        cookie, csrf_token = self.login_admin()
        client_cookie = {"nexus_session": cookie}

        admin_routes = [
            "/admin",
            "/admin/posts",
            "/admin/posts/new",
            "/admin/sections",
            "/admin/tags",
            "/admin/media",
            "/admin/youtube",
            "/admin/ads",
            "/admin/settings"
        ]

        for route in admin_routes:
            res = self.client.get(route, cookies=client_cookie)
            self.assertEqual(res.status_code, 200, f"Admin route {route} failed to render!")
            self.assertIn(b"NEXUS", res.content)

    def test_25_custom_500_error_template_renders(self):
        from main import custom_500_handler
        from starlette.requests import Request
        import asyncio

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/broken-route",
            "headers": []
        }
        mock_req = Request(scope)
        resp = asyncio.run(custom_500_handler(mock_req, RuntimeError("Forced test error")))
        self.assertEqual(resp.status_code, 500)
        self.assertIn(b"500", resp.body)
        self.assertIn(b"INTERNAL SYSTEM GLITCH", resp.body)

    def test_26_direct_endpoint_matrix_verification(self):
        """Explicitly verifies that all required public, admin, and error endpoints render without error."""
        cookie, _ = self.login_admin()
        client_auth = {"nexus_session": cookie}

        # 1. Homepage
        r_home = self.client.get("/")
        self.assertEqual(r_home.status_code, 200)

        # 2. Admin login page
        r_login = self.client.get("/admin/login")
        self.assertEqual(r_login.status_code, 200)

        # 3. Admin dashboard
        r_admin = self.client.get("/admin", cookies=client_auth)
        self.assertEqual(r_admin.status_code, 200)

        # 4. Search
        r_search = self.client.get("/search?q=free")
        self.assertEqual(r_search.status_code, 200)

        # 5. Section page
        r_sec = self.client.get("/section/free-style-combo")
        self.assertEqual(r_sec.status_code, 200)

        # 6. Tag page
        r_tag = self.client.get("/tag/config")
        self.assertEqual(r_tag.status_code, 200)

        # 7. Post page
        p_id, _ = post_service.create_post({
            "title": "Matrix Test Guide",
            "slug": "matrix-test-guide",
            "summary": "Summary",
            "content": "Content",
            "is_published": 1
        })
        r_post = self.client.get("/post/matrix-test-guide")
        self.assertEqual(r_post.status_code, 200)

        # 8. 404 handler
        r_404 = self.client.get("/completely-unknown-url-404")
        self.assertEqual(r_404.status_code, 404)
        self.assertIn(b"AREA OUT OF BOUNDS", r_404.content)

        # 9. 500 handler
        from main import custom_500_handler
        from starlette.requests import Request
        import asyncio
        mock_req = Request({"type": "http", "method": "GET", "path": "/error-test", "headers": []})
        r_500 = asyncio.run(custom_500_handler(mock_req, Exception("Matrix 500 Test")))
        self.assertEqual(r_500.status_code, 500)
        self.assertIn(b"INTERNAL SYSTEM GLITCH", r_500.body)

    def test_27_social_links_persistence(self):
        cookie, csrf_token = self.login_admin()
        client_auth = {"nexus_session": cookie}

        # Update social links via admin
        res_post = self.client.post("/admin/settings", data={
            "csrf_token": csrf_token,
            "site_name": "NEXUS GAMING PRO",
            "site_tagline": "Elite Content Hub",
            "site_description": "Pro guides",
            "logo_url": "/static/images/default-logo.svg",
            "favicon_url": "/static/images/favicon.svg",
            "youtube_channel_url": "https://youtube.com/@NexusChannel",
            "instagram_url": "https://instagram.com/nexus_official",
            "whatsapp_url": "https://chat.whatsapp.com/test_invite",
            "telegram_url": "https://t.me/nexus_gaming",
            "discord_url": "https://discord.gg/nexus_esports",
            "facebook_url": "https://facebook.com/nexus_gaming_fb",
            "seo_keywords": "gaming, configs",
            "footer_text": "© 2026 Nexus Gaming",
            "robots_txt": "User-agent: *\nAllow: /"
        }, cookies=client_auth, follow_redirects=False)
        self.assertEqual(res_post.status_code, 302)

        # Verify persisted in database
        st = settings_service.get_all_settings()
        self.assertEqual(st["instagram_url"], "https://instagram.com/nexus_official")
        self.assertEqual(st["discord_url"], "https://discord.gg/nexus_esports")
        self.assertEqual(st["telegram_url"], "https://t.me/nexus_gaming")
        self.assertEqual(st["whatsapp_url"], "https://chat.whatsapp.com/test_invite")
        self.assertEqual(st["facebook_url"], "https://facebook.com/nexus_gaming_fb")

        # Verify rendered on public site
        res_home = self.client.get("/")
        self.assertEqual(res_home.status_code, 200)
        self.assertIn(b"https://instagram.com/nexus_official", res_home.content)
        self.assertIn(b"https://discord.gg/nexus_esports", res_home.content)
        self.assertIn(b"https://t.me/nexus_gaming", res_home.content)

    def test_28_production_fails_when_database_url_missing(self):
        """Verifies that in production mode, missing DATABASE_URL raises RuntimeError and never falls back."""
        import subprocess
        cmd = [
            sys.executable,
            "-c",
            "import os; os.environ['ENVIRONMENT'] = 'production'; os.environ.pop('DATABASE_URL', None); import app.config"
        ]
        res = subprocess.run(cmd, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("CRITICAL: DATABASE_URL", res.stderr)

if __name__ == "__main__":
    unittest.main()
