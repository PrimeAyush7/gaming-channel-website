import os
import uvicorn
import starlette
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Gracefully adapt legacy Starlette (< 0.28) in local test environments so modern signature works seamlessly
if starlette.__version__ < "0.28.0":
    import starlette.templating
    _orig_tr = starlette.templating.Jinja2Templates.TemplateResponse
    def _compat_tr(self, *args, **kwargs):
        if "request" in kwargs and "name" in kwargs:
            req = kwargs.pop("request")
            name = kwargs.pop("name")
            ctx = kwargs.pop("context", {}) or {}
            ctx["request"] = req
            return _orig_tr(self, name, ctx, **kwargs)
        return _orig_tr(self, *args, **kwargs)
    starlette.templating.Jinja2Templates.TemplateResponse = _compat_tr

from app.templating import templates


from app.config import APP_DIR, PORT, ENVIRONMENT, APP_URL
from app.database import init_db
from app.routers import public, admin, api_v1
from app.services import settings as settings_service

# Initialize database tables
init_db()

# Bootstrap initial admin from environment variables if configured (Render Free deployment)
from app.services.auth import bootstrap_admin_from_env
bootstrap_admin_from_env()

app = FastAPI(
    title="GOD4XE GAMING API",
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)
# Persistent Uploaded Media Serving with PostgreSQL DB Fallback (survives Render dyno restarts/idle wipes)
@app.get("/static/uploads/{filename:path}")
@app.get("/media/{filename:path}")
async def serve_persistent_upload(filename: str):
    from fastapi.responses import FileResponse, Response
    from pathlib import Path
    from app.config import UPLOAD_DIR
    import mimetypes

    clean_filename = Path(filename).name
    target_path = UPLOAD_DIR / clean_filename

    # 1. Local disk fast cache
    if target_path.exists() and target_path.stat().st_size > 0:
        mime_type, _ = mimetypes.guess_type(str(target_path))
        if clean_filename.endswith(".svg"):
            mime_type = "image/svg+xml"
        return FileResponse(
            str(target_path),
            media_type=mime_type or "application/octet-stream",
            headers={"Cache-Control": "public, max-age=31536000, immutable"}
        )

    # 2. Ephemeral disk wiped on Render restart: Fetch & restore from persistent PostgreSQL database
    try:
        from app.services.media import get_media_bytes_by_filename
        record = get_media_bytes_by_filename(clean_filename)
        if record and record.get("file_data"):
            file_bytes = record["file_data"]
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(file_bytes)
            except Exception:
                pass
            return Response(
                content=file_bytes,
                media_type=record.get("mime_type") or "image/png",
                headers={"Cache-Control": "public, max-age=31536000, immutable"}
            )
    except Exception as e:
        print(f"[MEDIA DB RESTORE ERROR] {e}")

    return Response(content="Image Not Found", status_code=404)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
# templates imported from app.templating

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    settings = settings_service.get_all_settings()
    return templates.TemplateResponse(request=request, name="errors/404.html", context={
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": [],
        "ads": None
    }, status_code=status.HTTP_404_NOT_FOUND)

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc):
    settings = settings_service.get_all_settings()
    return templates.TemplateResponse(request=request, name="errors/500.html", context={
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": [],
        "ads": None
    }, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

app.include_router(public.router)
app.include_router(admin.router)
app.include_router(api_v1.router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", PORT))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=(ENVIRONMENT == "development"))
