"""Fetch a URL and return a *summarized* representation for the agent.

We deliberately never return raw HTML to the LLM. Raw scaler.com is ~500KB
and would blow the context budget without adding signal. Instead we extract:
  - title
  - meta description
  - section outline (top-level <section>, <header>, <footer>, <main>, h1/h2)
  - representative color tokens (from inline styles, <style>, and <link rel=stylesheet> heads)
  - cleaned body text, capped

The agent gets enough to reproduce the page; the heavy lifting (writing
matching HTML/CSS) is the LLM's job.
"""

from __future__ import annotations

import re
from collections import Counter

import httpx
from selectolax.parser import HTMLParser

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 ScalerCloner/0.1"
)
_TIMEOUT = httpx.Timeout(15.0, connect=8.0)
_MAX_TEXT_CHARS = 6000
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
_RGB_RE = re.compile(r"rgba?\([^)]+\)")


def _extract_colors(html: str) -> list[str]:
    hex_colors = _HEX_RE.findall(html)
    rgb_colors = _RGB_RE.findall(html)
    counts = Counter(c.lower() for c in hex_colors + rgb_colors)
    return [c for c, _ in counts.most_common(12)]


def _outline(tree: HTMLParser) -> list[dict]:
    outline: list[dict] = []
    for tag in ("header", "main", "section", "footer", "nav"):
        for node in tree.css(tag):
            heading = node.css_first("h1, h2, h3")
            outline.append(
                {
                    "tag": tag,
                    "id": node.attributes.get("id"),
                    "class": node.attributes.get("class"),
                    "heading": heading.text(strip=True)[:120] if heading else None,
                }
            )
            if len(outline) >= 30:
                return outline
    return outline


def _clean_text(tree: HTMLParser) -> str:
    for bad in tree.css("script, style, noscript, svg"):
        bad.decompose()
    body = tree.body
    if body is None:
        return ""
    raw = body.text(separator=" ", strip=True)
    raw = re.sub(r"\s+", " ", raw)
    return raw[:_MAX_TEXT_CHARS]


async def fetch_url(url: str) -> dict:
    """GET the URL, return a small structured summary suitable for an LLM context."""
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,*/*;q=0.8"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=_TIMEOUT, follow_redirects=True) as c:
            resp = await c.get(url)
    except httpx.HTTPError as e:
        return {"ok": False, "url": url, "error": f"http error: {e.__class__.__name__}: {e}"}

    if resp.status_code >= 400:
        return {"ok": False, "url": str(resp.url), "status": resp.status_code,
                "error": f"non-2xx response: {resp.status_code}"}

    html = resp.text
    tree = HTMLParser(html)

    title_node = tree.css_first("title")
    desc_node = tree.css_first('meta[name="description"]')

    return {
        "ok": True,
        "url": str(resp.url),
        "status": resp.status_code,
        "title": title_node.text(strip=True) if title_node else None,
        "description": (desc_node.attributes.get("content") if desc_node else None),
        "outline": _outline(tree),
        "colors": _extract_colors(html),
        "text": _clean_text(tree),
        "bytes": len(html),
    }
