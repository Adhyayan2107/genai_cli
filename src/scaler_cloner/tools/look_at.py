"""Vision tool — let the agent SEE a screenshot it took.

The agent gets text observations back, not the raw image. That keeps the main
ReAct loop's context text-only and cheap; the Gemini-vision call here is
isolated, like a subagent with a single job: describe what it sees.

We use the cheaper `fast_model` because vision summarization isn't reasoning.
"""

from __future__ import annotations

import asyncio

from google import genai
from google.genai import types

from scaler_cloner.config import Config

from ._sandbox import resolve_inside

_PROMPT = """\
You are looking at a screenshot of a webpage. Describe what you see in
concise, structured prose so another agent can replicate the layout in HTML/CSS.

Cover, in this order:
- Overall vibe (light/dark, modern/classic, dense/spacious).
- Color palette: 3-6 dominant colors with rough roles (background, accent, text, CTA).
- Header: logo position, nav items, CTA buttons.
- Hero: headline, subhead, CTA(s), media (image / illustration / gradient).
- Subsequent sections: heading + 1-line description for each.
- Footer: structure (columns, social, legal).
- Typography character (geometric sans, serif, etc — best guess).

If something is unclear, say so. Keep the whole response under 250 words.
Do not output markdown headers or fences — plain prose with line breaks is fine.
"""

_MAX_BYTES = 4 * 1024 * 1024  # safety: refuse >4MB images


async def look_at(run_id: str, path: str) -> dict:
    """Read the image at `path` (sandboxed) and ask Gemini what it shows."""
    try:
        target = resolve_inside(run_id, path)
    except PermissionError as e:
        return {"ok": False, "error": str(e)}
    if not target.exists():
        return {"ok": False, "error": f"not found: {path}"}

    data = target.read_bytes()
    if len(data) > _MAX_BYTES:
        return {"ok": False, "error": f"image too large: {len(data)} bytes"}

    suffix = target.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(suffix)
    if not mime:
        return {"ok": False, "error": f"unsupported image type: {suffix!r}"}

    cfg = Config.load()  # cheap; just env reads
    client = genai.Client(api_key=cfg.gemini_api_key)
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=512)

    contents = [
        types.Content(role="user", parts=[
            types.Part(text=_PROMPT),
            types.Part.from_bytes(data=data, mime_type=mime),
        ])
    ]

    try:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=cfg.fast_model,
            contents=contents,
            config=config,
        )
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    text = (resp.text or "").strip()
    if not text:
        return {"ok": False, "error": "empty vision response"}
    # Cap so a chatty model can't blow up the loop's context.
    return {"ok": True, "path": path, "observations": text[:2000], "bytes": len(data)}
