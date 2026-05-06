"""Post-run MemoryWriter — host-scoped.

Runs ONCE after OUTPUT. Sees user request, final OUTPUT, run id, target host,
and current MEMORY.md. Emits zero or more MemoryPatch objects.

The main loop has no write access — only this module does. Memory writes are
best-effort; a writer failure never fails the run.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from google import genai
from google.genai import types
from pydantic import ValidationError

from scaler_cloner.config import Config

from .llm import _extract_json_object, _strip_fences
from .memory import Memory, apply_patch, load_memory, save_memory
from .schema import MemoryPatch

_SYSTEM = """\
You are the MemoryWriter for the Site Cloner agent.

You have just observed one full run. Decide what, if anything, to persist
to MEMORY.md so future runs are smarter.

Rules:
- Output a JSON ARRAY of patches. Empty array `[]` is a valid, common answer.
- Each patch: { "section": "User preferences" | "Site knowledge" | "Run log",
                "op": "append" | "replace" | "delete",
                "content": "..." }
- Site knowledge is bucketed by host. The runtime auto-routes Site-knowledge
  patches into the bucket for THIS run's host — write content as if the bucket
  is "the host", e.g. "- palette: #0066ff, #0a0a0a" (no '### host' header).
- Save User preferences ONLY when the user explicitly stated one ("I like
  minimalist CSS" / "always use system fonts").
- Save Site knowledge ONLY when something concrete and durable was observed
  about THIS host.
- ALWAYS append a one-line entry to "Run log" with today's date, the host,
  and a ≤ 80-char summary.
- Do not duplicate facts already in memory.
- Reply with EXACTLY the JSON array. No prose, no fences.
"""


def _build_prompt(user_request: str, final_output: str, run_id: str,
                  target_host: str | None, mem: Memory) -> str:
    site_bucket = mem.site_bucket(target_host) if target_host else ""
    return (
        f"## Today\n{date.today().isoformat()}\n\n"
        f"## Target host\n{target_host or '(unknown)'}\n\n"
        f"## User request\n{user_request}\n\n"
        f"## Final output from agent\n{final_output}\n\n"
        f"## Run id\n{run_id}\n\n"
        f"## Current memory\n"
        f"### User preferences\n{mem.user_preferences or '(empty)'}\n\n"
        f"### Site knowledge for {target_host or 'host'}\n{site_bucket or '(empty)'}\n\n"
        f"### Run log\n{mem.run_log or '(empty)'}\n"
    )


def _parse_patches(raw: str) -> list[MemoryPatch]:
    text = _strip_fences(raw).strip()
    if text.startswith("{"):
        text = "[" + _extract_json_object(text) + "]"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        try:
            out.append(MemoryPatch.model_validate(item))
        except ValidationError:
            continue
    return out


async def write_memory(
    cfg: Config,
    user_request: str,
    final_output: str,
    run_id: str,
    *,
    target_host: str | None = None,
) -> list[MemoryPatch]:
    mem = load_memory(cfg.memory_path)
    prompt = _build_prompt(user_request, final_output, run_id, target_host, mem)

    client = genai.Client(api_key=cfg.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        response_mime_type="application/json",
        temperature=0.2,
        max_output_tokens=1024,
    )

    try:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=cfg.fast_model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=config,
        )
    except Exception:
        return []

    patches = _parse_patches(resp.text or "")
    new_mem = mem
    applied: list[MemoryPatch] = []
    for p in patches:
        new_mem = apply_patch(new_mem, p, host=target_host)
        applied.append(p)
    if applied:
        save_memory(cfg.memory_path, new_mem)
    return applied
