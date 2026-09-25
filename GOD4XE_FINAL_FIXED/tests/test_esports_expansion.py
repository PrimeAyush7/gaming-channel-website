import secrets
import os
import sys
import unittest
import io
import datetime
from PIL import Image

os.environ["DATABASE_URL"] = "postgresql://testuser:testpass@localhost:5432/testdb"
os.environ["ENVIRONMENT"] = "development"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import test environment mocks from test_all
import tests.test_all

from fastapi.testclient import TestClient
from main import app
from app.services import (
    users_auth as user_service,
    tournaments as tournament_service,
    wallet as wallet_service,
    content_features,
    auth as auth_service
)
from app.database import get_db

class TestEsportsExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.admin_id = auth_service.create_admin_with_role('expansion_admin', 'Pass1234!', 'SUPER_ADMIN', 'exp@admin.com')
        cls.admin_user = 'expansion_admin'

    def setUp(self):
        self.client = TestClient(app)

    def test_01_categories_and_subcategories(self):
        res = self.client.get("/api/v1/tournaments/categories")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        cats = data["categories"]
        slugs = [c["slug"] for c in cats]
        self.assertIn("battle-royale", slugs)
        self.assertIn("clash-squad", slugs)
        self.assertIn("guns-only-custom", slugs)

        # Check subcategories for Battle Royale
        br = next(c for c in cats if c["slug"] == "battle-royale")
        sub_slugs = [s["slug"] for s in br["subcategories"]]
        self.assertIn("solo", sub_slugs)
        self.assertIn("squad", sub_slugs)

    def test_02_guns_only_custom_options(self):
        res = self.client.get("/api/v1/tournaments/guns")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        codes = [g["code"] for g in data["guns"]]
        self.assertIn("DESERT_EAGLE", codes)
        self.assertIn("M1887", codes)
        self.assertIn("MP40", codes)
        self.assertIn("AWM", codes)

    def test_03_tournament_creation_with_category_and_per_kill(self):
        guns = tournament_service.list_guns()
        deagle = next(g for g in guns if g["code"] == "DESERT_EAGLE")
        cats = tournament_service.list_categories()
        guns_cat = next(c for c in cats if c["slug"] == "guns-only-custom")

        t = tournament_service.create_tournament(
            title="Desert Eagle Masters 1v1",
            category_id=guns_cat["id"],
            allowed_gun_id=deagle["id"],
            allowed_weapon="Desert Eagle Only",
            entry_type="DIAMONDS",
            entry_fee_diamonds=20,
            prize_amount_diamonds=500,
            per_kill_diamonds=10,
            max_slots=20,
            start_time=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        )
        self.assertEqual(t["category_name"], "Guns Only Custom")
        self.assertEqual(t["allowed_weapon"], "Desert Eagle Only")
        self.assertEqual(t["per_kill_diamonds"], 10)

        # Verify API detail returns it
        res = self.client.get(f"/api/v1/tournaments/{t['id']}")
        self.assertEqual(res.status_code, 200)
        td = res.json()["tournament"]
        self.assertEqual(td["allowed_weapon"], "Desert Eagle Only")
        self.assertEqual(td["per_kill_diamonds"], 10)

    def test_04_status_automation_and_manual_early_completion(self):
        # 1. Past start time tournament -> transitions to LIVE
        past_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
        t_live = tournament_service.create_tournament(
            title="Live Test Tourn",
            entry_type="FREE",
            start_time=past_time
        )
        tournament_service.check_and_update_tournament_statuses()
        t_live_fetched = tournament_service.get_tournament_by_id(t_live["id"])
        self.assertEqual(t_live_fetched["status"], "LIVE")

        # 2. 25 minutes past start time -> transitions to COMPLETED
        long_past_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=25)
        t_done = tournament_service.create_tournament(
            title="Completed Auto Tourn",
            entry_type="FREE",
            start_time=long_past_time
        )
        tournament_service.check_and_update_tournament_statuses()
        t_done_fetched = tournament_service.get_tournament_by_id(t_done["id"])
        self.assertEqual(t_done_fetched["status"], "COMPLETED")

        # 3. Manual early completion
        t_early = tournament_service.create_tournament(
            title="Early Complete Tourn",
            entry_type="FREE",
            start_time=datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        )
        tournament_service.mark_tournament_completed_early(t_early["id"], admin_id=self.admin_id)
        t_early_fetched = tournament_service.get_tournament_by_id(t_early["id"])
        self.assertEqual(t_early_fetched["status"], "COMPLETED")
        self.assertEqual(t_early_fetched["is_manually_completed"], 1)

    def test_05_participant_uid_ign_editing_before_live(self):
        # Register user
        reg = self.client.post("/api/v1/auth/register", json={
            "username": f"sniper_{secrets.token_hex(3)}",
            "email": f"sniper_{secrets.token_hex(3)}@test.com",
            "password": "Password123!"
        }).json()
        token = reg["token"]
        uid = reg["user"]["id"]

        # Create upcoming tournament
        t = tournament_service.create_tournament(
            title="UID Editing Tourn",
            entry_type="FREE",
            max_slots=10,
            start_time=datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        )

        # Join tournament
        join_res = self.client.post(
            f"/api/v1/tournaments/{t['id']}/join",
            headers={"Authorization": f"Bearer {token}"},
            json={"ff_uid": "11223344", "ff_ign": "Sniper_V1"}
        )
        self.assertEqual(join_res.status_code, 200)

        # Edit credentials before start -> should succeed
        edit_res = self.client.put(
            f"/api/v1/tournaments/{t['id']}/participant-credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={"ff_uid": "99887766", "ff_ign": "Sniper_V2"}
        )
        self.assertEqual(edit_res.status_code, 200)
        self.assertEqual(edit_res.json()["participant"]["ff_uid"], "99887766")
        self.assertEqual(edit_res.json()["participant"]["ff_ign"], "Sniper_V2")

        # Verify admin/public participants list has updated info
        parts = self.client.get(f"/api/v1/tournaments/{t['id']}/participants").json()["participants"]
        my_part = next(p for p in parts if p["user_id"] == uid)
        self.assertEqual(my_part["ff_uid"], "99887766")
        self.assertEqual(my_part["ff_ign"], "Sniper_V2")

        # Lock when tournament is LIVE
        with get_db() as conn:
            conn.cursor().execute("UPDATE tournaments SET status = 'LIVE' WHERE id = %s;", (t["id"],))

        locked_res = self.client.put(
            f"/api/v1/tournaments/{t['id']}/participant-credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={"ff_uid": "55555555", "ff_ign": "Sniper_Locked"}
        )
        self.assertEqual(locked_res.status_code, 400)
        self.assertIn("locked", locked_res.json()["detail"].lower())

    def test_06_public_profile_never_exposes_pii(self):
        reg = self.client.post("/api/v1/auth/register", json={
            "username": f"secret_{secrets.token_hex(3)}",
            "email": f"secret_{secrets.token_hex(3)}@private.com",
            "phone": "+919988776655",
            "password": "Password123!"
        }).json()
        target_uid = reg["user"]["id"]

        # Deposit diamonds so they have a balance
        wallet_service.credit_diamonds(target_uid, 500, "BONUS", description="Secret Balance")

        # Fetch public profile
        res = self.client.get(f"/api/v1/users/{target_uid}/public-profile")
        self.assertEqual(res.status_code, 200)
        p = res.json()["player"]

        # MUST show public details
        self.assertTrue(p["username"].startswith("secret_"))
        self.assertIn("rank_tier", p)
        self.assertIn("total_matches", p)
        self.assertIn("achievements", p)

        # STRICT PRIVACY: NEVER expose email, phone, diamond_balance, wallet info!
        self.assertNotIn("email", p)
        self.assertNotIn("phone", p)
        self.assertNotIn("diamond_balance", p)
        self.assertNotIn("balance", p)
        self.assertNotIn("locked_balance", p)
        self.assertNotIn("wallet", p)
        self.assertNotIn("password_hash", p)

    def test_07_avatar_upload_1mb_limit_and_moderation(self):
        reg = self.client.post("/api/v1/auth/register", json={
            "username": f"avatar_{secrets.token_hex(3)}",
            "email": f"avatar_{secrets.token_hex(3)}@test.com",
            "password": "Password123!"
        }).json()
        token = reg["token"]
        uid = reg["user"]["id"]

        # Create valid small image
        im = Image.new("RGB", (100, 100), color="purple")
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        small_bytes = buf.getvalue()

        # Upload valid image
        res = self.client.post(
            "/api/v1/users/avatar",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("avatar.png", small_bytes, "image/png")}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

        # Test upload > 1 MB -> should fail with 400
        large_bytes = b"0" * (1024 * 1024 + 10)
        oversized = self.client.post(
            "/api/v1/users/avatar",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("too_big.png", large_bytes, "image/png")}
        )
        self.assertEqual(oversized.status_code, 400)
        self.assertIn("1 mb", oversized.json()["detail"].lower())

        # Test disable avatar upload for user
        user_service.toggle_user_avatar_permission(uid, disabled=1)
        dis_res = self.client.post(
            "/api/v1/users/avatar",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("avatar.png", small_bytes, "image/png")}
        )
        self.assertEqual(dis_res.status_code, 400)
        self.assertIn("disabled", dis_res.json()["detail"].lower())

    def test_08_diamond_rates_and_withdrawal_flow(self):
        import app.services.wallet as w_mod
        orig_en = w_mod.WITHDRAWALS_ENABLED
        w_mod.WITHDRAWALS_ENABLED = True
        # Check rates endpoint
        rates = self.client.get("/api/v1/wallet/rates").json()
        self.assertEqual(rates["deposit"]["diamonds_per_ten_inr"], 10)
        self.assertEqual(rates["withdrawal"]["inr_per_ten_diamonds"], 8)

        # Register user and credit diamonds
        reg = self.client.post("/api/v1/auth/register", json={
            "username": f"with_{secrets.token_hex(3)}",
            "email": f"with_{secrets.token_hex(3)}@test.com",
            "password": "Password123!"
        }).json()
        token = reg["token"]
        uid = reg["user"]["id"]
        wallet_service.credit_diamonds(uid, 300, "WINNINGS", description="Match 1st place")

        # Submit withdrawal request
        w_res = self.client.post(
            "/api/v1/wallet/withdraw",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 100, "upi_id": "gamer@okhdfcbank"}
        )
        self.assertEqual(w_res.status_code, 201)
        req_id = w_res.json()["withdrawal"]["id"]

        # Balance after deduction should be 200
        bal = self.client.get("/api/v1/wallet/balance", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(bal["balance"], 200)

        # Admin rejects with refund
        wallet_service.review_withdrawal_request(req_id, admin_id=self.admin_id, approve=False, rejection_reason="UPI verification failed")
        bal_refund = self.client.get("/api/v1/wallet/balance", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(bal_refund["balance"], 300)

    def test_09_content_announcements_and_communities(self):
        # Updates
        up_res = self.client.get("/api/v1/updates/latest")
        self.assertEqual(up_res.status_code, 200)
        self.assertGreaterEqual(len(up_res.json()["updates"]), 1)

        # Announcements & Arena Marquee Notice
        notice_res = self.client.get("/api/v1/arena/notice")
        self.assertEqual(notice_res.status_code, 200)
        self.assertIn("ready before match starts", notice_res.json()["notice"])

        # Communities
        comm_res = self.client.get("/api/v1/social/communities")
        self.assertEqual(comm_res.status_code, 200)
        platforms = [c["platform"] for c in comm_res.json()["communities"]]
        self.assertIn("Instagram", platforms)
        self.assertIn("Discord", platforms)
        self.assertIn("YouTube", platforms)

        # Tutorials
        tut_res = self.client.get("/api/v1/tutorials")
        self.assertEqual(tut_res.status_code, 200)
        self.assertGreaterEqual(len(tut_res.json()["tutorials"]), 3)

    def test_10_match_results_and_per_kill_reward_payout(self):
        reg = self.client.post("/api/v1/auth/register", json={
            "username": f"champ_{secrets.token_hex(3)}",
            "email": f"champ_{secrets.token_hex(3)}@god4xe.com",
            "password": "Password123!"
        }).json()
        p_uid = reg["user"]["id"]

        t = tournament_service.create_tournament(
            title="Grand Finale 2026",
            entry_type="FREE",
            per_kill_diamonds=15,
            max_slots=10
        )
        tournament_service.join_tournament(t["id"], p_uid, "77889900", "Champ_IGN")

        # Admin enters results: Rank 1 (200 diamonds placement prize), 5 kills
        # Total payout should be: 200 + (5 * 15) = 275 diamonds!
        res_entry = tournament_service.enter_tournament_results(
            tournament_id=t["id"],
            results=[{
                "user_id": p_uid,
                "ff_uid": "77889900",
                "ff_ign": "Champ_IGN",
                "placement": 1,
                "kills": 5,
                "placement_prize_diamonds": 200
            }],
            proof_url="https://god4xe.com/proof.png",
            admin_id=self.admin_id
        )
        self.assertTrue(res_entry["success"])

        # Verify diamonds credited
        bal = wallet_service.get_wallet_info(p_uid)
        self.assertEqual(bal["balance"], 275)

        # Verify achievement unlocked (First Tournament & First Win!)
        achs = user_service.get_user_achievements(p_uid)
        unlocked_codes = [a["code"] for a in achs if a["is_unlocked"]]
        self.assertIn("FIRST_TOURNAMENT", unlocked_codes)
        self.assertIn("FIRST_WIN", unlocked_codes)


if __name__ == "__main__":
    unittest.main()
