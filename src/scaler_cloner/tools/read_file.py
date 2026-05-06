"""Sandboxed file read."""

from __future__ import annotations

from ._sandbox import resolve_inside

_MAX_BYTES = 64 * 1024  # cap so a misbehaving model can't blow up its own context


async def read_file(run_id: str, path: str) -> dict:
    try:
        target = resolve_inside(run_id, path)
    except PermissionError as e:
        return {"ok": False, "error": str(e)}
    if not target.exists():
        return {"ok": False, "error": f"not found: {path}"}
    data = target.read_bytes()
    truncated = len(data) > _MAX_BYTES
    text = data[:_MAX_BYTES].decode("utf-8", errors="replace")
    return {"ok": True, "path": path, "content": text, "truncated": truncated, "bytes": len(data)}
