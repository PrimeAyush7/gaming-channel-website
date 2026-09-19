from app.database import get_db

def get_all_settings() -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings;")
        rows = cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}
        return settings

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM site_settings WHERE key = ?;", (key,))
        row = cursor.fetchone()
        return row["value"] if row and row["value"] is not None else default

def update_settings(data: dict):
    with get_db() as conn:
        cursor = conn.cursor()
        for key, value in data.items():
            if value is not None:
                cursor.execute("""
                    INSERT INTO site_settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """, (key, str(value).strip()))
