import json
import urllib.request
import logging
from app.database import get_db

logger = logging.getLogger("bot_notifications")

def get_notification_settings() -> dict:
    """Fetches Discord & Telegram configuration from site_settings table."""
    keys = (
        "discord_webhook_url",
        "discord_activity_webhook",
        "telegram_bot_token",
        "telegram_chat_id",
        "notify_discord_enabled",
        "notify_telegram_enabled",
        "app_url"
    )
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings WHERE key IN %s;", (keys,))
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

def send_telegram_message(bot_token: str, chat_id: str, text: str, button_text: str = None, button_url: str = None) -> bool:
    """Dispatches an HTML formatted message to Telegram Bot API."""
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if button_text and button_url:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": button_text, "url": button_url}]
                ]
            }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception as e:
        logger.warning(f"[TELEGRAM MESSAGE FAILED] {e}")
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
            button_url=tourn_url
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

    # DISCORD ACTIVITY POST
    # Prefer dedicated activity webhook if available, else primary webhook
    discord_target = cfg.get("discord_activity_webhook") or cfg.get("discord_webhook_url")
    if cfg.get("notify_discord_enabled", "").lower() in ("true", "1") and discord_target:
        payload = {
            "content": f"⚡ **@{player_name}**{team_str} just joined **Slot #{slot_number}** in [{t.get('title')}]({tourn_url})! ({t.get('joined_players')}/{t.get('max_slots')} slots filled)"
        }
        send_discord_webhook(discord_target, payload)

    # TELEGRAM ACTIVITY POST
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
