import time
import uuid
import datetime
from app.database import get_db
from app.config import WITHDRAWALS_ENABLED

def get_deposit_settings() -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings WHERE key LIKE 'deposit_%' OR key LIKE 'upi_%';")
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
        
    rate = float(settings.get("deposit_diamonds_per_inr", "1.0") or 1.0)
    min_dep = int(settings.get("deposit_min_diamonds", "10") or 10)
    multiples = int(settings.get("deposit_multiples", "10") or 10)
    upi_id = settings.get("upi_id", "god4xe@upi")
    payee_name = settings.get("upi_payee_name", "GOD4XE ESPORTS")
    instructions = settings.get("deposit_instructions", "Scan QR or send UPI payment, then enter UTR reference.")
    qr_img = settings.get("upi_qr_image_url", "")
    
    return {
        "rate_inr_per_diamond": rate,
        "diamonds_per_ten_inr": int(10 * rate),
        "min_deposit_diamonds": min_dep,
        "multiples": multiples,
        "upi_id": upi_id,
        "payee_name": payeeee_name if 'payeeee_name' in locals() else payee_name,
        "instructions": instructions,
        "upi_qr_string": f"upi://pay?pa={upi_id}&pn={payee_name}&cu=INR",
        "upi_qr_image_url": qr_img
    }

def get_withdrawal_settings() -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings WHERE key LIKE 'withdraw_%' OR key = 'withdrawals_enabled';")
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
        
    enabled_setting = settings.get("withdrawals_enabled", "true").lower() in ("true", "1", "yes")
    rate = float(settings.get("withdraw_diamonds_per_inr", "0.8") or 0.8) # Default 10 Diamonds = Rs 8
    min_with = int(settings.get("withdraw_min_diamonds", "50") or 50)
    multiples = int(settings.get("withdraw_multiples", "10") or 10)
    
    return {
        "withdrawals_enabled": WITHDRAWALS_ENABLED and enabled_setting,
        "rate_inr_per_diamond": rate,
        "inr_per_ten_diamonds": int(10 * rate),
        "min_withdrawal_diamonds": min_with,
        "multiples": multiples
    }

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
        if info.get("updated_at") and hasattr(info["updated_at"], "isoformat"):
            info["updated_at"] = info["updated_at"].isoformat()
            
        with_cfg = get_withdrawal_settings()
        info["withdrawals_enabled"] = with_cfg["withdrawals_enabled"]
        info["withdrawal_rate_inr"] = with_cfg["rate_inr_per_diamond"]
        info["min_withdrawal_diamonds"] = with_cfg["min_withdrawal_diamonds"]
        
        dep_cfg = get_deposit_settings()
        info["deposit_rate_inr"] = dep_cfg["rate_inr_per_diamond"]
        info["min_deposit_diamonds"] = dep_cfg["min_deposit_diamonds"]
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
        cursor.execute("""
            INSERT INTO diamond_accounts (user_id, balance, locked_balance)
            VALUES (%s, 0, 0)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))
        cursor.execute("""
            SELECT balance, locked_balance 
            FROM diamond_accounts 
            WHERE user_id = %s 
            FOR UPDATE;
        """, (user_id,))
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
        if tx.get("created_at") and hasattr(tx["created_at"], "isoformat"):
            tx["created_at"] = tx["created_at"].isoformat()
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
        cursor.execute("""
            INSERT INTO diamond_accounts (user_id, balance, locked_balance)
            VALUES (%s, 0, 0)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))
        cursor.execute("""
            SELECT balance, locked_balance 
            FROM diamond_accounts 
            WHERE user_id = %s 
            FOR UPDATE;
        """, (user_id,))
        row = cursor.fetchone()
        current_balance = row["balance"] if isinstance(row, dict) else (row[0] if row else 0)

        if current_balance < amount:
            raise ValueError(f"Insufficient diamonds. User only has {current_balance} diamonds, but {amount} requested for removal.")

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
        if tx.get("created_at") and hasattr(tx["created_at"], "isoformat"):
            tx["created_at"] = tx["created_at"].isoformat()
    return tx

