
from app.services import (
    referrals as referrals_service,
    tournaments as tournament_service,
    wallet as wallet_service,
    matches as match_service,
    social as social_service
)
from app.config import (
    ROLE_SUPER_ADMIN,
    ROLE_TOURNAMENT_ADMIN,
    ROLE_FINANCE_ADMIN,
    ROLE_SUPPORT_ADMIN,
    ALL_ADMIN_ROLES
)
from fastapi import APIRouter, Request, Response, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templating import templates
from app.config import APP_DIR, ENVIRONMENT, UPLOAD_DIR
from app.services import (
    referrals as referrals_service,
    auth as auth_service,
    posts as post_service,
    sections as section_service,
    tags as tag_service,
    youtube as youtube_service,
    ads as ad_service,
    media as media_service,
    settings as settings_service,
    analytics as analytics_service,
    users_auth as user_service
)

router = APIRouter(prefix="/admin")
# templates imported from app.templating

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def check_admin(request: Request):
    admin = auth_service.get_current_admin(request)
    if not admin:
        return None
    return admin

def check_csrf(request: Request, submitted_token: str, admin: dict):
    if not auth_service.verify_csrf(request, submitted_token, admin.get("csrf_token")):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def require_admin_role(admin: dict, *allowed_roles: str):
    if admin.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="This action is not permitted for your admin role")

# --------------------------------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    admin = auth_service.get_current_admin(request)
    if admin:
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="admin/login.html", context={"request": request, "error": error})

@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = get_client_ip(request)
    admin_record, error_msg = auth_service.authenticate_admin(username, password, ip_address=ip)
    
    if error_msg or not admin_record:
        return templates.TemplateResponse(request=request, name="admin/login.html", context={
            "request": request,
            "error": error_msg or "Authentication failed."
        }, status_code=401)

    session_id, _ = auth_service.create_session(admin_record["id"])
    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    
    secure_cookie = ENVIRONMENT == "production" and not request.url.hostname.startswith("127.") and not request.url.hostname == "localhost"
    response.set_cookie(
        key="nexus_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        max_age=7 * 86400
    )
    return response

@router.post("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("nexus_session")
    if session_id:
        auth_service.delete_session(session_id)
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("nexus_session")
    return response

# --------------------------------------------------------------------------
# DASHBOARD
# --------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    stats = analytics_service.get_dashboard_stats()
    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context={
        "request": request,
        "admin": admin,
        "stats": stats,
        "active_nav": "dashboard"
    })

