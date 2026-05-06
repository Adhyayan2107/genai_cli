"""Codex-style prompt — '>' caret + flat Input. No outer border."""

from __future__ import annotations

from textual import on
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Static


class InputBox(Horizontal):
    DEFAULT_CSS = """
    InputBox { height: 3; width: 1fr; }
    InputBox > #caret { width: 2; height: 3; content-align: left middle; color: #d0a875; }
    InputBox > Input  { width: 1fr; height: 3; }
    """

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def compose(self):
        yield Static(">", id="caret")
        yield Input(placeholder="paste a URL · type ‘clone https://stripe.com’", id="prompt")

    @on(Input.Submitted, "#prompt")
    def _on_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self.post_message(self.Submitted(text))

    def focus_input(self) -> None:
        self.query_one("#prompt", Input).focus()
