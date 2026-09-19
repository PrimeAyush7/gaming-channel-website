from app.database import get_db

def get_ad_settings():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ad_settings WHERE id = 1;")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT OR IGNORE INTO ad_settings (id, is_enabled, client_id, custom_ads_txt)
                VALUES (1, 0, '', '# Google AdSense ads.txt configuration\n# google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0');
            """)
            cursor.execute("SELECT * FROM ad_settings WHERE id = 1;")
            row = cursor.fetchone()
        return dict(row)

def update_ad_settings(data: dict):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ad_settings SET
                is_enabled = ?,
                client_id = ?,
                slot_home_top = ?,
                slot_home_bottom = ?,
                slot_post_top = ?,
                slot_post_bottom = ?,
                slot_sidebar = ?,
                custom_ads_txt = ?
            WHERE id = 1;
        """, (
            1 if data.get("is_enabled") else 0,
            (data.get("client_id") or "").strip(),
            (data.get("slot_home_top") or "").strip(),
            (data.get("slot_home_bottom") or "").strip(),
            (data.get("slot_post_top") or "").strip(),
            (data.get("slot_post_bottom") or "").strip(),
            (data.get("slot_sidebar") or "").strip(),
            (data.get("custom_ads_txt") or "").strip()
        ))

def get_ads_txt_content() -> str:
    settings = get_ad_settings()
    custom = (settings.get("custom_ads_txt") or "").strip()
    client_id = (settings.get("client_id") or "").strip()
    
    if custom:
        return custom
    if client_id:
        # Extract pub-XXXX
        pub_id = client_id.replace("ca-", "")
        return f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n"
    return "# Google AdSense ads.txt placeholder\n# Configure in Admin -> AdSense Settings once approved.\n"
