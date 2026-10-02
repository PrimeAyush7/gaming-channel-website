from app.config import UPLOAD_DIR, APP_DIR, BASE_DIR
from PIL import Image
from pathlib import Path
import io
import html
import json
import os
import urllib.request
import urllib.error
import uuid
import logging
from app.database import get_db

logger = logging.getLogger("bot_notifications")

def clean_telegram_chat_id(chat_id: str) -> str:
    if not chat_id:
        return ""
    cid = str(chat_id).strip()
    if "t.me/" in cid:
        cid = cid.split("t.me/")[-1].replace("+", "").strip("/")
    if not cid.startswith("@") and not cid.startswith("-") and not cid.isdigit():
        cid = "@" + cid
    return cid

def resolve_app_url(base_candidate: str = None, request = None) -> str:
    """Guarantees a 100% valid absolute URL with hostname for Telegram/Discord/WhatsApp buttons."""
    if base_candidate and (str(base_candidate).startswith("http://") or str(base_candidate).startswith("https://")):
        return str(base_candidate).rstrip("/")
    if request:
        try:
            proto = request.headers.get("x-forwarded-proto", "https")
            host = request.headers.get("host")
            if host:
                return f"{proto}://{host}".rstrip("/")
            if hasattr(request, "base_url") and str(request.base_url).startswith("http"):
                return str(request.base_url).rstrip("/")
        except Exception:
            pass
    try:
        from app.config import APP_URL
        if APP_URL and (str(APP_URL).startswith("http://") or str(APP_URL).startswith("https://")):
            return str(APP_URL).rstrip("/")
    except Exception:
        pass
    return "https://god4xe.onrender.com"

def get_notification_settings() -> dict:
    """Fetches Discord, Telegram & WhatsApp configuration from site_settings table."""
    keys = (
        "discord_webhook_url",
        "discord_activity_webhook",
        "telegram_bot_token",
        "telegram_chat_id",
        "whatsapp_webhook_url",
        "notify_discord_enabled",
        "notify_telegram_enabled",
        "notify_whatsapp_enabled",
        "app_url"
    )
    placeholders = ','.join(['%s'] * len(keys))
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT key, value FROM site_settings WHERE key IN ({placeholders});", keys)
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
    return settings

