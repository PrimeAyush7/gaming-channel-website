import os
from app.database import get_db
from app.config import GOOGLE_CLIENT_ID

def _get_env_google_client_id() -> str:
    return (
        os.getenv("GOOGLE_CLIENT_ID", "").strip()
        or os.getenv("google_client_id", "").strip()
        or (GOOGLE_CLIENT_ID or "").strip()
    )

def get_all_settings() -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings;")
        rows = cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}
        
        env_id = _get_env_google_client_id()
        if (not settings.get("google_client_id") or not str(settings.get("google_client_id")).strip()) and env_id:
            settings["google_client_id"] = env_id
        return settings

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM site_settings WHERE key = %s;", (key,))
        row = cursor.fetchone()
        val = row["value"] if row and row["value"] is not None else ""
        if key == "google_client_id" and (not val or not str(val).strip()):
            env_id = _get_env_google_client_id()
            if env_id:
                return env_id
        return val if val else default

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
