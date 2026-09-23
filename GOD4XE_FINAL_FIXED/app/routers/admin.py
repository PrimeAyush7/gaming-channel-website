
from app.services import (
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
from app.config import APP_DIR, ENVIRONMENT
from app.services import (
    auth as auth_service,
    posts as post_service,
    sections as section_service,
    tags as tag_service,
    youtube as youtube_service,
    ads as ad_service,
    media as media_service,
    settings as settings_service,
    analytics as analytics_service
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
    return templates.TemplateResponse(request=request, name="admin/deposits.html", context={
        "request": request,
        "admin": admin,
        "deposits": deposits,
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
