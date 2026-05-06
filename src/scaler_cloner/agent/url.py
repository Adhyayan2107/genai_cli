"""URL extraction from a free-form user request.

We accept either an explicit URL ("clone https://stripe.com") or a bare host
("clone stripe.com" / "clone scaler"). On ambiguity we prefer the FIRST URL
or host-like token. Returns (url, host) — both normalized.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s,;]+", re.IGNORECASE)
_HOST_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b",
    re.IGNORECASE,
)


def extract_target(user_request: str) -> tuple[str | None, str | None]:
    """Return (url, host). Either may be None if extraction failed."""
    if not user_request:
        return None, None

    m = _URL_RE.search(user_request)
    if m:
        url = m.group(0).rstrip(".,;:)\"'")
        host = urlparse(url).hostname or ""
        return url, host.lower() or None

    m = _HOST_RE.search(user_request)
    if m:
        host = m.group(0).lower()
        return f"https://{host}", host

    return None, None
