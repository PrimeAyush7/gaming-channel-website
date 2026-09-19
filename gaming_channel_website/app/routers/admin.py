from fastapi import APIRouter, Request, Response, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
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
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

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
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": error})

@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = get_client_ip(request)
    admin_record, error_msg = auth_service.authenticate_admin(username, password, ip_address=ip)
    
    if error_msg or not admin_record:
        return templates.TemplateResponse("admin/login.html", {
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
    return templates.TemplateResponse("admin/dashboard.html", {
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
    return templates.TemplateResponse("admin/posts.html", {
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
    return templates.TemplateResponse("admin/post_form.html", {
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
        return templates.TemplateResponse("admin/post_form.html", {
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
    return templates.TemplateResponse("admin/post_form.html", {
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
        return templates.TemplateResponse("admin/post_form.html", {
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
    return templates.TemplateResponse("admin/sections.html", {
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
    return templates.TemplateResponse("admin/tags.html", {
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
    return templates.TemplateResponse("admin/media.html", {
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
        return templates.TemplateResponse("admin/media.html", {
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
    return templates.TemplateResponse("admin/youtube.html", {
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
        return templates.TemplateResponse("admin/youtube.html", {
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
    return templates.TemplateResponse("admin/ads.html", {
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
    return templates.TemplateResponse("admin/settings.html", {
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
        "seo_keywords": seo_keywords,
        "footer_text": footer_text,
        "robots_txt": robots_txt
    })
    return RedirectResponse(url="/admin/settings?msg=Settings+saved+successfully", status_code=status.HTTP_302_FOUND)
