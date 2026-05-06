"""Subtle Codex-style thinking indicator.

A small grey ▪ that tick-toggles every 0.6s, with a dim italic verb that
rotates every 1.8s. No orange. No pulse. Quiet by design.
"""

from __future__ import annotations

import random

from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

VERBS = [
    "thinking",
    "pondering",
    "scheming",
    "wrangling",
    "hatching",
    "musing",
    "cooking",
    "plotting",
    "weaving",
    "sketching",
    "drafting",
    "tinkering",
]

_GLYPHS = ("▪", " ")  # tick on/off


class ThinkingBubble(Horizontal):
    verb: reactive[str] = reactive("thinking")
    _tick_idx: int = 0
    _ticks_since_verb: int = 0

    def compose(self):
        yield Static(_GLYPHS[0], id="dot")
        yield Static(self.verb + "…", id="verb")

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.6, self._tick, pause=True)

    def _tick(self) -> None:
        self._tick_idx = 1 - self._tick_idx
        self.query_one("#dot", Static).update(_GLYPHS[self._tick_idx])
        self._ticks_since_verb += 1
        if self._ticks_since_verb >= 3:  # 3 * 0.6s = 1.8s
            self._ticks_since_verb = 0
            self.verb = random.choice(VERBS)

    def watch_verb(self, new: str) -> None:
        if self.is_mounted:
            self.query_one("#verb", Static).update(new + "…")

    def start(self, verb: str | None = None) -> None:
        if verb:
            self.verb = verb
        self._timer.resume()
        if self.parent is not None:
            self.parent.add_class("visible")

    def stop(self) -> None:
        self._timer.pause()
        if self.parent is not None:
            self.parent.remove_class("visible")
