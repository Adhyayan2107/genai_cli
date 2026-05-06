"""TUI smoke tests — VIBE-CODER edition."""

from __future__ import annotations

from pathlib import Path

import pytest

from scaler_cloner.config import Config
from scaler_cloner.tui.app import VibeCoderApp
from scaler_cloner.tui.widgets.banner import Banner
from scaler_cloner.tui.widgets.chat_log import ChatLog
from scaler_cloner.tui.widgets.input_box import InputBox
from scaler_cloner.tui.widgets.status_bar import StatusBar
from scaler_cloner.tui.widgets.thinking import ThinkingBubble


def _cfg(tmp_path: Path) -> Config:
    return Config(
        gemini_api_key="fake", model="gemini-2.5-pro", fast_model="gemini-2.5-flash",
        max_steps=10, max_tool_calls=5,
        output_dir=tmp_path / "output", memory_path=tmp_path / "MEMORY.md",
    )


@pytest.mark.asyncio
async def test_app_composes_with_banner(tmp_path):
    app = VibeCoderApp(_cfg(tmp_path))
    async with app.run_test(size=(140, 40)):
        assert app.query_one(Banner) is not None
        assert app.query_one(ChatLog) is not None
        assert app.query_one(InputBox) is not None
        assert app.query_one(StatusBar) is not None
        assert app.query_one(ThinkingBubble) is not None


@pytest.mark.asyncio
async def test_app_resizes_cleanly(tmp_path):
    app = VibeCoderApp(_cfg(tmp_path))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.resize_terminal(160, 50)
        await pilot.pause()
        assert app.query_one(ChatLog) is not None
        await pilot.resize_terminal(60, 20)
        await pilot.pause()
        assert app.query_one(ChatLog) is not None


@pytest.mark.asyncio
async def test_thinking_bubble_lifecycle(tmp_path):
    app = VibeCoderApp(_cfg(tmp_path))
    async with app.run_test(size=(140, 40)) as pilot:
        bubble = app.query_one(ThinkingBubble)
        bubble.start("scheming")
        await pilot.pause()
        assert bubble.parent.has_class("visible")
        assert bubble.verb == "scheming"
        bubble.stop()
        await pilot.pause()
        assert not bubble.parent.has_class("visible")


def test_back_compat_aliases():
    from scaler_cloner.tui.app import ScalerClonerApp, SiteClonerApp, VibeCoderApp
    assert ScalerClonerApp is VibeCoderApp
    assert SiteClonerApp is VibeCoderApp
