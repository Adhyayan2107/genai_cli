"""ASCII banner shown once on app mount."""

from __future__ import annotations

from textual.widgets import Static

BANNER = r"""
██╗   ██╗██╗██████╗ ███████╗      ██████╗ ██████╗ ██████╗ ███████╗██████╗
██║   ██║██║██╔══██╗██╔════╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
██║   ██║██║██████╔╝█████╗       ██║     ██║   ██║██║  ██║█████╗  ██████╔╝
╚██╗ ██╔╝██║██╔══██╗██╔══╝       ██║     ██║   ██║██║  ██║██╔══╝  ██╔══██╗
 ╚████╔╝ ██║██████╔╝███████╗     ╚██████╗╚██████╔╝██████╔╝███████╗██║  ██║
  ╚═══╝  ╚═╝╚═════╝ ╚══════╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
"""


class Banner(Static):
    DEFAULT_CSS = ""

    def __init__(self, **kw) -> None:
        super().__init__(BANNER.strip("\n"), **kw)


TAGLINE = "a clone specialist · point it at a URL · ⌘+c to quit"
