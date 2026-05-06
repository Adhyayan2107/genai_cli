"""Test the JSON-extraction helpers used by the Gemini wrapper.

We don't hit the live API in unit tests — those are integration concerns.
"""

from __future__ import annotations

import pytest

from scaler_cloner.agent.llm import _extract_json_object, _parse_step, _strip_fences
from scaler_cloner.agent.schema import AgentStep


def test_strip_fences_plain_passthrough():
    assert _strip_fences('{"a":1}') == '{"a":1}'


def test_strip_fences_removes_json_fence():
    raw = '```json\n{"a":1}\n```'
    assert _strip_fences(raw) == '{"a":1}'


def test_strip_fences_removes_bare_fence():
    raw = '```\n{"a":1}\n```'
    assert _strip_fences(raw) == '{"a":1}'


def test_extract_object_with_prefix_prose():
    raw = 'Here you go: {"step":"THINK","content":"hi"} thanks!'
    assert _extract_json_object(raw) == '{"step":"THINK","content":"hi"}'


def test_extract_object_handles_nested_braces():
    raw = '{"step":"TOOL","tool_name":"write_file","tool_args":{"path":"a","content":"b"}}'
    assert _extract_json_object(raw) == raw


def test_extract_object_handles_braces_in_strings():
    raw = '{"step":"THINK","content":"a } b"}'
    assert _extract_json_object(raw) == raw


def test_parse_step_valid():
    step = _parse_step('{"step":"THINK","content":"plan it"}')
    assert step == AgentStep(step="THINK", content="plan it")


def test_parse_step_with_fences():
    step = _parse_step('```json\n{"step":"OUTPUT","content":"done"}\n```')
    assert step.step == "OUTPUT"
    assert step.content == "done"


def test_parse_step_invalid_kind_raises():
    with pytest.raises(Exception):
        _parse_step('{"step":"BOGUS","content":""}')
