"""MEMORY.md — long-term memory for the agent.

Three sections, each with a token budget:
  - User preferences  (≤ 500 tokens)   — global, all runs
  - Site knowledge    (≤ 1500 tokens)  — per-host, sub-bucketed by '### host'
  - Run log           (≤ 1000 tokens, FIFO)

Per-host scoping: when the loop runs against `stripe.com`, only the
`### stripe.com` bucket of Site knowledge is loaded into context. Cloning
a different host doesn't see unrelated facts.

Read path: main loop -> User preferences + Site knowledge[host].
Write path: only the post-run MemoryWriter writes — never the main loop.

Tokens approximated as `chars / 4`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .schema import MemoryPatch

SECTION_NAMES = ("User preferences", "Site knowledge", "Run log")
SECTION_BUDGETS = {
    "User preferences": 500,
    "Site knowledge": 1500,
    "Run log": 1000,
}
_EMPTY_MARKER_RE = re.compile(r"^\s*_\(empty[^)]*\)_\s*$", re.MULTILINE)
_HOST_HEADER_RE = re.compile(r"^###\s+(\S+?)\s*$", re.MULTILINE)


def approx_tokens(text: str) -> int:
    return max(0, (len(text) + 3) // 4)


@dataclass
class Memory:
    user_preferences: str = ""
    # site_knowledge holds the FULL section text incl. ### host buckets.
    site_knowledge: str = ""
    run_log: str = ""

    def section(self, name: str) -> str:
        return {
            "User preferences": self.user_preferences,
            "Site knowledge": self.site_knowledge,
            "Run log": self.run_log,
        }[name]

    def site_bucket(self, host: str) -> str:
        """Return just the body of `### host` inside Site knowledge, or ''."""
        if not host or not self.site_knowledge.strip():
            return ""
        host = host.lower()
        # Split on ### headers; pick the matching one.
        chunks = re.split(r"(?m)^###\s+(\S+?)\s*$", self.site_knowledge)
        # `chunks` is [pre, host1, body1, host2, body2, ...]
        for i in range(1, len(chunks) - 1, 2):
            if chunks[i].lower() == host:
                return chunks[i + 1].strip()
        return ""

    def context_block(self, host: str | None = None) -> str:
        """Render the relevant memory for the current run.

        Includes User preferences (always) and the Site knowledge[host] bucket
        (only if non-empty). Empty placeholders are skipped entirely so the
        context builder can omit the whole section.
        """
        parts = []
        prefs = self.user_preferences.strip()
        if prefs and not _EMPTY_MARKER_RE.match(prefs):
            parts.append(f"### User preferences\n{prefs}")
        if host:
            bucket = self.site_bucket(host)
            if bucket and not _EMPTY_MARKER_RE.match(bucket):
                parts.append(f"### Site knowledge — {host}\n{bucket}")
        return "\n\n".join(parts)


def _split_sections(md: str) -> dict[str, str]:
    out = {name: "" for name in SECTION_NAMES}
    current: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and m.group(1) in SECTION_NAMES:
            if current is not None:
                out[current] = _clean(buf)
            current = m.group(1)
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = _clean(buf)
    return out


def _clean(buf: list[str]) -> str:
    text = "\n".join(buf).strip()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
    return text


def load_memory(path: Path) -> Memory:
    if not path.exists():
        return Memory()
    md = path.read_text(encoding="utf-8")
    sections = _split_sections(md)
    return Memory(
        user_preferences=sections["User preferences"],
        site_knowledge=sections["Site knowledge"],
        run_log=sections["Run log"],
    )


def _render(mem: Memory) -> str:
    def block(name: str, body: str) -> str:
        budget = SECTION_BUDGETS[name]
        comment = f"<!-- budget: {budget} tokens"
        if name == "Run log":
            comment += ", FIFO"
        if name == "Site knowledge":
            comment += ". Sub-bucketed by '### host'."
        comment += " -->"
        body = body.strip() or "_(empty)_"
        return f"## {name}\n{comment}\n{body}"

    return (
        "# MEMORY.md\n\n"
        "> Long-term memory for the Site Cloner agent.\n"
        "> Read by the context builder at the start of each turn.\n"
        "> Written only by the post-run `MemoryWriter` step.\n\n"
        + "\n\n".join([
            block("User preferences", mem.user_preferences),
            block("Site knowledge", mem.site_knowledge),
            block("Run log", mem.run_log),
        ])
        + "\n"
    )


def _enforce_budget(name: str, body: str) -> str:
    budget = SECTION_BUDGETS[name]
    if approx_tokens(body) <= budget:
        return body
    if name == "Run log":
        lines = body.splitlines()
        while lines and approx_tokens("\n".join(lines)) > budget:
            lines.pop(0)
        return "\n".join(lines)
    while approx_tokens(body) > budget:
        body = "\n".join(body.splitlines()[1:])
    return body


def _set_or_append_host_bucket(section_body: str, host: str, op: str, content: str) -> str:
    """Update the `### host` bucket inside the full Site knowledge section."""
    host = host.lower()
    pattern = re.compile(
        r"(?ms)^###\s+" + re.escape(host) + r"\s*$\n(.*?)(?=^###\s+\S|\Z)"
    )
    m = pattern.search(section_body)
    if op == "delete":
        if m:
            return (section_body[: m.start()] + section_body[m.end():]).strip()
        return section_body
    new_body = content.strip() if op == "replace" else (
        ((m.group(1).strip() + "\n") if m else "") + content.strip()
    )
    block = f"### {host}\n{new_body}\n"
    if m:
        return section_body[: m.start()] + block + section_body[m.end():]
    sep = "\n\n" if section_body.strip() else ""
    return (section_body.rstrip() + sep + block).strip()


def apply_patch(mem: Memory, patch: MemoryPatch, *, host: str | None = None) -> Memory:
    section = patch.section
    current = mem.section(section)

    if section == "Site knowledge" and host:
        new = _set_or_append_host_bucket(current, host, patch.op, patch.content)
    else:
        if patch.op == "replace":
            new = patch.content.strip()
        elif patch.op == "delete":
            new = ""
        else:
            sep = "\n" if current.strip() and patch.content.strip() else ""
            new = (current + sep + patch.content).strip() if current.strip() else patch.content.strip()
    new = _enforce_budget(section, new)
    return Memory(
        user_preferences=new if section == "User preferences" else mem.user_preferences,
        site_knowledge=new if section == "Site knowledge" else mem.site_knowledge,
        run_log=new if section == "Run log" else mem.run_log,
    )


def save_memory(path: Path, mem: Memory) -> None:
    path.write_text(_render(mem), encoding="utf-8")
