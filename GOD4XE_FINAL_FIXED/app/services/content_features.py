from app.config import UPLOAD_DIR, APP_DIR, BASE_DIR
from PIL import Image
from pathlib import Path
import io
import html
import uuid
import os
import datetime
from app.database import get_db

# --------------------------------------------------------------------------
# SMART NOTIFICATIONS
# --------------------------------------------------------------------------
def send_smart_notification(user_id: int, title: str, message: str, notif_type: str, action_url: str = None) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, action_url, is_read)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id, user_id, title, message, notification_type, action_url, is_read, created_at;
        """, (user_id, title, message, notif_type, action_url))
        row = cursor.fetchone()
        return dict(row) if row else None

# --------------------------------------------------------------------------
# LATEST UPDATES (HOME SCREEN)
# --------------------------------------------------------------------------
def list_latest_updates(only_published: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_published = 1" if only_published else ""
        cursor.execute(f"""
            SELECT id, heading, description, cover_image_url, youtube_video_url,
                   button_text, button_url, display_order, is_published, created_at
            FROM latest_updates
            {where}
            ORDER BY display_order ASC, id DESC;
        """)
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

def create_latest_update(heading: str, description: str, cover_image_url: str = None, youtube_video_url: str = None, button_text: str = None, button_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO latest_updates (heading, description, cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, heading, description, cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published, created_at;
        """, (heading.strip(), description.strip(), cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published))
        return dict(cursor.fetchone())

def update_latest_update(update_id: int, heading: str, description: str, cover_image_url: str = None, youtube_video_url: str = None, button_text: str = None, button_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE latest_updates
            SET heading = %s, description = %s, cover_image_url = %s, youtube_video_url = %s,
                button_text = %s, button_url = %s, display_order = %s, is_published = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, heading, description, cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published;
        """, (heading.strip(), description.strip(), cover_image_url, youtube_video_url, button_text, button_url, display_order, is_published, update_id))
        return dict(cursor.fetchone())

def delete_latest_update(update_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM latest_updates WHERE id = %s;", (update_id,))
    return True

# --------------------------------------------------------------------------
# ANNOUNCEMENTS & ARENA MARQUEE
# --------------------------------------------------------------------------
def list_announcements(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_active = 1" if only_active else ""
        cursor.execute(f"""
            SELECT id, title, message, banner_url, type, display_order, is_active, created_at
            FROM announcements
            {where}
            ORDER BY display_order ASC, id DESC;
        """)
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

def create_announcement(title: str, message: str, banner_url: str = None, type: str = 'INFO', display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO announcements (title, message, banner_url, type, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, title, message, banner_url, type, display_order, is_active, created_at;
        """, (title.strip(), message.strip(), banner_url, type, display_order, is_active))
        return dict(cursor.fetchone())

