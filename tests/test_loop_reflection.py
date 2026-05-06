"""Validator reflection: bad index.html -> synthetic OBSERVE -> retry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from scaler_cloner.agent import loop as loop_mod
from scaler_cloner.agent.llm import LLMResult
from scaler_cloner.agent.schema import AgentStep
from scaler_cloner.config import Config


@dataclass
class _ScriptedClient:
    script: list[AgentStep]
    i: int = 0

    async def complete(self, ctx, *, fast=False):
        step = self.script[self.i]
        self.i += 1
        return LLMResult(step=step, raw="(fake)", usage=None)


def _cfg(tmp_path: Path) -> Config:
    return Config(
        gemini_api_key="fake", model="x", fast_model="y",
        max_steps=10, max_tool_calls=5,
        output_dir=tmp_path / "output", memory_path=tmp_path / "MEMORY.md",
    )


@pytest.mark.asyncio
async def test_invalid_index_triggers_synthetic_observe(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")

    bad = "<header>only header</header>"
    good = ("<header>x</header><section class='hero'><h1>x</h1></section>"
            "<footer>x</footer>")

    script = [
        AgentStep(step="THINK", content="first attempt"),
        AgentStep(step="TOOL", tool_name="write_file",
                  tool_args={"path": "index.html", "content": bad}),
        AgentStep(step="THINK", content="fixing per validator"),
        AgentStep(step="TOOL", tool_name="write_file",
                  tool_args={"path": "index.html", "content": good}),
        AgentStep(step="OUTPUT", content="done"),
    ]
    monkeypatch.setattr(loop_mod, "GeminiClient", lambda cfg: _ScriptedClient(script))
    cfg = _cfg(tmp_path)
    result = await loop_mod.run_agent("clone https://scaler.com", cfg=cfg,
                                       write_memory_after=False)
    observes = [t.step.content for t in result.transcript
                if t.author == "user" and t.step.step == "OBSERVE"]
    assert any("INCOMPLETE" in o for o in observes)
    assert any("OK" in o for o in observes)
    final = (tmp_path / "output" / result.run_id / "index.html").read_text()
    assert "<footer>" in final
