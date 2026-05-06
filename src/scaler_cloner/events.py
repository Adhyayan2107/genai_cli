"""Async event bus. Agent publishes; TUI consumes. Decoupling boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

EventKind = Literal[
    "step_started",
    "think",
    "tool_called",
    "tool_returned",
    "observe",
    "output",
    "error",
    "memory_updated",
]


@dataclass
class AgentEvent:
    kind: EventKind
    content: str = ""
    tool_name: str | None = None
    tool_args: str | None = None
    ok: bool = True
    meta: dict | None = None


class EventBus:
    """Thin wrapper over asyncio.Queue so the agent never imports the TUI."""

    def __init__(self) -> None:
        self._q: asyncio.Queue[AgentEvent] = asyncio.Queue()

    async def publish(self, event: AgentEvent) -> None:
        await self._q.put(event)

    async def consume(self) -> AgentEvent:
        return await self._q.get()
