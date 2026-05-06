"""Real screenshot test against a local HTML file (no network).

Skipped automatically if Playwright/Chromium isn't installed in the env.
"""

from __future__ import annotations

import pytest

from scaler_cloner.tools._sandbox import new_run_id
from scaler_cloner.tools.screenshot_url import screenshot_url
from scaler_cloner.tools.write_file import write_file


def _have_playwright() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _have_playwright(), reason="playwright not installed")
@pytest.mark.asyncio
async def test_screenshot_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    rid = new_run_id()

    # Write a small HTML file inside the run sandbox.
    html = """<!doctype html>
<html><head><title>t</title></head>
<body style="margin:0;background:#FF6B1A;color:#fff;font:bold 80px sans-serif">
  <header style="padding:20px">scaler clone</header>
  <section><h1>hello vision</h1></section>
  <footer>©</footer>
</body></html>"""
    w = await write_file(rid, "index.html", html)
    assert w["ok"]

    # Screenshot it via local-file shortcut (no scheme → file:// auto-resolved)
    out = await screenshot_url(rid, "index.html", path="_ref/mine.png")
    assert out["ok"], out
    assert out["bytes"] > 1000
    assert out["path"] == "_ref/mine.png"

    # File actually exists on disk
    snap = tmp_path / "output" / rid / "_ref" / "mine.png"
    assert snap.exists()
    assert snap.stat().st_size == out["bytes"]


@pytest.mark.asyncio
async def test_screenshot_refuses_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    rid = new_run_id()
    out = await screenshot_url(rid, "https://example.com", path="../escape.png")
    assert out["ok"] is False
    assert "escapes sandbox" in out["error"]


@pytest.mark.asyncio
async def test_screenshot_missing_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    rid = new_run_id()
    out = await screenshot_url(rid, "does_not_exist.html")
    assert out["ok"] is False
    assert "not found" in out["error"]
