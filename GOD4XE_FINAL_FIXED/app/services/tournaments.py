import re
import json
import datetime
from app.database import get_db
from app.services.wallet import deduct_diamonds, credit_diamonds

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text)

def create_tournament(
    title: str,
    banner_url: str = None,
    description: str = None,
    game: str = "FREE_FIRE",
    mode: str = "SOLO",
    format: str = "BATTLE_ROYALE",
    entry_type: str = "FREE",
    entry_fee_diamonds: int = 0,
    prize_type: str = "DIAMONDS",
    prize_amount_diamonds: int = 0,
    prize_distribution: dict = None,
    max_slots: int = 48,
    rules: str = None,
    map_name: str = "BERMUDA",
    start_time: str = None,
    is_featured: int = 0,
    is_published: int = 1
) -> dict:
    title = title.strip()
    if not title:
        raise ValueError("Tournament title is required")

    entry_type = entry_type.upper().strip()
    if entry_type not in ("FREE", "DIAMONDS"):
        raise ValueError("entry_type must be either 'FREE' or 'DIAMONDS'")

    if entry_type == "FREE":
        entry_fee_diamonds = 0
    else:
        if entry_fee_diamonds <= 0:
            raise ValueError("entry_fee_diamonds must be greater than 0 for DIAMONDS entry_type")

    slug = slugify(title)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tournaments WHERE slug = %s;", (slug,))
        if cursor.fetchone():
            slug = f"{slug}-{int(datetime.datetime.utcnow().timestamp())}"

        dist_json = json.dumps(prize_distribution or {
            "1": int(prize_amount_diamonds * 0.5),
            "2": int(prize_amount_diamonds * 0.3),
            "3": int(prize_amount_diamonds * 0.2)
        })

        cursor.execute("""
            INSERT INTO tournaments (
                title, slug, banner_url, description, game, mode, format,
                entry_type, entry_fee_diamonds, prize_type, prize_amount_diamonds,
                prize_distribution, max_slots, joined_players, rules, map_name,
                start_time, status, is_registration_open, is_featured, is_published
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s,
                %s, 'UPCOMING', 1, %s, %s
            ) RETURNING id;
        """, (
            title, slug, banner_url, description, game, mode, format,
            entry_type, entry_fee_diamonds, prize_type, prize_amount_diamonds,
            dist_json, max_slots, rules, map_name,
            start_time or (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat(),
            1 if is_featured else 0, 1 if is_published else 0
        ))
        res = cursor.fetchone()
        t_id = res["id"] if isinstance(res, dict) else res[0]

        # Automatically create Match 1
        cursor.execute("""
            INSERT INTO matches (tournament_id, match_number, title, status, scheduled_time)
            VALUES (%s, 1, %s, 'SCHEDULED', %s);
        """, (t_id, f"{title} - Match 1", start_time))

    return get_tournament_by_id(t_id)

def get_tournament_by_id(tournament_id: int, user_id: int = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE id = %s;", (tournament_id,))
        row = cursor.fetchone()
        if not row:
            return None
        t = dict(row)
        if t.get("prize_distribution") and isinstance(t["prize_distribution"], str):
            try:
                t["prize_distribution"] = json.loads(t["prize_distribution"])
            except Exception:
                pass

        # Check user registration status
        t["is_user_joined"] = False
        t["user_slot_number"] = None
        if user_id:
            cursor.execute("""
                SELECT slot_number FROM tournament_participants
                WHERE tournament_id = %s AND user_id = %s;
            """, (tournament_id, user_id))
            part = cursor.fetchone()
            if part:
                t["is_user_joined"] = True
                t["user_slot_number"] = part["slot_number"] if isinstance(part, dict) else part[0]

        return t

def list_tournaments(status_filter: str = None, limit: int = 50, offset: int = 0, is_published_only: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM tournaments WHERE 1=1"
        params = []
        if is_published_only:
            query += " AND is_published = 1"
        if status_filter:
            query += " AND status = %s"
            params.append(status_filter.upper())
        query += " ORDER BY is_featured DESC, start_time ASC LIMIT %s OFFSET %s;"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if r.get("prize_distribution") and isinstance(r["prize_distribution"], str):
                try:
                    r["prize_distribution"] = json.loads(r["prize_distribution"])
                except Exception:
                    pass
        return rows

def join_tournament(tournament_id: int, user_id: int, ff_uid: str, ff_ign: str) -> dict:
    ff_uid = ff_uid.strip() if ff_uid else ""
    ff_ign = ff_ign.strip() if ff_ign else ""
    if not ff_uid or not ff_ign:
        raise ValueError("Free Fire UID and IGN are required to join")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE id = %s FOR UPDATE;", (tournament_id,))
        t = cursor.fetchone()
        if not t:
            raise ValueError("Tournament not found")
        t_dict = dict(t)

        if t_dict["status"] != "UPCOMING" or t_dict.get("is_registration_open", 1) == 0:
            raise ValueError("Registration for this tournament is closed")

        if t_dict["joined_players"] >= t_dict["max_slots"]:
            raise ValueError("Tournament is fully booked")

        # Check if already joined
        cursor.execute("""
            SELECT id FROM tournament_participants
            WHERE tournament_id = %s AND user_id = %s;
        """, (tournament_id, user_id))
        if cursor.fetchone():
            raise ValueError("You have already joined this tournament")

        # Deduct entry fee if DIAMONDS
        entry_fee = t_dict["entry_fee_diamonds"]
        if t_dict["entry_type"] == "DIAMONDS" and entry_fee > 0:
            deduct_diamonds(
                user_id=user_id,
                amount=entry_fee,
                tx_type="TOURNAMENT_ENTRY",
                reference_id=f"TOURN-{tournament_id}",
                description=f"Entry fee for {t_dict['title']}"
            )

        # Allocate next slot
        cursor.execute("""
            SELECT COALESCE(MAX(slot_number), 0) + 1 AS next_slot
            FROM tournament_participants WHERE tournament_id = %s;
        """, (tournament_id,))
        next_slot = cursor.fetchone()["next_slot"]

        cursor.execute("""
            INSERT INTO tournament_participants (
                tournament_id, user_id, slot_number, ff_uid, ff_ign,
                payment_status, diamonds_paid
            ) VALUES (%s, %s, %s, %s, %s, 'PAID', %s)
            RETURNING slot_number;
        """, (tournament_id, user_id, next_slot, ff_uid, ff_ign, entry_fee))

        cursor.execute("""
            UPDATE tournaments
            SET joined_players = joined_players + 1
            WHERE id = %s;
        """, (tournament_id,))

        # Update user profile with latest FF UID & IGN
        cursor.execute("""
            UPDATE user_profiles
            SET ff_uid = %s, ff_ign = %s
            WHERE user_id = %s;
        """, (ff_uid, ff_ign, user_id))

    return {
        "success": True,
        "message": f"Successfully registered for {t_dict['title']}",
        "slot_number": next_slot,
        "entry_fee_deducted": entry_fee
    }

def get_tournament_room_credentials(tournament_id: int, user_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT slot_number FROM tournament_participants
            WHERE tournament_id = %s AND user_id = %s;
        """, (tournament_id, user_id))
        if not cursor.fetchone():
            raise ValueError("Access restricted: You must be a confirmed participant to view room credentials")

        cursor.execute("""
            SELECT room_id, room_password, room_instructions, start_time, status
            FROM tournaments WHERE id = %s;
        """, (tournament_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tournament not found")
        data = dict(row)

        is_available = bool(data.get("room_id") and data.get("room_password"))
        return {
            "room_available": is_available,
            "room_id": data.get("room_id") if is_available else None,
            "room_password": data.get("room_password") if is_available else None,
            "room_instructions": data.get("room_instructions") or "Join the custom room using Room ID and Password 10 minutes prior to scheduled start.",
            "start_time": data.get("start_time")
        }

def update_tournament_room_credentials(tournament_id: int, room_id: str, room_password: str, instructions: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET room_id = %s, room_password = %s, room_instructions = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (room_id.strip(), room_password.strip(), instructions, tournament_id))
    return {"success": True, "tournament_id": tournament_id}

def update_tournament_status(tournament_id: int, new_status: str) -> dict:
    valid_statuses = ("UPCOMING", "LIVE", "COMPLETED", "CANCELLED")
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (new_status, tournament_id))
    return {"success": True, "status": new_status}
