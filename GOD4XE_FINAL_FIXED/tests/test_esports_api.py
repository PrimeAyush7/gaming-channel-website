import os
import sys
import unittest
import json

os.environ["DATABASE_URL"] = "postgresql://testuser:testpass@localhost:5432/testdb"
os.environ["ENVIRONMENT"] = "development"
os.environ["WITHDRAWALS_ENABLED"] = "false"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Setup test mock for psycopg2 if running offline
try:
    import psycopg2
except ImportError:
    pass

from fastapi.testclient import TestClient
from main import app
from app.services import auth as auth_service, wallet as wallet_service, tournaments as tournament_service

client = TestClient(app)

class TestEsportsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.super_admin_id = auth_service.create_admin_with_role("super_boss", "Pass1234!", "SUPER_ADMIN", "boss@god4xe.com")
        cls.tourn_admin_id = auth_service.create_admin_with_role("tourn_mod", "Pass1234!", "TOURNAMENT_ADMIN", "tourn@god4xe.com")
        cls.finance_admin_id = auth_service.create_admin_with_role("finance_mod", "Pass1234!", "FINANCE_ADMIN", "finance@god4xe.com")

    def test_01_user_registration_and_login(self):
        res = client.post("/api/v1/auth/register", json={
            "username": "sniper_god",
            "email": "sniper@test.com",
            "phone": "9876543210",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("token", data)
        self.assertEqual(data["user"]["username"], "sniper_god")
        self.assertTrue(data["user"]["referral_code"].startswith("G4X"))

        login_res = client.post("/api/v1/auth/login", json={
            "identity": "sniper@test.com",
            "password": "Password123!"
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["username"], "sniper_god")

    def test_02_zero_cost_otp_flow(self):
        req_res = client.post("/api/v1/auth/otp/request", json={"phone": "+919123456780"})
        self.assertEqual(req_res.status_code, 200)
        otp = req_res.json().get("test_otp")
        self.assertIsNotNone(otp)

        verify_res = client.post("/api/v1/auth/otp/verify", json={"phone": "+919123456780", "otp": otp})
        self.assertEqual(verify_res.status_code, 200)
        vdata = verify_res.json()
        self.assertTrue(vdata["success"])
        self.assertIn("token", vdata)

    def test_03_google_auth_flow(self):
        import base64
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "sub": "google_uid_1001",
            "email": "pro_gamer@gmail.com",
            "name": "Pro Gamer",
            "picture": "https://example.com/avatar.jpg",
            "iss": "accounts.google.com"
        }
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        c_b64 = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        fake_id_token = f"{h_b64}.{c_b64}.sig"

        res = client.post("/api/v1/auth/google", json={"id_token": fake_id_token})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["email"], "pro_gamer@gmail.com")

    def test_04_tournaments_system(self):
        t_free = tournament_service.create_tournament(
            title="Sunday Free Royale",
            entry_type="FREE",
            entry_fee_diamonds=0,
            prize_amount_diamonds=1000,
            max_slots=48
        )
        self.assertEqual(t_free["entry_type"], "FREE")
        self.assertEqual(t_free["entry_fee_diamonds"], 0)

        t_diamonds = tournament_service.create_tournament(
            title="Pro Diamond League",
            entry_type="DIAMONDS",
            entry_fee_diamonds=50,
            prize_amount_diamonds=5000,
            max_slots=48
        )
        self.assertEqual(t_diamonds["entry_type"], "DIAMONDS")
        self.assertEqual(t_diamonds["entry_fee_diamonds"], 50)

        list_res = client.get("/api/v1/tournaments?status=UPCOMING")
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(list_res.json()["count"], 2)

    def test_05_wallet_ledger_and_deposit_approval(self):
        user = client.post("/api/v1/auth/register", json={
            "username": "rich_player",
            "email": "rich@player.com",
            "password": "Password123!"
        }).json()
        token = user["token"]

        bal = client.get("/api/v1/wallet/balance", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(bal["balance"], 0)

        dep_res = client.post(
            "/api/v1/wallet/deposit-request",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 200, "utr_reference": "UTR_TEST_9999"}
        )
        self.assertEqual(dep_res.status_code, 201)
        req_id = dep_res.json()["request"]["id"]

        wallet_service.review_deposit_request(req_id, admin_id=self.finance_admin_id, approve=True)

        bal_after = client.get("/api/v1/wallet/balance", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(bal_after["balance"], 200)

    def test_06_withdrawals_disabled_by_default(self):
        user = client.post("/api/v1/auth/register", json={
            "username": "cash_user",
            "email": "cash@user.com",
            "password": "Password123!"
        }).json()
        token = user["token"]

        res = client.post(
            "/api/v1/wallet/withdraw",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 100, "upi_id": "test@upi"}
        )
        self.assertEqual(res.status_code, 403)

    def test_07_website_tournaments_rendering(self):
        t_page = client.get("/tournaments")
        self.assertEqual(t_page.status_code, 200)
        self.assertIn("GOD4XE ESPORTS", t_page.text)
        self.assertIn("Download Android APK", t_page.text)

if __name__ == '__main__':
    unittest.main()
