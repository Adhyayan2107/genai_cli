"""look_at: sandbox + path checks. Gemini-vision call is mocked."""

from __future__ import annotations

import pytest

from scaler_cloner.tools import look_at as la_mod
from scaler_cloner.tools._sandbox import new_run_id


_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfa\xcf"
    b"\x00\x00\x00\x03\x00\x01\xc0\xc1\x10\xc4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakeResp:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def generate_content(self, **kwargs):
        return _FakeResp("Dark hero with orange CTA, 5-item nav, 3-col footer.")


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.models = _FakeModels()


@pytest.mark.asyncio
async def test_look_at_returns_observations(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(la_mod.genai, "Client", _FakeClient)

    rid = new_run_id()
    img = tmp_path / "output" / rid / "_ref" / "page.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(_PNG_1x1)

    out = await la_mod.look_at(rid, "_ref/page.png")
    assert out["ok"] is True
    assert "orange CTA" in out["observations"]


@pytest.mark.asyncio
async def test_look_at_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    rid = new_run_id()
    out = await la_mod.look_at(rid, "_ref/missing.png")
    assert out["ok"] is False
    assert "not found" in out["error"]


@pytest.mark.asyncio
async def test_look_at_unsupported_ext(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    rid = new_run_id()
    p = tmp_path / "output" / rid / "weird.bmp"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    out = await la_mod.look_at(rid, "weird.bmp")
    assert out["ok"] is False
    assert "unsupported image type" in out["error"]


def test_registry_lists_vision_tools():
    from scaler_cloner.tools.registry import TOOL_MAP, schema_for_prompt

    assert "screenshot_url" in TOOL_MAP
    assert "look_at" in TOOL_MAP
    catalog = schema_for_prompt()
    assert "screenshot_url" in catalog
    assert "look_at" in catalog
