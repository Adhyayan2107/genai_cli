"""Status bar: model name, step count, tool calls, run id."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Static


class StatusBar(Horizontal):
    def compose(self):
        yield Static("scaler-cloner", id="left")
        yield Static("", id="middle")
        yield Static("", id="right")

    def update_status(
        self,
        *,
        model: str | None = None,
        steps: int | None = None,
        tool_calls: int | None = None,
        run_id: str | None = None,
        last_kind: str | None = None,
    ) -> None:
        if model is not None:
            self.query_one("#left", Static).update(f"scaler-cloner · {model}")
        bits = []
        if steps is not None:
            bits.append(f"step {steps}")
        if tool_calls is not None:
            bits.append(f"tools {tool_calls}")
        if last_kind:
            bits.append(last_kind)
        self.query_one("#middle", Static).update(" · ".join(bits))
        if run_id is not None:
            self.query_one("#right", Static).update(f"run {run_id}")
