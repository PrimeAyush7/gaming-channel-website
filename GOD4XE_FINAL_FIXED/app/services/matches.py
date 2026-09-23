import csv
import io
import datetime
from app.database import get_db
from app.services.wallet import credit_diamonds

def get_tournament_matches(tournament_id: int) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM matches WHERE tournament_id = %s ORDER BY match_number ASC;
        """, (tournament_id,))
        return [dict(r) for r in cursor.fetchall()]

def get_match_results(match_id: int) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.username, p.avatar_url
            FROM match_results r
            JOIN app_users u ON r.user_id = u.id
            JOIN user_profiles p ON r.user_id = p.user_id
            WHERE r.match_id = %s
            ORDER BY r.placement ASC, r.points DESC;
        """, (match_id,))
        return [dict(r) for r in cursor.fetchall()]

def submit_match_results(match_id: int, tournament_id: int, results: list[dict], admin_id: int) -> dict:
    if not results:
        raise ValueError("Results list cannot be empty")

    with get_db() as conn:
        cursor = conn.cursor()
        for item in results:
            user_id = item["user_id"]
            ff_uid = item.get("ff_uid", "")
            ff_ign = item.get("ff_ign", "")
            placement = int(item["placement"])
            kills = int(item.get("kills", 0))
            points = int(item.get("points", 0))
            diamonds_awarded = int(item.get("diamonds_awarded", 0))

            cursor.execute("""
                INSERT INTO match_results (
                    match_id, tournament_id, user_id, ff_uid, ff_ign,
                    placement, kills, points, diamonds_awarded, is_verified, admin_verified_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                ON CONFLICT (match_id, user_id) DO UPDATE SET
                    placement = EXCLUDED.placement,
                    kills = EXCLUDED.kills,
                    points = EXCLUDED.points,
                    diamonds_awarded = EXCLUDED.diamonds_awarded,
                    is_verified = 1,
                    admin_verified_by = EXCLUDED.admin_verified_by;
            """, (match_id, tournament_id, user_id, ff_uid, ff_ign, placement, kills, points, diamonds_awarded, admin_id))

            is_win = 1 if placement == 1 else 0
            cursor.execute("""
                UPDATE user_profiles
                SET total_matches = total_matches + 1,
                    wins = wins + %s,
                    losses = losses + (1 - %s),
                    kills = kills + %s,
                    points = points + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (is_win, is_win, kills, points, user_id))

            if diamonds_awarded > 0:
                credit_diamonds(
                    user_id=user_id,
                    amount=diamonds_awarded,
                    tx_type="TOURNAMENT_REWARD",
                    reference_id=f"TOURN-{tournament_id}-M{match_id}",
                    admin_id=admin_id,
                    description=f"Reward for Rank #{placement} ({kills} kills)"
                )

        cursor.execute("""
            UPDATE matches
            SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (match_id,))

        cursor.execute("""
            UPDATE tournaments
            SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (tournament_id,))

    return {"success": True, "match_id": match_id, "processed_players": len(results)}

def get_user_match_history(user_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.placement, r.kills, r.points, r.diamonds_awarded, r.created_at,
                   t.id AS tournament_id, t.title AS tournament_title, t.mode, t.map_name,
                   m.id AS match_id, m.match_number
            FROM match_results r
            JOIN tournaments t ON r.tournament_id = t.id
            JOIN matches m ON r.match_id = m.id
            WHERE r.user_id = %s
            ORDER BY r.created_at DESC LIMIT %s OFFSET %s;
        """, (user_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]
