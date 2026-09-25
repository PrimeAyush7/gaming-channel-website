import io
from urllib.parse import quote
from fastapi import APIRouter, Request, Response, HTTPException, status, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from app.templating import templates
from app.config import APP_DIR, APP_URL, JWT_SECRET
from app.services.jwt_util import decode_jwt
from app.services import users_auth as user_service, content_features
from app.services import (
    posts as post_service,
    sections as section_service,
    tags as tag_service,
    youtube as youtube_service,
    ads as ad_service,
    settings as settings_service,
    analytics as analytics_service,
    formatter
)

router = APIRouter()
# templates imported from app.templating

def get_common_context(request: Request):
    return {
        "request": request,
        "app_url": APP_URL,
        "settings": settings_service.get_all_settings(),
        "nav_sections": section_service.get_all_sections(only_nav=True),
        "ads": ad_service.get_ad_settings(),
        "web_user": _get_web_user(request)
    }
def _get_web_user(request: Request):
    token = request.cookies.get("god4xe_web_token")
    if not token:
        return None
    try:
        claims = decode_jwt(token)
        return {
            "id": int(claims.get("sub")),
            "username": claims.get("username", "")
        }
    except Exception:
        return None

def _set_web_auth_cookie(response: Response, token: str):
    response.set_cookie(
        "god4xe_web_token",
        token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax",
        secure=APP_URL.startswith("https://"),
        path="/"
    )



@router.get("/", response_class=HTMLResponse)
async def home_view(request: Request):
    ctx = get_common_context(request)
    posts_data = post_service.get_posts(page=1, per_page=9, only_published=True)
    popular_posts = post_service.get_popular_posts(limit=6)
    featured_video = youtube_service.get_featured_video()
    
    # Check if there is a featured post
    featured_post_data = post_service.get_posts(page=1, per_page=1, is_featured=True, only_published=True)
    featured_post = featured_post_data["posts"][0] if featured_post_data["posts"] else None

    # Record page view event
    analytics_service.record_event("page_view", page_path="/")

    ctx.update({
        "posts": posts_data["posts"],
        "popular_posts": popular_posts,
        "featured_video": featured_video,
        "featured_post": featured_post,
        "announcements": content_features.list_announcements(only_active=True),
        "updates": content_features.list_latest_updates(only_published=True),
    })
    return templates.TemplateResponse(request=request, name="public/home.html", context=ctx)

@router.get("/post/{slug}", response_class=HTMLResponse)
async def post_detail_view(request: Request, slug: str):
    ctx = get_common_context(request)
    post = post_service.get_post_by_slug(slug, only_published=True)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Increment view counter & record analytics
    post_service.increment_post_view(post["id"])
    analytics_service.record_event("post_view", target_id=post["id"], page_path=f"/post/{slug}")

    # Format content safely
    formatted_content = formatter.format_post_content(post["content"])
    
    # Related posts & popular posts
    related = post_service.get_related_posts(post["id"], post.get("section_id"), limit=4)
    popular = post_service.get_popular_posts(limit=5)

    ctx.update({
        "post": post,
        "formatted_content": formatted_content,
        "related_posts": related,
        "popular_posts": popular
    })
    return templates.TemplateResponse(request=request, name="public/post.html", context=ctx)

@router.get("/section/{slug}", response_class=HTMLResponse)
async def section_archive_view(request: Request, slug: str, page: int = 1):
    ctx = get_common_context(request)
    section = section_service.get_section_by_slug(slug)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    posts_data = post_service.get_posts(page=page, per_page=12, section_id=section["id"], only_published=True)
    analytics_service.record_event("page_view", target_id=section["id"], page_path=f"/section/{slug}")

    ctx.update({
        "section": section,
        "current_section": section,
        "posts": posts_data["posts"],
        "total": posts_data["total"],
        "page": posts_data["page"],
        "total_pages": posts_data["total_pages"],
        "has_next": posts_data["has_next"],
        "has_prev": posts_data["has_prev"]
    })
    return templates.TemplateResponse(request=request, name="public/section.html", context=ctx)

