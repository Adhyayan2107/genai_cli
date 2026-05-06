"""TUI smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from scaler_cloner.config import Config
from scaler_cloner.tui.app import SiteClonerApp
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


def _log_text(log: ChatLog) -> str:
    return "\n".join(str(c.render()) for c in log.children)


@pytest.mark.asyncio
async def test_app_composes(tmp_path):
    app = SiteClonerApp(_cfg(tmp_path))
    async with app.run_test(size=(120, 40)):
        assert app.query_one(ChatLog) is not None
        assert app.query_one(InputBox) is not None
        assert app.query_one(StatusBar) is not None
        assert app.query_one(ThinkingBubble) is not None
        text = _log_text(app.query_one(ChatLog)).lower()
        assert "welcome" in text
        assert "url" in text  # new generalist prompt mentions URL


@pytest.mark.asyncio
async def test_app_resizes_cleanly(tmp_path):
    app = SiteClonerApp(_cfg(tmp_path))
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
    app = SiteClonerApp(_cfg(tmp_path))
    async with app.run_test(size=(120, 40)) as pilot:
        bubble = app.query_one(ThinkingBubble)
        bubble.start("scheming")
        await pilot.pause()
        assert bubble.parent.has_class("visible")
        assert bubble.verb == "scheming"
        bubble.stop()
        await pilot.pause()
        assert not bubble.parent.has_class("visible")