# --------------------------------------------------------------------------
# POSTS CRUD
# --------------------------------------------------------------------------
@router.get("/posts", response_class=HTMLResponse)
async def list_posts(request: Request, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    posts_data = post_service.get_posts(page=1, per_page=100, only_published=False)
    return templates.TemplateResponse(request=request, name="admin/posts.html", context={
        "request": request,
        "admin": admin,
        "posts": posts_data["posts"],
        "total": posts_data["total"],
        "msg": msg,
        "error": error,
        "active_nav": "posts"
    })

@router.get("/posts/new", response_class=HTMLResponse)
async def new_post_page(request: Request):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    sections = section_service.get_all_sections()
    return templates.TemplateResponse(request=request, name="admin/post_form.html", context={
        "request": request,
        "admin": admin,
        "post": None,
        "sections": sections,
        "active_nav": "posts"
    })

@router.post("/posts/new")
async def create_post_submit(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(...),
    slug: str = Form(""),
    summary: str = Form(""),
    content: str = Form(...),
    thumbnail_url: str = Form(""),
    youtube_video_id: str = Form(""),
    download_url: str = Form(""),
    download_label: str = Form("DOWNLOAD FILE"),
    section_id: str = Form(""),
    tags: str = Form(""),
    seo_title: str = Form(""),
    seo_description: str = Form(""),
    is_published: int = Form(0),
    is_featured: int = Form(0)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    data = {
        "title": title,
        "slug": slug,
        "summary": summary,
        "content": content,
        "thumbnail_url": thumbnail_url,
        "youtube_video_id": youtube_video_id,
        "download_url": download_url,
        "download_label": download_label,
        "section_id": int(section_id) if section_id else None,
        "tags": tags,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "is_published": bool(is_published),
        "is_featured": bool(is_featured)
    }
    post_id, error = post_service.create_post(data)
    if error:
        sections = section_service.get_all_sections()
        return templates.TemplateResponse(request=request, name="admin/post_form.html", context={
            "request": request,
            "admin": admin,
            "post": data,
            "sections": sections,
            "error": error,
            "active_nav": "posts"
        }, status_code=400)

    return RedirectResponse(url="/admin/posts?msg=Post+created+successfully", status_code=status.HTTP_302_FOUND)

@router.get("/posts/edit/{post_id}", response_class=HTMLResponse)
async def edit_post_page(request: Request, post_id: int):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    post = post_service.get_post_by_id(post_id)
    if not post:
        return RedirectResponse(url="/admin/posts?error=Post+not+found", status_code=status.HTTP_302_FOUND)

    sections = section_service.get_all_sections()
    return templates.TemplateResponse(request=request, name="admin/post_form.html", context={
        "request": request,
        "admin": admin,
        "post": post,
        "sections": sections,
        "active_nav": "posts"
    })

@router.post("/posts/edit/{post_id}")
async def update_post_submit(
    request: Request,
    post_id: int,
    csrf_token: str = Form(...),
    title: str = Form(...),
    slug: str = Form(""),
    summary: str = Form(""),
    content: str = Form(...),
    thumbnail_url: str = Form(""),
    youtube_video_id: str = Form(""),
    download_url: str = Form(""),
    download_label: str = Form("DOWNLOAD FILE"),
    section_id: str = Form(""),
    tags: str = Form(""),
    seo_title: str = Form(""),
    seo_description: str = Form(""),
    is_published: int = Form(0),
    is_featured: int = Form(0)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    data = {
        "title": title,
        "slug": slug,
        "summary": summary,
        "content": content,
        "thumbnail_url": thumbnail_url,
        "youtube_video_id": youtube_video_id,
        "download_url": download_url,
        "download_label": download_label,
        "section_id": int(section_id) if section_id else None,
        "tags": tags,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "is_published": bool(is_published),
        "is_featured": bool(is_featured)
    }
    success, error = post_service.update_post(post_id, data)
    if error:
        sections = section_service.get_all_sections()
        data["id"] = post_id
        return templates.TemplateResponse(request=request, name="admin/post_form.html", context={
            "request": request,
            "admin": admin,
            "post": data,
            "sections": sections,
            "error": error,
            "active_nav": "posts"
        }, status_code=400)

    return RedirectResponse(url="/admin/posts?msg=Post+updated+successfully", status_code=status.HTTP_302_FOUND)

@router.post("/posts/delete/{post_id}")
async def delete_post_action(request: Request, post_id: int, csrf_token: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    post_service.delete_post(post_id)
    return RedirectResponse(url="/admin/posts?msg=Post+deleted+successfully", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# DYNAMIC SECTIONS
# --------------------------------------------------------------------------
@router.get("/sections", response_class=HTMLResponse)
async def sections_page(request: Request, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    sections = section_service.get_all_sections()
    return templates.TemplateResponse(request=request, name="admin/sections.html", context={
        "request": request,
        "admin": admin,
        "sections": sections,
        "msg": msg,
        "error": error,
        "active_nav": "sections"
    })

@router.post("/sections/new")
async def create_section_submit(
    request: Request,
    csrf_token: str = Form(...),
    name: str = Form(...),
    slug: str = Form(""),
    description: str = Form(""),
    icon: str = Form("🎮"),
    is_nav_visible: int = Form(0),
    sort_order: int = Form(0)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    section_service.create_section(
        name=name,
        slug=slug,
        description=description,
        icon=icon,
        is_nav_visible=bool(is_nav_visible),
        sort_order=sort_order
    )
    return RedirectResponse(url="/admin/sections?msg=Section+created+successfully", status_code=status.HTTP_302_FOUND)

@router.post("/sections/delete/{section_id}")
async def delete_section_action(request: Request, section_id: int, csrf_token: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    section_service.delete_section(section_id)
    return RedirectResponse(url="/admin/sections?msg=Section+deleted+successfully", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# TAGS
# --------------------------------------------------------------------------
@router.get("/tags", response_class=HTMLResponse)
async def tags_page(request: Request, msg: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    tags = tag_service.get_all_tags()
    return templates.TemplateResponse(request=request, name="admin/tags.html", context={
        "request": request,
        "admin": admin,
        "tags": tags,
        "msg": msg,
        "active_nav": "tags"
    })

@router.post("/tags/new")
async def create_tag_submit(request: Request, csrf_token: str = Form(...), name: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    tag_service.get_or_create_tag(name)
    return RedirectResponse(url="/admin/tags?msg=Tag+created", status_code=status.HTTP_302_FOUND)

@router.post("/tags/delete/{tag_id}")
async def delete_tag_action(request: Request, tag_id: int, csrf_token: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    tag_service.delete_tag(tag_id)
    return RedirectResponse(url="/admin/tags?msg=Tag+deleted", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# MEDIA MANAGEMENT
# --------------------------------------------------------------------------
@router.get("/media", response_class=HTMLResponse)
async def media_page(request: Request, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    media_files = media_service.get_all_media()
    return templates.TemplateResponse(request=request, name="admin/media.html", context={
        "request": request,
        "admin": admin,
        "media_files": media_files,
        "msg": msg,
        "error": error,
        "active_nav": "media"
    })

@router.post("/media/upload")
async def upload_media_submit(request: Request, csrf_token: str = Form(...), file: UploadFile = File(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    content = await file.read()
    record, error = media_service.save_media_file(file.filename, content, file.content_type)
    if error:
        media_files = media_service.get_all_media()
        return templates.TemplateResponse(request=request, name="admin/media.html", context={
            "request": request,
            "admin": admin,
            "media_files": media_files,
            "error": error,
            "active_nav": "media"
        }, status_code=400)

    return RedirectResponse(url="/admin/media?msg=File+uploaded+successfully", status_code=status.HTTP_302_FOUND)

@router.post("/media/delete/{media_id}")
async def delete_media_action(request: Request, media_id: int, csrf_token: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    media_service.delete_media(media_id)
    return RedirectResponse(url="/admin/media?msg=File+deleted", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# YOUTUBE MANAGEMENT
# --------------------------------------------------------------------------
@router.get("/youtube", response_class=HTMLResponse)
async def youtube_page(request: Request, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    videos = youtube_service.get_all_videos()
    return templates.TemplateResponse(request=request, name="admin/youtube.html", context={
        "request": request,
        "admin": admin,
        "videos": videos,
        "msg": msg,
        "error": error,
        "active_nav": "youtube"
    })

@router.post("/youtube/new")
async def add_youtube_submit(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(...),
    youtube_input: str = Form(...),
    is_featured: int = Form(0),
    sort_order: int = Form(0)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    video_id, error = youtube_service.add_video(
        title=title,
        youtube_input=youtube_input,
        is_featured=bool(is_featured),
        sort_order=sort_order
    )
    if error:
        videos = youtube_service.get_all_videos()
        return templates.TemplateResponse(request=request, name="admin/youtube.html", context={
            "request": request,
            "admin": admin,
            "videos": videos,
            "error": error,
            "active_nav": "youtube"
        }, status_code=400)

    return RedirectResponse(url="/admin/youtube?msg=Video+added+successfully", status_code=status.HTTP_302_FOUND)

@router.post("/youtube/delete/{video_id}")
async def delete_youtube_action(request: Request, video_id: int, csrf_token: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    youtube_service.delete_video(video_id)
    return RedirectResponse(url="/admin/youtube?msg=Video+removed", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# ADSENSE & ADS MANAGEMENT
# --------------------------------------------------------------------------
@router.get("/ads", response_class=HTMLResponse)
async def ads_page(request: Request, msg: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    ads = ad_service.get_ad_settings()
    return templates.TemplateResponse(request=request, name="admin/ads.html", context={
        "request": request,
        "admin": admin,
        "ads": ads,
        "msg": msg,
        "active_nav": "ads"
    })

@router.post("/ads")
async def update_ads_submit(
    request: Request,
    csrf_token: str = Form(...),
    is_enabled: int = Form(0),
    client_id: str = Form(""),
    slot_home_top: str = Form(""),
    slot_home_bottom: str = Form(""),
    slot_post_top: str = Form(""),
    slot_post_bottom: str = Form(""),
    slot_sidebar: str = Form(""),
    custom_ads_txt: str = Form("")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    ad_service.update_ad_settings({
        "is_enabled": bool(is_enabled),
        "client_id": client_id,
        "slot_home_top": slot_home_top,
        "slot_home_bottom": slot_home_bottom,
        "slot_post_top": slot_post_top,
        "slot_post_bottom": slot_post_bottom,
        "slot_sidebar": slot_sidebar,
        "custom_ads_txt": custom_ads_txt
    })
    return RedirectResponse(url="/admin/ads?msg=Monetization+settings+updated+successfully", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# SITE SETTINGS & SEO
# --------------------------------------------------------------------------
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, msg: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    settings = settings_service.get_all_settings()
    return templates.TemplateResponse(request=request, name="admin/settings.html", context={
        "request": request,
        "admin": admin,
        "settings": settings,
        "msg": msg,
        "active_nav": "settings"
    })

@router.post("/settings")
async def update_settings_submit(
    request: Request,
    csrf_token: str = Form(...),
    site_name: str = Form(...),
    site_tagline: str = Form(""),
    site_description: str = Form(""),
    hero_headline: str = Form("DOMINATE THE LOBBY"),
    logo_url: str = Form(""),
    favicon_url: str = Form(""),
    youtube_channel_url: str = Form(""),
    instagram_url: str = Form(""),
    whatsapp_url: str = Form(""),
    telegram_url: str = Form(""),
    discord_url: str = Form(""),
    facebook_url: str = Form(""),
    seo_keywords: str = Form(""),
    footer_text: str = Form(""),
    robots_txt: str = Form("")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    check_csrf(request, csrf_token, admin)

    settings_service.update_settings({
        "site_name": site_name,
        "site_tagline": site_tagline,
        "site_description": site_description,
        "hero_headline": hero_headline.strip() if hero_headline else "DOMINATE THE LOBBY",
        "logo_url": logo_url,
        "favicon_url": favicon_url,
        "youtube_channel_url": youtube_channel_url,
        "instagram_url": instagram_url,
        "whatsapp_url": whatsapp_url,
        "telegram_url": telegram_url,
        "discord_url": discord_url,
        "facebook_url": facebook_url,
        "seo_keywords": seo_keywords,
        "footer_text": footer_text,
        "robots_txt": robots_txt
    })
    return RedirectResponse(url="/admin/settings?msg=Settings+saved+successfully", status_code=status.HTTP_302_FOUND)

# --------------------------------------------------------------------------
# TOURNAMENTS MANAGEMENT (SUPER_ADMIN, TOURNAMENT_ADMIN)
# --------------------------------------------------------------------------
@router.get("/tournaments", response_class=HTMLResponse)
async def admin_tournaments(request: Request, status: str = None, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    tournaments = tournament_service.list_tournaments(status_filter=status, limit=100, is_published_only=False)
    return templates.TemplateResponse(request=request, name="admin/tournaments.html", context={
        "request": request,
        "admin": admin,
        "tournaments": tournaments,
        "active_nav": "tournaments",
        "current_status": status or "ALL",
        "msg": msg,
        "error": error
    })

@router.get("/tournaments/new", response_class=HTMLResponse)
async def admin_tournament_new_form(request: Request):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_TOURNAMENT_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role for tournament management")

    return templates.TemplateResponse(request=request, name="admin/tournament_form.html", context={
        "request": request,
        "admin": admin,
        "tournament": None,
        "active_nav": "tournaments"
    })

@router.post("/tournaments/new")
async def admin_tournament_create(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    banner_url: str = Form(""),
    game: str = Form("FREE_FIRE"),
    mode: str = Form("SOLO"),
    entry_type: str = Form("FREE"),
    entry_fee_diamonds: int = Form(0),
    prize_amount_diamonds: int = Form(0),
    max_slots: int = Form(48),
    map_name: str = Form("BERMUDA"),
    start_time: str = Form(...),
    rules: str = Form(""),
    is_featured: int = Form(0),
    is_published: int = Form(1)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_TOURNAMENT_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role")

    try:
        t = tournament_service.create_tournament(
            title=title,
            banner_url=banner_url,
            description=description,
            game=game,
            mode=mode,
            entry_type=entry_type,
            entry_fee_diamonds=entry_fee_diamonds,
            prize_type="DIAMONDS",
            prize_amount_diamonds=prize_amount_diamonds,
            max_slots=max_slots,
            rules=rules,
            map_name=map_name,
            start_time=start_time,
            is_featured=is_featured,
            is_published=is_published
        )
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="CREATE_TOURNAMENT",
            resource="tournaments",
            resource_id=t["id"],
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            after_state={"title": title, "entry_type": entry_type, "entry_fee": entry_fee_diamonds}
        )
        return RedirectResponse(url="/admin/tournaments?msg=Tournament+created+successfully", status_code=302)
    except ValueError as e:
        return templates.TemplateResponse(request=request, name="admin/tournament_form.html", context={
            "request": request,
            "admin": admin,
            "tournament": None,
            "active_nav": "tournaments",
            "error": str(e)
        }, status_code=400)

@router.post("/tournaments/{tournament_id}/room")
async def admin_update_room(
    tournament_id: int,
    request: Request,
    csrf_token: str = Form(...),
    room_id: str = Form(...),
    room_password: str = Form(...),
    instructions: str = Form("")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_TOURNAMENT_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role")

    tournament_service.update_tournament_room_credentials(tournament_id, room_id, room_password, instructions)
    auth_service.log_admin_action(
        admin_id=admin["admin_id"],
        admin_username=admin["username"],
        role=admin["role"],
        action="UPDATE_ROOM_CREDENTIALS",
        resource="tournaments",
        resource_id=tournament_id,
        ip_address=get_client_ip(request),
        after_state={"room_id": room_id}
    )
    return RedirectResponse(url=f"/admin/tournaments?msg=Room+credentials+updated", status_code=302)

@router.post("/tournaments/{tournament_id}/status")
async def admin_update_tournament_status(
    tournament_id: int,
    request: Request,
    csrf_token: str = Form(...),
    status: str = Form(...)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_TOURNAMENT_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role")

    tournament_service.update_tournament_status(tournament_id, status)
    auth_service.log_admin_action(
        admin_id=admin["admin_id"],
        admin_username=admin["username"],
        role=admin["role"],
        action="UPDATE_TOURNAMENT_STATUS",
        resource="tournaments",
        resource_id=tournament_id,
        ip_address=get_client_ip(request),
        after_state={"status": status}
    )
    return RedirectResponse(url="/admin/tournaments?msg=Status+updated", status_code=302)

# --------------------------------------------------------------------------
# DEPOSIT REQUESTS & WALLET (SUPER_ADMIN, FINANCE_ADMIN)
# --------------------------------------------------------------------------
@router.get("/deposits", response_class=HTMLResponse)
async def admin_deposits(request: Request, status: str = None, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_FINANCE_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role for finance records")

    deposits = wallet_service.list_all_deposit_requests(status_filter=status, limit=100)
    settings_dict = settings_service.get_all_settings()
    return templates.TemplateResponse(request=request, name="admin/deposits.html", context={
        "request": request,
        "admin": admin,
        "deposits": deposits,
        "settings": settings_dict,
        "active_nav": "deposits",
        "current_status": status or "ALL",
        "msg": msg,
        "error": error
    })

@router.post("/deposits/{request_id}/review")
async def admin_review_deposit(
    request_id: int,
    request: Request,
    csrf_token: str = Form(...),
    decision: str = Form(...),
    rejection_reason: str = Form("")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_FINANCE_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role")

    approve = decision.upper() == "APPROVE"
    try:
        wallet_service.review_deposit_request(
            request_id=request_id,
            admin_id=admin["admin_id"],
            approve=approve,
            rejection_reason=rejection_reason
        )
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="APPROVE_DEPOSIT" if approve else "REJECT_DEPOSIT",
            resource="deposit_requests",
            resource_id=request_id,
            ip_address=get_client_ip(request),
            after_state={"decision": decision, "reason": rejection_reason}
        )
        return RedirectResponse(url="/admin/deposits?msg=Deposit+reviewed+successfully", status_code=302)
    except ValueError as e:
        return RedirectResponse(url=f"/admin/deposits?error={e}", status_code=302)


@router.post("/deposits/upi-settings")
async def admin_update_upi_settings(
    request: Request,
    csrf_token: str = Form(...),
    upi_id: str = Form(...),
    upi_payee_name: str = Form("GOD4XE ESPORTS"),
    min_deposit_diamonds: str = Form("50"),
    qr_file: UploadFile = File(None)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_FINANCE_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized")

    payload = {
        "upi_id": upi_id.strip(),
        "upi_payee_name": upi_payee_name.strip(),
        "min_deposit_diamonds": min_deposit_diamonds.strip()
    }

    if qr_file and qr_file.filename:
        import secrets
        allowed_exts = {"jpg", "jpeg", "png", "webp"}
        ext = qr_file.filename.split(".")[-1].lower() if "." in qr_file.filename else "png"
        if ext in allowed_exts:
            contents = await qr_file.read()
            if 0 < len(contents) <= 5 * 1024 * 1024:
                safe_name = f"upi_qr_{secrets.token_hex(6)}.{ext}"
                target_path = UPLOAD_DIR / safe_name
                with open(target_path, "wb") as f_out:
                    f_out.write(contents)
                payload["upi_qr_image_url"] = f"/static/uploads/{safe_name}"

    settings_service.update_settings(payload)
    auth_service.record_audit_log(
        admin_id=admin.get("admin_id") or admin.get("id"),
        admin_username=admin["username"],
        role=admin["role"],
        action="UPDATE_UPI_SETTINGS",
        resource="site_settings",
        resource_id="upi_settings",
        ip_address=get_client_ip(request),
        after_state=payload
    )
    return RedirectResponse(url="/admin/deposits?msg=UPI+configuration+updated+successfully", status_code=302)

@router.post("/deposits/remove-qr")
async def admin_remove_upi_qr(request: Request, csrf_token: str = Form(...)):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_FINANCE_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized")

    settings_service.update_settings({"upi_qr_image_url": ""})
    auth_service.record_audit_log(
        admin_id=admin.get("admin_id") or admin.get("id"),
        admin_username=admin["username"],
        role=admin["role"],
        action="REMOVE_UPI_QR",
        resource="site_settings",
        resource_id="upi_qr",
        ip_address=get_client_ip(request),
        after_state={"upi_qr_image_url": ""}
    )
    return RedirectResponse(url="/admin/deposits?msg=UPI+QR+Code+removed", status_code=302)

# --------------------------------------------------------------------------
# REFERRAL MANAGEMENT & DYNAMIC RANKS
# --------------------------------------------------------------------------
@router.get("/referrals", response_class=HTMLResponse)
async def admin_referrals(
    request: Request,
    search: str = None,
    status: str = None,
    msg: str = None,
    error: str = None
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    referrals_list = referrals_service.admin_list_referrals(
        search=search,
        status_filter=status,
        limit=100
    )
    ranks = referrals_service.admin_get_ranks()

    total_refs = len(referrals_list)
    successful_refs = sum(1 for r in referrals_list if r.get("status") == "SUCCESSFUL")
    invalid_refs = sum(1 for r in referrals_list if r.get("status") == "INVALID")

    return templates.TemplateResponse(request=request, name="admin/referrals.html", context={
        "request": request,
        "admin": admin,
        "referrals": referrals_list,
        "ranks": ranks,
        "total_refs": total_refs,
        "successful_refs": successful_refs,
        "invalid_refs": invalid_refs,
        "search_query": search or "",
        "status_filter": status or "",
        "msg": msg,
        "error": error,
        "active_nav": "referrals"
    })

@router.post("/referrals/{referral_id}/invalidate")
async def admin_invalidate_referral(
    request: Request,
    referral_id: int,
    csrf_token: str = Form(...),
    reason: str = Form("Administratively invalidated / fraudulent activity")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)

    try:
        referrals_service.invalidate_referral(
            referral_id=referral_id,
            admin_id=admin.get("admin_id") or admin.get("id"),
            admin_username=admin["username"],
            reason=reason
        )
        return RedirectResponse(url="/admin/referrals?msg=Referral+invalidated+and+rank+recalculated", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/referrals?error={e}", status_code=302)

@router.post("/referrals/ranks")
async def admin_update_referral_ranks(
    request: Request,
    csrf_token: str = Form(...),
    rank_rookie_max: int = Form(9),
    rank_pro_min: int = Form(10),
    rank_pro_max: int = Form(24),
    rank_elite_min: int = Form(25),
    rank_elite_max: int = Form(49),
    rank_master_min: int = Form(50),
    rank_master_max: int = Form(99),
    rank_legend_min: int = Form(100)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)

    ranks_payload = [
        {"name": "ROOKIE", "min_referrals": 0, "max_referrals": rank_rookie_max, "badge_color": "#94a3b8", "is_active": True},
        {"name": "PRO", "min_referrals": rank_pro_min, "max_referrals": rank_pro_max, "badge_color": "#38bdf8", "is_active": True},
        {"name": "ELITE", "min_referrals": rank_elite_min, "max_referrals": rank_elite_max, "badge_color": "#a855f7", "is_active": True},
        {"name": "MASTER", "min_referrals": rank_master_min, "max_referrals": rank_master_max, "badge_color": "#f59e0b", "is_active": True},
        {"name": "LEGEND", "min_referrals": rank_legend_min, "max_referrals": None, "badge_color": "#ef4444", "is_active": True},
    ]

    try:
        referrals_service.admin_update_ranks(ranks_payload)
        auth_service.record_audit_log(
            admin_id=admin.get("admin_id") or admin.get("id"),
            admin_username=admin["username"],
            role=admin["role"],
            action="UPDATE_REFERRAL_RANKS",
            resource="referral_ranks",
            ip_address=get_client_ip(request),
            after_state={"ranks": ranks_payload}
        )
        return RedirectResponse(url="/admin/referrals?msg=Referral+ranks+updated+successfully", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/referrals?error={e}", status_code=302)

# --------------------------------------------------------------------------
# REDEEM CODES (SUPER_ADMIN, FINANCE_ADMIN, TOURNAMENT_ADMIN)
# --------------------------------------------------------------------------
@router.get("/redeem", response_class=HTMLResponse)
async def admin_redeem_list(request: Request, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    with auth_service.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM redeem_codes ORDER BY id DESC LIMIT 100;")
        codes = [dict(r) for r in cursor.fetchall()]

    return templates.TemplateResponse(request=request, name="admin/redeem.html", context={
        "request": request,
        "admin": admin,
        "codes": codes,
        "active_nav": "redeem",
        "msg": msg,
        "error": error
    })

@router.post("/redeem/new")
async def admin_redeem_create(
    request: Request,
    csrf_token: str = Form(...),
    code: str = Form(...),
    reward_diamonds: int = Form(...),
    max_uses: int = Form(100),
    per_user_limit: int = Form(1),
    expires_at: str = Form("")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if not auth_service.has_role_permission(admin["role"], [ROLE_SUPER_ADMIN, ROLE_FINANCE_ADMIN]):
        raise HTTPException(status_code=403, detail="Unauthorized role")

    try:
        social_service.create_redeem_code(
            code=code,
            reward_diamonds=reward_diamonds,
            max_uses=max_uses,
            per_user_limit=per_user_limit,
            expires_at=expires_at or None
        )
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="CREATE_REDEEM_CODE",
            resource="redeem_codes",
            resource_id=code,
            ip_address=get_client_ip(request),
            after_state={"code": code, "reward": reward_diamonds}
        )
        return RedirectResponse(url="/admin/redeem?msg=Redeem+code+created", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/redeem?error={e}", status_code=302)

# --------------------------------------------------------------------------
# ADMIN USERS & RBAC (SUPER_ADMIN ONLY)
# --------------------------------------------------------------------------
@router.get("/admins", response_class=HTMLResponse)
async def admin_list_accounts(request: Request, msg: str = None, error: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    if admin["role"] != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")

    admins_list = auth_service.list_admins()
    return templates.TemplateResponse(request=request, name="admin/admins.html", context={
        "request": request,
        "admin": admin,
        "admins_list": admins_list,
        "roles": ALL_ADMIN_ROLES,
        "active_nav": "admins",
        "msg": msg,
        "error": error
    })

@router.post("/admins/new")
async def admin_create_account(
    request: Request,
    csrf_token: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("TOURNAMENT_ADMIN"),
    email: str = Form("")
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if admin["role"] != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")

    try:
        new_id = auth_service.create_admin_with_role(username, password, role, email or None)
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="CREATE_ADMIN",
            resource="admins",
            resource_id=new_id,
            ip_address=get_client_ip(request),
            after_state={"username": username, "role": role}
        )
        return RedirectResponse(url="/admin/admins?msg=Admin+account+created", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/admins?error={e}", status_code=302)

@router.post("/admins/{target_id}/status")
async def admin_toggle_status(
    target_id: int,
    request: Request,
    csrf_token: str = Form(...),
    is_active: int = Form(1)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    if admin["role"] != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")

    auth_service.update_admin_status(target_id, is_active)
    auth_service.log_admin_action(
        admin_id=admin["admin_id"],
        admin_username=admin["username"],
        role=admin["role"],
        action="TOGGLE_ADMIN_STATUS",
        resource="admins",
        resource_id=target_id,
        ip_address=get_client_ip(request),
        after_state={"is_active": is_active}
    )
    return RedirectResponse(url="/admin/admins?msg=Admin+status+updated", status_code=302)

# --------------------------------------------------------------------------
# AUDIT LOGS (SUPER_ADMIN, TOURNAMENT_ADMIN, FINANCE_ADMIN)
# --------------------------------------------------------------------------
@router.get("/audit-logs", response_class=HTMLResponse)
async def admin_view_audit_logs(request: Request, resource: str = None):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    logs = auth_service.get_audit_logs(limit=150, resource=resource)
    return templates.TemplateResponse(request=request, name="admin/audit_logs.html", context={
        "request": request,
        "admin": admin,
        "logs": logs,
        "active_nav": "audit_logs"
    })

# --------------------------------------------------------------------------
# APP USER MANAGEMENT (ALL ADMIN ROLES CAN VIEW, SUPER_ADMIN CAN MODIFY)
# --------------------------------------------------------------------------
@router.get("/users", response_class=HTMLResponse)
async def admin_list_users(
    request: Request,
    q: str = None,
    provider: str = None,
    status_filter: str = None,
    page: int = 1,
    msg: str = None
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    limit = 30
    offset = (page - 1) * limit
    users, total = user_service.list_app_users(
        search=q,
        provider_filter=provider,
        status_filter=status_filter,
        limit=limit,
        offset=offset
    )
    total_pages = max(1, (total + limit - 1) // limit)
    return templates.TemplateResponse(request=request, name="admin/users.html", context={
        "request": request,
        "admin": admin,
        "active_nav": "users",
        "users": users,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q or "",
        "provider": provider or "ALL",
        "status_filter": status_filter or "ALL",
        "msg": msg
    })

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_view_user(
    user_id: int,
    request: Request,
    msg: str = None,
    error: str = None
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    user = user_service.get_user_full_admin_details(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse(request=request, name="admin/user_detail.html", context={
        "request": request,
        "admin": admin,
        "active_nav": "users",
        "u": user,
        "msg": msg,
        "error": error
    })

@router.post("/users/{user_id}/status")
async def admin_toggle_user_status(
    user_id: int,
    request: Request,
    is_active: int = Form(...),
    csrf_token: str = Form(...)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)

    user_service.toggle_user_status(user_id, is_active)
    state = "activated" if is_active else "deactivated"
    auth_service.log_admin_action(
        admin_id=admin["admin_id"],
        admin_username=admin["username"],
        role=admin["role"],
        action="UPDATE_USER_STATUS",
        resource="app_users",
        resource_id=user_id,
        ip_address=get_client_ip(request),
        after_state={"is_active": is_active}
    )
    return RedirectResponse(url=f"/admin/users/{user_id}?msg=User+successfully+{state}", status_code=302)

@router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    csrf_token: str = Form(...)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)

    try:
        user_service.admin_reset_user_password(user_id, new_password)
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="RESET_USER_PASSWORD",
            resource="app_users",
            resource_id=user_id,
            ip_address=get_client_ip(request)
        )
        return RedirectResponse(url=f"/admin/users/{user_id}?msg=Password+reset+successfully", status_code=302)
    except ValueError as e:
        return RedirectResponse(url=f"/admin/users/{user_id}?error={e}", status_code=302)

@router.post("/users/{user_id}/diamonds")
async def admin_adjust_user_diamonds(
    user_id: int,
    request: Request,
    amount: int = Form(...),
    reason: str = Form(...),
    csrf_token: str = Form(...)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    require_admin_role(admin, ROLE_SUPER_ADMIN, ROLE_FINANCE_ADMIN)

    try:
        tx = user_service.admin_adjust_user_diamonds(
            user_id=user_id,
            amount=amount,
            admin_id=admin["admin_id"],
            reason=reason,
        )
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="ADJUST_USER_DIAMONDS",
            resource="app_users",
            resource_id=user_id,
            ip_address=get_client_ip(request),
            details={"amount": amount, "balance_after": tx.get("balance_after"), "reason": reason[:500]},
        )
        return RedirectResponse(url=f"/admin/users/{user_id}?msg=Diamonds+updated+successfully", status_code=302)
    except ValueError as e:
        return RedirectResponse(url=f"/admin/users/{user_id}?error={str(e).replace(' ', '+')}", status_code=302)

@router.post("/users/{user_id}/delete")
async def admin_delete_user(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
    confirm_text: str = Form(...)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)
    require_admin_role(admin, ROLE_SUPER_ADMIN)
    if confirm_text.strip() != "DELETE":
        return RedirectResponse(url=f"/admin/users/{user_id}?error=Type+DELETE+to+confirm", status_code=302)

    try:
        deleted = user_service.delete_user_if_safe(user_id)
        auth_service.log_admin_action(
            admin_id=admin["admin_id"],
            admin_username=admin["username"],
            role=admin["role"],
            action="DELETE_APP_USER",
            resource="app_users",
            resource_id=user_id,
            ip_address=get_client_ip(request),
            before_state={"username": deleted.get("username"), "referral_code": deleted.get("referral_code")},
        )
        return RedirectResponse(url="/admin/users?msg=Test+user+deleted+successfully", status_code=302)
    except ValueError as e:
        return RedirectResponse(url=f"/admin/users/{user_id}?error={str(e).replace(' ', '+')}", status_code=302)

@router.post("/users/{user_id}/revoke-sessions")
async def admin_revoke_user_sessions(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...)
):
    admin = check_admin(request)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)
    check_csrf(request, csrf_token, admin)

    count = user_service.revoke_user_sessions(user_id)
    auth_service.log_admin_action(
        admin_id=admin["admin_id"],
        admin_username=admin["username"],
        role=admin["role"],
        action="REVOKE_USER_SESSIONS",
        resource="app_users",
        resource_id=user_id,
        ip_address=get_client_ip(request),
        details={"revoked_count": count}
    )
    return RedirectResponse(url=f"/admin/users/{user_id}?msg={count}+sessions+revoked", status_code=302)
