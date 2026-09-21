from starlette.templating import Jinja2Templates
from app.config import APP_DIR

# Native modern Starlette Jinja2Templates instance
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
