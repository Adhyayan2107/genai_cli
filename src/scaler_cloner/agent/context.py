"""Layered context assembler.

Layout, top to bottom of the system block:
  [SYSTEM]   identity, schema, hard rules, tool catalog
  [TASK]     the cloning goal — target URL is parameterized
  [MEMORY]   relevant sections from MEMORY.md (lazy-loaded)
  [SUMMARY]  compressed summary of older completed steps
  [REMINDER] schema repeated at the bottom (recency + primacy)

RECENT turns and CURRENT prompt go in the `history` / `current` fields
(separately from the system block) so prompt caching works on the stable
prefix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scaler_cloner.tools.registry import schema_for_prompt

from .schema import Turn

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_RECENT_WINDOW = 6


def _load(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _system_block() -> str:
    base = _load("system.md").replace("{TOOL_CATALOG}", schema_for_prompt())
    examples = _load("examples.md")
    return f"{base}\n\n## Examples\n\n{examples}".strip()


def _task_block(target_url: str) -> str:
    return (
        "## Task\n\n"
        f"Clone the website at **{target_url}** into `output/<run-id>/`. "
        "Produce `index.html`, `styles.css`, and `app.js`.\n\n"
        "Acceptance:\n"
        "- `index.html` contains a `<header>`, a hero section, and a `<footer>`\n"
        "- The page opens in a browser without errors and visually resembles the source\n"
        "- CSS and JS are linked from index.html (no inline bundles)"
    )


_REMINDER = (
    "## Schema reminder\n\n"
    "Reply with EXACTLY one JSON object: "
    '{ "step": "...", "content": "...", "tool_name": "...", "tool_args": {...} }. '
    "No prose outside the JSON. No markdown fences."
)


@dataclass
class BuiltContext:
    system: str
    history: list[dict]
    current: dict


def _summarize(older: list[Turn]) -> str:
    if not older:
        return ""
    lines = []
    for t in older:
        s = t.step
        if s.step == "TOOL":
            lines.append(f"- TOOL {s.tool_name}({_short_args(s.tool_args)})")
        elif s.step == "OBSERVE":
            lines.append(f"- OBSERVE {_short(s.content, 80)}")
        elif s.step == "THINK":
            lines.append(f"- THINK {_short(s.content, 80)}")
        elif s.step == "START":
            lines.append(f"- START {_short(s.content, 80)}")
    return "## Earlier steps (compressed)\n\n" + "\n".join(lines)


def _short(text: str, n: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _short_args(args: dict | None) -> str:
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        sv = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        parts.append(f"{k}={_short(str(sv), 40)}")
    return ", ".join(parts)


def build_context(
    transcript: list[Turn],
    *,
    target_url: str,
    memory_block: str = "",
    user_request: str | None = None,
) -> BuiltContext:
    """Assemble the layered context. `target_url` parameterizes the Task block."""
    if len(transcript) > _RECENT_WINDOW:
        older, recent = transcript[:-_RECENT_WINDOW], transcript[-_RECENT_WINDOW:]
    else:
        older, recent = [], transcript

    summary_block = _summarize(older)

    parts = [_system_block(), _task_block(target_url)]
    if memory_block.strip():
        parts.append("## Long-term memory\n\n" + memory_block.strip())
    if summary_block:
        parts.append(summary_block)
    parts.append(_REMINDER)
    system = "\n\n".join(parts)

    history: list[dict] = []
    for t in recent:
        role = "assistant" if t.author == "assistant" else "user"
        history.append({"role": role, "content": t.step.model_dump_json(exclude_none=True)})

    if user_request is not None and not transcript:
        current = {"role": "user", "content": user_request}
    else:
        if recent:
            last = recent[-1]
            history = history[:-1]
            current = {
                "role": "user" if last.author != "assistant" else "assistant",
                "content": last.step.model_dump_json(exclude_none=True),
            }
        else:
            current = {"role": "user", "content": user_request or ""}

    return BuiltContext(system=system, history=history, current=current)
