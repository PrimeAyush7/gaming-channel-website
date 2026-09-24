import io
import logging
from pathlib import Path
from PIL import Image
from reportlab.graphics.barcode import qr
from app.config import APP_DIR, APP_URL

logger = logging.getLogger("qr_generator")

PRODUCTION_APK_URL = "https://god4xe.onrender.com/download/app"

def get_qr_matrix(data: str):
    """Generate a standard compliant QR code boolean matrix."""
    widget = qr.QrCodeWidget(data)
    widget.qr.make()
    return widget.qr.modules

def generate_qr_svg(url: str = PRODUCTION_APK_URL, border: int = 4, size: int = 256) -> str:
    """Returns a standalone, scalable, scannable SVG string encoding the given URL."""
    matrix = get_qr_matrix(url)
    n = len(matrix)
    dim = n + border * 2
    paths = []
    for y in range(n):
        for x in range(n):
            if matrix[y][x]:
                paths.append(f"M{x + border},{y + border}h1v1h-1z")
    path_d = " ".join(paths)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" width="{size}" height="{size}" shape-rendering="crispEdges">\n'
        f'  <rect width="{dim}" height="{dim}" fill="#ffffff"/>\n'
        f'  <path d="{path_d}" fill="#0f071c"/>\n'
        f'</svg>'
    )

def generate_qr_png_bytes(url: str = PRODUCTION_APK_URL, border: int = 4, scale: int = 10) -> bytes:
    """Returns PNG bytes of the crisp scannable QR code."""
    matrix = get_qr_matrix(url)
    n = len(matrix)
    dim = n + border * 2
    img = Image.new("RGB", (dim * scale, dim * scale), "white")
    pixels = img.load()
    dark_color = (15, 7, 28)
    for y in range(n):
        for x in range(n):
            if matrix[y][x]:
                for dy in range(scale):
                    for dx in range(scale):
                        pixels[(x + border) * scale + dx, (y + border) * scale + dy] = dark_color
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def ensure_static_qr_files():
    """Ensure pre-rendered static QR assets exist in static/images."""
    try:
        images_dir = APP_DIR / "static" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        svg_file = images_dir / "qr_download_apk.svg"
        png_file = images_dir / "qr_download_apk.png"

        svg_content = generate_qr_svg(PRODUCTION_APK_URL)
        with open(svg_file, "w", encoding="utf-8") as f:
            f.write(svg_content)

        png_bytes = generate_qr_png_bytes(PRODUCTION_APK_URL)
        with open(png_file, "wb") as f:
            f.write(png_bytes)

        logger.info("[QR_GENERATOR] Static production APK QR code generated successfully.")
    except Exception as e:
        logger.error(f"[QR_GENERATOR] Failed to write static QR files: {e}", exc_info=True)

# Generate files at module load
ensure_static_qr_files()
