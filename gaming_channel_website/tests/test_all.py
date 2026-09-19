import os
import sys
import unittest
import io
from PIL import Image

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
            cursor.execute("DELETE FROM admins WHERE username = ?;", (cls.test_username,))
        auth_service.create_admin_user(cls.test_username, cls.test_password)

    def login_admin(self):
        """Helper to log in and return session client and admin info."""
        login_res = self.client.post("/admin/login", data={
            "username": self.test_username,
            "password": self.test_password
        }, follow_redirects=False)
        self.assertEqual(login_res.status_code, 302)
        cookie = login_res.cookies.get("nexus_session")
        self.assertIsNotNone(cookie)
        
        # Fetch csrf token for this session
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT csrf_token FROM sessions WHERE session_id = ?;", (cookie,))
            csrf_token = cursor.fetchone()["csrf_token"]
            
        return cookie, csrf_token

    # --------------------------------------------------------------------------
    # 1. PUBLIC ROUTES & HOMEPAGE
    # --------------------------------------------------------------------------
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
        # Default seeded sections
        self.assertIn(b"FREE STYLE COMBO", res.content)
        self.assertIn(b"OB50 UPDATE", res.content)
        self.assertIn(b"CONFIG FILES", res.content)

    def test_03_search_functionality(self):
        # Create a specific search test post
        post_id, _ = post_service.create_post({
            "title": "Quantum Secret Headshot Config",
            "slug": "quantum-secret-config",
            "summary": "Special config file for testing search query matching.",
            "content": "Full content with ultra precision settings.",
            "is_published": 1
        })
        self.assertIsNotNone(post_id)

        # Search matching
        res = self.client.get("/search?q=Quantum+Secret")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Quantum Secret Headshot Config", res.content)

        # Search non-matching
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
        # Robots.txt
        res_robots = self.client.get("/robots.txt")
        self.assertEqual(res_robots.status_code, 200)
        self.assertEqual(res_robots.headers["content-type"], "text/plain; charset=utf-8")
        self.assertIn("User-agent:", res_robots.text)

        # Sitemap.xml
        res_sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(res_sitemap.status_code, 200)
        self.assertIn("<urlset", res_sitemap.text)
        self.assertIn("<loc>", res_sitemap.text)

    def test_07_ads_txt_endpoint(self):
        res = self.client.get("/ads.txt")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "text/plain; charset=utf-8")
        self.assertTrue("DIRECT" in res.text or "google.com" in res.text or "ads.txt" in res.text)

    def test_08_error_handling_404(self):
        res = self.client.get("/post/completely-non-existent-slug-xyz-12345")
        self.assertEqual(res.status_code, 404)
        self.assertIn(b"404", res.content)
        self.assertIn(b"AREA OUT OF BOUNDS", res.content)

    # --------------------------------------------------------------------------
    # 2. SECURITY, AUTHENTICATION & AUTHORIZATION
    # --------------------------------------------------------------------------
    def test_09_unauthorized_admin_access_redirects(self):
        # Attempting to access admin without cookie redirects to /admin/login
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
        # Login
        cookie, csrf_token = self.login_admin()
        
        # Access admin dashboard with session cookie
        res_dash = self.client.get("/admin", cookies={"nexus_session": cookie})
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Analytics & Overview", res_dash.content)
        self.assertIn(self.test_username.encode(), res_dash.content)

        # Logout
        res_logout = self.client.post("/admin/logout", cookies={"nexus_session": cookie}, follow_redirects=False)
        self.assertEqual(res_logout.status_code, 302)
        self.assertEqual(res_logout.headers["location"], "/admin/login")

        # Verify old session cookie is now invalid
        res_check = self.client.get("/admin", cookies={"nexus_session": cookie}, follow_redirects=False)
        self.assertEqual(res_check.status_code, 302)

    def test_12_csrf_protection_enforcement(self):
        cookie, csrf_token = self.login_admin()

        # Attempt to create section with forged/missing CSRF token
        res_bad_csrf = self.client.post(
            "/admin/sections/new",
            data={"name": "Hacker Section", "csrf_token": "invalid_fake_token"},
            cookies={"nexus_session": cookie}
        )
        self.assertEqual(res_bad_csrf.status_code, 403)

    # --------------------------------------------------------------------------
    # 3. CONTENT MANAGEMENT & DYNAMIC SECTIONS CRUD
    # --------------------------------------------------------------------------
    def test_13_dynamic_section_crud(self):
        cookie, csrf_token = self.login_admin()

        # 1. Create Section
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

        # Verify section appears on live website navigation
        res_public = self.client.get("/")
        self.assertIn(b"OB53 UPDATE", res_public.content)

        # Retrieve created section ID
        sec = section_service.get_section_by_slug("ob53-update")
        self.assertIsNotNone(sec)
        self.assertEqual(sec["name"], "OB53 UPDATE")

        # 2. Delete Section
        res_del = self.client.post(
            f"/admin/sections/delete/{sec['id']}",
            data={"csrf_token": csrf_token},
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_del.status_code, 302)
        
        # Verify deleted
        self.assertIsNone(section_service.get_section_by_slug("ob53-update"))

    def test_14_post_crud_and_download_system(self):
        cookie, csrf_token = self.login_admin()

        # 1. Create Post with External Download & YouTube
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

        # Verify post renders on public site
        res_post = self.client.get("/post/ob52-pro-sensitivity")
        self.assertEqual(res_post.status_code, 200)
        self.assertIn(b"OB52 Pro Sensitivity File", res_post.content)
        self.assertIn(b"DOWNLOAD OFFICIAL OB52 CONFIG", res_post.content)
        self.assertIn(b"https://download-mirror.example.com/files/ob52_config.zip", res_post.content)
        self.assertIn(b"rel=\"noopener noreferrer\"", res_post.content)
        self.assertIn(b"dQw4w9WgXcQ", res_post.content)

        # Verify Analytics tracking for download
        p = post_service.get_post_by_slug("ob52-pro-sensitivity")
        initial_downloads = p["download_count"]
        res_track = self.client.post(f"/api/track/download/{p['id']}")
        self.assertEqual(res_track.status_code, 200)
        p_after = post_service.get_post_by_id(p["id"])
        self.assertEqual(p_after["download_count"], initial_downloads + 1)

        # 2. Update Post
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

        # 3. Delete Post
        res_del = self.client.post(
            f"/admin/posts/delete/{p['id']}",
            data={"csrf_token": csrf_token},
            cookies={"nexus_session": cookie},
            follow_redirects=False
        )
        self.assertEqual(res_del.status_code, 302)
        self.assertIsNone(post_service.get_post_by_id(p["id"]))

    def test_15_download_url_validation(self):
        # Valid URLs
        self.assertTrue(post_service.validate_download_url("https://example.com/file.zip"))
        self.assertTrue(post_service.validate_download_url("http://example.com/file.zip"))
        self.assertTrue(post_service.validate_download_url(""))  # empty allowed if no download

        # Malicious / Invalid URLs rejected
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

        # 1. Test Valid PNG Upload
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

        # 2. Test Malicious Executable disguised as an image
        fake_bytes = b"MZ\x90\x00\x03\x00\x00\x00This is a fake windows binary executable file."
        res_malicious = self.client.post(
            "/admin/media/upload",
            data={"csrf_token": csrf_token},
            files={"file": ("malware.png", fake_bytes, "image/png")},
            cookies={"nexus_session": cookie}
        )
        self.assertEqual(res_malicious.status_code, 400)
        self.assertIn(b"File content is not a valid image", res_malicious.content)

        # 3. Test Disallowed Extension
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
        
        # Script tags must be safely escaped, not raw
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<h2>Safe Heading</h2>", rendered)
        self.assertIn("<strong>Bold Text</strong>", rendered)

    def test_19_adsense_configuration_flow(self):
        cookie, csrf_token = self.login_admin()

        # Update Ads Settings
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

        # Verify AdSense configuration is active in database and ads.txt
        ads = ad_service.get_ad_settings()
        self.assertEqual(ads["is_enabled"], 1)
        self.assertEqual(ads["client_id"], "ca-pub-9998887776665554")
        
        ads_txt_res = self.client.get("/ads.txt")
        self.assertIn("pub-9998887776665554", ads_txt_res.text)


    # --------------------------------------------------------------------------
    # 4. RENDER FREE BOOTSTRAP & ADMIN INTEGRITY TESTS
    # --------------------------------------------------------------------------
    def test_20_bootstrap_admin_from_env_provisions_admin(self):
        # In a separate test DB or temporary clean state
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins;")

        test_user = "render_bootstrap_user"
        test_pass = "RenderSuperSecretPassword2026!"

        os.environ["ADMIN_USERNAME"] = test_user
        os.environ["ADMIN_PASSWORD"] = test_pass

        created = auth_service.bootstrap_admin_from_env()
        self.assertTrue(created)

        # Verify admin exists and password verifies
        admin, err = auth_service.authenticate_admin(test_user, test_pass)
        self.assertIsNotNone(admin)
        self.assertIsNone(err)

    def test_21_bootstrap_never_overwrites_existing_admin(self):
        # Admin already exists from test_20
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM admins;")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0)
            cursor.execute("SELECT password_hash, salt FROM admins WHERE username = 'render_bootstrap_user';")
            orig_row = cursor.fetchone()
            orig_hash = orig_row["password_hash"]

        # Try to run bootstrap with different credentials
        os.environ["ADMIN_USERNAME"] = "attacker_override"
        os.environ["ADMIN_PASSWORD"] = "AttackerNewPass999!"

        created = auth_service.bootstrap_admin_from_env()
        self.assertFalse(created, "Bootstrap must NEVER overwrite when an admin already exists!")

        # Verify original admin password hash was not altered
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM admins WHERE username = 'render_bootstrap_user';")
            current_row = cursor.fetchone()
            self.assertEqual(current_row["password_hash"], orig_hash)
            # Verify attacker username was not created
            cursor.execute("SELECT * FROM admins WHERE username = 'attacker_override';")
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
            # Run bootstrap
            auth_service.bootstrap_admin_from_env()

        captured_stdout = stdout_capture.getvalue()
        captured_stderr = stderr_capture.getvalue()

        # The password string must NEVER appear in stdout or stderr
        self.assertNotIn(secret_password, captured_stdout)
        self.assertNotIn(secret_password, captured_stderr)

    def test_23_application_startup_and_schema_health(self):
        # Verify all tables exist and are healthy
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {r["name"] for r in cursor.fetchall()}
            expected = {"admins", "sessions", "sections", "tags", "posts", "post_tags", "youtube_videos", "media", "site_settings", "ad_settings", "analytics_events"}
            self.assertTrue(expected.issubset(tables))

        # Re-ensure testadmin is seeded for any subsequent test runs
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM admins WHERE username = ?;", (self.test_username,))
            if not cursor.fetchone():
                auth_service.create_admin_user(self.test_username, self.test_password)

if __name__ == "__main__":
    unittest.main()
