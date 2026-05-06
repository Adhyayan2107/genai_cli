"""Context builder: layering, compression, target injection."""

from __future__ import annotations

from scaler_cloner.agent.context import build_context
from scaler_cloner.agent.schema import AgentStep, Turn


def _t(author: str, **kw) -> Turn:
    return Turn(author=author, step=AgentStep(**kw))


def test_initial_call_no_transcript():
    ctx = build_context([], target_url="https://stripe.com", user_request="clone stripe")
    assert "Site Cloner" in ctx.system
    assert "## Task" in ctx.system
    assert "https://stripe.com" in ctx.system
    assert "## Schema reminder" in ctx.system
    assert "fetch_url" in ctx.system
    assert "screenshot_url" in ctx.system
    assert "look_at" in ctx.system
    assert ctx.history == []
    assert ctx.current == {"role": "user", "content": "clone stripe"}


def test_target_url_changes_task_block():
    a = build_context([], target_url="https://a.com", user_request="x").system
    b = build_context([], target_url="https://b.io", user_request="x").system
    assert "https://a.com" in a and "https://b.io" not in a
    assert "https://b.io" in b and "https://a.com" not in b


def test_memory_block_included_when_nonempty():
    ctx = build_context([], target_url="https://x.com", memory_block="user prefers minimal CSS",
                       user_request="go")
    assert "Long-term memory" in ctx.system
    assert "minimal CSS" in ctx.system


def test_memory_block_omitted_when_empty():
    ctx = build_context([], target_url="https://x.com", memory_block="   ", user_request="go")
    assert "Long-term memory" not in ctx.system


def test_long_transcript_compresses_older_turns():
    transcript = [_t("assistant", step="THINK", content=f"thought {i}") for i in range(10)]
    ctx = build_context(transcript, target_url="https://x.com")
    assert "Earlier steps (compressed)" in ctx.system
    assert "thought 0" in ctx.system
    assert any("thought 9" in m["content"] for m in [ctx.current, *ctx.history])


def test_tool_catalog_lists_all_tools():
    ctx = build_context([], target_url="https://x.com", user_request="go")
    for name in ("fetch_url", "screenshot_url", "look_at", "write_file",
                 "read_file", "list_dir", "open_in_browser"):
        assert name in ctx.system, f"{name} missing from system prompt"
