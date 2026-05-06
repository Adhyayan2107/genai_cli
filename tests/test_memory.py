"""Memory: parse, render, host-scoped patches, budget enforcement."""

from __future__ import annotations

from scaler_cloner.agent.memory import (
    Memory,
    SECTION_BUDGETS,
    apply_patch,
    approx_tokens,
    load_memory,
    save_memory,
)
from scaler_cloner.agent.schema import MemoryPatch


_FRESH = """\
# MEMORY.md

> notes

## User preferences
<!-- budget: 500 tokens -->
_(empty)_

## Site knowledge
<!-- budget: 1500 tokens. Sub-bucketed by '### host'. -->
### scaler.com
- header: logo + 5 nav + CTA

### stripe.com
- palette: indigo + white

## Run log
<!-- budget: 1000 tokens, FIFO -->
- 2026-05-04 — first clone
"""


def test_load_round_trip(tmp_path):
    p = tmp_path / "MEMORY.md"
    p.write_text(_FRESH)
    mem = load_memory(p)
    assert "scaler.com" in mem.site_knowledge
    assert "stripe.com" in mem.site_knowledge
    assert "first clone" in mem.run_log


def test_site_bucket_returns_only_host_facts(tmp_path):
    p = tmp_path / "MEMORY.md"
    p.write_text(_FRESH)
    mem = load_memory(p)
    assert "logo + 5 nav" in mem.site_bucket("scaler.com")
    assert "indigo" not in mem.site_bucket("scaler.com")
    assert "indigo" in mem.site_bucket("stripe.com")
    assert mem.site_bucket("unknown.io") == ""


def test_context_block_only_loads_current_host():
    mem = Memory(
        user_preferences="likes minimal css",
        site_knowledge="### scaler.com\n- a\n\n### stripe.com\n- b\n",
        run_log="",
    )
    block = mem.context_block(host="scaler.com")
    assert "scaler.com" in block
    assert "- a" in block
    assert "- b" not in block
    assert "stripe.com" not in block


def test_apply_patch_creates_new_host_bucket():
    mem = Memory()
    out = apply_patch(
        mem,
        MemoryPatch(section="Site knowledge", op="append", content="- palette: blue"),
        host="newco.io",
    )
    assert "### newco.io" in out.site_knowledge
    assert "- palette: blue" in out.site_knowledge


def test_apply_patch_appends_within_existing_host_bucket():
    mem = Memory(site_knowledge="### scaler.com\n- header: logo\n")
    out = apply_patch(
        mem,
        MemoryPatch(section="Site knowledge", op="append", content="- footer: 4 col"),
        host="scaler.com",
    )
    bucket = out.site_bucket("scaler.com")
    assert "header" in bucket and "footer" in bucket


def test_apply_patch_replace_within_host_bucket():
    mem = Memory(site_knowledge="### scaler.com\n- old\n\n### stripe.com\n- keep\n")
    out = apply_patch(
        mem,
        MemoryPatch(section="Site knowledge", op="replace", content="- fresh"),
        host="scaler.com",
    )
    assert "old" not in out.site_bucket("scaler.com")
    assert "fresh" in out.site_bucket("scaler.com")
    assert "keep" in out.site_bucket("stripe.com")


def test_apply_patch_global_user_prefs_unchanged_by_host():
    mem = Memory(user_preferences="likes minimal")
    out = apply_patch(
        mem,
        MemoryPatch(section="User preferences", op="append", content=" + dark mode"),
        host="anything.com",
    )
    assert "dark mode" in out.user_preferences


def test_run_log_fifo_budget():
    long_lines = "\n".join(f"- entry {i}" for i in range(500))
    mem = Memory(run_log=long_lines)
    out = apply_patch(mem, MemoryPatch(section="Run log", op="append", content="- newest"))
    assert "newest" in out.run_log
    assert approx_tokens(out.run_log) <= SECTION_BUDGETS["Run log"]
    assert "entry 0" not in out.run_log


def test_save_renders_all_three_sections(tmp_path):
    p = tmp_path / "MEMORY.md"
    save_memory(p, Memory(user_preferences="likes minimal css"))
    text = p.read_text()
    assert "## User preferences" in text
    assert "## Site knowledge" in text
    assert "## Run log" in text
    assert "Site Cloner" in text
