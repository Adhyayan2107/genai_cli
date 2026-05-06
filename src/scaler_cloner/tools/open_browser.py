"""Open a file inside the run sandbox in the user's default browser."""

from __future__ import annotations

import webbrowser

from ._sandbox import resolve_inside


async def open_in_browser(run_id: str, path: str = "index.html") -> dict:
    try:
        target = resolve_inside(run_id, path)
    except PermissionError as e:
        return {"ok": False, "error": str(e)}
    if not target.exists():
        return {"ok": False, "error": f"not found: {path}"}
    url = target.as_uri()
    opened = webbrowser.open(url)
    return {"ok": opened, "url": url}
