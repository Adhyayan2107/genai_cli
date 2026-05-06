"""End-to-end loop test with a scripted fake LLM. No network."""

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

    async def complete(self, ctx, *, fast: bool = False):
        if self.i >= len(self.script):
            raise RuntimeError("script exhausted")
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
async def test_loop_writes_file_and_terminates(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    script = [
        AgentStep(step="THINK", content="planning"),
        AgentStep(step="TOOL", tool_name="write_file",
                  tool_args={"path": "index.html",
                             "content": "<header></header><section class='hero'></section><footer></footer>"}),
        AgentStep(step="OUTPUT", content="done"),
    ]
    monkeypatch.setattr(loop_mod, "GeminiClient", lambda cfg: _ScriptedClient(script))
    result = await loop_mod.run_agent("clone https://scaler.com", cfg=_cfg(tmp_path),
                                       write_memory_after=False)
    assert result.target_url == "https://scaler.com"
    assert result.steps == 3
    assert (tmp_path / "output" / result.run_id / "index.html").exists()


@pytest.mark.asyncio
async def test_loop_handles_unknown_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    script = [
        AgentStep(step="TOOL", tool_name="not_a_tool", tool_args={}),
        AgentStep(step="OUTPUT", content="giving up"),
    ]
    monkeypatch.setattr(loop_mod, "GeminiClient", lambda cfg: _ScriptedClient(script))
    result = await loop_mod.run_agent("clone https://x.io", cfg=_cfg(tmp_path),
                                       write_memory_after=False)
    observes = [t for t in result.transcript if t.author == "user" and t.step.step == "OBSERVE"]
    assert any("unknown tool" in o.step.content for o in observes)


@pytest.mark.asyncio
async def test_loop_step_budget_caps_runs(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")
    long_script = [AgentStep(step="THINK", content=f"step {i}") for i in range(20)]
    monkeypatch.setattr(loop_mod, "GeminiClient", lambda cfg: _ScriptedClient(long_script))
    cfg = _cfg(tmp_path)
    result = await loop_mod.run_agent("clone https://x.io", cfg=cfg,
                                       write_memory_after=False)
    assert result.steps == cfg.max_steps
    assert result.final_output == ""


@pytest.mark.asyncio
async def test_loop_no_url_terminates_early(tmp_path, monkeypatch):
    monkeypatch.setattr("scaler_cloner.tools._sandbox._OUTPUT_ROOT", tmp_path / "output")

    # Should never call the LLM.
    class _Boom:
        def __init__(self, cfg): pass
        async def complete(self, ctx, *, fast=False):
            raise AssertionError("should not be called")

    monkeypatch.setattr(loop_mod, "GeminiClient", _Boom)
    result = await loop_mod.run_agent("just do it", cfg=_cfg(tmp_path),
                                       write_memory_after=False)
    assert result.target_url is None
    assert result.steps == 0
    assert "URL" in result.final_output