def send_discord_webhook(webhook_url: str, payload: dict) -> tuple:
    """Dispatches a payload to a Discord webhook URL."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False, "Invalid Discord Webhook URL"
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                return True, "Success"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        logger.warning(f"[DISCORD WEBHOOK FAILED] {e.code}: {err_msg}")
        return False, f"HTTP {e.code}: {err_msg[:80]}"
    except Exception as e:
        logger.warning(f"[DISCORD WEBHOOK FAILED] {e}")
        return False, str(e)

def prepare_telegram_caption(text: str, max_len: int = 1000) -> str:
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

def strip_html_tags(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)

def _fetch_and_convert_to_jpeg(photo_source: str) -> tuple:
    """
    Resolves local or remote photo source and converts to standard RGB JPEG bytes.
    Returns (jpeg_bytes, None) on success or (None, error_str).
    """
    if not photo_source:
        return None, "Empty photo source"
    src = str(photo_source).strip()

    raw_bytes = None

    # 1. Check local file candidates
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
            except Exception as e:
                logger.warning(f"[PHOTO READ ERROR] {c}: {e}")

    # 2. If not on local disk and it's a web URL, download it with browser headers
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
            logger.warning(f"[PHOTO DOWNLOAD FAILED] {src}: {e}")

    if not raw_bytes:
        return None, f"Image not found locally or remotely: {src}"

    # 3. Convert to clean RGB JPEG bytes using PIL
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
        logger.warning(f"[PHOTO JPEG CONVERT FAILED] {e}")
        return None, str(e)

def _send_telegram_photo_multipart(
    bot_token: str,
    chat_id: str,
    jpeg_bytes: bytes,
    caption: str = None,
    reply_markup: dict = None,
    parse_mode: str = "HTML"
) -> tuple:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    parts = []

    def add_field(name, val):
        hdr = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + str(name) + "\"\r\n\r\n" + str(val) + "\r\n").encode("utf-8")
        parts.append(hdr)

    add_field("chat_id", chat_id)
    if caption:
        safe_caption = prepare_telegram_caption(caption, max_len=1020) if parse_mode else caption[:1020]
        add_field("caption", safe_caption)
        if parse_mode:
            add_field("parse_mode", parse_mode)
    if reply_markup:
        add_field("reply_markup", json.dumps(reply_markup))

    file_header = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"banner.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode("utf-8")

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
            if resp.status == 200:
                return True, "Success"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        logger.warning(f"[TELEGRAM PHOTO MULTIPART FAILED] {e.code}: {err_msg}")
        if parse_mode and e.code == 400 and ("parse entities" in err_msg.lower() or "entity" in err_msg.lower()):
            logger.info("[TELEGRAM RETRYING PHOTO WITH PLAIN CAPTION]")
            plain_caption = strip_html_tags(caption)
            return _send_telegram_photo_multipart(
                bot_token=bot_token,
                chat_id=chat_id,
                jpeg_bytes=jpeg_bytes,
                caption=plain_caption,
                reply_markup=reply_markup,
                parse_mode=None
            )
        try:
            err_json = json.loads(err_msg)
            return False, err_json.get("description", err_msg[:80])
        except Exception:
            return False, f"HTTP {e.code}: {err_msg[:80]}"
    except Exception as e:
        logger.warning(f"[TELEGRAM PHOTO MULTIPART EXCEPTION] {e}")
        return False, str(e)

def send_telegram_message(bot_token: str, chat_id: str, text: str, button_text: str = None, button_url: str = None, photo_url: str = None) -> tuple:
    """Dispatches an HTML formatted message (with photo if available) to Telegram Bot API."""
    if not bot_token:
        return False, "Telegram Bot Token is missing in Settings"
    cleaned_chat_id = clean_telegram_chat_id(chat_id)
    if not cleaned_chat_id:
        return False, "Telegram Chat ID is missing in Settings"

    reply_markup = None
    if button_text and button_url:
        clean_btn_url = button_url if button_url.startswith("http") else f"https://god4xe.onrender.com{button_url}"
        reply_markup = {
            "inline_keyboard": [
                [{"text": button_text, "url": clean_btn_url}]
            ]
        }

    # 1. Attempt sendPhoto using JPEG bytes upload
    if photo_url and str(photo_url).strip():
        clean_photo = str(photo_url).strip()
        jpeg_bytes, err = _fetch_and_convert_to_jpeg(clean_photo)
        if jpeg_bytes:
            ok, msg = _send_telegram_photo_multipart(
                bot_token=bot_token,
                chat_id=cleaned_chat_id,
                jpeg_bytes=jpeg_bytes,
                caption=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            if ok:
                return True, "Success"
            logger.warning(f"[PHOTO MULTIPART FAILED: {msg}]")

        # Fallback for remote URLs: try sending photo URL directly if bytes failed
        elif clean_photo.startswith("http://") or clean_photo.startswith("https://"):
            try:
                url = f"https://api.telegram.org/bot{bot_token.strip()}/sendPhoto"
                safe_caption = prepare_telegram_caption(text, max_len=1020)
                payload = {
                    "chat_id": cleaned_chat_id,
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
                        return True, "Success"
            except Exception as e:
                logger.warning(f"[TELEGRAM PHOTO URL FAILED, FALLING BACK] {e}")

    # 2. Fallback to standard sendMessage text
    try:
        url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
        payload = {
            "chat_id": cleaned_chat_id,
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "Success"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        logger.warning(f"[TELEGRAM MESSAGE FAILED] {e.code}: {err_msg}")
        # If HTML entity error on text message, retry plain text
        if e.code == 400 and ("parse entities" in err_msg.lower() or "entity" in err_msg.lower()):
            try:
                plain_payload = {
                    "chat_id": cleaned_chat_id,
                    "text": strip_html_tags(text),
                    "disable_web_page_preview": False
                }
                if reply_markup:
                    plain_payload["reply_markup"] = reply_markup
                req = urllib.request.Request(
                    url,
                    data=json.dumps(plain_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        return True, "Success"
            except Exception:
                pass
        try:
            err_json = json.loads(err_msg)
            return False, err_json.get("description", err_msg[:80])
        except Exception:
            return False, f"HTTP {e.code}: {err_msg[:80]}"
    except Exception as e:
        logger.warning(f"[TELEGRAM MESSAGE FAILED] {e}")
        return False, str(e)

def send_whatsapp_webhook(webhook_url: str, payload: dict) -> tuple:
    """Dispatches a notification payload to WhatsApp Webhook URL (Make, Zapier, UltraMsg, n8n, etc.)."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False, "WhatsApp Webhook URL is missing or invalid in Settings"
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201, 202, 204):
                return True, "Success"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        logger.warning(f"[WHATSAPP WEBHOOK FAILED] {e.code}: {err_msg}")
        return False, f"HTTP {e.code}: {err_msg[:80]}"
    except Exception as e:
        logger.warning(f"[WHATSAPP WEBHOOK FAILED] {e}")
        return False, str(e)

