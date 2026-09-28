from fastapi import APIRouter, Request, Response, HTTPException, status, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, FileResponse
from app.templating import templates
from app.config import APP_DIR, APP_URL
from app.services import (
    posts as post_service,
    sections as section_service,
    tags as tag_service,
    youtube as youtube_service,
    ads as ad_service,
    settings as settings_service,
    analytics as analytics_service,
    formatter,
    tournaments as tournament_service,
    content_features as content_features_service,
    users_auth as users_auth_service,
    jwt_util
)

router = APIRouter()

def get_optional_current_user(request: Request) -> dict | None:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.cookies.get("god4xe_user_token"):
        token = request.cookies.get("god4xe_user_token")

    if not token:
        return None

    try:
        payload = jwt_util.decode_jwt(token)
        user_id = int(payload.get("sub", 0))
        if user_id:
            return users_auth_service.get_user_by_id(user_id)
    except Exception:
        return None
    return None

def get_common_context(request: Request):
    all_s = settings_service.get_all_settings()
    return {
        "request": request,
        "app_url": APP_URL,
        "settings": all_s,
        "nav_sections": section_service.get_all_sections(only_nav=True),
        "ads": ad_service.get_ad_settings(),
        "current_user": get_optional_current_user(request),
        "google_client_id": all_s.get("google_client_id", "")
    }

@router.get("/", response_class=HTMLResponse)
async def home_view(request: Request):
    ctx = get_common_context(request)
    posts_data = post_service.get_posts(page=1, per_page=9, only_published=True)
    popular_posts = post_service.get_popular_posts(limit=6)
    featured_video = youtube_service.get_featured_video()
    
    # Check if there is a featured post
    featured_post_data = post_service.get_posts(page=1, per_page=1, is_featured=True, only_published=True)
    featured_post = featured_post_data["posts"][0] if featured_post_data["posts"] else None

    # Esports tournaments for homepage arena section
    esports_tournaments = tournament_service.list_tournaments(status_filter="UPCOMING", limit=4, is_published_only=True)
    if not esports_tournaments:
        esports_tournaments = tournament_service.list_tournaments(limit=4, is_published_only=True)

    # Announcements for homepage ticker & highlights
    announcements = content_features_service.list_announcements(only_active=True)[:4]
    arena_notice = settings_service.get_setting("arena_notice", "")

    # Record page view event
    analytics_service.record_event("page_view", page_path="/")

    ctx.update({
        "posts": posts_data["posts"],
        "popular_posts": popular_posts,
        "featured_video": featured_video,
        "featured_post": featured_post,
        "esports_tournaments": esports_tournaments,
        "announcements": announcements,
        "arena_notice": arena_notice,
    })
    return templates.TemplateResponse(request=request, name="public/home.html", context=ctx)

@router.get("/post/{slug}", response_class=HTMLResponse)
async def post_detail_view(request: Request, slug: str):
    ctx = get_common_context(request)
    post = post_service.get_post_by_slug(slug, only_published=True)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post_service.increment_post_view(post["id"])
    analytics_service.record_event("post_view", target_id=post["id"], page_path=f"/post/{slug}")

    formatted_content = formatter.format_post_content(post["content"])
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

@router.get("/esports", response_class=HTMLResponse)
async def esports_view(request: Request):
    ctx = get_common_context(request)
    tournaments = tournament_service.list_tournaments(limit=20, is_published_only=True)
    ctx.update({
        "tournaments": tournaments
    })
    return templates.TemplateResponse(request=request, name="public/esports.html", context=ctx)

@router.get("/announcements", response_class=HTMLResponse)
async def announcements_view(request: Request):
    ctx = get_common_context(request)
    announcements = content_features_service.list_announcements(only_active=True)
    arena_notice = settings_service.get_setting("arena_notice", "")
    ctx.update({
        "announcements": announcements,
        "arena_notice": arena_notice
    })
    return templates.TemplateResponse(request=request, name="public/announcements.html", context=ctx)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, success: str = None):
    ctx = get_common_context(request)
    if ctx.get("current_user"):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    ctx.update({
        "error": error,
        "success_msg": success
    })
    return templates.TemplateResponse(request=request, name="public/login.html", context=ctx)

@router.post("/login")
async def login_submit(
    request: Request,
    identity: str = Form(...),
    password: str = Form(...)
):
    ip_address = request.client.host if request.client else "127.0.0.1"
    try:
        user, token = users_auth_service.authenticate_user(identity.strip(), password, ip_address=ip_address)
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="god4xe_user_token",
            value=token,
            max_age=30 * 24 * 3600,
            httponly=True,
            samesite="lax"
        )
        return response
    except Exception as e:
        error_msg = getattr(e, "detail", str(e))
        ctx = get_common_context(request)
        ctx.update({"error": error_msg})
        return templates.TemplateResponse(request=request, name="public/login.html", context=ctx)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    ctx = get_common_context(request)
    if ctx.get("current_user"):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    ctx.update({"error": error})
    return templates.TemplateResponse(request=request, name="public/register.html", context=ctx)

@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    ff_uid: str = Form(None),
    ff_ign: str = Form(None),
    referral_code: str = Form(None)
):
    try:
        reg_result = users_auth_service.register_user(
            username=username.strip(),
            phone=phone.strip(),
            password=password,
            email=email.strip() if email else None,
            referral_code=referral_code.strip() if referral_code else None
        )
        user = reg_result["user"]
        token = reg_result["token"]
        if ff_uid or ff_ign:
            try:
                users_auth_service.update_user_freefire(user["id"], (ff_uid or "").strip(), (ff_ign or "").strip())
            except Exception:
                pass

        response = RedirectResponse(url="/?welcome=1", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="god4xe_user_token",
            value=token,
            max_age=30 * 24 * 3600,
            httponly=True,
            samesite="lax"
        )
        return response
    except Exception as e:
        error_msg = getattr(e, "detail", str(e))
        ctx = get_common_context(request)
        ctx.update({"error": error_msg})
        return templates.TemplateResponse(request=request, name="public/register.html", context=ctx)

