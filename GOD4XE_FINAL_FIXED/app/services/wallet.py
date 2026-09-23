import uuid
import datetime
from app.database import get_db
from app.config import WITHDRAWALS_ENABLED

def get_wallet_info(user_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT balance, locked_balance, updated_at
            FROM diamond_accounts
            WHERE user_id = %s;
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO diamond_accounts (user_id, balance, locked_balance)
                VALUES (%s, 0, 0)
                RETURNING balance, locked_balance, updated_at;
            """, (user_id,))
            row = cursor.fetchone()
        
        info = dict(row)
        info["withdrawals_enabled"] = WITHDRAWALS_ENABLED
        return info

def credit_diamonds(
    user_id: int,
    amount: int,
    tx_type: str,
    reference_id: str = None,
    admin_id: int = None,
    description: str = None
) -> dict:
    if amount <= 0:
        raise ValueError("Credit amount must be positive")

    tx_uuid = str(uuid.uuid4())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM diamond_accounts WHERE user_id = %s FOR UPDATE;", (user_id,))
        row = cursor.fetchone()
        current_balance = row["balance"] if isinstance(row, dict) else (row[0] if row else 0)
        
        new_balance = current_balance + amount
        cursor.execute("""
            UPDATE diamond_accounts
            SET balance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (new_balance, user_id))

        cursor.execute("""
            INSERT INTO diamond_transactions (
                transaction_uuid, user_id, amount, balance_after,
                tx_type, reference_id, admin_id, description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, transaction_uuid, amount, balance_after, tx_type, created_at;
        """, (tx_uuid, user_id, amount, new_balance, tx_type, reference_id, admin_id, description))
        tx = dict(cursor.fetchone())
    return tx

def deduct_diamonds(
    user_id: int,
    amount: int,
    tx_type: str,
    reference_id: str = None,
    admin_id: int = None,
    description: str = None
) -> dict:
    if amount <= 0:
        raise ValueError("Deduct amount must be positive")

    tx_uuid = str(uuid.uuid4())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM diamond_accounts WHERE user_id = %s FOR UPDATE;", (user_id,))
        row = cursor.fetchone()
        current_balance = row["balance"] if isinstance(row, dict) else (row[0] if row else 0)

        if current_balance < amount:
            raise ValueError(f"Insufficient diamonds. You have {current_balance} diamonds, but {amount} are required.")

        new_balance = current_balance - amount
        cursor.execute("""
            UPDATE diamond_accounts
            SET balance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (new_balance, user_id))

        cursor.execute("""
            INSERT INTO diamond_transactions (
                transaction_uuid, user_id, amount, balance_after,
                tx_type, reference_id, admin_id, description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, transaction_uuid, amount, balance_after, tx_type, created_at;
        """, (tx_uuid, user_id, -amount, new_balance, tx_type, reference_id, admin_id, description))
        tx = dict(cursor.fetchone())
    return tx

def list_transactions(user_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, transaction_uuid, amount, balance_after, tx_type,
                   reference_id, description, created_at
            FROM diamond_transactions
            WHERE user_id = %s
            ORDER BY id DESC LIMIT %s OFFSET %s;
        """, (user_id, limit, offset))
        return [dict(r) for r in cursor.fetchall()]

def create_deposit_request(user_id: int, amount: int, utr_reference: str, payment_proof_url: str = None) -> dict:
    if amount < 10:
        raise ValueError("Minimum deposit is 10 diamonds")
    utr_clean = utr_reference.strip()
    if len(utr_clean) < 6:
        raise ValueError("Please provide a valid UTR or payment reference number")
    if not payment_proof_url or not str(payment_proof_url).strip():
        raise ValueError("Payment screenshot proof is required")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM deposit_requests WHERE utr_reference = %s;", (utr_clean,))
        if cursor.fetchone():
            raise ValueError("This UTR reference has already been submitted")

        cursor.execute("""
            INSERT INTO deposit_requests (user_id, amount, utr_reference, payment_proof_url, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
            RETURNING id, user_id, amount, utr_reference, status, created_at;
        """, (user_id, amount, utr_clean, payment_proof_url))
        req = dict(cursor.fetchone())
    return req

def list_user_deposit_requests(user_id: int, limit: int = 20) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, amount, utr_reference, payment_proof_url, status,
                   rejection_reason, created_at, reviewed_at
            FROM deposit_requests
            WHERE user_id = %s
            ORDER BY id DESC LIMIT %s;
        """, (user_id, limit))
        return [dict(r) for r in cursor.fetchall()]

def list_all_deposit_requests(status_filter: str = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute("""
                SELECT d.*, u.username, u.email, u.phone
                FROM deposit_requests d
                JOIN app_users u ON d.user_id = u.id
                WHERE d.status = %s
                ORDER BY d.id DESC LIMIT %s OFFSET %s;
            """, (status_filter.upper(), limit, offset))
        else:
            cursor.execute("""
                SELECT d.*, u.username, u.email, u.phone
                FROM deposit_requests d
                JOIN app_users u ON d.user_id = u.id
                ORDER BY d.id DESC LIMIT %s OFFSET %s;
            """, (limit, offset))
        return [dict(r) for r in cursor.fetchall()]

def review_deposit_request(request_id: int, admin_id: int, approve: bool, rejection_reason: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deposit_requests WHERE id = %s;", (request_id,))
        req = cursor.fetchone()
        if not req:
            raise ValueError("Deposit request not found")

        req_dict = dict(req)
        if req_dict["status"] != "PENDING":
            raise ValueError(f"Request has already been processed (status: {req_dict['status']})")

        new_status = "APPROVED" if approve else "REJECTED"
        cursor.execute("""
            UPDATE deposit_requests
            SET status = %s, reviewed_by_admin_id = %s, rejection_reason = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (new_status, admin_id, rejection_reason if not approve else None, request_id))

    if approve:
        credit_diamonds(
            user_id=req_dict["user_id"],
            amount=req_dict["amount"],
            tx_type="DEPOSIT",
            reference_id=f"DEP-{request_id}",
            admin_id=admin_id,
            description=f"Deposit verified (UTR: {req_dict['utr_reference']})"
        )

    return {"success": True, "request_id": request_id, "status": new_status}
