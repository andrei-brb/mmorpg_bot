import io
import os
from urllib.parse import quote
from typing import Any, Dict, Optional

import aiohttp


def get_render_api_base_url() -> Optional[str]:
    """
    Base URL for the Vercel Next.js render service.
    Example: https://your-app.vercel.app
    """
    url = (os.getenv("RENDER_API_BASE_URL") or "").strip()
    if not url:
        return None
    return url.rstrip("/")


def get_render_icons_base_url() -> Optional[str]:
    """
    Base URL where item icons are hosted.
    If not set, defaults to RENDER_API_BASE_URL.
    Example: https://your-icons-site.vercel.app
    """
    url = (os.getenv("RENDER_ICONS_BASE_URL") or "").strip()
    if url:
        return url.rstrip("/")
    return get_render_api_base_url()


def icon_url_for_template(template_id: Optional[str]) -> Optional[str]:
    """
    Build a public icon URL for a given item template id.
    Returns None if no base URL is configured.
    """
    base = get_render_icons_base_url()
    if not base:
        return None
    if not template_id:
        return f"{base}/icons/unknown.png"
    return f"{base}/icons/{template_id}.png"


def icon_url_for_item_name(name: Optional[str]) -> Optional[str]:
    """
    Build a public icon URL from the item's display name (e.g. "Iron Sword" -> .../icons/Iron%20Sword.png).
    Use this when icons are named by display name (e.g. "Iron Sword.png") instead of template_id.
    """
    base = get_render_icons_base_url()
    if not base:
        return None
    if not (name and str(name).strip()):
        return f"{base}/icons/unknown.png"
    encoded = quote(str(name).strip(), safe="")
    return f"{base}/icons/{encoded}.png"


async def post_png(path: str, payload: Dict[str, Any], *, timeout_s: float = 15.0) -> io.BytesIO:
    """
    POST JSON payload to RENDER_API_BASE_URL + path and return response bytes as BytesIO.
    Raises aiohttp exceptions on errors.
    """
    base = get_render_api_base_url()
    if not base:
        raise RuntimeError("RENDER_API_BASE_URL is not set")

    url = f"{base}{path}"
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.read()
            return io.BytesIO(data)

