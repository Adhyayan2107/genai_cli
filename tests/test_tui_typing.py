"""Verify the input field actually accepts keystrokes."""

from __future__ import annotations

from pathlib import Path

import pytest

from scaler_cloner.config import Config
from scaler_cloner.tui.app import VibeCoderApp
from scaler_cloner.tui.widgets.input_box import InputBox
from textual.widgets import Input


def _cfg(tmp_path: Path) -> Config:
    return Config(
        gemini_api_key="fake", model="gemini-2.5-pro", fast_model="gemini-2.5-flash",
        max_steps=10, max_tool_calls=5,
        output_dir=tmp_path / "output", memory_path=tmp_path / "MEMORY.md",
    )


@pytest.mark.asyncio
async def test_keystrokes_land_in_input(tmp_path):
    app = VibeCoderApp(_cfg(tmp_path))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt", Input)
        # Confirm focus is on the prompt
        assert app.focused is prompt, f"focus is {app.focused!r}, expected the Input"
        await pilot.press("h", "i")
        await pilot.pause()
        assert prompt.value == "hi", f"got value {prompt.value!r}"


@pytest.mark.asyncio
async def test_input_box_visible_and_sized(tmp_path):
    """The InputBox region must have non-zero height/width or typing won't work."""
    app = VibeCoderApp(_cfg(tmp_path))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        ib = app.query_one(InputBox)
        # region is a Region(x, y, width, height)
        assert ib.region.width > 10, f"InputBox too narrow: {ib.region}"
        assert ib.region.height >= 1, f"InputBox too short: {ib.region}"
        prompt = app.query_one("#prompt", Input)
        assert prompt.region.width > 0, f"Input collapsed: {prompt.region}"
        assert prompt.region.height >= 1, f"Input zero-height: {prompt.region}"
