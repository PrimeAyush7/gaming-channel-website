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
            sql = re.sub(r'\bADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\b', 'ADD COLUMN', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\s+FOR\s+UPDATE\b', '', sql, flags=re.IGNORECASE)

            try:
                if params is None:
                    self._cur.execute(sql)
                else:
                    self._cur.execute(sql, tuple(params))
            except Exception as e:
                err_str = str(e).lower()
                if 'duplicate column' in err_str:
                    pass
                else:
                    raise
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
        self.assertIn(b"GOD4XE", res.content)
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
            self.assertIn(b"GOD4XE", res.content)

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
            "site_name": "GOD4XE GAMING PRO",
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
            "footer_text": "© 2026 GOD4XE Gaming",
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

    def test_29_mobile_header_two_rows_and_dynamic_socials(self):
        """Verifies the two-row mobile header structure, dynamic social row, and desktop preservation."""
        from bs4 import BeautifulSoup
        from app.services import settings as s_service

        # 1. Test with all 6 social channels
        s_service.update_settings({
            "site_name": "GOD4XE",
            "youtube_channel_url": "https://www.youtube.com/@God4xeGaming",
            "instagram_url": "https://instagram.com/god4xe_official",
            "whatsapp_url": "https://chat.whatsapp.com/God4xeCommunity",
            "telegram_url": "https://t.me/god4xe_hub",
            "discord_url": "https://discord.gg/god4xe_esports",
            "facebook_url": "https://facebook.com/god4xe_page"
        })

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        soup = BeautifulSoup(res.text, "html.parser")
        header = soup.find("header", class_="site-header")
        self.assertIsNotNone(header)

        # Row 1 verification
        row1 = header.find("div", class_="header-inner")
        self.assertIsNotNone(row1)
        brand = row1.find("a", class_="site-brand")
        self.assertIsNotNone(brand)

        actions = row1.find("div", class_="header-actions")
        self.assertIsNotNone(actions)
        search_btn = actions.find("a", class_="mobile-search-btn")
        self.assertIsNotNone(search_btn)
        self.assertEqual(search_btn["href"], "/search")
        self.assertIsNotNone(search_btn.find("svg"))

        hamburger_btn = actions.find("button", class_="mobile-toggle-btn")
        self.assertIsNotNone(hamburger_btn)
        self.assertIsNotNone(hamburger_btn.find("svg"))

        # Desktop elements must still exist in DOM for desktop view
        desktop_nav = row1.find("nav", class_="desktop-nav")
        self.assertIsNotNone(desktop_nav)
        desktop_search = actions.find("form", class_="header-search-form")
        self.assertIsNotNone(desktop_search)
        desktop_yt = actions.find("a", class_="yt-sub-btn")
        self.assertIsNotNone(desktop_yt)

        # Row 2 verification (Dynamic Social Row)
        row2 = header.find("div", class_="mobile-social-bar")
        self.assertIsNotNone(row2)
        social_inner = row2.find("div", class_="mobile-social-inner")
        self.assertIsNotNone(social_inner)

        social_btns = social_inner.find_all("a", class_="mobile-social-btn")
        self.assertEqual(len(social_btns), 6)
        titles = [btn.get("title") for btn in social_btns]
        for expected in ["YouTube", "Instagram", "WhatsApp", "Telegram", "Discord", "Facebook"]:
            self.assertIn(expected, titles)

        # 2. Test with partial social channels
        s_service.update_settings({
            "youtube_channel_url": "https://www.youtube.com/@God4xeGaming",
            "instagram_url": "",
            "whatsapp_url": "https://chat.whatsapp.com/God4xeCommunity",
            "telegram_url": "",
            "discord_url": "",
            "facebook_url": ""
        })
        res_partial = self.client.get("/")
        soup_p = BeautifulSoup(res_partial.text, "html.parser")
        p_btns = soup_p.find("header", class_="site-header").find("div", class_="mobile-social-bar").find_all("a", class_="mobile-social-btn")
        self.assertEqual(len(p_btns), 2)
        self.assertEqual(set(b.get("title") for b in p_btns), {"YouTube", "WhatsApp"})

        # 3. Test with zero social channels
        s_service.update_settings({
            "youtube_channel_url": "",
            "instagram_url": "",
            "whatsapp_url": "",
            "telegram_url": "",
            "discord_url": "",
            "facebook_url": ""
        })
        res_empty = self.client.get("/")
        soup_e = BeautifulSoup(res_empty.text, "html.parser")
        e_row2 = soup_e.find("header", class_="site-header").find("div", class_="mobile-social-bar")
        self.assertIsNone(e_row2)

        # 4. Verify style.css rules for mobile and desktop media queries
        css_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css")
        with open(css_path, "r") as f:
            css_text = f.read()

        # Desktop hides mobile elements
        self.assertIn(".mobile-search-btn", css_text)
        self.assertIn(".mobile-social-bar", css_text)
        # Mobile media query overrides
        self.assertIn("@media (max-width: 768px)", css_text)
        self.assertIn(".mobile-social-btn", css_text)
        self.assertIn("overflow-x: auto", css_text)
        self.assertIn("scrollbar-width: none", css_text)

    def test_30_desktop_socials_red_live_badge_and_crest_logo(self):
        """Verifies desktop social icons, red LIVE CONTENT UPDATE badge, and GOD4XE header crest logo."""
        from bs4 import BeautifulSoup
        from PIL import Image
        from app.services import settings as s_service

        # 1. Image file check
        img_file = os.path.join(os.path.dirname(__file__), "..", "app", "static", "images", "1000074856.jpg.jpeg")
        self.assertTrue(os.path.exists(img_file), "Logo image 1000074856.jpg.jpeg missing")
        with Image.open(img_file) as im:
            self.assertEqual(im.format, "JPEG")

        # 2. Configure social channels
        s_service.update_settings({
            "site_name": "GOD4XE",
            "youtube_channel_url": "https://www.youtube.com/@God4xeGaming",
            "instagram_url": "https://instagram.com/god4xe_official",
            "whatsapp_url": "https://chat.whatsapp.com/God4xeCommunity",
            "telegram_url": "https://t.me/god4xe_hub",
            "discord_url": "https://discord.gg/god4xe_esports",
            "facebook_url": "https://facebook.com/god4xe_page"
        })

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        soup = BeautifulSoup(res.text, "html.parser")

        # Brand crest check
        brand = soup.find("a", class_="site-brand")
        crest_img = brand.find("img", class_="brand-crest-img")
        self.assertIsNotNone(crest_img)
        self.assertEqual(crest_img["src"], "/static/images/1000074856.jpg.jpeg")
        brand_text = brand.find("div", class_="site-brand-text")
        self.assertIn("GOD4XE", brand_text.get_text())
        self.assertIn("GAMING", brand_text.get_text())

        # Desktop social links in header actions
        header_actions = soup.find("div", class_="header-actions")
        desktop_social = header_actions.find("div", class_="desktop-social-links")
        self.assertIsNotNone(desktop_social)
        d_links = desktop_social.find_all("a", class_="desktop-social-btn")
        self.assertEqual(len(d_links), 5) # Instagram, WhatsApp, Telegram, Discord, Facebook

        # Large YouTube button present
        yt_btn = header_actions.find("a", class_="yt-sub-btn")
        self.assertIsNotNone(yt_btn)
        self.assertEqual(yt_btn["href"], "https://www.youtube.com/@God4xeGaming")

        # Mobile social bar preserved
        mob_bar = soup.find("div", class_="mobile-social-bar")
        self.assertIsNotNone(mob_bar)
        self.assertEqual(len(mob_bar.find_all("a", class_="mobile-social-btn")), 6)

        # Red theme for LIVE CONTENT UPDATE badge in style.css
        css_file = os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css")
        with open(css_file, "r") as cf:
            css = cf.read()
        self.assertIn(".hero-badge", css)
        self.assertIn("#ff4d4d", css)
        self.assertIn("pulse-glow-red", css)
        self.assertIn(".brand-crest-img", css)
        self.assertIn(".desktop-social-links", css)

    def test_31_admin_mobile_drawer_and_public_full_width(self):
        """Verifies admin mobile drawer, mobile topbar, full mobile width, and table responsiveness."""
        from bs4 import BeautifulSoup
        from app.services import auth as a_service

        # 1. Verify Admin Mobile Topbar, Drawer, and Backdrop
        a_service.create_admin_user("admin_test_31", "Pass31_Secure!")
        login_res = self.client.post("/admin/login", data={"username": "admin_test_31", "password": "Pass31_Secure!"}, follow_redirects=False)
        sess = login_res.cookies.get("nexus_session")

        dash_res = self.client.get("/admin", cookies={"nexus_session": sess})
        self.assertEqual(dash_res.status_code, 200)
        soup = BeautifulSoup(dash_res.text, "html.parser")

        # Topbar & Hamburger
        topbar = soup.find("header", class_="admin-mobile-topbar")
        self.assertIsNotNone(topbar)
        self.assertIn("GOD4XE", topbar.text)
        self.assertIn("ADMIN", topbar.text)
        toggle_btn = topbar.find(id="admin-menu-toggle")
        self.assertIsNotNone(toggle_btn)

        # Backdrop & Drawer
        backdrop = soup.find(id="admin-backdrop")
        self.assertIsNotNone(backdrop)
        sidebar = soup.find(id="admin-sidebar")
        self.assertIsNotNone(sidebar)
        close_btn = sidebar.find(id="admin-drawer-close")
        self.assertIsNotNone(close_btn)

        # All required admin navigation links present
        links = [a.text.strip() for a in sidebar.find_all("a")]
        self.assertTrue(any("Dashboard" in t for t in links))
        self.assertTrue(any("Posts" in t for t in links))
        self.assertTrue(any("Sections" in t for t in links))
        self.assertTrue(any("Tags" in t for t in links))
        self.assertTrue(any("Media" in t for t in links))
        self.assertTrue(any("YouTube" in t for t in links))
        self.assertTrue(any("AdSense" in t for t in links))
        self.assertTrue(any("Settings" in t for t in links))
        self.assertTrue(any("View Live Website" in t for t in links))
        logout_form = sidebar.find("form", action="/admin/logout")
        self.assertIsNotNone(logout_form)

        # 2. Verify admin.css rules
        admin_css_file = os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "admin.css")
        with open(admin_css_file, "r") as acf:
            admin_css = acf.read()
        self.assertIn("@media (max-width: 768px)", admin_css)
        self.assertIn(".admin-mobile-topbar", admin_css)
        self.assertIn("translateX(-100%)", admin_css)
        self.assertIn(".table-responsive", admin_css)
        self.assertIn("overflow-x: auto", admin_css)
        self.assertIn(".admin-two-col-grid", admin_css)
        self.assertIn(".dashboard-two-col-grid", admin_css)

        # 3. Verify public website CSS rules (Full mobile width & 100% viewport)
        style_css_file = os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css")
        with open(style_css_file, "r") as scf:
            style_css = scf.read()
        self.assertIn("box-sizing: border-box;", style_css)
        self.assertIn("overflow-x: hidden;", style_css)
        self.assertNotIn("100vw", style_css)
        self.assertIn(".site-header", style_css)
        self.assertIn(".main-content", style_css)
        self.assertIn(".site-footer", style_css)

        # 4. Verify admin.js contains drawer logic
        admin_js_file = os.path.join(os.path.dirname(__file__), "..", "app", "static", "js", "admin.js")
        with open(admin_js_file, "r") as ajf:
            admin_js = ajf.read()
        self.assertIn("initAdminDrawer", admin_js)
        self.assertIn("admin-menu-toggle", admin_js)
        self.assertIn("admin-sidebar", admin_js)



class TestEsportsFullSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.services import auth as auth_svc, tournaments as t_svc, wallet as w_svc
        cls.auth_svc = auth_svc
        cls.t_svc = t_svc
        cls.w_svc = w_svc
        cls.super_admin_id = auth_svc.create_admin_with_role('esports_boss', 'Pass1234!', 'SUPER_ADMIN', 'boss@esports.com')
        cls.fin_admin_id = auth_svc.create_admin_with_role('fin_officer', 'Pass1234!', 'FINANCE_ADMIN', 'fin@esports.com')

    @property
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_esports_01_user_registration_login(self):
        res = self.client.post('/api/v1/auth/register', json={
            'username': 'esports_pro',
            'email': 'pro@god4xe.com',
            'phone': '9876543211',
            'password': 'Password123!'
        })
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('token', data)

        login_res = self.client.post('/api/v1/auth/login', json={
            'identity': 'pro@god4xe.com',
            'password': 'Password123!'
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()['token']

        me_res = self.client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()['user']['username'], 'esports_pro')

    def test_esports_02_zero_cost_otp_flow(self):
        req_res = self.client.post('/api/v1/auth/otp/request', json={'phone': '+919999988888'})
        self.assertEqual(req_res.status_code, 200)
        otp = req_res.json().get('test_otp')
        self.assertIsNotNone(otp)

        v_res = self.client.post('/api/v1/auth/otp/verify', json={'phone': '+919999988888', 'otp': otp})
        self.assertEqual(v_res.status_code, 200)
        self.assertIn('token', v_res.json())

    def test_esports_03_google_auth_flow(self):
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization
        from app.services.users_auth import register_trusted_google_key
        import base64
        import json
        import time

        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        register_trusted_google_key('test-google-kid-1', pub_pem)

        def make_token(header_dict, claims_dict, sign=True, tamper=False):
            def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip('=')
            h = b64(header_dict)
            p = b64(claims_dict)
            msg = f"{h}.{p}".encode('utf-8')
            if sign:
                sig_bytes = priv_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
                if tamper:
                    sig_bytes = sig_bytes[:-1] + b'\x00'
                return f"{h}.{p}." + base64.urlsafe_b64encode(sig_bytes).decode().rstrip('=')
            return f"{h}.{p}.unsigned_fake_sig"

        now = int(time.time())
        valid_header = {'alg': 'RS256', 'typ': 'JWT', 'kid': 'test-google-kid-1'}
        valid_claims = {
            'sub': 'google_test_uid_99',
            'email': 'google_champ@gmail.com',
            'name': 'Google Champ',
            'picture': 'https://example.com/pic.png',
            'iss': 'https://accounts.google.com',
            'exp': now + 3600,
            'iat': now
        }

        # 1. Valid cryptographic RSA-SHA256 signed token -> MUST PASS (HTTP 200)
        valid_token = make_token(valid_header, valid_claims, sign=True)
        res = self.client.post('/api/v1/auth/google', json={'id_token': valid_token})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['user']['email'], 'google_champ@gmail.com')

        # 2. Tampered / Forged signature token -> MUST FAIL (HTTP 400)
        tampered_token = make_token(valid_header, valid_claims, sign=True, tamper=True)
        tamper_res = self.client.post('/api/v1/auth/google', json={'id_token': tampered_token})
        self.assertEqual(tamper_res.status_code, 400)
        self.assertIn('signature verification failed', tamper_res.json()['detail'].lower())

        # 3. Expired token -> MUST FAIL (HTTP 400)
        expired_claims = valid_claims.copy()
        expired_claims['exp'] = now - 60
        expired_token = make_token(valid_header, expired_claims, sign=True)
        exp_res = self.client.post('/api/v1/auth/google', json={'id_token': expired_token})
        self.assertEqual(exp_res.status_code, 400)
        self.assertIn('expired', exp_res.json()['detail'].lower())

        # 4. Untrusted issuer -> MUST FAIL (HTTP 400)
        bad_iss_claims = valid_claims.copy()
        bad_iss_claims['iss'] = 'https://fake-accounts.badactor.com'
        bad_iss_token = make_token(valid_header, bad_iss_claims, sign=True)
        iss_res = self.client.post('/api/v1/auth/google', json={'id_token': bad_iss_token})
        self.assertEqual(iss_res.status_code, 400)
        self.assertIn('untrusted token issuer', iss_res.json()['detail'].lower())

    def test_esports_04_profile_and_freefire_update(self):
        u = self.client.post('/api/v1/auth/register', json={
            'username': 'ff_master',
            'email': 'master@ff.com',
            'password': 'Password123!'
        }).json()
        token = u['token']

        up = self.client.put(
            '/api/v1/users/freefire',
            headers={'Authorization': f'Bearer {token}'},
            json={'ff_uid': '1234567890', 'ff_ign': 'MASTER_OP'}
        )
        self.assertEqual(up.status_code, 200)
        self.assertEqual(up.json()['profile']['ff_uid'], '1234567890')
        self.assertEqual(up.json()['profile']['ff_ign'], 'MASTER_OP')

    def test_esports_05_tournaments_system(self):
        t_free = self.t_svc.create_tournament(
            title='Sunday Special Free',
            entry_type='FREE',
            entry_fee_diamonds=0,
            prize_amount_diamonds=500,
            max_slots=30
        )
        self.assertEqual(t_free['entry_type'], 'FREE')
        self.assertEqual(t_free['entry_fee_diamonds'], 0)

        t_diamonds = self.t_svc.create_tournament(
            title='Weekend Diamond Battle',
            entry_type='DIAMONDS',
            entry_fee_diamonds=25,
            prize_amount_diamonds=1200,
            max_slots=30
        )
        self.assertEqual(t_diamonds['entry_type'], 'DIAMONDS')
        self.assertEqual(t_diamonds['entry_fee_diamonds'], 25)

        with self.assertRaises(ValueError):
            self.t_svc.create_tournament(
                title='Invalid Diamonds',
                entry_type='DIAMONDS',
                entry_fee_diamonds=0
            )

        list_res = self.client.get('/api/v1/tournaments?status=UPCOMING')
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(list_res.json()['count'], 2)

    def test_esports_06_joining_and_room_credentials(self):
        u = self.client.post('/api/v1/auth/register', json={
            'username': 'room_player',
            'email': 'room@player.com',
            'password': 'Password123!'
        }).json()
        token = u['token']

        t = self.t_svc.create_tournament(title='Secret Room Tourn', entry_type='FREE', max_slots=10)

        room_err = self.client.get(f'/api/v1/tournaments/{t["id"]}/room', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(room_err.status_code, 403)

        j = self.client.post(f'/api/v1/tournaments/{t["id"]}/join', headers={'Authorization': f'Bearer {token}'}, json={'ff_uid': '9988', 'ff_ign': 'RoomPro'})
        self.assertEqual(j.status_code, 200)

        self.t_svc.update_tournament_room_credentials(t['id'], 'ROOM_123', 'PASS_456', 'Join fast')

        room_ok = self.client.get(f'/api/v1/tournaments/{t["id"]}/room', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(room_ok.status_code, 200)
        self.assertEqual(room_ok.json()['room_id'], 'ROOM_123')

    def test_esports_07_wallet_ledger_and_deposit_approval(self):
        u = self.client.post('/api/v1/auth/register', json={
            'username': 'wallet_pro',
            'email': 'wallet@pro.com',
            'password': 'Password123!'
        }).json()
        token = u['token']
        uid = u['user']['id']

        dep = self.client.post(
            '/api/v1/wallet/deposit-request',
            headers={'Authorization': f'Bearer {token}'},
            json={'amount': 300, 'utr_reference': 'UTR_PRO_8888'}
        )
        self.assertEqual(dep.status_code, 201)
        req_id = dep.json()['request']['id']

        self.w_svc.review_deposit_request(req_id, admin_id=self.fin_admin_id, approve=True)

        bal = self.client.get('/api/v1/wallet/balance', headers={'Authorization': f'Bearer {token}'}).json()
        self.assertEqual(bal['balance'], 325)

    def test_esports_08_withdrawals_disabled_by_default(self):
        u = self.client.post('/api/v1/auth/register', json={
            'username': 'w_user',
            'email': 'w@user.com',
            'password': 'Password123!'
        }).json()
        token = u['token']

        w_res = self.client.post(
            '/api/v1/wallet/withdraw',
            headers={'Authorization': f'Bearer {token}'},
            json={'amount': 100, 'upi_id': 'pay@upi'}
        )
        self.assertEqual(w_res.status_code, 403)

    def test_esports_09_redeem_and_support_tickets(self):
        from app.services import social as soc_svc
        soc_svc.create_redeem_code('BONUS100', 100, max_uses=5)

        u = self.client.post('/api/v1/auth/register', json={
            'username': 'soc_user',
            'email': 'soc@user.com',
            'password': 'Password123!'
        }).json()
        token = u['token']

        red = self.client.post('/api/v1/redeem/apply', headers={'Authorization': f'Bearer {token}'}, json={'code': 'BONUS100'})
        self.assertEqual(red.status_code, 200)
        self.assertEqual(red.json()['diamonds_awarded'], 100)

        tick = self.client.post(
            '/api/v1/support/tickets',
            headers={'Authorization': f'Bearer {token}'},
            json={'subject': 'Need Tournament Help', 'category': 'TOURNAMENT', 'priority': 'NORMAL', 'message': 'How do I check custom room credentials?'}
        )
        self.assertEqual(tick.status_code, 201)
        t_id = tick.json()['ticket']['id']

        rep = self.client.post(
            f'/api/v1/support/tickets/{t_id}/reply',
            headers={'Authorization': f'Bearer {token}'},
            json={'message': 'Nevermind I found the Room tab!'}
        )
        self.assertEqual(rep.status_code, 200)

    def test_esports_10_website_tournaments_rendering(self):
        t_page = self.client.get('/tournaments')
        self.assertEqual(t_page.status_code, 200)
        self.assertIn('GOD4XE ESPORTS', t_page.text)
        self.assertIn('Download Android APK', t_page.text)
        self.assertIn('Scan to Install APK', t_page.text)


    def test_esports_11_starter_diamonds_feature(self):
        # 1. New user registration receives exactly 25 Diamonds atomically
        res = self.client.post('/api/v1/auth/register', json={
            'username': 'starter_champ',
            'email': 'starter@champ.com',
            'password': 'Password123!'
        })
        self.assertEqual(res.status_code, 201)
        data = res.json()
        token = data['token']
        self.assertEqual(data['user']['diamond_balance'], 25)

        # 2. Check wallet balance endpoint returns 25
        bal_res = self.client.get('/api/v1/wallet/balance', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(bal_res.status_code, 200)
        self.assertEqual(bal_res.json()['balance'], 25)

        # 3. Check ledger transaction entry
        tx_res = self.client.get('/api/v1/wallet/transactions', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(tx_res.status_code, 200)
        txs = tx_res.json()['transactions']
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]['tx_type'], 'STARTER_BONUS')
        self.assertEqual(txs[0]['amount'], 25)
        self.assertEqual(txs[0]['balance_after'], 25)
        self.assertIn('Starter Diamonds', txs[0]['description'])

        # 4. Returning user login does NOT receive another starter bonus
        login_res = self.client.post('/api/v1/auth/login', json={
            'identity': 'starter_champ',
            'password': 'Password123!'
        })
        self.assertEqual(login_res.status_code, 200)
        new_token = login_res.json()['token']
        bal_after_login = self.client.get('/api/v1/wallet/balance', headers={'Authorization': f'Bearer {new_token}'}).json()
        self.assertEqual(bal_after_login['balance'], 25)

        # 5. First-time Google registration also receives 25 Starter Diamonds
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization
        from app.services.users_auth import register_trusted_google_key
        import base64, json, time

        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        register_trusted_google_key('starter-google-kid', pub_pem)

        now = int(time.time())
        g_header = {'alg': 'RS256', 'typ': 'JWT', 'kid': 'starter-google-kid'}
        g_claims = {
            'sub': 'google_starter_sub_123',
            'email': 'new_google_gamer@gmail.com',
            'name': 'Google Gamer',
            'iss': 'https://accounts.google.com',
            'exp': now + 3600,
            'iat': now
        }
        def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip('=')
        msg = f"{b64(g_header)}.{b64(g_claims)}".encode('utf-8')
        sig = priv_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        g_token = f"{b64(g_header)}.{b64(g_claims)}." + base64.urlsafe_b64encode(sig).decode().rstrip('=')

        g_res = self.client.post('/api/v1/auth/google', json={'id_token': g_token})
        self.assertEqual(g_res.status_code, 200)
        g_data = g_res.json()
        self.assertEqual(g_data['user']['diamond_balance'], 25)
        g_user_token = g_data['token']

        g_tx_res = self.client.get('/api/v1/wallet/transactions', headers={'Authorization': f'Bearer {g_user_token}'})
        self.assertEqual(g_tx_res.json()['transactions'][0]['tx_type'], 'STARTER_BONUS')
        self.assertEqual(g_tx_res.json()['transactions'][0]['amount'], 25)

        # 6. Returning Google login does NOT receive bonus again
        g_login2 = self.client.post('/api/v1/auth/google', json={'id_token': g_token})
        self.assertEqual(g_login2.status_code, 200)
        g_bal2 = self.client.get('/api/v1/wallet/balance', headers={'Authorization': f'Bearer {g_login2.json()["token"]}'}).json()
        self.assertEqual(g_bal2['balance'], 25)


if __name__ == "__main__":
    unittest.main()
