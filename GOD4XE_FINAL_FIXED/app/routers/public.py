from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
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
        "ads": ad_service.get_ad_settings()
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

    # Record page view event
    analytics_service.record_event("page_view", page_path="/")

    ctx.update({
        "posts": posts_data["posts"],
        "popular_posts": popular_posts,
        "featured_video": featured_video,
        "featured_post": featured_post,
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
from app.services import referrals as referrals_service
from app.services import users_auth as user_service


@router.get("/referrals", response_class=HTMLResponse)
async def public_referrals(request: Request, ref: str = None):
    ctx = get_common_context(request)
    
    current_user = None
    user_summary = None
    try:
        current_user = user_service.get_current_user(request)
        if current_user:
            user_summary = referrals_service.get_user_referral_summary(current_user["id"])
    except Exception:
        pass

    leaderboard_data = referrals_service.get_referral_leaderboard(limit=50)
    ranks = referrals_service.get_active_ranks()

    ctx.update({
        "current_user": current_user,
        "user_summary": user_summary,
        "leaderboard": leaderboard_data["leaderboard"],
        "total_referrers": leaderboard_data["total"],
        "ranks": ranks,
        "prefill_ref": ref or ""
    })
    return templates.TemplateResponse(request=request, name="public/referrals.html", context=ctx)

@router.get("/esports", response_class=HTMLResponse)
async def public_esports_landing(request: Request):
    ctx = get_common_context(request)
    
    current_user = None
    try:
        current_user = user_service.get_current_user(request)
    except Exception:
        pass

    upcoming_tournaments = tournament_service.list_tournaments(status_filter="UPCOMING", limit=6, is_published_only=True)
    live_tournaments = tournament_service.list_tournaments(status_filter="LIVE", limit=6, is_published_only=True)
    completed_tournaments = tournament_service.list_tournaments(status_filter="COMPLETED", limit=4, is_published_only=True)
    leaderboard_data = referrals_service.get_referral_leaderboard(limit=5)
    ranks = referrals_service.get_active_ranks()

    ctx.update({
        "current_user": current_user,
        "upcoming_tournaments": upcoming_tournaments,
        "live_tournaments": live_tournaments,
        "completed_tournaments": completed_tournaments,
        "leaderboard": leaderboard_data.get("leaderboard", []),
        "ranks": ranks,
    })
    return templates.TemplateResponse(request=request, name="public/esports.html", context=ctx)

@router.get("/download/app")
@router.get("/download/apk")
async def public_download_apk():
    apk_path = APP_DIR / "static" / "downloads" / "god4xe_esports.apk"
    if not apk_path.exists():
        raise HTTPException(status_code=404, detail="APK download package not found")
    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename="god4xe_esports.apk"
    )

@router.get("/download/qr")
async def public_download_qr(format: str = "svg"):
    from app.services import qr_generator
    if format.lower() == "png":
        png_bytes = qr_generator.generate_qr_png_bytes()
        return Response(content=png_bytes, media_type="image/png")
    svg_str = qr_generator.generate_qr_svg()
    return Response(content=svg_str, media_type="image/svg+xml")

@router.get("/tournaments", response_class=HTMLResponse)
async def public_tournaments(request: Request, status: str = None):
    settings = settings_service.get_all_settings()
    nav_sections = section_service.get_all_sections(only_nav=True)
    ads = ad_service.get_ad_settings()
    normalized_status = None if (not status or status.strip().upper() == "ALL") else status.strip().upper()
    tournaments = tournament_service.list_tournaments(status_filter=normalized_status, limit=50, is_published_only=True)

    return templates.TemplateResponse(request=request, name="public/tournaments.html", context={
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": nav_sections,
        "ads": ads,
        "tournaments": tournaments,
        "current_filter": status.strip().upper() if status else "ALL"
    })

@router.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
async def public_tournament_detail(tournament_id: int, request: Request):
    settings = settings_service.get_all_settings()
    nav_sections = section_service.get_all_sections(only_nav=True)
    ads = ad_service.get_ad_settings()
    tournament = tournament_service.get_tournament_by_id(tournament_id)
    if not tournament or tournament.get("is_published", 1) == 0:
        raise HTTPException(status_code=404, detail="Tournament not found")

    return templates.TemplateResponse(request=request, name="public/tournament_detail.html", context={
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": nav_sections,
        "ads": ads,
        "tournament": tournament
    })
