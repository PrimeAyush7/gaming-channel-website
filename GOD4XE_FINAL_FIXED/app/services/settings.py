from app.database import get_db
from app.config import GOOGLE_CLIENT_ID

def get_all_settings() -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings;")
        rows = cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}
        if "google_client_id" not in settings and GOOGLE_CLIENT_ID:
            settings["google_client_id"] = GOOGLE_CLIENT_ID
        return settings

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM site_settings WHERE key = %s;", (key,))
        row = cursor.fetchone()
        if row and row["value"] is not None:
            return row["value"]
        if key == "google_client_id" and GOOGLE_CLIENT_ID:
            return GOOGLE_CLIENT_ID
        return default

def update_settings(data: dict):
    with get_db() as conn:
        cursor = conn.cursor()
        for key, value in data.items():
            if value is not None:
                cursor.execute("""
                    INSERT INTO site_settings (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value;
                """, (key, str(value).strip()))
