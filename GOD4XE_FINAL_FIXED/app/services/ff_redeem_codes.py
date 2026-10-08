import re
import datetime
from app.database import get_db

CODE_REGEX = re.compile(r'[A-Za-z0-9]{4}-?[A-Za-z0-9]{4}-?[A-Za-z0-9]{4}(?:-?[A-Za-z0-9]{4})?')

def format_code(raw: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]', '', raw).upper()
    if len(cleaned) == 12:
        return f"{cleaned[:4]}-{cleaned[4:8]}-{cleaned[8:12]}"
    elif len(cleaned) == 16:
        return f"{cleaned[:4]}-{cleaned[4:8]}-{cleaned[8:12]}-{cleaned[12:16]}"
    return cleaned

def get_active_codes(limit: int = 30) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, reward_desc, server_region, release_date, expires_at, is_active, copy_count, created_at
            FROM ff_daily_redeem_codes
            WHERE is_active = 1
            ORDER BY id DESC
            LIMIT %s;
        """, (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("release_date"), (datetime.date, datetime.datetime)):
                d["release_date"] = str(d["release_date"])
            if isinstance(d.get("created_at"), (datetime.date, datetime.datetime)):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result

def get_all_codes_admin(limit: int = 100) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, reward_desc, server_region, release_date, expires_at, is_active, copy_count, created_at
            FROM ff_daily_redeem_codes
            ORDER BY id DESC
            LIMIT %s;
        """, (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("release_date"), (datetime.date, datetime.datetime)):
                d["release_date"] = str(d["release_date"])
            if isinstance(d.get("created_at"), (datetime.date, datetime.datetime)):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result

def increment_copy_count(code_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE ff_daily_redeem_codes SET copy_count = copy_count + 1 WHERE id = %s;", (code_id,))

def add_code(code: str, reward_desc: str = None, server_region: str = None) -> tuple[bool, str]:
    c_fmt = format_code(code)
    if not c_fmt:
        return False, "Invalid Code Format"
    r_desc = (reward_desc or "Exclusive In-Game Weapon / Voucher").strip()
    s_region = (server_region or "India & Global").strip()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ff_daily_redeem_codes (code, reward_desc, server_region, release_date, is_active)
            VALUES (%s, %s, %s, CURRENT_DATE, 1)
            ON CONFLICT (code) DO UPDATE SET
                reward_desc = EXCLUDED.reward_desc,
                server_region = EXCLUDED.server_region,
                is_active = 1,
                release_date = CURRENT_DATE;
        """, (c_fmt, r_desc, s_region))
        return True, "Code Added/Updated Successfully"

def bulk_import_codes(raw_text: str, default_server: str = "India & Global", default_reward: str = "Exclusive In-Game Weapon / Voucher") -> int:
    if not raw_text:
        return 0
    
    matches = CODE_REGEX.findall(raw_text)
    imported = 0
    with get_db() as conn:
        cursor = conn.cursor()
        for raw_m in matches:
            c = format_code(raw_m)
            if len(c) in (14, 19): # 12 + 2 hyphens or 16 + 3 hyphens
                cursor.execute("""
                    INSERT INTO ff_daily_redeem_codes (code, reward_desc, server_region, release_date, is_active)
                    VALUES (%s, %s, %s, CURRENT_DATE, 1)
                    ON CONFLICT (code) DO UPDATE SET
                        is_active = 1,
                        release_date = CURRENT_DATE;
                """, (c, default_reward, default_server))
                imported += 1
    return imported

def delete_code(code_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ff_daily_redeem_codes WHERE id = %s;", (code_id,))

def toggle_code_active(code_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE ff_daily_redeem_codes SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = %s;", (code_id,))