@router.get("/logout")
async def logout_view():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("god4xe_user_token")
    return response

@router.get("/tournaments", response_class=HTMLResponse)
async def public_tournaments(request: Request, status: str = None):
    ctx = get_common_context(request)
    tournaments = tournament_service.list_tournaments(status_filter=status, limit=30, is_published_only=True)
    ctx.update({
        "tournaments": tournaments,
        "current_filter": status or "ALL"
    })
    return templates.TemplateResponse(request=request, name="public/tournaments.html", context=ctx)

@router.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
async def public_tournament_detail(tournament_id: int, request: Request):
    ctx = get_common_context(request)
    user_id = ctx["current_user"]["id"] if ctx.get("current_user") else None
    tournament = tournament_service.get_tournament_by_id(tournament_id, user_id=user_id)
    if not tournament or tournament.get("is_published", 1) == 0:
        raise HTTPException(status_code=404, detail="Tournament not found")

    participants = tournament_service.list_tournament_participants(tournament_id)
    my_slot = None
    if user_id:
        my_slot = next((p for p in participants if p.get("user_id") == user_id), None)

    ctx.update({
        "tournament": tournament,
        "participants": participants,
        "my_slot": my_slot,
        "is_joined": bool(my_slot)
    })
    return templates.TemplateResponse(request=request, name="public/tournament_detail.html", context=ctx)

@router.post("/tournaments/{tournament_id}/join")
async def public_tournament_join(
    tournament_id: int,
    request: Request,
    ff_uid: str = Form(...),
    ff_ign: str = Form(...),
    team_name: str = Form(None),
    teammates: str = Form(None)
):
    current_user = get_optional_current_user(request)
    if not current_user:
        return RedirectResponse(
            url=f"/login?error=Please+login+to+join+the+tournament&return_to=/tournaments/{tournament_id}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    teammates_list = [t.strip() for t in teammates.split(",")] if teammates else []
    try:
        tournament_service.join_tournament(
            tournament_id=tournament_id,
            user_id=current_user["id"],
            ff_uid=ff_uid.strip(),
            ff_ign=ff_ign.strip(),
            team_name=team_name.strip() if team_name else None,
            teammates=teammates_list
        )
        return RedirectResponse(
            url=f"/tournaments/{tournament_id}?joined=1",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        error_msg = getattr(e, "detail", str(e))
        import urllib.parse
        return RedirectResponse(
            url=f"/tournaments/{tournament_id}?error={urllib.parse.quote(str(error_msg))}",
            status_code=status.HTTP_303_SEE_OTHER
        )

@router.get("/download-app")
async def download_app_redirect():
    apk_url = settings_service.get_setting("apk_download_url", "")
    if apk_url and apk_url.startswith("http"):
        return RedirectResponse(url=apk_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    local_apk = APP_DIR / "static" / "downloads" / "god4xe_esports.apk"
    if local_apk.exists() and local_apk.stat().st_size > 0:
        return FileResponse(
            path=str(local_apk),
            filename="god4xe_esports.apk",
            media_type="application/vnd.android.package-archive"
        )

    tg_url = settings_service.get_setting("telegram_url", "")
    if tg_url and tg_url.startswith("http"):
        return RedirectResponse(url=tg_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return RedirectResponse(url="/?msg=APK+update+in+progress.+Please+join+our+Telegram+community.", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

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

    xml_lines.append(f'  <url><loc>{APP_URL}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>')
    xml_lines.append(f'  <url><loc>{APP_URL}/esports</loc><changefreq>daily</changefreq><priority>0.9</priority></url>')
    xml_lines.append(f'  <url><loc>{APP_URL}/announcements</loc><changefreq>daily</changefreq><priority>0.8</priority></url>')
    xml_lines.append(f'  <url><loc>{APP_URL}/tournaments</loc><changefreq>daily</changefreq><priority>0.9</priority></url>')

    for s in all_sections:
        xml_lines.append(f'  <url><loc>{APP_URL}/section/{s["slug"]}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')

    for p in all_posts:
        pub_date = p.get("updated_at") or p.get("published_at")
        date_str = pub_date[:10] if pub_date else "2026-01-01"
        xml_lines.append(f'  <url><loc>{APP_URL}/post/{p["slug"]}</loc><lastmod>{date_str}</lastmod><changefreq>monthly</changefreq><priority>0.9</priority></url>')

    for t in all_tags:
        xml_lines.append(f'  <url><loc>{APP_URL}/tag/{t["slug"]}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>')

    xml_lines.append('</urlset>')
    return Response(content="\n".join(xml_lines), media_type="application/xml")

@router.get("/api/qr")
@router.get("/qr-code")
async def dynamic_qr_code(request: Request, url: str = None):
    target_url = url or settings_service.get_setting("apk_download_url", "")
    if not target_url or not target_url.startswith("http"):
        base_url = str(request.base_url).rstrip('/')
        target_url = f"{base_url}/download-app"
    
    try:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderSVG

        d = Drawing(160, 160)
        w = qr.QrCodeWidget(target_url)
        w.barWidth = 140
        w.barHeight = 140
        w.x = 10
        w.y = 10
        d.add(w)
        svg_content = renderSVG.drawToString(d)
        return Response(content=svg_content, media_type="image/svg+xml")
    except Exception:
        import urllib.parse
        return RedirectResponse(
            url=f"https://api.qrserver.com/v1/create-qr-code/?size=160x160&data={urllib.parse.quote(target_url)}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )
