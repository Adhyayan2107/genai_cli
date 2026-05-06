"""Wire-format models for the agent loop.

`AgentStep` is what the LLM emits (and what we validate before doing anything).
`Turn` is what the loop appends to its working transcript.
`MemoryPatch` is what the post-run MemoryWriter emits.

Strict on the way in (extra='ignore' — tolerate model adding fields),
strict on the way out (we serialize a known shape).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StepKind = Literal["START", "THINK", "TOOL", "OBSERVE", "OUTPUT"]


class AgentStep(BaseModel):
    """One message in the ReAct loop. Always a single JSON object."""

    model_config = ConfigDict(extra="ignore")

    step: StepKind
    content: str = ""
    tool_name: str | None = None
    tool_args: dict | None = None


class Turn(BaseModel):
    """Internal transcript entry. Author tells us who produced this turn."""

    model_config = ConfigDict(extra="ignore")

    author: Literal["user", "assistant", "tool"]
    step: AgentStep


class MemoryPatch(BaseModel):
    section: Literal["User preferences", "Site knowledge", "Run log"]
    op: Literal["append", "replace", "delete"]
    content: str = Field(default="")
