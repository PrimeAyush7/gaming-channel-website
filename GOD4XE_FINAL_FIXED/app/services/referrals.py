import datetime
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.config import APP_URL

# Fallback default rank tiers if database table is empty
DEFAULT_RANKS = [
    {"name": "ROOKIE", "min_referrals": 0, "max_referrals": 9, "display_order": 1, "badge_color": "#94a3b8", "is_active": True},
    {"name": "PRO", "min_referrals": 10, "max_referrals": 24, "display_order": 2, "badge_color": "#38bdf8", "is_active": True},
    {"name": "ELITE", "min_referrals": 25, "max_referrals": 49, "display_order": 3, "badge_color": "#a855f7", "is_active": True},
    {"name": "MASTER", "min_referrals": 50, "max_referrals": 99, "display_order": 4, "badge_color": "#f59e0b", "is_active": True},
    {"name": "LEGEND", "min_referrals": 100, "max_referrals": None, "display_order": 5, "badge_color": "#ef4444", "is_active": True},
]

def get_active_ranks() -> List[Dict[str, Any]]:
    """Retrieve all active referral ranks ordered by display_order ascending."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, min_referrals, max_referrals, display_order, badge_color, is_active
                FROM referral_ranks
                WHERE is_active = TRUE or is_active = 1
                ORDER BY display_order ASC, min_referrals ASC;
            """)
            rows = cursor.fetchall()
            if rows:
                return [dict(r) for r in rows]
    except Exception:
        pass
    return DEFAULT_RANKS