def notify_tournament_created(tournament_id: int, request = None) -> dict:
    """Broadcasts a newly created/published tournament to Discord, Telegram, and WhatsApp."""
    from app.services import tournaments as tournament_service

    t = tournament_service.get_tournament_by_id(tournament_id)
    if not t:
        return {"status": "error", "detail": "Tournament not found"}

    cfg = get_notification_settings()
    app_base = resolve_app_url(cfg.get("app_url"), request)
    tourn_url = f"{app_base}/tournaments/{t['id']}"

    entry_fee_str = "FREE ENTRY" if t.get("entry_type") == "FREE" else f"💎 {t.get('entry_fee_diamonds', 0)} Diamonds"
    prize_str = f"💎 {t.get('prize_amount_diamonds', 0)} Diamonds"
    sched_time = str(t.get('start_time', 'TBA'))[:16].replace('T', ' ')
    slots_str = f"{t.get('joined_players', 0)} / {t.get('max_slots', 48)}"

    results = {"discord": None, "telegram": None, "whatsapp": None}

    # 1. DISCORD EMBED
    discord_enabled = str(cfg.get("notify_discord_enabled", "")).lower() in ("true", "1", "on", "yes")
    discord_url = (cfg.get("discord_webhook_url") or "").strip()
    if not discord_enabled:
        results["discord"] = "Disabled in Settings"
    elif not discord_url:
        results["discord"] = "Webhook URL empty in Settings"
    else:
        embed = {
            "title": f"🏆 NEW TOURNAMENT: {t.get('title')}",
            "description": f"Official Free Fire **{t.get('mode')}** match on **{t.get('map_name')}** is now open for registration!",
            "url": tourn_url,
            "color": 11032055,
            "fields": [
                {"name": "💰 Prize Pool", "value": prize_str, "inline": True},
                {"name": "🎟️ Entry Fee", "value": entry_fee_str, "inline": True},
                {"name": "👥 Slots Available", "value": slots_str, "inline": True},
                {"name": "🎮 Format & Map", "value": f"{t.get('mode')} • {t.get('map_name')}", "inline": True},
                {"name": "⏰ Start Schedule", "value": sched_time, "inline": True}
            ],
            "footer": {
                "text": "GOD4XE ESPORTS • Dominate The Lobby"
            }
        }
        raw_banner = t.get("banner_url") or ""
        if raw_banner:
            if raw_banner.startswith("/"):
                raw_banner = f"{app_base}{raw_banner}"
            if raw_banner.startswith("http://") or raw_banner.startswith("https://"):
                embed["image"] = {"url": raw_banner}

        payload = {
            "content": f"📢 @everyone **New Free Fire Tournament Announced!** Register your slot now: {tourn_url}",
            "embeds": [embed]
        }
        ok, msg = send_discord_webhook(discord_url, payload)
        results["discord"] = "Sent Successfully" if ok else f"Failed: {msg}"

    # 2. TELEGRAM BROADCAST
    telegram_enabled = str(cfg.get("notify_telegram_enabled", "")).lower() in ("true", "1", "on", "yes")
    tg_token = (cfg.get("telegram_bot_token") or "").strip()
    tg_chat = (cfg.get("telegram_chat_id") or "").strip()
    if not telegram_enabled:
        results["telegram"] = "Disabled in Settings"
    elif not tg_token or not tg_chat:
        results["telegram"] = "Bot Token or Chat ID empty in Settings"
    else:
        text = (
            "🏆 <b>NEW FREE FIRE TOURNAMENT ANNOUNCED!</b>\n\n"
            f"🎮 <b>{t.get('title')}</b>\n"
            f"🗺️ <b>Map:</b> {t.get('map_name')} | <b>Mode:</b> {t.get('mode')}\n"
            f"💰 <b>Prize Pool:</b> {prize_str}\n"
            f"🎟️ <b>Entry:</b> {entry_fee_str}\n"
            f"👥 <b>Slots:</b> {slots_str}\n"
            f"⏰ <b>Schedule:</b> {sched_time}\n\n"
            "⚡ <i>Book your slot before it gets full!</i>"
        )
        ok, msg = send_telegram_message(
            bot_token=tg_token,
            chat_id=tg_chat,
            text=text,
            button_text="🎮 Register Slot on GOD4XE",
            button_url=tourn_url,
            photo_url=raw_banner
        )
        results["telegram"] = "Sent Successfully" if ok else f"Failed: {msg}"

    # 3. WHATSAPP ALERT
    whatsapp_enabled = str(cfg.get("notify_whatsapp_enabled", "")).lower() in ("true", "1", "on", "yes")
    wa_url = (cfg.get("whatsapp_webhook_url") or "").strip()
    if not whatsapp_enabled:
        results["whatsapp"] = "Disabled in Settings"
    elif not wa_url:
        results["whatsapp"] = "WhatsApp Webhook URL empty in Settings"
    else:
        wa_text = (
            f"🏆 *NEW FREE FIRE TOURNAMENT ANNOUNCED!* 🏆\n\n"
            f"🎮 *{t.get('title')}*\n"
            f"🗺️ Map: {t.get('map_name')} | Mode: {t.get('mode')}\n"
            f"💰 Prize Pool: {prize_str}\n"
            f"🎟️ Entry: {entry_fee_str}\n"
            f"👥 Slots: {slots_str}\n"
            f"⏰ Schedule: {sched_time}\n\n"
            f"👉 *Register Slot Now:* {tourn_url}"
        )
        wa_payload = {
            "event": "TOURNAMENT_CREATED",
            "tournament_id": t.get("id"),
            "title": t.get("title"),
            "url": tourn_url,
            "message": wa_text,
            "text": wa_text
        }
        ok, msg = send_whatsapp_webhook(wa_url, wa_payload)
        results["whatsapp"] = "Sent Successfully" if ok else f"Failed: {msg}"

    return results

