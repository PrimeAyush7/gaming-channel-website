import os
import sys
import unittest
import time
import json
import re
import types

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
            ctx = kwargs.pop("context", {})
            ctx["request"] = req
            return _orig_tr(self, name, ctx, **kwargs)
        return _orig_tr(self, *args, **kwargs)
    starlette.templating.Jinja2Templates.TemplateResponse = _compat_tr

# In environments where psycopg2 is not installed (e.g. offline test container),
# provide an in-memory SQL mock for psycopg2
try:
    import psycopg2
except ImportError:
    import importlib
    _mem_driver = importlib.import_module("sqlite3")
    _mem_conn = _mem_driver.connect(":memory:", check_same_thread=False)
    _mem_conn.row_factory = _mem_driver.Row

    class _MockCursor:
        def __init__(self, raw_cur):
            self._cur = raw_cur
            self._returning_row = None

        def execute(self, query, params=None):
            sql = query
            self._returning_row = None
            
            # Check for RETURNING
            ret_match = re.search(r'\s+RETURNING\s+(.+?)\s*;?$', sql, re.IGNORECASE)
            ret_cols = None
            if ret_match:
                ret_cols = ret_match.group(1).rstrip(';').strip()
                sql = sql[:ret_match.start()] + ';'

            is_insert = bool(re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE))
            is_update = bool(re.search(r'UPDATE\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE))

            table_name = None
            if is_insert:
                m = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
                if m:
                    table_name = m.group(1).strip()
            elif is_update:
                m = re.search(r'UPDATE\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
                if m:
                    table_name = m.group(1).strip()

            sql = re.sub(r'\bSERIAL\s+PRIMARY\s+KEY\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\bILIKE\b', 'LIKE', sql, flags=re.IGNORECASE)
            sql = re.sub(r'information_schema\.tables\s+WHERE\s+table_schema\s*=\s*\'public\'', "sqlite_master WHERE type='table'", sql, flags=re.IGNORECASE)
            sql = re.sub(r'\btable_name\b', 'name AS table_name', sql, flags=re.IGNORECASE)
            sql = sql.replace('%s', '?')
            sql = re.sub(r'\bADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\b', 'ADD COLUMN', sql, flags=re.IGNORECASE)
            sql = re.sub(r'\s+FOR\s+UPDATE\b', '', sql, flags=re.IGNORECASE)

            # If UPDATE with RETURNING, capture where clause for fetch
            where_query = None
            where_params = None
            if is_update and ret_cols and table_name and 'WHERE' in sql.upper():
                try:
                    where_part = re.split(r'WHERE', sql, flags=re.IGNORECASE)[1].strip().rstrip(';')
                    set_part = re.split(r'WHERE', sql, flags=re.IGNORECASE)[0]
                    num_set_q = set_part.count('?')
                    where_query = f"SELECT {ret_cols} FROM {table_name} WHERE {where_part}"
                    if params:
                        where_params = tuple(params[num_set_q:])
                    else:
                        where_params = ()
                except Exception:
                    pass

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

            last_id = self._cur.lastrowid
            if is_insert and ret_cols and table_name and last_id:
                try:
                    q_ret = f"SELECT {ret_cols} FROM {table_name} WHERE rowid = ?"
                    res = self._cur.execute(q_ret, (last_id,)).fetchone()
                    if res:
                        self._returning_row = res
                except Exception:
                    self._returning_row = {"id": last_id, 0: last_id}
            elif is_update and where_query:
                try:
                    res = self._cur.execute(where_query, where_params).fetchone()
                    if res:
                        self._returning_row = res
                except Exception:
                    pass

            return self

        def executemany(self, query, seq):
            for p in seq:
                self.execute(query, p)
            return self

        def fetchone(self):
            if self._returning_row is not None:
                r = self._returning_row
                self._returning_row = None
                return r
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
from app.services import (
    users_auth as user_service,
    wallet as wallet_service,
    auth as auth_service
)


class TestV11Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_01_pwa_assets_available(self):
        """Verify manifest.json and sw.js are served correctly."""
        res_m = self.client.get("/static/manifest.json")
        self.assertEqual(res_m.status_code, 200)
        data = res_m.json()
        self.assertEqual(data["name"], "GOD4XE ESPORTS")
        self.assertEqual(data["theme_color"], "#06030b")
        self.assertGreaterEqual(len(data["icons"]), 1)

        res_sw = self.client.get("/static/sw.js")
        self.assertEqual(res_sw.status_code, 200)
        self.assertIn("CACHE_NAME", res_sw.text)

    def test_02_opengraph_tags_in_tournament_detail(self):
        """Verify dynamic Open Graph and Twitter Card tags render on tournament page."""
        from app.services import tournaments as tournament_service
        t = tournament_service.create_tournament(
            title="OG Meta Showcase Cup",
            entry_type="FREE",
            mode="SQUAD",
            map_name="PURGATORY",
            prize_amount_diamonds=1500,
            max_slots=12
        )
        res = self.client.get(f"/tournaments/{t['id']}")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('property="og:title"', html)
        self.assertIn("OG Meta Showcase Cup", html)
        self.assertIn("1500", html)
        self.assertIn('name="twitter:card"', html)
        self.assertIn("api.whatsapp.com/send", html)

    def test_03_squad_registration_and_roster(self):
        """Verify team captain can register team name and teammates in tournament."""
        from app.services import users_auth as user_service
        from app.services import tournaments as tournament_service
        import random

        u_cap = user_service.register_user(
            username=f"captain_{random.randint(100000, 999999)}",
            email=f"cap_{random.randint(100000, 999999)}@test.com",
            phone=f"+9198{random.randint(10000000, 99999999)}",
            password="CaptainPassword123!"
        )["user"]

        t = tournament_service.create_tournament(
            title="Squad Clash Tournament",
            entry_type="FREE",
            mode="SQUAD",
            max_slots=12
        )

        teammates_data = [
            {"ff_uid": "11223344", "ff_ign": "Racer_One"},
            {"ff_uid": "55667788", "ff_ign": "Sniper_Two"},
            {"ff_uid": "99001122", "ff_ign": "Rusher_Three"}
        ]

        join_res = tournament_service.join_tournament(
            tournament_id=t["id"],
            user_id=u_cap["id"],
            ff_uid="10002000",
            ff_ign="Cap_Alpha",
            team_name="TEAM GOD4XE ELITE",
            teammates=teammates_data
        )
        self.assertTrue(join_res["success"])

        # Fetch participants list and verify team roster is stored
        parts = tournament_service.list_tournament_participants(t["id"])
        self.assertEqual(len(parts), 1)
        p = parts[0]
        self.assertEqual(p["team_name"], "TEAM GOD4XE ELITE")
        self.assertEqual(p["team_role"], "CAPTAIN")
        self.assertEqual(len(p["teammates"]), 3)
        self.assertEqual(p["teammates"][0]["ff_ign"], "Racer_One")

    def test_04_cloudinary_helper_safe_fallback(self):
        """Verify Cloudinary upload gracefully falls back to local disk when unconfigured."""
        from app.services import media as media_service
        res_cloud = media_service.upload_to_cloudinary(b"test_bytes", "test.png")
        self.assertIsNone(res_cloud)  # Unconfigured in test environment


    def test_06_public_html_pages_restored(self):
        """Verifies that public login, register, announcements, and esports pages render properly."""
        # 1. /login
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn("PLAYER PORTAL", res_login.text)
        self.assertIn("Username, Mobile or Email", res_login.text)

        # 2. /register
        res_reg = self.client.get("/register")
        self.assertEqual(res_reg.status_code, 200)
        self.assertIn("JOIN GOD4XE ARENA", res_reg.text)
        self.assertIn("Free Fire UID", res_reg.text)

        # 3. /announcements
        res_ann = self.client.get("/announcements")
        self.assertEqual(res_ann.status_code, 200)
        self.assertIn("OFFICIAL ANNOUNCEMENTS", res_ann.text)

        # 4. /esports
        res_esp = self.client.get("/esports")
        self.assertEqual(res_esp.status_code, 200)
        self.assertIn("DOMINATE THE BATTLEFIELD", res_esp.text)
        self.assertIn("Download Android APK", res_esp.text)

        # 5. Homepage contains Esports & Announcements sections
        res_home = self.client.get("/")
        self.assertEqual(res_home.status_code, 200)
        self.assertIn("FREE FIRE ESPORTS ARENA", res_home.text)
        self.assertIn("OFFICIAL ANNOUNCEMENTS & NEWS", res_home.text)

    def test_07_public_auth_flow(self):
        """Verifies user registration and login via the public web interface."""
        import random
        r = random.randint(100000, 999999)
        test_user = f"webwarrior_{r}"
        test_phone = f"+9198{r}00"
        
        # Test Registration
        res_reg = self.client.post("/register", data={
            "username": test_user,
            "phone": test_phone,
            "password": "securepassword123",
            "ff_uid": f"FF_{r}",
            "ff_ign": f"IGN_{r}"
        }, follow_redirects=False)
        self.assertEqual(res_reg.status_code, 303)
        self.assertIn("god4xe_user_token", res_reg.cookies)

        # Test Login
        res_login = self.client.post("/login", data={
            "identity": test_user,
            "password": "securepassword123"
        }, follow_redirects=False)
        self.assertEqual(res_login.status_code, 303)
        self.assertIn("god4xe_user_token", res_login.cookies)

        # Test Logout
        res_logout = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(res_logout.status_code, 302)



    def test_08_google_login_buttons_present(self):
        """Verifies Google login and registration buttons are rendered."""
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn("Continue with Google", res_login.text)
        self.assertIn("google-login-btn", res_login.text)

        res_reg = self.client.get("/register")
        self.assertEqual(res_reg.status_code, 200)
        self.assertIn("Sign up with Google", res_reg.text)
        self.assertIn("google-register-btn", res_reg.text)

    def test_09_direct_website_tournament_join(self):
        """Verifies direct website tournament registration and dynamic QR code."""
        # 1. Dynamic QR code endpoint
        res_qr = self.client.get("/api/qr")
        self.assertIn(res_qr.status_code, (200, 307))

        res_qr2 = self.client.get("/qr-code")
        self.assertIn(res_qr2.status_code, (200, 307))

        # 2. Tournament Detail Page Join UI
        res_td = self.client.get("/tournaments/1")
        self.assertEqual(res_td.status_code, 200)
        self.assertIn("Join Tournament Directly on Website", res_td.text)
        self.assertIn("Scan to Install APK", res_td.text)
        self.assertIn("/api/qr", res_td.text)

        # 3. Direct Website Join with Logged-in User
        import random
        r = random.randint(100000, 999999)
        test_user = f"joiner_{r}"
        reg = self.client.post("/register", data={
            "username": test_user,
            "phone": f"+9197{r}00",
            "password": "password123",
            "ff_uid": f"UID_{r}",
            "ff_ign": f"IGN_{r}"
        }, follow_redirects=False)
        self.assertEqual(reg.status_code, 303)

        # Join tournament directly on website
        res_join = self.client.post("/tournaments/1/join", data={
            "ff_uid": f"UID_{r}",
            "ff_ign": f"IGN_{r}",
            "team_name": "God Squad"
        }, follow_redirects=False)
        self.assertEqual(res_join.status_code, 303)
        self.assertIn("joined=1", res_join.headers.get("location"))

        # Verify enrolled state
        res_after = self.client.get("/tournaments/1")
        self.assertEqual(res_after.status_code, 200)
        self.assertIn("You Are Enrolled in this Match", res_after.text)

    def test_10_apk_bundled_and_served(self):
        """Verifies the user's bundled APK is served from /download-app."""
        res = self.client.get("/download-app", follow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn("vnd.android.package-archive", res.headers.get("content-type", ""))

if __name__ == "__main__":
    unittest.main()
