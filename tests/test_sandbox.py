"""Sandbox: refuse path traversal, allow legit relative paths."""

from __future__ import annotations

import pytest

from scaler_cloner.tools._sandbox import new_run_id, resolve_inside, run_dir


def test_resolve_inside_ok(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path)
    rid = new_run_id()
    p = resolve_inside(rid, "index.html")
    assert p.parent == run_dir(rid)


def test_resolve_inside_refuses_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path)
    rid = new_run_id()
    with pytest.raises(PermissionError):
        resolve_inside(rid, "../../etc/passwd")


def test_resolve_inside_refuses_absolute(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path)
    rid = new_run_id()
    with pytest.raises(PermissionError):
        resolve_inside(rid, "/etc/passwd")