def notify_post_created(post_id: int, request = None) -> dict:
    """Broadcasts a newly published post/guide to Telegram, Discord, and WhatsApp."""
    from app.services import posts as post_service

    p = post_service.get_post_by_id(post_id)
    if not p:
        return {"status": "error", "detail": "Post not found"}

    cfg = get_notification_settings()
    app_base = resolve_app_url(cfg.get("app_url"), request)
    post_url = f"{app_base}/post/{p['slug']}"

    results = {"discord": None, "telegram": None, "whatsapp": None}

    title = p.get("title", "New Post")
    summary = p.get("summary") or (p.get("content", "")[:180] + "...")
    section_name = p.get("section_name") or "Gaming Guide"
    
    thumbnail = (p.get("thumbnail_url") or "").strip()
    if not thumbnail:
        # Check if content has an image markdown or HTML img
        img_m = re.search(r'!\[.*?\]\((.*?)\)', p.get("content", ""))
        if img_m:
            thumbnail = img_m.group(1).strip()
        else:
            html_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', p.get("content", ""))
            if html_m:
                thumbnail = html_m.group(1).strip()
    if not thumbnail:
        thumbnail = (cfg.get("logo_url") or "").strip()
    if not thumbnail:
        uploads = list(UPLOAD_DIR.glob("*.*"))
        if uploads:
            thumbnail = uploads[0].name

    if thumbnail.startswith("/"):
        thumbnail = f"{app_base}{thumbnail}"

    clean_title = html.escape(title, quote=False)
    clean_summary = html.escape(summary, quote=False)
    clean_section = html.escape(section_name, quote=False)

    # 1. DISCORD EMBED
    discord_enabled = str(cfg.get("notify_discord_enabled", "")).lower() in ("true", "1", "on", "yes")
    discord_url = (cfg.get("discord_webhook_url") or "").strip()
    if not discord_enabled:
        results["discord"] = "Disabled in Settings"
    elif not discord_url:
        results["discord"] = "Webhook URL empty in Settings"
    else:
        embed = {
            "title": f"📰 {title}",
            "description": f"{summary}\n\n[**Read Full Article on Website →**]({post_url})",
            "url": post_url,
            "color": 11032055,  # Neon Purple
            "fields": [
                {"name": "📁 Category", "value": section_name, "inline": True},
                {"name": "🌐 Website", "value": "GOD4XE ESPORTS", "inline": True}
            ],
            "footer": {
                "text": "GOD4XE ESPORTS • Official Gaming Update"
            }
        }
        if thumbnail and (thumbnail.startswith("http://") or thumbnail.startswith("https://")):
            embed["image"] = {"url": thumbnail}

        payload = {
            "content": f"🔥 **New Update / Guide Published!** Check it out: {post_url}",
            "embeds": [embed]
        }
        ok, msg = send_discord_webhook(discord_url, payload)
        results["discord"] = "Sent Successfully" if ok else f"Failed: {msg}"

    # 2. TELEGRAM BROADCAST
    telegram_enabled = str(cfg.get("notify_telegram_enabled", "")).lower() in ("true", "1", "on", "yes")
    tg_token = (cfg.get("telegram_bot_token") or "").strip()
    tg_chat = (cfg.get("telegram_chat_id") or "").strip()
    if not telegram_enabled:
        results["telegram"] = "Disabled in Settings"
    elif not tg_token or not tg_chat:
        results["telegram"] = "Bot Token or Chat ID empty in Settings"
    else:
        text = (
            "📰 <b>NEW POST / GUIDE PUBLISHED!</b>\n\n"
            f"⚡ <b>{title}</b>\n\n"
            f"📁 <i>Category: {section_name}</i>\n"
            f"📝 {summary}\n\n"
            "👉 <i>Click below to read full guide & download configs!</i>"
        )
        ok, msg = send_telegram_message(
            bot_token=tg_token,
            chat_id=tg_chat,
            text=text,
            button_text="📖 Read Full Post on GOD4XE",
            button_url=post_url,
            photo_url=thumbnail
        )
        results["telegram"] = "Sent Successfully" if ok else f"Failed: {msg}"

    # 3. WHATSAPP BROADCAST
    whatsapp_enabled = str(cfg.get("notify_whatsapp_enabled", "")).lower() in ("true", "1", "on", "yes")
    wa_url = (cfg.get("whatsapp_webhook_url") or "").strip()
    if not whatsapp_enabled:
        results["whatsapp"] = "Disabled in Settings"
    elif not wa_url:
        results["whatsapp"] = "WhatsApp Webhook URL empty in Settings"
    else:
        wa_text = f"🔥 *{title}*\n\n📁 _{section_name}_\n\n{summary}\n\n👉 *Read Full Post:* {post_url}"
        wa_payload = {
            "event": "POST_PUBLISHED",
            "title": title,
            "summary": summary,
            "url": post_url,
            "image_url": thumbnail,
            "message": wa_text,
            "text": wa_text
        }
        ok, msg = send_whatsapp_webhook(wa_url, wa_payload)
        results["whatsapp"] = "Sent Successfully" if ok else f"Failed: {msg}"

    return results

