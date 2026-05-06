"""Render a URL with headless Chromium (Playwright) and save a PNG inside the sandbox.

Trust boundary: Playwright is sandboxed-ish (it's a real browser) but we still
restrict the OUTPUT path to the run dir. URL is freeform — same posture as
fetch_url. Local files go through `file://` automatically.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ._sandbox import resolve_inside

_DEFAULT_VIEWPORT = {"width": 1440, "height": 900}
_TIMEOUT_MS = 20_000
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "ScalerCloner/0.1"
)


async def screenshot_url(
    run_id: str,
    url: str,
    path: str = "_ref/page.png",
    full_page: bool = True,
) -> dict:
    """Save a screenshot of `url` to `path` (relative to the run dir).

    Returns {ok, path, bytes, width, height} on success.
    """
    if not isinstance(url, str) or not url.strip():
        return {"ok": False, "error": "url required"}

    # Normalize bare local paths to file:// URLs (so the agent can screenshot
    # files it just wrote without thinking about schemes).
    parsed = urlparse(url)
    if not parsed.scheme:
        try:
            local = resolve_inside(run_id, url)
        except PermissionError as e:
            return {"ok": False, "error": str(e)}
        if not local.exists():
            return {"ok": False, "error": f"not found: {url}"}
        url = local.as_uri()

    try:
        out_path = resolve_inside(run_id, path)
    except PermissionError as e:
        return {"ok": False, "error": str(e)}
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": (
            "playwright not installed. Run: "
            ".venv/bin/pip install playwright && .venv/bin/playwright install chromium"
        )}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(
                    viewport=_DEFAULT_VIEWPORT, user_agent=_USER_AGENT
                )
                page = await ctx.new_page()
                await page.goto(url, wait_until="networkidle", timeout=_TIMEOUT_MS)
                # Give CSS animations a beat to settle.
                await page.wait_for_timeout(400)
                await page.screenshot(path=str(out_path), full_page=full_page)
            finally:
                await browser.close()
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    size = out_path.stat().st_size
    return {
        "ok": True,
        "path": path,
        "bytes": size,
        "viewport": f"{_DEFAULT_VIEWPORT['width']}x{_DEFAULT_VIEWPORT['height']}",
        "full_page": full_page,
    }
