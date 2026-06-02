"""Custom font discovery — lists, uploads, deletes user-supplied font files in static/fonts/custom/."""
import os
import re
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from core.middleware import require_admin
from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)

CUSTOM_FONTS_DIR = os.path.join("static", "fonts", "custom")
FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}
MAX_FONT_FILE_SIZE = 20 * 1024 * 1024  # 20 MB per file


def _derive_family(filename):
    """Derive a font-family name from a filename like 'JetBrainsMono-Regular.woff2' → 'JetBrains Mono'."""
    name = os.path.splitext(filename)[0]
    # Strip common weight/style suffixes
    name = re.sub(
        r'[-_ ]?(Thin|ExtraLight|UltraLight|Light|Regular|Medium|SemiBold|DemiBold|Bold|ExtraBold|UltraBold|Black|Heavy|Italic|Oblique|Variable|VF)$',
        '', name, flags=re.IGNORECASE
    )
    # Insert spaces before uppercase runs: "JetBrainsMono" → "Jet Brains Mono"
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    # Replace dashes/underscores with spaces
    name = re.sub(r'[-_]+', ' ', name).strip()
    return name or filename


def setup_font_routes():
    router = APIRouter(prefix="/api/fonts", tags=["fonts"])

    @router.get("/custom")
    async def list_custom_fonts():
        """Return available custom fonts grouped by derived family name."""
        os.makedirs(CUSTOM_FONTS_DIR, exist_ok=True)
        families = {}
        for f in sorted(os.listdir(CUSTOM_FONTS_DIR)):
            ext = os.path.splitext(f)[1].lower()
            if ext not in FONT_EXTENSIONS:
                continue
            family = _derive_family(f)
            if family not in families:
                families[family] = []
            families[family].append({
                "file": f,
                "url": f"/static/fonts/custom/{f}",
                "format": ext.lstrip('.'),
            })
        return {"fonts": families}

    @router.post("/custom/upload")
    async def upload_custom_font(request: Request, file: UploadFile = File(...)):
        """Upload a custom font file (.ttf, .otf, .woff, .woff2)."""
        require_admin(request)
        if not file.filename:
            raise HTTPException(400, "No filename provided")
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in FONT_EXTENSIONS:
            raise HTTPException(400, f"Unsupported font format: {ext}. Use .ttf, .otf, .woff, or .woff2")
        # Sanitize filename — keep only alphanumeric, dash, underscore, dot
        safe_name = re.sub(r'[^\w\-.]', '_', file.filename)
        if len(safe_name) > 100:
            safe_name = safe_name[:100] + ext
        os.makedirs(CUSTOM_FONTS_DIR, exist_ok=True)
        dest = os.path.join(CUSTOM_FONTS_DIR, safe_name)
        # Read and write with size limit
        content = await file.read()
        if len(content) > MAX_FONT_FILE_SIZE:
            raise HTTPException(400, f"Font file too large. Maximum size is {MAX_FONT_FILE_SIZE // 1024 // 1024} MB")
        with open(dest, "wb") as f:
            f.write(content)
        family = _derive_family(safe_name)
        logger.info(f"Custom font uploaded: {safe_name} → family '{family}'")
        return {
            "ok": True,
            "file": safe_name,
            "family": family,
            "url": f"/static/fonts/custom/{safe_name}",
            "format": ext.lstrip('.'),
        }

    @router.delete("/custom/{filename}")
    async def delete_custom_font(request: Request, filename: str):
        """Delete a custom font file."""
        require_admin(request)
        # Sanitize to prevent path traversal
        safe_name = os.path.basename(filename)
        path = os.path.join(CUSTOM_FONTS_DIR, safe_name)
        if not os.path.isfile(path):
            raise HTTPException(404, f"Font file not found: {safe_name}")
        os.remove(path)
        logger.info(f"Custom font deleted: {safe_name}")
        return {"ok": True, "file": safe_name}

    @router.post("/google/validate")
    async def validate_google_font(request: Request):
        """Validate a Google Font family name by checking availability.

        Accepts JSON body: {"family": "Inter"}
        Returns: {"valid": true/false, "family": "...", "url": "..."}
        """
        get_current_user(request)
        body = await request.json()
        family = (body.get("family") or "").strip()
        if not family:
            raise HTTPException(400, "Missing 'family' field")
        # Google Fonts CSS2 API URL — returns CSS with @font-face rules
        # We just verify it's a real font by checking if the API returns valid CSS
        import httpx
        css_url = (
            f"https://fonts.googleapis.com/css2"
            f"?family={family.replace(' ', '+')}:wght@400;500;600;700&display=swap"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(css_url)
                if resp.status_code == 200 and "@font-face" in resp.text:
                    return {"valid": True, "family": family, "url": css_url}
                return {"valid": False, "family": family, "reason": "Font not found on Google Fonts"}
        except Exception as e:
            logger.warning(f"Google Fonts validation failed for '{family}': {e}")
            return {"valid": False, "family": family, "reason": str(e)}

    return router
