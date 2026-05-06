"""Gemini client wrapper.

Single entry point: `complete(ctx) -> AgentStep`.

Responsibilities:
  - Call Gemini with response_mime_type='application/json'
  - Retry on transient errors with bounded backoff
  - Strip markdown fences if the model leaks them (it sometimes does)
  - Parse + validate against `AgentStep`. On parse failure, retry once with
    a corrective nudge in the prompt — this is way cheaper than crashing the loop.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import ValidationError

from scaler_cloner.config import Config

from .context import BuiltContext
from .schema import AgentStep

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)
_MAX_RETRIES = 2


@dataclass
class LLMResult:
    step: AgentStep
    raw: str
    usage: dict | None = None


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _extract_json_object(text: str) -> str:
    """Find the first balanced {...} substring. Tolerant to prefix/suffix prose."""
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return text[start:]


def _parse_step(raw: str) -> AgentStep:
    cleaned = _extract_json_object(_strip_fences(raw))
    obj = json.loads(cleaned)
    return AgentStep.model_validate(obj)


class GeminiClient:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._client = genai.Client(api_key=cfg.gemini_api_key)

    async def complete(self, ctx: BuiltContext, *, fast: bool = False) -> LLMResult:
        model = self._cfg.fast_model if fast else self._cfg.model

        # Gemini takes the conversation as `contents`; the system instruction is separate.
        contents: list[types.Content] = []
        for msg in ctx.history:
            role = "user" if msg["role"] != "assistant" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        cur_role = "user" if ctx.current["role"] != "assistant" else "model"
        contents.append(types.Content(role=cur_role, parts=[types.Part(text=ctx.current["content"])]))

        config = types.GenerateContentConfig(
            system_instruction=ctx.system,
            response_mime_type="application/json",
            temperature=0.4,
            max_output_tokens=8192,
        )

        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                )
                raw = resp.text or ""
                step = _parse_step(raw)
                usage = None
                if getattr(resp, "usage_metadata", None):
                    um = resp.usage_metadata
                    usage = {
                        "prompt": getattr(um, "prompt_token_count", None),
                        "output": getattr(um, "candidates_token_count", None),
                        "total": getattr(um, "total_token_count", None),
                    }
                return LLMResult(step=step, raw=raw, usage=usage)
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = e
                # Nudge with a parser hint and try again
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=(
                            "Your previous reply was not valid JSON matching the AgentStep "
                            f"schema ({e.__class__.__name__}). Reply now with EXACTLY one "
                            "JSON object: {step, content, tool_name?, tool_args?}. No prose, no fences."
                        ))],
                    )
                )
                if attempt == _MAX_RETRIES:
                    break
            except Exception as e:  # network / quota / etc
                last_err = e
                if attempt == _MAX_RETRIES:
                    break
                await asyncio.sleep(1.5 * (attempt + 1))

        raise RuntimeError(f"Gemini call failed after {_MAX_RETRIES + 1} attempts: {last_err}")


# Module-level convenience used by tests / older imports
async def complete(*args, **kwargs):
    raise NotImplementedError("Use agent.llm.GeminiClient(cfg).complete(ctx) instead.")
