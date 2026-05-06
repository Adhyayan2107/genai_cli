"""ReAct executor — the heart of the agent.

Reads MEMORY.md at start (host-scoped), runs the post-run MemoryWriter after
OUTPUT, and runs the deterministic validator after every successful
`index.html` write.

The target URL is extracted from the user's message; if none is found, the
loop terminates with a request for one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from scaler_cloner.config import Config
from scaler_cloner.events import AgentEvent, EventBus
from scaler_cloner.tools._sandbox import new_run_id, resolve_inside
from scaler_cloner.tools.registry import TOOL_MAP, TOOL_SCHEMAS

from .context import build_context
from .llm import GeminiClient
from .memory import load_memory
from .schema import AgentStep, Turn
from .url import extract_target
from .validator import validate_index_html

_INJECTS_RUN_ID = {s["name"] for s in TOOL_SCHEMAS if s.get("injects_run_id")}


@dataclass
class RunResult:
    run_id: str
    target_url: str | None
    final_output: str
    steps: int
    tool_calls: int
    transcript: list[Turn] = field(default_factory=list)


async def run_agent(
    user_request: str,
    cfg: Config,
    bus: EventBus | None = None,
    *,
    write_memory_after: bool = True,
) -> RunResult:
    bus = bus or EventBus()
    run_id = new_run_id()

    target_url, target_host = extract_target(user_request)
    if not target_url:
        msg = ("No URL found in the request. Try: 'clone https://stripe.com' "
               "or 'clone stripe.com'.")
        await bus.publish(AgentEvent(kind="error", content=msg))
        await bus.publish(AgentEvent(kind="output", content=msg))
        return RunResult(run_id=run_id, target_url=None, final_output=msg,
                         steps=0, tool_calls=0, transcript=[])

    client = GeminiClient(cfg)

    memory = load_memory(cfg.memory_path)
    memory_block = memory.context_block(host=target_host)

    transcript: list[Turn] = [
        Turn(author="user", step=AgentStep(step="START", content=user_request))
    ]
    steps = 0
    tool_calls = 0
    final_output = ""

    await bus.publish(AgentEvent(kind="step_started",
                                 content=user_request,
                                 meta={"run_id": run_id, "target": target_url}))

    while True:
        if steps >= cfg.max_steps:
            await bus.publish(AgentEvent(kind="error",
                                         content=f"step budget exhausted ({cfg.max_steps})"))
            break
        if tool_calls > cfg.max_tool_calls:
            transcript.append(Turn(author="user", step=AgentStep(
                step="OBSERVE",
                content=("Tool budget reached. Stop calling tools and emit OUTPUT "
                         "summarizing what was produced."),
            )))

        ctx = build_context(transcript, target_url=target_url, memory_block=memory_block)
        result = await client.complete(ctx)
        step = result.step
        steps += 1

        transcript.append(Turn(author="assistant", step=step))

        if step.step in ("START", "THINK"):
            await bus.publish(AgentEvent(kind="think", content=step.content))

        elif step.step == "OUTPUT":
            await bus.publish(AgentEvent(kind="output", content=step.content))
            final_output = step.content
            break

        elif step.step == "TOOL":
            tool_calls += 1
            args_for_log = step.tool_args if isinstance(step.tool_args, dict) else {}
            await bus.publish(AgentEvent(
                kind="tool_called",
                tool_name=step.tool_name,
                tool_args=json.dumps(args_for_log, ensure_ascii=False)[:200],
            ))

            obs = await _dispatch_tool(run_id, step)

            await bus.publish(AgentEvent(
                kind="tool_returned",
                tool_name=step.tool_name,
                ok=obs.get("ok", False),
                content=_short_json(obs, 240),
            ))

            transcript.append(Turn(author="user", step=AgentStep(
                step="OBSERVE",
                content=json.dumps(obs, ensure_ascii=False)[:4000],
            )))

            if (step.tool_name == "write_file"
                    and obs.get("ok")
                    and isinstance(step.tool_args, dict)
                    and step.tool_args.get("path") == "index.html"):
                verdict_obs = _validate_run_index(run_id)
                if verdict_obs:
                    await bus.publish(AgentEvent(
                        kind="observe",
                        ok=verdict_obs["ok"],
                        content=verdict_obs["content"],
                    ))
                    transcript.append(Turn(author="user", step=AgentStep(
                        step="OBSERVE",
                        content=verdict_obs["content"],
                    )))

        elif step.step == "OBSERVE":
            await bus.publish(AgentEvent(
                kind="error",
                content="model emitted OBSERVE; only the runtime does that. Reminding.",
            ))
            transcript.append(Turn(author="user", step=AgentStep(
                step="OBSERVE",
                content=("You may not author OBSERVE steps. Only the runtime emits them "
                         "in response to your TOOL calls. Continue with THINK or TOOL or OUTPUT."),
            )))

    if write_memory_after and final_output:
        try:
            from .memory_writer import write_memory
            applied = await write_memory(
                cfg, user_request, final_output, run_id, target_host=target_host
            )
            if applied:
                await bus.publish(AgentEvent(
                    kind="memory_updated",
                    content=f"+{len(applied)} memory patch(es)",
                ))
        except Exception as e:
            await bus.publish(AgentEvent(
                kind="error",
                content=f"memory writer failed: {e.__class__.__name__}",
            ))

    return RunResult(
        run_id=run_id,
        target_url=target_url,
        final_output=final_output,
        steps=steps,
        tool_calls=tool_calls,
        transcript=transcript,
    )


def _validate_run_index(run_id: str) -> dict | None:
    try:
        path = resolve_inside(run_id, "index.html")
    except PermissionError:
        return None
    if not path.exists():
        return None
    verdict = validate_index_html(path.read_text(encoding="utf-8"))
    return {"ok": verdict.ok, "content": verdict.as_observe()}


async def _dispatch_tool(run_id: str, step: AgentStep) -> dict:
    name = step.tool_name or ""
    if name not in TOOL_MAP:
        return {"ok": False, "error": f"unknown tool: {name!r}"}

    args = step.tool_args or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return {"ok": False, "error": "tool_args must be an object, got string"}

    fn = TOOL_MAP[name]
    try:
        if name in _INJECTS_RUN_ID:
            return await fn(run_id=run_id, **args)
        return await fn(**args)
    except TypeError as e:
        return {"ok": False, "error": f"bad tool_args: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def _short_json(obj: dict, n: int) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"
