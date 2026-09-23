import datetime
from app.database import get_db
from app.services.wallet import credit_diamonds

# --- REDEEM CODES ---
def create_redeem_code(code: str, reward_diamonds: int, max_uses: int = 100, per_user_limit: int = 1, expires_at: str = None) -> dict:
    code_clean = code.strip().upper()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO redeem_codes (code, reward_diamonds, max_uses, per_user_limit, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *;
        """, (code_clean, reward_diamonds, max_uses, per_user_limit, expires_at))
        return dict(cursor.fetchone())

def redeem_code_for_user(user_id: int, code: str) -> dict:
    code_clean = code.strip().upper()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM redeem_codes WHERE code = %s;", (code_clean,))
        code_row = cursor.fetchone()
        if not code_row:
            raise ValueError("Invalid redeem code")

        c = dict(code_row)
        if c.get("is_active", 1) == 0:
            raise ValueError("This redeem code has expired or is deactivated")

        if c.get("times_used", 0) >= c.get("max_uses", 100):
            raise ValueError("This redeem code has reached its maximum redemption limit")

        if c.get("expires_at"):
            exp_val = c["expires_at"]
            if isinstance(exp_val, str):
                exp = datetime.datetime.fromisoformat(exp_val.replace("Z", ""))
            else:
                exp = exp_val
            if datetime.datetime.utcnow() > exp:
                raise ValueError("This redeem code has expired")

        # Check per-user redemption limit
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM redeem_history
            WHERE code_id = %s AND user_id = %s;
        """, (c["id"], user_id))
        cnt = cursor.fetchone()["cnt"]
        if cnt >= c.get("per_user_limit", 1):
            raise ValueError("You have already redeemed this code")

        # Record redemption
        reward = c["reward_diamonds"]
        cursor.execute("""
            INSERT INTO redeem_history (code_id, user_id, diamonds_awarded)
            VALUES (%s, %s, %s);
        """, (c["id"], user_id, reward))

        cursor.execute("""
            UPDATE redeem_codes
            SET times_used = times_used + 1
            WHERE id = %s;
        """, (c["id"],))

    credit_diamonds(
        user_id=user_id,
        amount=reward,
        tx_type="REDEEM_CODE",
        reference_id=f"REDEEM-{code_clean}",
        description=f"Redeem code reward: {code_clean}"
    )

    return {
        "success": True,
        "diamonds_awarded": reward,
        "message": f"Successfully claimed {reward} diamonds with code {code_clean}!"
    }

# --- REFERRALS ---
def get_referral_stats(user_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT referral_code FROM app_users WHERE id = %s;", (user_id,))
        ref_code = cursor.fetchone()["referral_code"]

        cursor.execute("""
            SELECT r.id, r.status, r.reward_diamonds, r.created_at, u.username
            FROM referrals r
            JOIN app_users u ON r.referee_id = u.id
            WHERE r.referrer_id = %s
            ORDER BY r.id DESC;
        """, (user_id,))
        invited = [dict(r) for r in cursor.fetchall()]

        total_earned = sum(item["reward_diamonds"] for item in invited if item["status"] == "COMPLETED")

    return {
        "referral_code": ref_code,
        "total_invited": len(invited),
        "total_earned_diamonds": total_earned,
        "referral_reward_per_user": 25,
        "invited_users": invited
    }

# --- NOTIFICATIONS ---
def create_notification(user_id: int, title: str, message: str, notification_type: str = "ANNOUNCEMENT", action_url: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, action_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *;
        """, (user_id, title, message, notification_type, action_url))
        return dict(cursor.fetchone())

def broadcast_notification(title: str, message: str, notification_type: str = "ANNOUNCEMENT", action_url: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM app_users WHERE is_active = 1;")
        users = cursor.fetchall()
        for u in users:
            uid = u["id"] if isinstance(u, dict) else u[0]
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, action_url)
                VALUES (%s, %s, %s, %s, %s);
            """, (uid, title, message, notification_type, action_url))

def get_user_notifications(user_id: int, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM notifications
            WHERE user_id = %s OR user_id IS NULL
            ORDER BY created_at DESC LIMIT %s;
        """, (user_id, limit))
        return [dict(r) for r in cursor.fetchall()]

def mark_notification_as_read(notification_id: int, user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications SET is_read = 1
            WHERE id = %s AND (user_id = %s OR user_id IS NULL);
        """, (notification_id, user_id))

# --- SUPPORT TICKETS ---
def create_support_ticket(user_id: int, subject: str, category: str, priority: str, message: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_tickets (user_id, subject, category, priority, status)
            VALUES (%s, %s, %s, %s, 'OPEN')
            RETURNING *;
        """, (user_id, subject.strip(), category, priority))
        ticket = dict(cursor.fetchone())
        ticket_id = ticket["id"]

        cursor.execute("""
            INSERT INTO support_messages (ticket_id, sender_type, sender_id, message)
            VALUES (%s, 'USER', %s, %s);
        """, (ticket_id, user_id, message.strip()))

    return ticket

def list_user_support_tickets(user_id: int) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM support_tickets WHERE user_id = %s ORDER BY updated_at DESC;
        """, (user_id,))
        return [dict(r) for r in cursor.fetchall()]

def get_ticket_conversation(ticket_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM support_tickets WHERE id = %s;", (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            return None
        ticket_dict = dict(ticket)

        cursor.execute("""
            SELECT * FROM support_messages WHERE ticket_id = %s ORDER BY created_at ASC;
        """, (ticket_id,))
        ticket_dict["messages"] = [dict(m) for m in cursor.fetchall()]
        return ticket_dict

def reply_to_ticket(ticket_id: int, sender_type: str, sender_id: int, message: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_messages (ticket_id, sender_type, sender_id, message)
            VALUES (%s, %s, %s, %s)
            RETURNING *;
        """, (ticket_id, sender_type, sender_id, message.strip()))
        msg = dict(cursor.fetchone())

        cursor.execute("""
            UPDATE support_tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = %s;
        """, (ticket_id,))
        return msg

# --- DISPUTES ---
def create_match_dispute(match_id: int, tournament_id: int, reporter_user_id: int, reason: str, proof_url: str = None, description: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO match_disputes (
                match_id, tournament_id, reporter_user_id, reason, proof_url, description, status
            ) VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
            RETURNING *;
        """, (match_id, tournament_id, reporter_user_id, reason, proof_url, description))
        return dict(cursor.fetchone())

def list_disputes(status_filter: str = None) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute("""
                SELECT d.*, u.username AS reporter_username, t.title AS tournament_title
                FROM match_disputes d
                JOIN app_users u ON d.reporter_user_id = u.id
                JOIN tournaments t ON d.tournament_id = t.id
                WHERE d.status = %s
                ORDER BY d.id DESC;
            """, (status_filter.upper(),))
        else:
            cursor.execute("""
                SELECT d.*, u.username AS reporter_username, t.title AS tournament_title
                FROM match_disputes d
                JOIN app_users u ON d.reporter_user_id = u.id
                JOIN tournaments t ON d.tournament_id = t.id
                ORDER BY d.id DESC;
            """)
        return [dict(r) for r in cursor.fetchall()]

# --- BANNERS ---
def list_active_banners() -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM banners WHERE is_active = 1 ORDER BY sort_order ASC, id DESC;
        """)
        return [dict(r) for r in cursor.fetchall()]
