from app.database import get_db

def get_leaderboard(board_type: str = "MOST_WINNING", limit: int = 50) -> dict:
    board_type = board_type.upper().strip()
    if board_type not in ("MOST_WINNING", "MOST_KILLS", "MOST_PLAYING"):
        board_type = "MOST_WINNING"

    order_clause = {
        "MOST_WINNING": "p.wins DESC, p.points DESC, p.kills DESC",
        "MOST_KILLS": "p.kills DESC, p.points DESC, p.wins DESC",
        "MOST_PLAYING": "p.total_matches DESC, p.wins DESC, p.kills DESC"
    }[board_type]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT u.id AS user_id, u.username, p.avatar_url, p.ff_uid, p.ff_ign,
                   p.total_matches, p.wins, p.losses, p.kills, p.points, p.rank_tier
            FROM app_users u
            JOIN user_profiles p ON u.id = p.user_id
            WHERE u.is_active = 1 AND p.total_matches > 0
            ORDER BY {order_clause}
            LIMIT %s;
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]

    rankings = []
    for idx, row in enumerate(rows, start=1):
        tot = row.get("total_matches", 0) or 0
        wins = row.get("wins", 0) or 0
        win_rate = round((wins / tot) * 100, 1) if tot > 0 else 0.0
        row["rank"] = idx
        row["win_rate"] = win_rate
        rankings.append(row)

    return {
        "type": board_type,
        "count": len(rankings),
        "rankings": rankings
    }