@router.get("/tag/{slug}", response_class=HTMLResponse)
async def tag_archive_view(request: Request, slug: str, page: int = 1):
    ctx = get_common_context(request)
    tag = tag_service.get_tag_by_slug(slug)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    posts_data = post_service.get_posts(page=page, per_page=12, tag_slug=tag["slug"], only_published=True)
    analytics_service.record_event("page_view", target_id=tag["id"], page_path=f"/tag/{slug}")

    ctx.update({
        "tag": tag,
        "posts": posts_data["posts"],
        "total": posts_data["total"],
        "page": posts_data["page"],
        "total_pages": posts_data["total_pages"],
        "has_next": posts_data["has_next"],
        "has_prev": posts_data["has_prev"]
    })
    return templates.TemplateResponse(request=request, name="public/tag.html", context=ctx)

@router.get("/search", response_class=HTMLResponse)
async def search_view(request: Request, q: str = "", page: int = 1):
    ctx = get_common_context(request)
    query = q.strip()
    posts_data = post_service.get_posts(page=page, per_page=12, search_query=query, only_published=True)
    analytics_service.record_event("page_view", page_path=f"/search?q={query}")

    ctx.update({
        "query": query,
        "posts": posts_data["posts"],
        "total": posts_data["total"],
        "page": posts_data["page"],
        "total_pages": posts_data["total_pages"],
        "has_next": posts_data["has_next"],
        "has_prev": posts_data["has_prev"]
    })
    return templates.TemplateResponse(request=request, name="public/search.html", context=ctx)

@router.post("/api/track/download/{post_id}")
async def track_download_api(post_id: int):
    post_service.increment_post_download(post_id)
    analytics_service.record_event("download_click", target_id=post_id)
    return {"status": "success"}

@router.post("/api/track/youtube/{post_id}")
async def track_youtube_api(post_id: int):
    analytics_service.record_event("youtube_click", target_id=post_id)
    return {"status": "success"}

@router.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt_view():
    content = ad_service.get_ads_txt_content()
    return PlainTextResponse(content=content, media_type="text/plain")

@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt_view():
    robots_content = settings_service.get_setting("robots_txt")
    if not robots_content:
        robots_content = "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nSitemap: /sitemap.xml"
    return PlainTextResponse(content=robots_content, media_type="text/plain")

@router.get("/sitemap.xml")
async def sitemap_xml_view():
    all_posts = post_service.get_posts(page=1, per_page=1000, only_published=True)["posts"]
    all_sections = section_service.get_all_sections(only_nav=False)
    all_tags = tag_service.get_all_tags()

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    # Homepage
    xml_lines.append(f'  <url><loc>{APP_URL}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>')

    # Sections
    for s in all_sections:
        xml_lines.append(f'  <url><loc>{APP_URL}/section/{s["slug"]}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')

    # Posts
    for p in all_posts:
        pub_date = p.get("updated_at") or p.get("published_at")
        date_str = pub_date[:10] if pub_date else "2026-01-01"
        xml_lines.append(f'  <url><loc>{APP_URL}/post/{p["slug"]}</loc><lastmod>{date_str}</lastmod><changefreq>monthly</changefreq><priority>0.9</priority></url>')

    # Tags
    for t in all_tags:
        xml_lines.append(f'  <url><loc>{APP_URL}/tag/{t["slug"]}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>')

    xml_lines.append('</urlset>')
    return Response(content="\n".join(xml_lines), media_type="application/xml")


from app.services import tournaments as tournament_service


@router.get("/login", response_class=HTMLResponse)
async def web_login(request: Request):
    if _get_web_user(request):
        return RedirectResponse("/tournaments", status_code=303)
    ctx = get_common_context(request)
    ctx["error"] = request.query_params.get("error")
    ctx["next_url"] = request.query_params.get("next", "/tournaments")
    return templates.TemplateResponse(request=request, name="public/login.html", context=ctx)

@router.post("/login")
async def web_login_submit(
    request: Request,
    identity: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/tournaments")
):
    user, token_or_err = user_service.authenticate_user(identity, password, ip_address=request.client.host if request.client else "127.0.0.1")
    if not user:
        return RedirectResponse(f"/login?error={quote(str(token_or_err))}&next={quote(next_url)}", status_code=303)
    response = RedirectResponse(next_url if next_url.startswith("/") else "/tournaments", status_code=303)
    _set_web_auth_cookie(response, token_or_err)
    return response

@router.get("/register", response_class=HTMLResponse)
async def web_register(request: Request):
    if _get_web_user(request):
        return RedirectResponse("/tournaments", status_code=303)
    ctx = get_common_context(request)
    ctx["error"] = request.query_params.get("error")
    return templates.TemplateResponse(request=request, name="public/register.html", context=ctx)