def admin_adjust_diamonds(
    user_id: int,
    amount: int,
    action: str,
    reason: str,
    admin_id: int = None
) -> dict:
    if not reason or not reason.strip():
        raise ValueError("Reason is required for diamond balance adjustment")
    if amount <= 0:
        raise ValueError("Amount must be a positive integer greater than zero")

    action = action.upper().strip()
    if action not in ("ADD", "REMOVE", "CREDIT", "DEBIT"):
        raise ValueError(f"Invalid adjustment action: {action}")

    clean_reason = reason.strip()
    ref_id = f"ADMIN_MANUAL_{admin_id or 0}_{int(time.time())}"

    if action in ("ADD", "CREDIT"):
        return credit_diamonds(
            user_id=user_id,
            amount=amount,
            tx_type="ADMIN_CREDIT",
            reference_id=ref_id,
            admin_id=admin_id,
            description=f"Admin credit: {clean_reason}"
        )
    else:
        return deduct_diamonds(
            user_id=user_id,
            amount=amount,
            tx_type="ADMIN_DEBIT",
            reference_id=ref_id,
            admin_id=admin_id,
            description=f"Admin debit: {clean_reason}"
        )

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
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

# --------------------------------------------------------------------------
# DEPOSIT REQUESTS
# --------------------------------------------------------------------------
def create_deposit_request(user_id: int, amount: int, utr_reference: str, payment_proof_url: str = None) -> dict:
    cfg = get_deposit_settings()
    min_dep = cfg["min_deposit_diamonds"]
    if amount < min_dep:
        raise ValueError(f"Minimum deposit is {min_dep} diamonds")
    if amount % cfg["multiples"] != 0:
        raise ValueError(f"Deposit amount must be a multiple of {cfg['multiples']} diamonds")
        
    utr_clean = utr_reference.strip()
    if len(utr_clean) < 6:
        raise ValueError("Please provide a valid UTR or payment reference number")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM deposit_requests WHERE utr_reference = %s;", (utr_clean,))
        if cursor.fetchone():
            raise ValueError("This UTR reference has already been submitted")

        cursor.execute("""
            INSERT INTO deposit_requests (user_id, amount, utr_reference, payment_proof_url, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
            RETURNING id, user_id, amount, utr_reference, payment_proof_url, status, created_at;
        """, (user_id, amount, utr_clean, payment_proof_url))
        req = dict(cursor.fetchone())
        if req.get("created_at") and hasattr(req["created_at"], "isoformat"):
            req["created_at"] = req["created_at"].isoformat()
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
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            for k in ("created_at", "reviewed_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            results.append(d)
        return results

def list_all_deposit_requests(status_filter: str = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        if status_filter and status_filter.upper() not in ("ALL", ""):
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
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            for k in ("created_at", "reviewed_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            results.append(d)
        return results

def review_deposit_request(request_id: int, admin_id: int, approve: bool, rejection_reason: str = None) -> dict:
    from app.services import content_features
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
        content_features.send_smart_notification(
            user_id=req_dict["user_id"],
            title="Deposit Approved!",
            message=f"💎 {req_dict['amount']} Diamonds have been credited to your wallet (UTR: {req_dict['utr_reference']}).",
            notif_type="DEPOSIT_APPROVED",
            action_url="/wallet"
        )
    else:
        content_features.send_smart_notification(
            user_id=req_dict["user_id"],
            title="Deposit Rejected",
            message=f"Your deposit of {req_dict['amount']} Diamonds was rejected. Reason: {rejection_reason or 'Invalid UTR reference'}.",
            notif_type="DEPOSIT_REJECTED",
            action_url="/wallet"
        )

    return {"success": True, "request_id": request_id, "status": new_status}

# --------------------------------------------------------------------------
# WITHDRAWAL REQUESTS & CONTROLS
# --------------------------------------------------------------------------
def create_withdrawal_request(user_id: int, amount: int, upi_id: str) -> dict:
    from app.services import content_features
    cfg = get_withdrawal_settings()
    if not cfg["withdrawals_enabled"]:
        raise ValueError("Withdrawals are currently disabled for review and legal compliance.")
        
    min_with = cfg["min_withdrawal_diamonds"]
    if amount < min_with:
        raise ValueError(f"Minimum withdrawal is {min_with} diamonds")
    if amount % cfg["multiples"] != 0:
        raise ValueError(f"Withdrawal amount must be in multiples of {cfg['multiples']} diamonds")
        
    clean_upi = upi_id.strip()
    if len(clean_upi) < 3 or "@" not in clean_upi:
        raise ValueError("Please enter a valid UPI ID (e.g., yourname@bank)")

    # Deduct diamonds from user balance
    deduct_diamonds(
        user_id=user_id,
        amount=amount,
        tx_type="WITHDRAWAL_REQUEST",
        description=f"Withdrawal request for {amount} diamonds (Payout: Rs. {int(amount * cfg['rate_inr_per_diamond'])}) to {clean_upi}"
    )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO withdrawal_requests (user_id, amount, upi_id, status)
            VALUES (%s, %s, %s, 'PENDING')
            RETURNING id, user_id, amount, upi_id, status, created_at;
        """, (user_id, amount, clean_upi))
        req = dict(cursor.fetchone())
        if req.get("created_at") and hasattr(req["created_at"], "isoformat"):
            req["created_at"] = req["created_at"].isoformat()

    content_features.send_smart_notification(
        user_id=user_id,
        title="Withdrawal Submitted",
        message=f"Your withdrawal request of 💎 {amount} Diamonds (₹{int(amount * cfg['rate_inr_per_diamond'])}) is pending review.",
        notif_type="WITHDRAWAL_PENDING",
        action_url="/wallet"
    )

    return req

def list_user_withdrawal_requests(user_id: int, limit: int = 20) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, amount, upi_id, status, payout_reference,
                   rejection_reason, created_at, reviewed_at
            FROM withdrawal_requests
            WHERE user_id = %s
            ORDER BY id DESC LIMIT %s;
        """, (user_id, limit))
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            for k in ("created_at", "reviewed_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            results.append(d)
        return results

def list_all_withdrawal_requests(status_filter: str = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        if status_filter and status_filter.upper() not in ("ALL", ""):
            cursor.execute("""
                SELECT w.*, u.username, u.email, u.phone
                FROM withdrawal_requests w
                JOIN app_users u ON w.user_id = u.id
                WHERE w.status = %s
                ORDER BY w.id DESC LIMIT %s OFFSET %s;
            """, (status_filter.upper(), limit, offset))
        else:
            cursor.execute("""
                SELECT w.*, u.username, u.email, u.phone
                FROM withdrawal_requests w
                JOIN app_users u ON w.user_id = u.id
                ORDER BY w.id DESC LIMIT %s OFFSET %s;
            """, (limit, offset))
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            for k in ("created_at", "reviewed_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            results.append(d)
        return results

def review_withdrawal_request(request_id: int, admin_id: int, approve: bool, payout_reference: str = None, rejection_reason: str = None) -> dict:
    from app.services import content_features
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawal_requests WHERE id = %s;", (request_id,))
        req = cursor.fetchone()
        if not req:
            raise ValueError("Withdrawal request not found")

        req_dict = dict(req)
        if req_dict["status"] != "PENDING":
            raise ValueError(f"Request has already been processed (status: {req_dict['status']})")

        new_status = "APPROVED" if approve else "REJECTED"
        cursor.execute("""
            UPDATE withdrawal_requests
            SET status = %s, reviewed_by_admin_id = %s, payout_reference = %s,
                rejection_reason = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (new_status, admin_id, payout_reference if approve else None, rejection_reason if not approve else None, request_id))

    if not approve:
        # Refund diamonds back to user
        credit_diamonds(
            user_id=req_dict["user_id"],
            amount=req_dict["amount"],
            tx_type="WITHDRAWAL_REFUND",
            reference_id=f"WITH-{request_id}",
            admin_id=admin_id,
            description=f"Withdrawal refund: {rejection_reason or 'Rejected by administrator'}"
        )
        content_features.send_smart_notification(
            user_id=req_dict["user_id"],
            title="Withdrawal Rejected (Refunded)",
            message=f"💎 {req_dict['amount']} Diamonds refunded to your wallet. Reason: {rejection_reason or 'Details could not be verified'}.",
            notif_type="WITHDRAWAL_REJECTED",
            action_url="/wallet"
        )
    else:
        content_features.send_smart_notification(
            user_id=req_dict["user_id"],
            title="Withdrawal Payout Sent!",
            message=f"Your withdrawal of ₹{int(req_dict['amount'] * 0.8)} has been paid (UTR: {payout_reference or 'PROCESSED'}).",
            notif_type="WITHDRAWAL_APPROVED",
            action_url="/wallet"
        )

    return {"success": True, "request_id": request_id, "status": new_status}
