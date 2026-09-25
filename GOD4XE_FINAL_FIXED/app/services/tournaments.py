import uuid
import datetime
import json
from app.database import get_db

def _format_tournament_row(row: dict) -> dict:
    if not row:
        return None
    d = dict(row)
    for col in ("start_time", "created_at", "updated_at", "scheduled_time", "completed_at", "joined_at"):
        if col in d and d[col] is not None and hasattr(d[col], "isoformat"):
            d[col] = d[col].isoformat()
    return d

def check_and_update_tournament_statuses():
    """
    Automated backend status transition:
    - UPCOMING -> LIVE at start_time
    - LIVE -> COMPLETED 20 minutes after start_time (unless manually completed)
    """
    now = datetime.datetime.utcnow()
    with get_db() as conn:
        cursor = conn.cursor()
        # 1. UPCOMING -> LIVE
        cursor.execute("""
            UPDATE tournaments
            SET status = 'LIVE', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'UPCOMING' AND start_time <= %s;
        """, (now,))
        
        # 2. LIVE -> COMPLETED after 20 mins (if not manually completed)
        twenty_mins_ago = now - datetime.timedelta(minutes=20)
        cursor.execute("""
            UPDATE tournaments
            SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'LIVE' 
              AND is_manually_completed = 0 
              AND start_time <= %s;
        """, (twenty_mins_ago,))