def calculate_rank_details(successful_count: int, ranks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Given a user's current valid successful referral count, determine:
    - current_rank
    - badge_color
    - next_rank
    - referrals_to_next_rank
    - required_for_next_rank
    - progress_percentage
    - is_max_rank
    """
    if ranks is None:
        ranks = get_active_ranks()

    count = max(0, int(successful_count))

    current_rank_item = None
    next_rank_item = None

    # Sort ranks by min_referrals ascending
    sorted_ranks = sorted(ranks, key=lambda x: x["min_referrals"])

    for r in sorted_ranks:
        min_ref = r["min_referrals"]
        max_ref = r["max_referrals"]
        if count >= min_ref and (max_ref is None or count <= max_ref):
            current_rank_item = r
            break

    # If count is somehow below first rank min, default to first rank
    if not current_rank_item and sorted_ranks:
        current_rank_item = sorted_ranks[0]

    # Find the next rank tier
    if current_rank_item:
        current_min = current_rank_item["min_referrals"]
        for r in sorted_ranks:
            if r["min_referrals"] > current_min and r["min_referrals"] > count:
                next_rank_item = r
                break

    if next_rank_item:
        next_min = next_rank_item["min_referrals"]
        needed = max(0, next_min - count)
        # Calculate progress
        prev_min = current_rank_item["min_referrals"] if current_rank_item else 0
        span = next_min - prev_min
        progress_val = count - prev_min
        if span > 0:
            pct = min(100.0, max(0.0, (progress_val / span) * 100.0))
        else:
            pct = 100.0

        return {
            "current_rank": current_rank_item["name"] if current_rank_item else "ROOKIE",
            "badge_color": current_rank_item.get("badge_color", "#a855f7") if current_rank_item else "#a855f7",
            "next_rank": next_rank_item["name"],
            "referrals_to_next_rank": needed,
            "required_for_next_rank": next_min,
            "progress_percentage": round(pct, 1),
            "progress_text": f"{count} / {next_min}",
            "remaining_text": f"{needed} referrals to next rank",
            "is_max_rank": False
        }
    else:
        # User is at the highest rank
        return {
            "current_rank": current_rank_item["name"] if current_rank_item else "LEGEND",
            "badge_color": current_rank_item.get("badge_color", "#ef4444") if current_rank_item else "#ef4444",
            "next_rank": None,
            "referrals_to_next_rank": 0,
            "required_for_next_rank": current_rank_item["min_referrals"] if current_rank_item else 100,
            "progress_percentage": 100.0,
            "progress_text": "Maximum Rank Reached",
            "remaining_text": "Maximum Rank Reached",
            "is_max_rank": True
        }

def get_successful_referral_count(user_id: int) -> int:
    """Return the exact count of valid SUCCESSFUL referrals for a given user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM referrals
            WHERE referrer_id = %s AND status = 'SUCCESSFUL';
        """, (user_id,))
        row = cursor.fetchone()
        return row["cnt"] if row else 0

def get_user_leaderboard_position(user_id: int, successful_count: Optional[int] = None) -> int:
    """
    Calculate the user's authoritative position on the live referral leaderboard.
    Sort order: successful_referrals DESC, referrer_id ASC.
    """
    if successful_count is None:
        successful_count = get_successful_referral_count(user_id)

    with get_db() as conn:
        cursor = conn.cursor()
        if successful_count > 0:
            cursor.execute("""
                WITH ref_counts AS (
                    SELECT referrer_id, COUNT(*) AS successful_referrals
                    FROM referrals
                    WHERE status = 'SUCCESSFUL'
                    GROUP BY referrer_id
                )
                SELECT COUNT(*) + 1 AS pos
                FROM ref_counts
                WHERE successful_referrals > %s
                   OR (successful_referrals = %s AND referrer_id < %s);
            """, (successful_count, successful_count, user_id))
            row = cursor.fetchone()
            return int(row["pos"]) if row and row["pos"] is not None else 1
        else:
            # Users with 0 successful referrals rank after all users with >= 1 referral,
            # ordered deterministically by app_users.id ASC
            cursor.execute("""
                WITH ref_counts AS (
                    SELECT referrer_id
                    FROM referrals
                    WHERE status = 'SUCCESSFUL'
                    GROUP BY referrer_id
                )
                SELECT (SELECT COUNT(DISTINCT referrer_id) FROM referrals WHERE status = 'SUCCESSFUL') +
                       (SELECT COUNT(*) FROM app_users WHERE id NOT IN (SELECT referrer_id FROM ref_counts) AND id < %s AND (is_active = 1 OR is_active = TRUE)) + 1 AS pos;
            """, (user_id,))
            row = cursor.fetchone()
            return int(row["pos"]) if row and row["pos"] is not None else 1

def get_user_referral_summary(user_id: int) -> Dict[str, Any]:
    """
    Return comprehensive, live referral data for the authenticated user:
    - referral_code
    - referral_link
    - successful_referrals
    - total_referrals
    - current_rank
    - next_rank
    - referrals_to_next_rank
    - progress_percentage
    - leaderboard_position
    - invited_users
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT referral_code FROM app_users WHERE id = %s;", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise ValueError("User not found")
        ref_code = user_row["referral_code"] or f"GOD{user_id}"

        # Fetch invited users list
        cursor.execute("""
            SELECT r.id, r.referee_id, r.status, r.created_at, r.invalidation_reason, u.username
            FROM referrals r
            JOIN app_users u ON r.referee_id = u.id
            WHERE r.referrer_id = %s
            ORDER BY r.id DESC;
        """, (user_id,))
        invited = [dict(r) for r in cursor.fetchall()]

    successful_count = sum(1 for item in invited if item.get("status") == "SUCCESSFUL")
    total_count = len(invited)

    ranks = get_active_ranks()
    rank_details = calculate_rank_details(successful_count, ranks)
    position = get_user_leaderboard_position(user_id, successful_count)

    base_url = APP_URL.rstrip("/")
    ref_link = f"{base_url}/tournaments/register?ref={ref_code}"

    return {
        "success": True,
        "referral_code": ref_code,
        "referral_link": ref_link,
        "successful_referrals": successful_count,
        "total_referrals": total_count,
        "current_rank": rank_details["current_rank"],
        "badge_color": rank_details["badge_color"],
        "next_rank": rank_details["next_rank"],
        "referrals_to_next_rank": rank_details["referrals_to_next_rank"],
        "required_for_next_rank": rank_details["required_for_next_rank"],
        "progress_percentage": rank_details["progress_percentage"],
        "progress_text": rank_details["progress_text"],
        "remaining_text": rank_details["remaining_text"],
        "is_max_rank": rank_details["is_max_rank"],
        "leaderboard_position": position,
        "invited_users": invited
    }

def get_referral_leaderboard(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    Return the live, authoritative referral leaderboard sorted by:
    1. successful_referrals DESC
    2. referrer_id ASC
    """
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))

    ranks = get_active_ranks()

    with get_db() as conn:
        cursor = conn.cursor()
        # Total distinct referrers with at least 1 successful referral
        cursor.execute("""
            SELECT COUNT(DISTINCT referrer_id) AS total_count
            FROM referrals
            WHERE status = 'SUCCESSFUL';
        """)
        total_row = cursor.fetchone()
        total_leaderboard_users = total_row["total_count"] if total_row else 0

        cursor.execute("""
            WITH ref_counts AS (
                SELECT referrer_id, COUNT(*) AS successful_referrals
                FROM referrals
                WHERE status = 'SUCCESSFUL'
                GROUP BY referrer_id
            )
            SELECT 
                rc.referrer_id AS user_id,
                u.username,
                rc.successful_referrals
            FROM ref_counts rc
            JOIN app_users u ON rc.referrer_id = u.id
            WHERE u.is_active = 1 OR u.is_active = TRUE
            ORDER BY rc.successful_referrals DESC, rc.referrer_id ASC
            LIMIT %s OFFSET %s;
        """, (limit, offset))
        rows = [dict(r) for r in cursor.fetchall()]

    leaderboard = []
    for idx, row in enumerate(rows):
        pos = offset + idx + 1
        count = row["successful_referrals"]
        rank_details = calculate_rank_details(count, ranks)
        leaderboard.append({
            "position": pos,
            "user_id": row["user_id"],
            "username": row["username"],
            "successful_referrals": count,
            "referral_rank": rank_details["current_rank"],
            "badge_color": rank_details["badge_color"]
        })

    return {
        "success": True,
        "count": len(leaderboard),
        "total": total_leaderboard_users,
        "offset": offset,
        "limit": limit,
        "leaderboard": leaderboard
    }

def record_referral(referrer_code: str, referee_id: int) -> Optional[Dict[str, Any]]:
    """
    Safely attribute a referral during registration:
    - Resolves referrer by referral_code
    - Prevents self-referral (referrer_id != referee_id)
    - Prevents duplicate referral for the same referee account
    - Awards ZERO diamonds
    - Sets status to 'SUCCESSFUL'
    """
    if not referrer_code or not str(referrer_code).strip():
        return None

    code_clean = str(referrer_code).strip().upper()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM app_users WHERE referral_code = %s;", (code_clean,))
        ref_row = cursor.fetchone()
        if not ref_row:
            return None

        referrer_id = ref_row["id"]

        # Prevent self-referral
        if referrer_id == referee_id:
            return None

        # Check if referee was already referred
        cursor.execute("SELECT id FROM referrals WHERE referee_id = %s;", (referee_id,))
        if cursor.fetchone():
            return None

        # Record successful referral with 0 diamonds
        cursor.execute("""
            INSERT INTO referrals (referrer_id, referee_id, reward_diamonds, status)
            VALUES (%s, %s, 0, 'SUCCESSFUL')
            ON CONFLICT (referee_id) DO NOTHING
            RETURNING *;
        """, (referrer_id, referee_id))
        created = cursor.fetchone()
        return dict(created) if created else None

def invalidate_referral(referral_id: int, admin_id: int, admin_username: str, reason: str) -> Dict[str, Any]:
    """
    Administratively invalidate/reverse a referral:
    - Sets status to 'INVALID'
    - Records admin identity, reason, and timestamp
    - Logs to audit_logs
    - Since ranks are computed dynamically, the referrer's count and rank will immediately reflect this change
    """
    reason_clean = (reason or "Administratively invalidated").strip()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM referrals WHERE id = %s;", (referral_id,))
        ref = cursor.fetchone()
        if not ref:
            raise ValueError("Referral record not found")

        ref_dict = dict(ref)
        prev_status = ref_dict.get("status")

        cursor.execute("""
            UPDATE referrals
            SET status = 'INVALID',
                invalidation_reason = %s,
                invalidated_at = CURRENT_TIMESTAMP,
                invalidated_by_admin_id = %s
            WHERE id = %s
            RETURNING *;
        """, (reason_clean, admin_id, referral_id))
        updated = dict(cursor.fetchone())

    # Audit log entry
    from app.services import auth as auth_service
    auth_service.record_audit_log(
        admin_id=admin_id,
        admin_username=admin_username,
        role="ADMIN",
        action="INVALIDATE_REFERRAL",
        resource="referral",
        resource_id=referral_id,
        ip_address='127.0.0.1',
        before_state={"status": prev_status},
        after_state={"status": "INVALID", "reason": reason_clean}
    )

    return updated

def admin_list_referrals(search: Optional[str] = None, status_filter: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Query referral records for admin console with referrer/referee details and live rank info."""
    ranks = get_active_ranks()

    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                r.id,
                r.referrer_id,
                r.referee_id,
                r.reward_diamonds,
                r.status,
                r.created_at,
                r.invalidation_reason,
                r.invalidated_at,
                u_ref.username AS referrer_username,
                u_ref.email AS referrer_email,
                u_ref.phone AS referrer_phone,
                u_ref.referral_code AS referrer_code,
                u_referee.username AS referee_username,
                u_referee.email AS referee_email,
                u_referee.phone AS referee_phone,
                u_referee.created_at AS referee_registered_at
            FROM referrals r
            JOIN app_users u_ref ON r.referrer_id = u_ref.id
            JOIN app_users u_referee ON r.referee_id = u_referee.id
            WHERE 1=1
        """
        params = []
        if status_filter:
            query += " AND r.status = %s"
            params.append(status_filter.upper())
        if search:
            query += " AND (u_ref.username ILIKE %s OR u_referee.username ILIKE %s OR u_ref.referral_code ILIKE %s)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        query += " ORDER BY r.id DESC LIMIT %s OFFSET %s;"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]

    # Augment each row with referrer's total successful referrals and rank
    referrer_counts = {}
    for r in rows:
        rid = r["referrer_id"]
        if rid not in referrer_counts:
            referrer_counts[rid] = get_successful_referral_count(rid)
        r["referrer_successful_count"] = referrer_counts[rid]
        rank_details = calculate_rank_details(referrer_counts[rid], ranks)
        r["referrer_current_rank"] = rank_details["current_rank"]
        r["referrer_badge_color"] = rank_details["badge_color"]

    return rows

def admin_get_ranks() -> List[Dict[str, Any]]:
    return get_active_ranks()

def admin_update_ranks(ranks_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update or upsert rank thresholds with validation."""
    # Validate no overlapping ranges among active ranks
    sorted_data = sorted(ranks_data, key=lambda x: int(x.get("min_referrals", 0)))
    for i in range(len(sorted_data) - 1):
        curr_max = sorted_data[i].get("max_referrals")
        next_min = sorted_data[i + 1].get("min_referrals")
        if curr_max is not None and next_min is not None and curr_max >= next_min:
            raise ValueError(f"Conflicting rank thresholds: Rank '{sorted_data[i].get('name')}' max ({curr_max}) must be less than '{sorted_data[i+1].get('name')}' min ({next_min})")

    with get_db() as conn:
        cursor = conn.cursor()
        for idx, r in enumerate(sorted_data):
            name = r["name"].strip().upper()
            min_r = int(r["min_referrals"])
            max_r = int(r["max_referrals"]) if r.get("max_referrals") not in (None, "", "null") else None
            badge_color = r.get("badge_color", "#a855f7")
            is_active = bool(r.get("is_active", True))

            cursor.execute("""
                INSERT INTO referral_ranks (name, min_referrals, max_referrals, display_order, badge_color, is_active, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (name) DO UPDATE
                SET min_referrals = EXCLUDED.min_referrals,
                    max_referrals = EXCLUDED.max_referrals,
                    display_order = EXCLUDED.display_order,
                    badge_color = EXCLUDED.badge_color,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP;
            """, (name, min_r, max_r, idx + 1, badge_color, is_active))

    return get_active_ranks()
