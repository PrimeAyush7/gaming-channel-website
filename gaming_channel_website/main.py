import os
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import APP_DIR, PORT, ENVIRONMENT, APP_URL
from app.database import init_db
from app.routers import public, admin
from app.services import settings as settings_service

# Initialize database tables
init_db()

# Bootstrap initial admin from environment variables if configured (Render Free deployment)
from app.services.auth import bootstrap_admin_from_env
bootstrap_admin_from_env()

app = FastAPI(
    title="NEXUS GAMING API",
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
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    settings = settings_service.get_all_settings()
    return templates.TemplateResponse("errors/404.html", {
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": [],
        "ads": None
    }, status_code=status.HTTP_404_NOT_FOUND)

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc):
    settings = settings_service.get_all_settings()
    return templates.TemplateResponse("errors/500.html", {
        "request": request,
        "app_url": APP_URL,
        "settings": settings,
        "nav_sections": [],
        "ads": None
    }, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

app.include_router(public.router)
app.include_router(admin.router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", PORT))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=(ENVIRONMENT == "development"))
