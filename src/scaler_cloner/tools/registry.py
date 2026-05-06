"""Tool registry — single source of truth for the agent.

Each tool is described once: name, JSON schema, and the async callable.
The agent loop reads `TOOL_SCHEMAS` to render the catalog into the system
prompt, and reads `TOOL_MAP` to dispatch a TOOL step.

`run_id` is injected by the loop, never asked of the LLM — that's a
deterministic concern, not a fuzzy one.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from .fetch_url import fetch_url
from .list_dir import list_dir
from .look_at import look_at
from .open_browser import open_in_browser
from .read_file import read_file
from .screenshot_url import screenshot_url
from .write_file import write_file

ToolFn = Callable[..., Awaitable[dict]]


TOOL_SCHEMAS: list[dict] = [
    {
        "name": "fetch_url",
        "description": (
            "Fetch a public web page and return a small structured summary "
            "(title, description, section outline, dominant colors, cleaned text). "
            "Never returns raw HTML. Use first to gather reference material."
        ),
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "injects_run_id": False,
    },
    {
        "name": "screenshot_url",
        "description": (
            "Render a URL (or a local file path inside the run sandbox) with "
            "headless Chromium and save a PNG to the sandbox. Use to capture a "
            "visual reference of scaler.com and to capture your own output for "
            "self-comparison. Pair with `look_at` to actually see the result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "https://… or a local path"},
                "path": {"type": "string", "default": "_ref/page.png"},
                "full_page": {"type": "boolean", "default": True},
            },
            "required": ["url"],
        },
        "injects_run_id": True,
    },
    {
        "name": "look_at",
        "description": (
            "Look at an image in the run sandbox using a vision model. Returns "
            "concise structured observations (palette, layout, sections, vibe). "
            "Use after `screenshot_url` to understand a reference page or to "
            "audit your own rendered output against the reference."
        ),
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "injects_run_id": True,
    },
    {
        "name": "write_file",
        "description": (
            "Write a UTF-8 text file inside the run sandbox (output/<run-id>/). "
            "Use for index.html, styles.css, app.js."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        "injects_run_id": True,
    },
    {
        "name": "read_file",
        "description": "Read a file previously written under the run sandbox.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "injects_run_id": True,
    },
    {
        "name": "list_dir",
        "description": "List files in the run sandbox (or a subdirectory).",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
            "required": [],
        },
        "injects_run_id": True,
    },
    {
        "name": "open_in_browser",
        "description": (
            "Open a file from the run sandbox in the user's default browser. "
            "Final step of a successful run."
        ),
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "index.html"}},
            "required": [],
        },
        "injects_run_id": True,
    },
]


TOOL_MAP: dict[str, ToolFn] = {
    "fetch_url": fetch_url,
    "screenshot_url": screenshot_url,
    "look_at": look_at,
    "write_file": write_file,
    "read_file": read_file,
    "list_dir": list_dir,
    "open_in_browser": open_in_browser,
}


def schema_for_prompt() -> str:
    """Render the tool catalog as compact text for the system prompt."""
    lines = []
    for s in TOOL_SCHEMAS:
        params = s["parameters"].get("properties", {})
        sig = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
        lines.append(f"- {s['name']}({sig}) — {s['description']}")
    return "\n".join(lines)
