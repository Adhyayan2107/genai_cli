"""Scrollable, monochrome event log."""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static

from scaler_cloner.events import AgentEvent


class ChatLog(VerticalScroll):
    def append_user(self, text: str) -> None:
        self._append("> " + text, "chat-user")

    def append_event(self, ev: AgentEvent) -> None:
        if ev.kind == "step_started":
            return
        if ev.kind == "think":
            self._append("· " + ev.content, "chat-think")
        elif ev.kind == "tool_called":
            self._append(f"⤳ {ev.tool_name}({ev.tool_args or ''})", "chat-tool")
        elif ev.kind == "tool_returned":
            cls = "chat-tool-ok" if ev.ok else "chat-tool-err"
            glyph = "✓" if ev.ok else "✗"
            self._append(f"  {glyph} {ev.content}", cls)
        elif ev.kind == "observe":
            cls = "chat-validator" if ev.ok else "chat-error"
            self._append("◇ " + ev.content, cls)
        elif ev.kind == "output":
            self._append("⏎ " + ev.content, "chat-output")
        elif ev.kind == "error":
            self._append("! " + ev.content, "chat-error")
        elif ev.kind == "memory_updated":
            self._append("· " + ev.content, "chat-memory")

    def _append(self, text: str, css_class: str) -> None:
        line = Static(text, classes=css_class)
        self.mount(line)
        self.scroll_end(animate=False)
