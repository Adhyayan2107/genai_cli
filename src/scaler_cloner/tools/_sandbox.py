"""Sandbox helpers — every file tool resolves paths through here.

Trust boundary: tool args come from the LLM. We refuse anything that escapes
the run directory under output/<run-id>/.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from scaler_cloner.config import PROJECT_ROOT

_OUTPUT_ROOT = PROJECT_ROOT / "output"


def new_run_id() -> str:
    """Stable, sortable, human-glanceable run id."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{stamp}-{suffix}"


def run_dir(run_id: str) -> Path:
    d = _OUTPUT_ROOT / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_inside(run_id: str, rel_path: str) -> Path:
    """Resolve `rel_path` against the run dir and refuse traversal."""
    base = run_dir(run_id).resolve()
    candidate = (base / rel_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as e:
        raise PermissionError(
            f"path escapes sandbox: {rel_path!r} not under {base}"
        ) from e
    return candidate


def output_root() -> Path:
    return _OUTPUT_ROOT