def update_announcement(announcement_id: int, title: str, message: str, banner_url: str = None, type: str = 'INFO', display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE announcements
            SET title = %s, message = %s, banner_url = %s, type = %s, display_order = %s, is_active = %s
            WHERE id = %s
            RETURNING id, title, message, banner_url, type, display_order, is_active;
        """, (title.strip(), message.strip(), banner_url, type, display_order, is_active, announcement_id))
        return dict(cursor.fetchone())

def delete_announcement(announcement_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM announcements WHERE id = %s;", (announcement_id,))
    return True

# --------------------------------------------------------------------------
# COMMUNITIES (SOCIAL LINKS)
# --------------------------------------------------------------------------
def list_communities(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_active = 1" if only_active else ""
        cursor.execute(f"""
            SELECT id, platform, name, url, logo_url, display_order, is_active, created_at
            FROM communities
            {where}
            ORDER BY display_order ASC, id ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

def update_community(comm_id: int, platform: str, name: str, url: str, logo_url: str = None, display_order: int = 0, is_active: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE communities
            SET platform = %s, name = %s, url = %s, logo_url = %s, display_order = %s, is_active = %s
            WHERE id = %s
            RETURNING id, platform, name, url, logo_url, display_order, is_active;
        """, (platform.strip(), name.strip(), url.strip(), logo_url, display_order, is_active, comm_id))
        return dict(cursor.fetchone())

def create_community(platform: str, name: str, url: str, logo_url: str = None, display_order: int = 0) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO communities (platform, name, url, logo_url, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            RETURNING id, platform, name, url, logo_url, display_order, is_active;
        """, (platform.strip(), name.strip(), url.strip(), logo_url, display_order))
        return dict(cursor.fetchone())

def delete_community(comm_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM communities WHERE id = %s;", (comm_id,))
    return True

# --------------------------------------------------------------------------
# TUTORIALS / HOW TO PLAY
# --------------------------------------------------------------------------
def list_tutorials(only_published: bool = True) -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        where = "WHERE is_published = 1" if only_published else ""
        cursor.execute(f"""
            SELECT id, title, slug, category, content, image_url, video_url, display_order, is_published, created_at
            FROM tutorials
            {where}
            ORDER BY display_order ASC, id ASC;
        """)
        results = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results

def get_tutorial_by_slug(slug: str) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tutorials WHERE slug = %s;", (slug.strip().lower(),))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        return d

def create_tutorial(title: str, slug: str, category: str, content: str, image_url: str = None, video_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tutorials (title, slug, category, content, image_url, video_url, display_order, is_published)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, title, slug, category, content, image_url, video_url, display_order, is_published, created_at;
        """, (title.strip(), slug.strip().lower(), category.strip().upper(), content.strip(), image_url, video_url, display_order, is_published))
        return dict(cursor.fetchone())

def update_tutorial(tut_id: int, title: str, slug: str, category: str, content: str, image_url: str = None, video_url: str = None, display_order: int = 0, is_published: int = 1) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tutorials
            SET title = %s, slug = %s, category = %s, content = %s, image_url = %s, video_url = %s, display_order = %s, is_published = %s
            WHERE id = %s
            RETURNING id, title, slug, category, content, image_url, video_url, display_order, is_published;
        """, (title.strip(), slug.strip().lower(), category.strip().upper(), content.strip(), image_url, video_url, display_order, is_published, tut_id))
        return dict(cursor.fetchone())

def delete_tutorial(tut_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tutorials WHERE id = %s;", (tut_id,))
    return True


# --------------------------------------------------------------------------
# DISCORD & TELEGRAM COMMUNITY BROADCAST NOTIFICATIONS
# --------------------------------------------------------------------------
import json
import urllib.request
import logging

logger = logging.getLogger("bot_notifications")

def get_notification_settings() -> dict:
    """Fetches Discord & Telegram configuration from site_settings table."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings WHERE key LIKE 'discord_%' OR key LIKE 'telegram_%' OR key LIKE 'notify_%' OR key = 'app_url';")
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
    return settings

def send_discord_webhook(webhook_url: str, payload: dict) -> bool:
    """Dispatches a payload to a Discord webhook URL using standard library."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GOD4XE-Esports-Bot/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        logger.warning(f"[DISCORD WEBHOOK FAILED] {e}")
        return False

def prepare_telegram_caption_cf(text: str, max_len: int = 1000) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_open = truncated.rfind('<')
    last_close = truncated.rfind('>')
    if last_open > last_close:
        truncated = truncated[:last_open]
    truncated = truncated.rstrip() + "..."
    tags = re.findall(r'<(/?[a-zA-Z0-9]+)[^>]*>', truncated)
    open_tags = []
    for t in tags:
        if t.startswith('/'):
            tag_name = t[1:].lower()
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
        else:
            open_tags.append(t.lower())
    for t in reversed(open_tags):
        truncated += f"</{t}>"
    return truncated

def strip_html_tags_cf(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)

def _fetch_and_convert_to_jpeg_cf(photo_source: str) -> tuple:
    if not photo_source:
        return None, "Empty source"
    src = str(photo_source).strip()
    raw_bytes = None
    clean_url = src.split("?")[0].rstrip("/")
    filename = clean_url.split("/")[-1] if "/" in clean_url else clean_url
    filename = urllib.parse.unquote(filename)

    candidates = [
        UPLOAD_DIR / filename,
        BASE_DIR / src.lstrip("/"),
        APP_DIR / src.lstrip("/"),
        Path(src)
    ]
    for c in candidates:
        if c.is_file():
            try:
                with open(c, "rb") as f:
                    raw_bytes = f.read()
                break
            except Exception:
                pass

    if not raw_bytes and (src.startswith("http://") or src.startswith("https://")):
        try:
            req = urllib.request.Request(
                src,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_bytes = resp.read()
        except Exception as e:
            logger.warning(f"[PHOTO DOWNLOAD FAILED CF] {src}: {e}")

    if not raw_bytes:
        return None, "Not found"

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        if max(img.size) > 2560:
            img.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        return buf.getvalue(), None
    except Exception as e:
        return None, str(e)

def _send_telegram_photo_multipart_cf(bot_token: str, chat_id: str, jpeg_bytes: bytes, caption: str = None, reply_markup: dict = None, parse_mode: str = "HTML") -> bool:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    parts = []
    def add_field(name, val):
        hdr = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + str(name) + "\"\r\n\r\n" + str(val) + "\r\n").encode("utf-8")
        parts.append(hdr)
    add_field("chat_id", chat_id)
    if caption:
        safe_caption = prepare_telegram_caption_cf(caption, max_len=1020) if parse_mode else caption[:1020]
        add_field("caption", safe_caption)
        if parse_mode:
            add_field("parse_mode", parse_mode)
    if reply_markup:
        add_field("reply_markup", json.dumps(reply_markup))
    file_header = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"banner.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode("utf-8")
    with open("/dev/null", "rb") as f:
        pass
    body = b"".join(parts) + file_header + jpeg_bytes + ("\r\n--" + boundary + "--\r\n").encode("utf-8")
    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendPhoto"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        if parse_mode and e.code == 400:
            plain_caption = strip_html_tags_cf(caption)
            return _send_telegram_photo_multipart_cf(bot_token, chat_id, jpeg_bytes, plain_caption, reply_markup, parse_mode=None)
        return False
    except Exception:
        return False

def send_telegram_message(bot_token: str, chat_id: str, text: str, button_text: str = None, button_url: str = None, photo_url: str = None) -> bool:
    """Dispatches an HTML formatted message (with photo if available) to Telegram Bot API."""
    if not bot_token or not chat_id:
        return False

    reply_markup = None
    if button_text and button_url:
        reply_markup = {
            "inline_keyboard": [
                [{"text": button_text, "url": button_url}]
            ]
        }

    # 1. Attempt sendPhoto using JPEG bytes upload
    if photo_url and str(photo_url).strip():
        clean_photo = str(photo_url).strip()
        jpeg_bytes, err = _fetch_and_convert_to_jpeg_cf(clean_photo)
        if jpeg_bytes:
            if _send_telegram_photo_multipart_cf(bot_token, chat_id, jpeg_bytes, caption=text, reply_markup=reply_markup, parse_mode="HTML"):
                return True

        # Fallback for remote URLs: try sending photo URL directly if bytes failed
        elif clean_photo.startswith("http://") or clean_photo.startswith("https://"):
            try:
                url = f"https://api.telegram.org/bot{bot_token.strip()}/sendPhoto"
                safe_caption = prepare_telegram_caption_cf(text, max_len=1020)
                payload = {
                    "chat_id": chat_id,
                    "photo": clean_photo,
                    "caption": safe_caption,
                    "parse_mode": "HTML"
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass

    try:
        url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False

def notify_tournament_created(tournament_id: int):
    """Broadcasts a newly created/published tournament to Discord and Telegram."""
    from app.services import tournaments as tournament_service
    from app.config import APP_URL

    t = tournament_service.get_tournament_by_id(tournament_id)
    if not t:
        return

    cfg = get_notification_settings()
    app_base = cfg.get("app_url") or APP_URL
    tourn_url = f"{app_base.rstrip('/')}/tournaments/{t['id']}"

    entry_fee_str = "FREE ENTRY" if t.get("entry_type") == "FREE" else f"💎 {t.get('entry_fee_diamonds', 0)} Diamonds"
    prize_str = f"💎 {t.get('prize_amount_diamonds', 0)} Diamonds"

    # 1. DISCORD EMBED
    if cfg.get("notify_discord_enabled", "").lower() in ("true", "1") and cfg.get("discord_webhook_url"):
        embed = {
            "title": f"🏆 NEW TOURNAMENT: {t.get('title')}",
            "description": f"Official Free Fire **{t.get('mode')}** match on **{t.get('map_name')}** is now open for registration!",
            "url": tourn_url,
            "color": 11032055,  # Neon Purple
            "fields": [
                {"name": "💰 Prize Pool", "value": prize_str, "inline": True},
                {"name": "🎟️ Entry Fee", "value": entry_fee_str, "inline": True},
                {"name": "👥 Slots Available", "value": f"{t.get('joined_players', 0)} / {t.get('max_slots', 48)}", "inline": True},
                {"name": "🎮 Format & Map", "value": f"{t.get('mode')} • {t.get('map_name')}", "inline": True},
                {"name": "⏰ Start Schedule", "value": str(t.get('start_time', 'TBA'))[:16].replace('T', ' '), "inline": True}
            ],
            "footer": {
                "text": "GOD4XE ESPORTS • Dominate The Lobby"
            }
        }
        if t.get("banner_url") and str(t.get("banner_url")).startswith("http"):
            embed["image"] = {"url": t.get("banner_url")}

        payload = {
            "content": f"📢 @everyone **New Free Fire Tournament Announced!** Register your slot now: {tourn_url}",
            "embeds": [embed]
        }
        send_discord_webhook(cfg.get("discord_webhook_url"), payload)

    # 2. TELEGRAM BROADCAST
    if cfg.get("notify_telegram_enabled", "").lower() in ("true", "1") and cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
        text = (
            f"🏆 <b>NEW FREE FIRE TOURNAMENT ANNOUNCED!</b>\n\n"
            f"🎮 <b>{t.get('title')}</b>\n"
            f"🗺️ <b>Map:</b> {t.get('map_name')} | <b>Mode:</b> {t.get('mode')}\n"
            f"💰 <b>Prize Pool:</b> {prize_str}\n"
            f"🎟️ <b>Entry:</b> {entry_fee_str}\n"
            f"👥 <b>Slots:</b> {t.get('joined_players', 0)} / {t.get('max_slots', 48)}\n"
            f"⏰ <b>Schedule:</b> {str(t.get('start_time', 'TBA'))[:16].replace('T', ' ')}\n\n"
            f"⚡ <i>Book your slot before it gets full!</i>"
        )
        send_telegram_message(
            bot_token=cfg.get("telegram_bot_token"),
            chat_id=cfg.get("telegram_chat_id"),
            text=text,
            button_text="🎮 Register Slot on GOD4XE",
            button_url=tourn_url,
            photo_url=t.get("banner_url")
        )

def notify_player_joined(tournament_id: int, user_id: int, slot_number: int, team_name: str = None):
    """Dispatches a live player activity alert to Discord and/or Telegram."""
    from app.services import tournaments as tournament_service
    from app.services import users_auth as user_service
    from app.config import APP_URL

    cfg = get_notification_settings()
    if cfg.get("notify_discord_enabled", "").lower() not in ("true", "1") and cfg.get("notify_telegram_enabled", "").lower() not in ("true", "1"):
        return

    t = tournament_service.get_tournament_by_id(tournament_id)
    u = user_service.get_user_by_id(user_id)
    if not t or not u:
        return

    app_base = cfg.get("app_url") or APP_URL
    tourn_url = f"{app_base.rstrip('/')}/tournaments/{t['id']}"

    player_name = u.get("display_name") or u.get("username")
    team_str = f" (Team: **{team_name}**)" if team_name else ""

    discord_target = cfg.get("discord_activity_webhook") or cfg.get("discord_webhook_url")
    if cfg.get("notify_discord_enabled", "").lower() in ("true", "1") and discord_target:
        payload = {
            "content": f"⚡ **@{player_name}**{team_str} just joined **Slot #{slot_number}** in [{t.get('title')}]({tourn_url})! ({t.get('joined_players')}/{t.get('max_slots')} slots filled)"
        }
        send_discord_webhook(discord_target, payload)

    if cfg.get("notify_telegram_enabled", "").lower() in ("true", "1") and cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
        text = (
            f"⚡ <b>Slot Booked!</b>\n"
            f"Player: <b>@{player_name}</b>{team_str}\n"
            f"Tournament: <b>{t.get('title')}</b>\n"
            f"Slot: <b>#{slot_number}</b> ({t.get('joined_players')}/{t.get('max_slots')} filled)\n\n"
            f"👉 <a href='{tourn_url}'>Join Tournament</a>"
        )
        send_telegram_message(
            bot_token=cfg.get("telegram_bot_token"),
            chat_id=cfg.get("telegram_chat_id"),
            text=text
        )
