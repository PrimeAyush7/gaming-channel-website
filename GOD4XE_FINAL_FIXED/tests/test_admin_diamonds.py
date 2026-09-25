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

class TestAdminDiamondBalanceManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        # Create unique test admin
        self.admin_username = f"adm_diam_{int(time.time() * 1000)}"
        self.admin_password = "AdminSecretPass123!"
        self.admin_id = auth_service.create_admin_with_role(
            self.admin_username,
            self.admin_password,
            role="SUPER_ADMIN"
        )

        # Authenticate admin session
        res = self.client.post("/admin/login", data={
            "username": self.admin_username,
            "password": self.admin_password
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.session_cookie = res.cookies.get("nexus_session")
        self.assertTrue(self.session_cookie)

        # Get CSRF token
        dash_res = self.client.get("/admin", cookies={"nexus_session": self.session_cookie})
        self.assertEqual(dash_res.status_code, 200)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT csrf_token FROM sessions WHERE session_id = %s;", (self.session_cookie,))
            row = cursor.fetchone()
            self.csrf_token = row["csrf_token"] if isinstance(row, dict) else row[0]

        # Register a test app user (starts with 0 diamonds per business rule)
        import random
        rand_id = random.randint(100000, 999999)
        self.test_username = f"player_{int(time.time() * 1000)}_{rand_id}"
        reg_result = user_service.register_user(
            username=self.test_username,
            email=f"{self.test_username}@test.com",
            phone=f"+919{random.randint(100000000, 999999999)}",
            password="PlayerPassword123!"
        )
        self.user = reg_result["user"]
        self.user_id = self.user["id"]

    def test_01_initial_balance_is_zero(self):
        """Verify business rule: new users start with 0 diamonds."""
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 0)
        self.assertEqual(w_info["locked_balance"], 0)

    def test_02_wallet_service_credit_and_deduct_with_locking(self):
        """Direct test of credit_diamonds and deduct_diamonds with row creation & locking."""
        # Credit 150 diamonds
        tx1 = wallet_service.credit_diamonds(
            user_id=self.user_id,
            amount=150,
            tx_type="ADMIN_CREDIT",
            reference_id="TEST_REF_01",
            admin_id=self.admin_id,
            description="Test credit"
        )
        self.assertEqual(tx1["amount"], 150)
        self.assertEqual(tx1["balance_after"], 150)

        # Verify DB balance
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 150)

        # Deduct 50 diamonds
        tx2 = wallet_service.deduct_diamonds(
            user_id=self.user_id,
            amount=50,
            tx_type="ADMIN_DEBIT",
            reference_id="TEST_REF_02",
            admin_id=self.admin_id,
            description="Test debit"
        )
        self.assertEqual(tx2["amount"], -50)
        self.assertEqual(tx2["balance_after"], 100)

        w_info2 = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info2["balance"], 100)

        # Deduct more than balance must fail and NOT reduce balance
        with self.assertRaises(ValueError):
            wallet_service.deduct_diamonds(
                user_id=self.user_id,
                amount=500,
                tx_type="ADMIN_DEBIT",
                reference_id="TEST_REF_FAIL",
                admin_id=self.admin_id,
                description="Should fail"
            )

        w_info3 = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info3["balance"], 100)

    def test_03_admin_endpoint_add_diamonds(self):
        """Test POST /admin/users/{user_id}/adjust-balance (ADD) creates ledger & audit log."""
        res = self.client.post(
            f"/admin/users/{self.user_id}/adjust-balance",
            data={
                "action_type": "ADD",
                "amount": "250",
                "reason": "Tournament Winner Prize",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res.status_code, 303)
        self.assertIn(f"/admin/users/{self.user_id}", res.headers["location"])
        self.assertIn("msg=", res.headers["location"])

        # Check balance
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 250)

        # Check diamond_transactions ledger
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, amount, balance_after, tx_type, admin_id, description
                FROM diamond_transactions
                WHERE user_id = %s AND tx_type = 'ADMIN_CREDIT';
            """, (self.user_id,))
            tx = cursor.fetchone()
            self.assertIsNotNone(tx)
            self.assertEqual(tx["amount"], 250)
            self.assertEqual(tx["balance_after"], 250)
            self.assertEqual(tx["admin_id"], self.admin_id)
            self.assertIn("Tournament Winner Prize", tx["description"])

        # Check admin_audit_logs
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT admin_id, action, resource, resource_id, after_state
                FROM admin_audit_logs
                WHERE admin_id = %s AND action = 'ADD_DIAMONDS' AND resource_id = %s;
            """, (self.admin_id, str(self.user_id)))
            log = cursor.fetchone()
            self.assertIsNotNone(log)
            self.assertEqual(log["action"], "ADD_DIAMONDS")
            self.assertEqual(log["resource"], "diamond_accounts")

    def test_04_admin_endpoint_remove_diamonds(self):
        """Test POST /admin/users/{user_id}/adjust-balance (REMOVE) creates ledger & audit log."""
        # First credit 100
        wallet_service.credit_diamonds(self.user_id, 100, "SYSTEM_CREDIT")

        res = self.client.post(
            f"/admin/users/{self.user_id}/adjust-balance",
            data={
                "action_type": "REMOVE",
                "amount": "40",
                "reason": "Rule violation penalty",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res.status_code, 303)
        self.assertIn("msg=", res.headers["location"])

        # Check balance
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 60)

        # Check audit log
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT admin_id, action, resource, resource_id
                FROM admin_audit_logs
                WHERE admin_id = %s AND action = 'REMOVE_DIAMONDS' AND resource_id = %s;
            """, (self.admin_id, str(self.user_id)))
            log = cursor.fetchone()
            self.assertIsNotNone(log)

    def test_05_admin_endpoint_validation_negative_and_missing_reason(self):
        """Validation tests: missing reason, non-positive amount, and excessive deduction."""
        # 1. Missing reason
        res1 = self.client.post(
            f"/admin/users/{self.user_id}/adjust-balance",
            data={
                "action_type": "ADD",
                "amount": "100",
                "reason": "   ",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res1.status_code, 303)
        self.assertIn("error=", res1.headers["location"])

        # 2. Zero amount
        res2 = self.client.post(
            f"/admin/users/{self.user_id}/adjust-balance",
            data={
                "action_type": "ADD",
                "amount": "0",
                "reason": "Some reason",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res2.status_code, 303)
        self.assertIn("error=", res2.headers["location"])

        # 3. Excessive deduction (user currently has 0 diamonds)
        res3 = self.client.post(
            f"/admin/users/{self.user_id}/adjust-balance",
            data={
                "action_type": "REMOVE",
                "amount": "50",
                "reason": "Some reason",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res3.status_code, 303)
        self.assertIn("error=", res3.headers["location"])
        # Ensure balance stayed 0
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 0)

    def test_06_direct_route_aliases_and_page_render(self):
        """Test /add-diamonds and /remove-diamonds route aliases and HTML page rendering."""
        # Test add alias
        res_add = self.client.post(
            f"/admin/users/{self.user_id}/add-diamonds",
            data={
                "amount": "80",
                "reason": "Alias Add Test",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res_add.status_code, 303)
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 80)

        # Test remove alias
        res_rem = self.client.post(
            f"/admin/users/{self.user_id}/remove-diamonds",
            data={
                "amount": "30",
                "reason": "Alias Remove Test",
                "csrf_token": self.csrf_token
            },
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(res_rem.status_code, 303)
        w_info = wallet_service.get_wallet_info(self.user_id)
        self.assertEqual(w_info["balance"], 50)

        # Test GET /admin/users/{user_id} page render
        page_res = self.client.get(
            f"/admin/users/{self.user_id}",
            cookies={"nexus_session": self.session_cookie}, follow_redirects=False
        )
        self.assertEqual(page_res.status_code, 200)
        html = page_res.text
        self.assertIn("💎 Diamond Balance Controls", html)
        self.assertIn("Add Diamonds", html)
        self.assertIn("Remove Diamonds", html)
        self.assertIn("Diamond Ledger History", html)
        self.assertIn("confirmAddDiamonds", html)
        self.assertIn("confirmRemoveDiamonds", html)

if __name__ == "__main__":
    unittest.main()