@router.post("/register")
async def web_register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    referral_code: str = Form("")
):
    try:
        result = user_service.register_user(
            username=username,
            email=email,
            password=password,
            referral_code=referral_code or None
        )
        response = RedirectResponse("/tournaments", status_code=303)
        _set_web_auth_cookie(response, result["token"])
        return response
    except Exception as exc:
        return RedirectResponse(f"/register?error={quote(str(exc))}", status_code=303)

@router.get("/logout")
async def web_logout():
    response = RedirectResponse("/tournaments", status_code=303)
    response.delete_cookie("god4xe_web_token", path="/")
    return response

@router.get("/esports", response_class=HTMLResponse)
async def public_esports_landing(request: Request):
    ctx = get_common_context(request)
    ctx.update({
        "web_user": _get_web_user(request),
        "upcoming_tournaments": tournament_service.list_tournaments(status_filter="UPCOMING", limit=8, is_published_only=True),
        "live_tournaments": tournament_service.list_tournaments(status_filter="LIVE", limit=8, is_published_only=True),
        "completed_tournaments": tournament_service.list_tournaments(status_filter="COMPLETED", limit=6, is_published_only=True),
        "announcements": content_features.list_announcements(only_active=True),
        "updates": content_features.list_latest_updates(only_published=True),
    })
    return templates.TemplateResponse(request=request, name="public/esports.html", context=ctx)

@router.get("/announcements", response_class=HTMLResponse)
async def public_announcements(request: Request):
    ctx = get_common_context(request)
    ctx.update({
        "announcements": content_features.list_announcements(only_active=True),
        "updates": content_features.list_latest_updates(only_published=True),
        "web_user": _get_web_user(request)
    })
    return templates.TemplateResponse(request=request, name="public/announcements.html", context=ctx)

@router.get("/download/qr")
async def download_qr():
    import qrcode
    apk_url = f"{APP_URL}/static/downloads/god4xe_esports.apk"
    img = qrcode.make(apk_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png", headers={"Cache-Control": "no-store"})

@router.get("/tournaments", response_class=HTMLResponse)
async def public_tournaments(request: Request, status: str = None):
    settings = settings_service.get_all_settings()
    nav_sections = section_service.get_all_sections(only_nav=True)
    ads = ad_service.get_ad_settings()
    tournaments = tournament_service.list_tournaments(status_filter=status, limit=30, is_published_only=True)
    web_user = _get_web_user(request)
    updates = content_features.list_latest_updates(only_published=True)
    announcements = content_features.list_announcements(only_active=True)

    return templates.TemplateResponse(request=request, name="public/tournaments.html", context={
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": nav_sections,
        "ads": ads,
        "tournaments": tournaments,
        "current_filter": status or "ALL",
        "web_user": web_user,
        "updates": updates,
        "announcements": announcements,
        "apk_version": "1.0.4"
    })

@router.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
async def public_tournament_detail(tournament_id: int, request: Request):
    settings = settings_service.get_all_settings()
    nav_sections = section_service.get_all_sections(only_nav=True)
    ads = ad_service.get_ad_settings()
    web_user = _get_web_user(request)
    user_id = web_user["id"] if web_user else None
    tournament = tournament_service.get_tournament_by_id(tournament_id, user_id=user_id)
    if not tournament or tournament.get("is_published", 1) == 0:
        raise HTTPException(status_code=404, detail="Tournament not found")

    return templates.TemplateResponse(request=request, name="public/tournament_detail.html", context={
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": nav_sections,
        "ads": ads,
        "tournament": tournament,
        "web_user": web_user,
        "apk_version": "1.0.4"
    })

@router.post("/tournaments/{tournament_id}/join")
async def public_tournament_join(
    tournament_id: int,
    request: Request,
    ff_uid: str = Form(...),
    ff_ign: str = Form(...),
):
    web_user = _get_web_user(request)
    if not web_user:
        return RedirectResponse(f"/login?next=/tournaments/{tournament_id}", status_code=303)
    try:
        tournament_service.join_tournament(
            tournament_id=tournament_id,
            user_id=web_user["id"],
            ff_uid=ff_uid.strip(),
            ff_ign=ff_ign.strip()
        )
        return RedirectResponse(f"/tournaments/{tournament_id}?joined=1", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/tournaments/{tournament_id}?error={quote(str(exc))}", status_code=303)

