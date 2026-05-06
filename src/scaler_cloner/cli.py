"""Entrypoint.

`site-cloner`            — launches the Textual TUI.
`site-cloner --headless [PROMPT]` — runs the agent and streams events to stdout.

A URL must appear somewhere in the user's request (or default prompt). The
agent itself extracts it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console

from .agent.loop import run_agent
from .config import Config
from .events import AgentEvent, EventBus

DEFAULT_PROMPT = "Clone https://scaler.com into output/<run-id>/."


async def _print_events(bus: EventBus, console: Console, done: asyncio.Event) -> None:
    while not done.is_set() or not bus._q.empty():  # noqa: SLF001
        try:
            ev: AgentEvent = await asyncio.wait_for(bus.consume(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        _render(ev, console)


def _render(ev: AgentEvent, console: Console) -> None:
    if ev.kind == "step_started":
        target = ""
        if ev.meta and "target" in ev.meta:
            target = f" → [italic]{ev.meta['target']}[/]"
        console.print(f"[bold cyan]▸ start[/]{target}  {ev.content}")
    elif ev.kind == "think":
        console.print(f"[dim]·[/] {ev.content}")
    elif ev.kind == "tool_called":
        console.print(f"[#FFA559]▸ tool[/]   {ev.tool_name}({ev.tool_args})")
    elif ev.kind == "tool_returned":
        glyph = "[green]✓[/]" if ev.ok else "[red]✗[/]"
        console.print(f"  {glyph} {ev.content}")
    elif ev.kind == "observe":
        color = "magenta" if ev.ok else "red"
        console.print(f"[{color}]◇[/] {ev.content}")
    elif ev.kind == "output":
        console.print(f"[bold green]▸ done[/]  {ev.content}")
    elif ev.kind == "error":
        console.print(f"[bold red]▸ error[/]  {ev.content}")
    elif ev.kind == "memory_updated":
        console.print(f"[#C792EA]▸ memory[/] {ev.content}")


async def _run_headless(prompt: str) -> int:
    cfg = Config.load()
    bus = EventBus()
    console = Console()
    done = asyncio.Event()

    pump = asyncio.create_task(_print_events(bus, console, done))
    try:
        result = await run_agent(prompt, cfg=cfg, bus=bus)
    finally:
        done.set()
        await pump

    console.print()
    console.print(f"[bold]target:[/] {result.target_url or '—'}")
    console.print(f"[bold]run_id:[/] {result.run_id}")
    console.print(f"[bold]steps:[/] {result.steps}  [bold]tool calls:[/] {result.tool_calls}")
    console.print(f"[bold]output dir:[/] output/{result.run_id}/")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="site-cloner")
    parser.add_argument(
        "--headless",
        nargs="?",
        const=DEFAULT_PROMPT,
        default=None,
        help="Skip the TUI; run the agent and stream events to stdout.",
    )
    args = parser.parse_args()

    if args.headless is not None:
        raise SystemExit(asyncio.run(_run_headless(args.headless)))

    try:
        from .tui.app import run_tui
    except Exception as e:
        sys.stderr.write(f"TUI failed to import ({e}); falling back to headless.\n")
        raise SystemExit(asyncio.run(_run_headless(DEFAULT_PROMPT)))

    run_tui()


if __name__ == "__main__":
    main()
