"""Pulsating orange bubble + verb cycler — Claude Code style.

Implementation notes:
  - The bubble is a single ● character whose color cycles between
    #FF6B1A and #FFA559 on a 1.2s sine via Textual's interval timer.
  - The verb is rotated every 1.8s. We pick from a hand-curated list so the
    user gets variety without jitter mid-frame.
  - `start(verb=None)` pins a verb (used when the runtime knows the step kind);
    `start()` rotates them.
  - Hidden by default; the parent toggles `.visible` on the row.
"""

from __future__ import annotations

import math
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


def _lerp_color(t: float) -> str:
    """t in [0,1] -> hex between #FF6B1A and #FFA559."""
    a = (0xFF, 0x6B, 0x1A)
    b = (0xFF, 0xA5, 0x59)
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    bl = int(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


class ThinkingBubble(Horizontal):
    verb: reactive[str] = reactive("thinking")
    _phase: float = 0.0
    _ticks_since_verb: int = 0

    def compose(self):
        yield Static("●", id="dot")
        yield Static(self.verb + "…", id="verb")

    def on_mount(self) -> None:
        # 60 ms tick — smooth enough for a pulse, cheap enough on any terminal.
        self._timer = self.set_interval(0.06, self._tick, pause=True)

    def _tick(self) -> None:
        self._phase += 0.06
        # Sinusoidal in [0,1] over a 1.2s period
        t = 0.5 + 0.5 * math.sin((self._phase / 1.2) * 2 * math.pi)
        dot = self.query_one("#dot", Static)
        dot.styles.color = _lerp_color(t)

        self._ticks_since_verb += 1
        if self._ticks_since_verb >= 30:  # 30 * 60ms = 1.8s
            self._ticks_since_verb = 0
            self.verb = random.choice(VERBS)

    def watch_verb(self, new: str) -> None:
        if self.is_mounted:
            self.query_one("#verb", Static).update(new + "…")

    def start(self, verb: str | None = None) -> None:
        if verb:
            self.verb = verb
        self._timer.resume()
        self.parent.add_class("visible")  # row toggle

    def stop(self) -> None:
        self._timer.pause()
        if self.parent is not None:
            self.parent.remove_class("visible")
