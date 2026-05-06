"""Rounded-border prompt input.

The actual `border: round` is applied by the wrapping container in theme.tcss
because Textual's `Input` widget owns its own border slot. Wrapping in a
container lets us color the box and the input independently.
"""

from __future__ import annotations

from textual import on
from textual.containers import Container
from textual.message import Message
from textual.widgets import Input


class InputBox(Container):
    """Container around a single-line Input. Emits `Submitted(text)`."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def compose(self):
        yield Input(placeholder="message — try ‘clone scaler.com’", id="prompt")

    @on(Input.Submitted, "#prompt")
    def _on_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self.post_message(self.Submitted(text))

    def focus_input(self) -> None:
        self.query_one(Input).focus()