# --------------------------------------------------------------------------
# CATEGORIES & SUBCATEGORIES
# --------------------------------------------------------------------------
def list_categories(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_active = 1" if only_active else ""
        cursor.execute(f"""
            SELECT id, name, slug, description, image_url, display_order, is_active, created_at
            FROM tournament_categories
            {where}
            ORDER BY display_order ASC, id ASC;
        """)
        cats = [dict(r) for r in cursor.fetchall()]
        
        for c in cats:
            cursor.execute("""
                SELECT id, category_id, name, slug, description, image_url, display_order, is_active
                FROM tournament_subcategories
                WHERE category_id = %s AND (is_active = 1 OR %s = 0)
                ORDER BY display_order ASC, id ASC;
            """, (c["id"], 1 if only_active else 0))
            c["subcategories"] = [dict(s) for s in cursor.fetchall()]
        return cats

def get_category_by_id(cat_id: int) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournament_categories WHERE id = %s;", (cat_id,))
        r = cursor.fetchone()
        return dict(r) if r else None

def create_category(name: str, slug: str, description: str = None, image_url: str = None, display_order: int = 0) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tournament_categories (name, slug, description, image_url, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            RETURNING id, name, slug, description, image_url, display_order, is_active, created_at;
        """, (name.strip(), slug.strip().lower(), description, image_url, display_order))
        return dict(cursor.fetchone())

def update_category(cat_id: int, name: str, slug: str, description: str = None, image_url: str = None, display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournament_categories
            SET name = %s, slug = %s, description = %s, image_url = %s, display_order = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, name, slug, description, image_url, display_order, is_active, created_at;
        """, (name.strip(), slug.strip().lower(), description, image_url, display_order, is_active, cat_id))
        return dict(cursor.fetchone())

def delete_category(cat_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tournament_categories WHERE id = %s;", (cat_id,))
    return True

def create_subcategory(category_id: int, name: str, slug: str, description: str = None, image_url: str = None, display_order: int = 0) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tournament_subcategories (category_id, name, slug, description, image_url, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            RETURNING id, category_id, name, slug, description, image_url, display_order, is_active, created_at;
        """, (category_id, name.strip(), slug.strip().lower(), description, image_url, display_order))
        return dict(cursor.fetchone())

def update_subcategory(sub_id: int, name: str, slug: str, description: str = None, image_url: str = None, display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournament_subcategories
            SET name = %s, slug = %s, description = %s, image_url = %s, display_order = %s, is_active = %s
            WHERE id = %s
            RETURNING id, category_id, name, slug, description, image_url, display_order, is_active;
        """, (name.strip(), slug.strip().lower(), description, image_url, display_order, is_active, sub_id))
        return dict(cursor.fetchone())

def delete_subcategory(sub_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tournament_subcategories WHERE id = %s;", (sub_id,))
    return True

# --------------------------------------------------------------------------
# ALLOWED WEAPONS / GUNS (GUNS ONLY CUSTOM)
# --------------------------------------------------------------------------
def list_guns(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_active = 1" if only_active else ""
        cursor.execute(f"""
            SELECT id, name, code, image_url, display_order, is_active, created_at
            FROM tournament_guns
            {where}
            ORDER BY display_order ASC, id ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

def create_gun(name: str, code: str, image_url: str = None, display_order: int = 0) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tournament_guns (name, code, image_url, display_order, is_active)
            VALUES (%s, %s, %s, %s, 1)
            RETURNING id, name, code, image_url, display_order, is_active, created_at;
        """, (name.strip(), code.strip().upper(), image_url, display_order))
        return dict(cursor.fetchone())

def update_gun(gun_id: int, name: str, code: str, image_url: str = None, display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournament_guns
            SET name = %s, code = %s, image_url = %s, display_order = %s, is_active = %s
            WHERE id = %s
            RETURNING id, name, code, image_url, display_order, is_active;
        """, (name.strip(), code.strip().upper(), image_url, display_order, is_active, gun_id))
        return dict(cursor.fetchone())

def delete_gun(gun_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tournament_guns WHERE id = %s;", (gun_id,))
    return True

# --------------------------------------------------------------------------
# TOURNAMENTS CORE CRUD & QUERIES
# --------------------------------------------------------------------------
def list_tournaments(
    status_filter: str = None,
    category_slug: str = None,
    subcategory_slug: str = None,
    entry_type: str = None,
    search_query: str = None,
    user_id: int = None,
    joined_only: bool = False,
    is_published_only: bool = True,
    limit: int = 50,
    offset: int = 0
) -> list[dict]:
    check_and_update_tournament_statuses()
    
    with get_db() as conn:
        cursor = conn.cursor()
        base_where = "WHERE 1=1"
        params = []
        
        if is_published_only:
            base_where += " AND t.is_published = 1"
            
        if status_filter and status_filter.strip().upper() not in ("ALL", ""):
            base_where += " AND t.status = %s"
            params.append(status_filter.strip().upper())
            
        if category_slug and category_slug.strip().lower() not in ("all", ""):
            base_where += " AND LOWER(c.slug) = %s"
            params.append(category_slug.strip().lower())
            
        if subcategory_slug and subcategory_slug.strip().lower() not in ("all", ""):
            base_where += " AND LOWER(s.slug) = %s"
            params.append(subcategory_slug.strip().lower())
            
        if entry_type and entry_type.strip().upper() not in ("ALL", ""):
            base_where += " AND t.entry_type = %s"
            params.append(entry_type.strip().upper())
            
        if search_query and search_query.strip():
            term = f"%{search_query.strip().lower()}%"
            base_where += " AND (LOWER(t.title) LIKE %s OR LOWER(COALESCE(t.map_name, '')) LIKE %s OR LOWER(COALESCE(t.allowed_weapon, '')) LIKE %s)"
            params.extend([term, term, term])
            
        if joined_only and user_id:
            base_where += " AND EXISTS (SELECT 1 FROM tournament_participants tp WHERE tp.tournament_id = t.id AND tp.user_id = %s)"
            params.append(user_id)
            
        query = f"""
            SELECT t.*,
                   c.name AS category_name, c.slug AS category_slug,
                   s.name AS subcategory_name, s.slug AS subcategory_slug,
                   g.name AS allowed_gun_name, g.code AS allowed_gun_code,
                   (CASE WHEN %s IS NOT NULL AND EXISTS(
                       SELECT 1 FROM tournament_participants tp WHERE tp.tournament_id = t.id AND tp.user_id = %s
                   ) THEN 1 ELSE 0 END) AS is_user_joined,
                   (CASE WHEN %s IS NOT NULL AND EXISTS(
                       SELECT 1 FROM tournament_favorites tf WHERE tf.tournament_id = t.id AND tf.user_id = %s
                   ) THEN 1 ELSE 0 END) AS is_favorited
            FROM tournaments t
            LEFT JOIN tournament_categories c ON t.category_id = c.id
            LEFT JOIN tournament_subcategories s ON t.subcategory_id = s.id
            LEFT JOIN tournament_guns g ON t.allowed_gun_id = g.id
            {base_where}
            ORDER BY 
              CASE WHEN t.status = 'LIVE' THEN 1
                   WHEN t.status = 'UPCOMING' THEN 2
                   ELSE 3 END,
              t.start_time ASC
            LIMIT %s OFFSET %s;
        """
        fetch_params = [user_id, user_id, user_id, user_id] + params + [limit, offset]
        cursor.execute(query, tuple(fetch_params))
        results = []
        for r in cursor.fetchall():
            d = _format_tournament_row(r)
            if not d.get("allowed_weapon") and d.get("allowed_gun_name"):
                d["allowed_weapon"] = d["allowed_gun_name"]
            results.append(d)
        return results

def get_tournament_by_id(tournament_id: int, user_id: int = None) -> dict:
    check_and_update_tournament_statuses()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*,
                   c.name AS category_name, c.slug AS category_slug,
                   s.name AS subcategory_name, s.slug AS subcategory_slug,
                   g.name AS allowed_gun_name, g.code AS allowed_gun_code,
                   (CASE WHEN %s IS NOT NULL AND EXISTS(
                       SELECT 1 FROM tournament_participants tp WHERE tp.tournament_id = t.id AND tp.user_id = %s
                   ) THEN 1 ELSE 0 END) AS is_user_joined,
                   (CASE WHEN %s IS NOT NULL AND EXISTS(
                       SELECT 1 FROM tournament_favorites tf WHERE tf.tournament_id = t.id AND tf.user_id = %s
                   ) THEN 1 ELSE 0 END) AS is_favorited
            FROM tournaments t
            LEFT JOIN tournament_categories c ON t.category_id = c.id
            LEFT JOIN tournament_subcategories s ON t.subcategory_id = s.id
            LEFT JOIN tournament_guns g ON t.allowed_gun_id = g.id
            WHERE t.id = %s;
        """, (user_id, user_id, user_id, user_id, tournament_id))
        row = cursor.fetchone()
        if not row:
            return None
        d = _format_tournament_row(row)
        if not d.get("allowed_weapon") and d.get("allowed_gun_name"):
            d["allowed_weapon"] = d["allowed_gun_name"]
            
        # Hide room credentials if user has not joined OR not authorized/configured
        # Room credentials visible if tournament is LIVE or within 15 mins of start
        is_joined = bool(d.get("is_user_joined", 0))
        now = datetime.datetime.utcnow()
        st_val = row["start_time"] if isinstance(row["start_time"], datetime.datetime) else now
        mins_until = (st_val - now).total_seconds() / 60.0
        
        # Room credentials exposed only if user is joined AND (status == 'LIVE' or status == 'COMPLETED' or mins_until <= 15)
        if not (is_joined and (d["status"] in ("LIVE", "COMPLETED") or mins_until <= 15)):
            d["room_id"] = None
            d["room_password"] = None
            
        return d

def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text)

def create_tournament(data_dict: dict = None, **kwargs) -> dict:
    import secrets
    data = {}
    if data_dict and isinstance(data_dict, dict):
        data.update(data_dict)
    data.update(kwargs)

    title = data.get("title", "Free Fire Tournament").strip()
    entry_type = data.get("entry_type", "DIAMONDS").strip().upper()
    entry_fee_diamonds = int(data.get("entry_fee_diamonds", 0) or 0)
    if entry_type == "DIAMONDS" and entry_fee_diamonds <= 0:
        raise ValueError("Diamond tournaments must have entry_fee_diamonds > 0")
    slug = data.get("slug")
    if not slug:
        slug = f"{slugify(title)}-{secrets.token_hex(3)}"

    start_time = data.get("start_time")
    if not start_time:
        start_time = datetime.datetime.utcnow() + datetime.timedelta(hours=2)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tournaments (
                title, slug, banner_url, description, game, mode, format,
                category_id, subcategory_id, allowed_gun_id, allowed_weapon,
                entry_type, entry_fee_diamonds, prize_type, prize_amount_diamonds,
                per_kill_diamonds, prize_distribution, max_slots, rules, map_name,
                room_id, room_password, room_instructions, start_time, status,
                is_registration_open, is_featured, is_published
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            ) RETURNING id, title, slug, status;
        """, (
            title, slug, data.get("banner_url"), data.get("description"),
            data.get("game", "FREE_FIRE"), data.get("mode", "SOLO"), data.get("format", "BATTLE_ROYALE"),
            data.get("category_id"), data.get("subcategory_id"), data.get("allowed_gun_id"), data.get("allowed_weapon"),
            data.get("entry_type", "DIAMONDS"), data.get("entry_fee_diamonds", 0),
            data.get("prize_type", "DIAMONDS"), data.get("prize_amount_diamonds", 0),
            data.get("per_kill_diamonds", 0),
            data.get("prize_distribution"), data.get("max_slots", 48), data.get("rules"),
            data.get("map_name", "BERMUDA"), data.get("room_id"), data.get("room_password"),
            data.get("room_instructions"), start_time, data.get("status", "UPCOMING"),
            data.get("is_registration_open", 1), data.get("is_featured", 0), data.get("is_published", 1)
        ))
        res = cursor.fetchone()
        t_id = res["id"] if isinstance(res, dict) else res[0]
    return get_tournament_by_id(t_id)

def update_tournament(tournament_id: int, data_dict: dict = None, **kwargs) -> dict:
    data = {}
    if data_dict and isinstance(data_dict, dict):
        data.update(data_dict)
    data.update(kwargs)

    curr = get_tournament_by_id(tournament_id)
    if not curr:
        raise ValueError("Tournament not found")

    title = data.get("title", curr.get("title"))
    slug = data.get("slug", curr.get("slug"))
    start_time = data.get("start_time", curr.get("start_time"))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournaments SET
                title = %s, slug = %s, banner_url = %s, description = %s,
                game = %s, mode = %s, format = %s,
                category_id = %s, subcategory_id = %s, allowed_gun_id = %s, allowed_weapon = %s,
                entry_type = %s, entry_fee_diamonds = %s,
                prize_type = %s, prize_amount_diamonds = %s, per_kill_diamonds = %s,
                prize_distribution = %s, max_slots = %s, rules = %s, map_name = %s,
                room_id = %s, room_password = %s, room_instructions = %s,
                start_time = %s, status = %s,
                is_registration_open = %s, is_featured = %s, is_published = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (
            title, slug, data.get("banner_url", curr.get("banner_url")), data.get("description", curr.get("description")),
            data.get("game", curr.get("game", "FREE_FIRE")), data.get("mode", curr.get("mode", "SOLO")), data.get("format", curr.get("format", "BATTLE_ROYALE")),
            data.get("category_id", curr.get("category_id")), data.get("subcategory_id", curr.get("subcategory_id")), data.get("allowed_gun_id", curr.get("allowed_gun_id")), data.get("allowed_weapon", curr.get("allowed_weapon")),
            data.get("entry_type", curr.get("entry_type", "DIAMONDS")), data.get("entry_fee_diamonds", curr.get("entry_fee_diamonds", 0)),
            data.get("prize_type", curr.get("prize_type", "DIAMONDS")), data.get("prize_amount_diamonds", curr.get("prize_amount_diamonds", 0)),
            data.get("per_kill_diamonds", curr.get("per_kill_diamonds", 0)),
            data.get("prize_distribution", curr.get("prize_distribution")), data.get("max_slots", curr.get("max_slots", 48)), data.get("rules", curr.get("rules")),
            data.get("map_name", curr.get("map_name", "BERMUDA")), data.get("room_id", curr.get("room_id")), data.get("room_password", curr.get("room_password")),
            data.get("room_instructions", curr.get("room_instructions")), start_time, data.get("status", curr.get("status", "UPCOMING")),
            data.get("is_registration_open", curr.get("is_registration_open", 1)), data.get("is_featured", curr.get("is_featured", 0)), data.get("is_published", curr.get("is_published", 1)),
            tournament_id
        ))
    return get_tournament_by_id(tournament_id)

def mark_tournament_completed_early(tournament_id: int, admin_id: int = None) -> bool:
    """Manual early completion by Admin. Sets is_manually_completed to 1 to lock status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET status = 'COMPLETED', is_manually_completed = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (tournament_id,))
    return True

# --------------------------------------------------------------------------
# JOIN & PARTICIPANT CREDENTIAL EDITING
# --------------------------------------------------------------------------
def join_tournament(tournament_id: int, user_id: int, ff_uid: str, ff_ign: str) -> dict:
    from app.services import wallet as wallet_service
    ff_uid = ff_uid.strip() if ff_uid else ""
    ff_ign = ff_ign.strip() if ff_ign else ""
    if not ff_uid or not ff_ign:
        raise ValueError("Valid Free Fire UID and IGN are required to join.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE id = %s FOR UPDATE;", (tournament_id,))
        t = cursor.fetchone()
        if not t:
            raise ValueError("Tournament not found")
        t_dict = dict(t)

        if t_dict["status"] != "UPCOMING":
            raise ValueError(f"Registration closed. Tournament status is {t_dict['status']}.")
        if not t_dict["is_registration_open"]:
            raise ValueError("Registration for this tournament is closed.")
        if t_dict["joined_players"] >= t_dict["max_slots"]:
            raise ValueError("Tournament is full. All slots are booked.")

        # Check already joined
        cursor.execute("SELECT 1 FROM tournament_participants WHERE tournament_id = %s AND user_id = %s;", (tournament_id, user_id))
        if cursor.fetchone():
            raise ValueError("You have already joined this tournament.")

        fee = t_dict["entry_fee_diamonds"]
        if fee > 0:
            wallet_service.deduct_diamonds(
                user_id=user_id,
                amount=fee,
                tx_type="TOURNAMENT_ENTRY",
                reference_id=f"TOURN-{tournament_id}",
                description=f"Entry fee for {t_dict['title']}"
            )

        slot = t_dict["joined_players"] + 1
        cursor.execute("""
            INSERT INTO tournament_participants (
                tournament_id, user_id, slot_number, ff_uid, ff_ign, payment_status, diamonds_paid
            ) VALUES (%s, %s, %s, %s, %s, 'PAID', %s)
            RETURNING id, slot_number, joined_at;
        """, (tournament_id, user_id, slot, ff_uid, ff_ign, fee))
        part = dict(cursor.fetchone())

        cursor.execute("""
            UPDATE tournaments
            SET joined_players = joined_players + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (tournament_id,))

        # Update user profile total matches
        cursor.execute("""
            UPDATE user_profiles
            SET total_matches = total_matches + 1, ff_uid = %s, ff_ign = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (ff_uid, ff_ign, user_id))

        # Dispatch Smart Notification
        from app.services import content_features
        content_features.send_smart_notification(
            user_id=user_id,
            title="Tournament Joined!",
            message=f"You successfully booked Slot #{slot} in {t_dict['title']}. Room ID will be available before start.",
            notif_type="TOURNAMENT_JOINED",
            action_url=f"/tournaments/{tournament_id}"
        )

    return {"success": True, "message": f"Joined successfully! Your slot is #{slot}.", "slot_number": slot}

def update_participant_credentials(tournament_id: int, user_id: int, ff_uid: str, ff_ign: str) -> dict:
    """
    Allows player to edit Free Fire UID/IGN ONLY before the tournament starts.
    Once LIVE, editing is strictly locked.
    """
    check_and_update_tournament_statuses()
    ff_uid = ff_uid.strip() if ff_uid else ""
    ff_ign = ff_ign.strip() if ff_ign else ""
    if not ff_uid or not ff_ign:
        raise ValueError("Free Fire UID and IGN cannot be empty")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, start_time FROM tournaments WHERE id = %s;", (tournament_id,))
        t = cursor.fetchone()
        if not t:
            raise ValueError("Tournament not found")
        t_dict = dict(t)
        
        now = datetime.datetime.utcnow()
        st_val = t_dict.get("start_time")
        if isinstance(st_val, str):
            try:
                st_val = datetime.datetime.fromisoformat(st_val.replace('Z', '+00:00'))
                if st_val.tzinfo:
                    st_val = st_val.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            except Exception:
                st_val = now + datetime.timedelta(hours=1)
        elif not isinstance(st_val, datetime.datetime):
            st_val = now + datetime.timedelta(hours=1)
        
        if t_dict["status"] != "UPCOMING" or now >= st_val:
            raise ValueError("Tournament is already LIVE or concluded. Free Fire credentials are locked and cannot be edited.")

        cursor.execute("""
            UPDATE tournament_participants
            SET ff_uid = %s, ff_ign = %s
            WHERE tournament_id = %s AND user_id = %s
            RETURNING id, slot_number, ff_uid, ff_ign;
        """, (ff_uid, ff_ign, tournament_id, user_id))
        row = cursor.fetchone()
        if not row:
            raise ValueError("You have not joined this tournament")

        # Sync with user profile
        cursor.execute("UPDATE user_profiles SET ff_uid = %s, ff_ign = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s;", (ff_uid, ff_ign, user_id))

    return {"success": True, "message": "Credentials updated successfully!", "participant": dict(row)}

def list_tournament_participants(tournament_id: int) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.tournament_id, p.user_id, p.slot_number, p.ff_uid, p.ff_ign,
                   p.payment_status, p.diamonds_paid, p.joined_at,
                   u.username, COALESCE(pr.display_name, u.username) AS display_name,
                   COALESCE(pr.avatar_url, '/static/images/default-avatar.png') AS avatar_url,
                   COALESCE(pr.rank_tier, 'Bronze') AS rank_tier,
                   pr.total_matches, pr.wins, pr.kills
            FROM tournament_participants p
            JOIN app_users u ON p.user_id = u.id
            LEFT JOIN user_profiles pr ON u.id = pr.user_id
            WHERE p.tournament_id = %s
            ORDER BY p.slot_number ASC;
        """, (tournament_id,))
        return [_format_tournament_row(r) for r in cursor.fetchall()]

# --------------------------------------------------------------------------
# RESULTS ENTRY & PRIZE CREDIT
# --------------------------------------------------------------------------
def enter_tournament_results(tournament_id: int, results: list[dict], proof_url: str = None, admin_id: int = None) -> dict:
    from app.services import wallet as wallet_service
    from app.services import content_features
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE id = %s FOR UPDATE;", (tournament_id,))
        t = cursor.fetchone()
        if not t:
            raise ValueError("Tournament not found")
        t_dict = dict(t)
        per_kill_rate = t_dict.get("per_kill_diamonds", 0) or 0

        # Create or fetch match record
        cursor.execute("SELECT id FROM matches WHERE tournament_id = %s LIMIT 1;", (tournament_id,))
        m = cursor.fetchone()
        if m:
            match_id = m["id"] if isinstance(m, dict) else m[0]
        else:
            cursor.execute("""
                INSERT INTO matches (tournament_id, match_number, title, status, completed_at)
                VALUES (%s, 1, 'Final Round', 'COMPLETED', CURRENT_TIMESTAMP)
                RETURNING id;
            """, (tournament_id,))
            match_id = cursor.fetchone()["id"]

        # Process each result
        awarded_total = 0
        for res in results:
            user_id = res["user_id"]
            placement = res.get("placement", 0)
            kills = res.get("kills", 0)
            placement_prize = res.get("placement_prize_diamonds", 0)
            kill_reward = kills * per_kill_rate
            total_diamonds = placement_prize + kill_reward
            awarded_total += total_diamonds

            cursor.execute("""
                INSERT INTO match_results (
                    match_id, tournament_id, user_id, ff_uid, ff_ign,
                    placement, kills, diamonds_awarded, is_verified, admin_verified_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                ON CONFLICT (match_id, user_id) DO UPDATE SET
                    placement = EXCLUDED.placement,
                    kills = EXCLUDED.kills,
                    diamonds_awarded = EXCLUDED.diamonds_awarded,
                    is_verified = 1;
            """, (match_id, tournament_id, user_id, res.get("ff_uid", ""), res.get("ff_ign", ""), placement, kills, total_diamonds, admin_id))

            # Update player profile stats
            is_win = 1 if placement == 1 else 0
            cursor.execute("""
                UPDATE user_profiles
                SET wins = wins + %s, kills = kills + %s, points = points + %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (is_win, kills, (50 if is_win else 10) + (kills * 2), user_id))

            # Credit diamonds if any won
            if total_diamonds > 0:
                wallet_service.credit_diamonds(
                    user_id=user_id,
                    amount=total_diamonds,
                    tx_type="PRIZE_PAYOUT",
                    reference_id=f"TOURN-{tournament_id}-RANK{placement}",
                    admin_id=admin_id,
                    description=f"Prize reward for {t_dict['title']} (Rank #{placement}, {kills} kills)"
                )
                
            # Notify player
            content_features.send_smart_notification(
                user_id=user_id,
                title="Tournament Results Published!",
                message=f"Results out for {t_dict['title']}! You achieved Rank #{placement} with {kills} eliminations (Reward: 💎 {total_diamonds}).",
                notif_type="RESULT_PUBLISHED",
                action_url=f"/tournaments/{tournament_id}"
            )

        # Mark tournament as completed
        cursor.execute("""
            UPDATE tournaments
            SET status = 'COMPLETED', is_manually_completed = 1, match_proof_url = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (proof_url, tournament_id))

    return {"success": True, "message": f"Results published and 💎 {awarded_total} diamonds awarded!"}

def get_tournament_results(tournament_id: int) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.username, COALESCE(pr.display_name, u.username) AS display_name,
                   COALESCE(pr.avatar_url, '/static/images/default-avatar.png') AS avatar_url
            FROM match_results r
            JOIN app_users u ON r.user_id = u.id
            LEFT JOIN user_profiles pr ON u.id = pr.user_id
            WHERE r.tournament_id = %s
            ORDER BY r.placement ASC;
        """, (tournament_id,))
        return [dict(r) for r in cursor.fetchall()]

# --------------------------------------------------------------------------
# FAVORITES & DISPUTES
# --------------------------------------------------------------------------
def toggle_favorite(user_id: int, tournament_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tournament_favorites WHERE user_id = %s AND tournament_id = %s;", (user_id, tournament_id))
        if cursor.fetchone():
            cursor.execute("DELETE FROM tournament_favorites WHERE user_id = %s AND tournament_id = %s;", (user_id, tournament_id))
            return False
        else:
            cursor.execute("INSERT INTO tournament_favorites (user_id, tournament_id) VALUES (%s, %s);", (user_id, tournament_id))
            return True

def list_user_favorites(user_id: int) -> list[dict]:
    check_and_update_tournament_statuses()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, c.name AS category_name, s.name AS subcategory_name, 1 AS is_favorited
            FROM tournament_favorites f
            JOIN tournaments t ON f.tournament_id = t.id
            LEFT JOIN tournament_categories c ON t.category_id = c.id
            LEFT JOIN tournament_subcategories s ON t.subcategory_id = s.id
            WHERE f.user_id = %s AND t.is_published = 1
            ORDER BY t.start_time ASC;
        """, (user_id,))
        return [_format_tournament_row(r) for r in cursor.fetchall()]

def create_tournament_dispute(tournament_id: int, user_id: int, dispute_type: str, description: str, proof_url: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tournament_disputes (tournament_id, user_id, dispute_type, description, proof_url, status)
            VALUES (%s, %s, %s, %s, %s, 'PENDING')
            RETURNING id, tournament_id, user_id, dispute_type, description, status, created_at;
        """, (tournament_id, user_id, dispute_type.strip(), description.strip(), proof_url))
        return dict(cursor.fetchone())

def list_tournament_disputes(status_filter: str = None, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE 1=1"
        params = []
        if status_filter and status_filter.upper() not in ("ALL", ""):
            where += " AND d.status = %s"
            params.append(status_filter.upper())
        query = f"""
            SELECT d.*, u.username, u.email, t.title AS tournament_title
            FROM tournament_disputes d
            JOIN app_users u ON d.user_id = u.id
            JOIN tournaments t ON d.tournament_id = t.id
            {where}
            ORDER BY d.id DESC LIMIT %s OFFSET %s;
        """
        cursor.execute(query, tuple(params + [limit, offset]))
        return [dict(r) for r in cursor.fetchall()]

def resolve_tournament_dispute(dispute_id: int, admin_id: int, status: str, admin_response: str = None) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournament_disputes
            SET status = %s, admin_response = %s, resolved_by_admin_id = %s, resolved_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (status.upper(), admin_response, admin_id, dispute_id))
    return True

def get_tournament_room_credentials(tournament_id: int, user_id: int) -> dict:
    t = get_tournament_by_id(tournament_id, user_id=user_id)
    if not t:
        raise ValueError("Tournament not found")
    if not t.get("is_user_joined", 0):
        raise ValueError("You must join the tournament to view room credentials")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT room_id, room_password, room_instructions FROM tournaments WHERE id = %s;", (tournament_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tournament not found")
        d = dict(row)
        if not d.get("room_id") or not d.get("room_password"):
            raise ValueError("Room credentials have not been released by the admin yet.")
        return d

def update_tournament_room_credentials(tournament_id: int, room_id: str, room_password: str, room_instructions: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tournaments
            SET room_id = %s, room_password = %s, room_instructions = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, room_id, room_password, room_instructions;
        """, (room_id.strip(), room_password.strip(), room_instructions, tournament_id))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Tournament not found")
        
        cursor.execute("SELECT user_id FROM tournament_participants WHERE tournament_id = %s;", (tournament_id,))
        for p in cursor.fetchall():
            u_id = p["user_id"] if isinstance(p, dict) else p[0]
            try:
                from app.services import content_features
                content_features.send_smart_notification(
                    user_id=u_id,
                    title="Room ID & Password Available!",
                    message=f"Room ID: {room_id} | Password: {room_password}. Be ready before match starts!",
                    notif_type="ROOM_CREDENTIALS",
                    action_url=f"/tournaments/{tournament_id}"
                )
            except Exception:
                pass
        return dict(row)
