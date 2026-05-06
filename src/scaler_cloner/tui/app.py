"""Root Textual app — VIBE-CODER edition.

Layout (top to bottom):
  banner (block letters, shown once)
  tagline
  chat (1fr, monochrome event log)
  thinking row (single ▪ + dim verb, only when active)
  thin rule + '>' prompt
  status bar
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Static

from scaler_cloner.agent.loop import run_agent
from scaler_cloner.config import Config
from scaler_cloner.events import AgentEvent, EventBus

from .widgets.banner import Banner, TAGLINE
from .widgets.chat_log import ChatLog
from .widgets.input_box import InputBox
from .widgets.status_bar import StatusBar
from .widgets.thinking import ThinkingBubble

_KIND_TO_VERB = {
    "step_started": "thinking",
    "think": "pondering",
    "tool_called": "fetching",
    "tool_returned": "weaving",
    "observe": "checking",
    "memory_updated": "remembering",
}


class VibeCoderApp(App):
    CSS_PATH = Path(__file__).parent / "theme.tcss"
    TITLE = "vibe-coder"

    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True),
        Binding("ctrl+l", "clear_chat", "clear"),
        Binding("escape", "focus_input", "focus input", show=False),
    ]

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self._cfg = cfg
        self._bus = EventBus()
        self._agent_task: asyncio.Task | None = None
        self._pump_task: asyncio.Task | None = None
        self._steps = 0
        self._tool_calls = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("vibe-coder", id="title")
            yield Static(self._cfg.model, id="meta")
        yield Banner(id="banner")
        yield Static(TAGLINE, id="banner-tag")
        with Container(id="chat"):
            yield ChatLog(id="chatlog")
        with Container(id="thinking-row"):
            yield ThinkingBubble()
        with Container(id="input-row"):
            yield InputBox(id="inputbox")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.query_one(StatusBar).update_status(
            model=self._cfg.model, steps=0, tool_calls=0, run_id="—"
        )
        # Defer focus until children are mounted and laid out.
        self.call_after_refresh(self._focus_prompt)

    def _focus_prompt(self) -> None:
        self.query_one(InputBox).focus_input()

    @on(InputBox.Submitted)
    def _on_submit(self, event: InputBox.Submitted) -> None:
        if self._agent_task and not self._agent_task.done():
            self.query_one(ChatLog)._append(
                "! agent is busy — wait or ctrl+c", "chat-error"
            )
            return
        self.query_one(ChatLog).append_user(event.text)
        self._steps = 0
        self._tool_calls = 0
        self._start_agent(event.text)

    def _start_agent(self, prompt: str) -> None:
        self.query_one(ThinkingBubble).start("thinking")
        self._pump_task = asyncio.create_task(self._pump_events())
        self._agent_task = asyncio.create_task(self._run(prompt))

    async def _run(self, prompt: str) -> None:
        try:
            await run_agent(prompt, cfg=self._cfg, bus=self._bus)
        except Exception as e:
            await self._bus.publish(AgentEvent(
                kind="error", content=f"{e.__class__.__name__}: {e}"
            ))
        finally:
            await asyncio.sleep(0.05)
            self.query_one(ThinkingBubble).stop()

    async def _pump_events(self) -> None:
        log: ChatLog = self.query_one(ChatLog)
        bubble: ThinkingBubble = self.query_one(ThinkingBubble)
        status: StatusBar = self.query_one(StatusBar)
        while True:
            try:
                ev: AgentEvent = await asyncio.wait_for(self._bus.consume(), timeout=0.25)
            except asyncio.TimeoutError:
                if self._agent_task and self._agent_task.done() and self._bus._q.empty():
                    return
                continue
            log.append_event(ev)

            if ev.kind == "tool_called":
                self._tool_calls += 1
            if ev.kind in ("think", "tool_called", "tool_returned", "observe", "step_started"):
                self._steps += 1
            if ev.kind in _KIND_TO_VERB:
                bubble.start(_KIND_TO_VERB[ev.kind])
            if ev.kind == "output":
                bubble.stop()

            run_id = None
            if ev.meta and "run_id" in ev.meta:
                run_id = ev.meta["run_id"]
            status.update_status(
                steps=self._steps,
                tool_calls=self._tool_calls,
                run_id=run_id,
                last_kind=ev.kind,
            )

    def action_clear_chat(self) -> None:
        log = self.query_one(ChatLog)
        for child in list(log.children):
            child.remove()

    def action_focus_input(self) -> None:
        self.query_one(InputBox).focus_input()


# Back-compat aliases
SiteClonerApp = VibeCoderApp
ScalerClonerApp = VibeCoderApp


def run_tui(cfg: Config | None = None) -> None:
    cfg = cfg or Config.load()
    VibeCoderApp(cfg).run()
