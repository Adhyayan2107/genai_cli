"""List the contents of a directory inside the run sandbox."""

from __future__ import annotations

from ._sandbox import resolve_inside, run_dir


async def list_dir(run_id: str, path: str = ".") -> dict:
    try:
        target = resolve_inside(run_id, path) if path not in ("", ".") else run_dir(run_id)
    except PermissionError as e:
        return {"ok": False, "error": str(e)}
    if not target.exists():
        return {"ok": True, "path": path, "entries": []}
    entries = []
    for child in sorted(target.iterdir()):
        entries.append(
            {
                "name": child.name,
                "kind": "dir" if child.is_dir() else "file",
                "bytes": child.stat().st_size if child.is_file() else None,
            }
        )
    return {"ok": True, "path": path, "entries": entries}
