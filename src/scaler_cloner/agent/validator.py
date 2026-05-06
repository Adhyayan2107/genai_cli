"""Deterministic validator for the cloned page.

Runs after every `index.html` write. Returns a structured verdict the loop
can convert into an OBSERVE. The validator is the *only* feedback signal
the agent gets that isn't from a tool — so we keep it specific and cheap.

We deliberately don't validate styles.css or app.js: those are exercised
visually, and over-strict validation creates noise the agent can't fix.
"""

from __future__ import annotations

from dataclasses import dataclass

from selectolax.parser import HTMLParser

_HERO_HINTS = ("hero", "banner", "headline", "intro", "masthead")


@dataclass
class Verdict:
    ok: bool
    missing: list[str]
    notes: list[str]

    def as_observe(self) -> str:
        if self.ok:
            return "validator: index.html OK — header, hero, footer all present"
        bits = ["validator: index.html INCOMPLETE"]
        if self.missing:
            bits.append("missing: " + ", ".join(self.missing))
        if self.notes:
            bits.extend(self.notes)
        bits.append("Fix and write the file again.")
        return " | ".join(bits)


def _has_hero(tree: HTMLParser) -> bool:
    """Heuristic: a hero is the first big <section> with an h1/h2,
    OR any element whose class/id contains a hero-ish word."""
    for hint in _HERO_HINTS:
        if tree.css_first(f'[class*="{hint}"]') or tree.css_first(f'[id*="{hint}"]'):
            return True
    for sec in tree.css("section"):
        if sec.css_first("h1, h2"):
            return True
    # Also accept a top-of-page <main> > h1 pattern
    main = tree.css_first("main")
    if main and main.css_first("h1"):
        return True
    return False


def validate_index_html(html: str) -> Verdict:
    if not html.strip():
        return Verdict(ok=False, missing=["non-empty content"], notes=[])

    tree = HTMLParser(html)
    missing: list[str] = []
    notes: list[str] = []

    if not tree.css_first("header"):
        missing.append("<header>")
    if not _has_hero(tree):
        missing.append("hero section (a <section> with a heading, or any element with class/id containing 'hero')")
    if not tree.css_first("footer"):
        missing.append("<footer>")

    # Soft checks — surfaced as notes, don't fail the verdict on their own
    if not tree.css_first('link[rel="stylesheet"]') and not tree.css_first("style"):
        notes.append("note: no CSS linked or inline — the page will look unstyled")
    if not tree.css_first("title"):
        notes.append("note: no <title> set")

    return Verdict(ok=not missing, missing=missing, notes=notes)