def notify_player_joined(tournament_id: int, user_id: int, slot_number: int, team_name: str = None, request = None):
    """Dispatches a live player activity alert to Discord and/or Telegram."""
    from app.services import tournaments as tournament_service
    from app.services import users_auth as user_service

    cfg = get_notification_settings()
    discord_enabled = str(cfg.get("notify_discord_enabled", "")).lower() in ("true", "1", "on", "yes")
    telegram_enabled = str(cfg.get("notify_telegram_enabled", "")).lower() in ("true", "1", "on", "yes")

    if not discord_enabled and not telegram_enabled:
        return

    t = tournament_service.get_tournament_by_id(tournament_id)
    u = user_service.get_user_by_id(user_id)
    if not t or not u:
        return

    app_base = resolve_app_url(cfg.get("app_url"), request)
    tourn_url = f"{app_base}/tournaments/{t['id']}"

    player_name = u.get("display_name") or u.get("username")
    team_str = f" (Team: **{team_name}**)" if team_name else ""

    # DISCORD ACTIVITY POST
    discord_target = cfg.get("discord_activity_webhook") or cfg.get("discord_webhook_url")
    if discord_enabled and discord_target:
        payload = {
            "content": f"⚡ **@{player_name}**{team_str} just joined **Slot #{slot_number}** in [{t.get('title')}]({tourn_url})! ({t.get('joined_players')}/{t.get('max_slots')} slots filled)"
        }
        send_discord_webhook(discord_target, payload)

    # TELEGRAM ACTIVITY POST
    if telegram_enabled and cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
        slots_filled = f"{t.get('joined_players')}/{t.get('max_slots')}"
        text = (
            "⚡ <b>Slot Booked!</b>\n"
            f"Player: <b>@{player_name}</b>{team_str}\n"
            f"Tournament: <b>{t.get('title')}</b>\n"
            f"Slot: <b>#{slot_number}</b> ({slots_filled} filled)\n\n"
            f"👉 <a href='{tourn_url}'>Join Tournament</a>"
        )
        send_telegram_message(
            bot_token=cfg.get("telegram_bot_token"),
            chat_id=cfg.get("telegram_chat_id"),
            text=text
        )
