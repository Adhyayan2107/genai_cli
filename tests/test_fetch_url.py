"""fetch_url against an in-process httpx mock — no network."""

from __future__ import annotations

import httpx
import pytest

from scaler_cloner.tools import fetch_url as fetch_mod


SAMPLE_HTML = """\
<!doctype html>
<html><head>
  <title>Scaler — Master Tech &amp; Scale</title>
  <meta name="description" content="Learn from the best.">
  <style>:root { --accent: #FFA559; --bg: #0a0a0a; }</style>
</head>
<body>
  <header><nav><h1>Scaler</h1></nav></header>
  <main>
    <section class="hero"><h2>Build a career in tech</h2></section>
    <section><h2>Programs</h2></section>
  </main>
  <footer><p>© Scaler</p></footer>
  <script>console.log("ignore me");</script>
</body></html>
"""


@pytest.mark.asyncio
async def test_fetch_url_summarizes(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=SAMPLE_HTML)

    transport = httpx.MockTransport(handler)

    real_async_client = httpx.AsyncClient

    def make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(fetch_mod.httpx, "AsyncClient", make_client)

    out = await fetch_mod.fetch_url("https://example.test/")
    assert out["ok"] is True
    assert out["title"].startswith("Scaler")
    assert out["description"] == "Learn from the best."
    tags = [o["tag"] for o in out["outline"]]
    assert "header" in tags and "footer" in tags and "section" in tags
    assert any(c.lower() == "#ffa559" for c in out["colors"])
    assert "ignore me" not in out["text"]  # script stripped
    assert "Build a career in tech" in out["text"]


@pytest.mark.asyncio
async def test_fetch_url_handles_404(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(fetch_mod.httpx, "AsyncClient", make_client)

    out = await fetch_mod.fetch_url("https://example.test/missing")
    assert out["ok"] is False
    assert out["status"] == 404
