"""Runtime configuration. Loaded once at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    gemini_api_key: str
    model: str
    fast_model: str
    max_steps: int
    max_tool_calls: int
    output_dir: Path
    memory_path: Path

    @classmethod
    def load(cls) -> "Config":
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and fill it in."
            )
        return cls(
            gemini_api_key=key,
            model=os.environ.get("SCALER_CLONER_MODEL", "gemini-2.5-pro"),
            fast_model=os.environ.get("SCALER_CLONER_FAST_MODEL", "gemini-2.5-flash"),
            max_steps=int(os.environ.get("SCALER_CLONER_MAX_STEPS", "25")),
            max_tool_calls=int(os.environ.get("SCALER_CLONER_MAX_TOOL_CALLS", "8")),
            output_dir=PROJECT_ROOT / "output",
            memory_path=PROJECT_ROOT / "MEMORY.md",
        )
