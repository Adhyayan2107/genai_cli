"""Roundtrip: write -> list -> read."""

from __future__ import annotations

import pytest

from scaler_cloner.tools._sandbox import new_run_id
from scaler_cloner.tools.list_dir import list_dir
from scaler_cloner.tools.read_file import read_file
from scaler_cloner.tools.write_file import write_file


@pytest.mark.asyncio
async def test_write_read_list_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path)
    rid = new_run_id()

    w = await write_file(rid, "index.html", "<html><body>hi</body></html>")
    assert w["ok"] is True
    assert w["bytes"] == 28

    ls = await list_dir(rid, ".")
    assert ls["ok"] is True
    names = [e["name"] for e in ls["entries"]]
    assert "index.html" in names

    r = await read_file(rid, "index.html")
    assert r["ok"] is True
    assert "<html>" in r["content"]


@pytest.mark.asyncio
async def test_write_refuses_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path)
    rid = new_run_id()
    out = await write_file(rid, "../escape.txt", "nope")
    assert out["ok"] is False
    assert "escapes sandbox" in out["error"]


@pytest.mark.asyncio
async def test_read_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path)
    rid = new_run_id()
    out = await read_file(rid, "nope.html")
    assert out["ok"] is False
    assert "not found" in out["error"]
