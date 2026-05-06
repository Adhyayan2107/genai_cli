"""Sandboxed file write under output/<run-id>/."""

from __future__ import annotations

from ._sandbox import resolve_inside


async def write_file(run_id: str, path: str, content: str) -> dict:
    """Write `content` to `path` (relative to the run dir).

    Returns a small structured outcome — never echoes content back to the model.
    """
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}
    try:
        target = resolve_inside(run_id, path)
    except PermissionError as e:
        return {"ok": False, "error": str(e)}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(target.parents[1])), "bytes": len(content)}
