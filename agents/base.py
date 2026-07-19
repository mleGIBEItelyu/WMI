"""Shared helpers for agents: prompt loading and lenient item validation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence, Type, TypeVar

from pydantic import BaseModel, ValidationError

from config import Settings
from gemini_client import GeminiClient
from logging_utils import get_logger

log = get_logger("agent")

T = TypeVar("T", bound=BaseModel)


class AgentError(RuntimeError):
    """Raised when an agent cannot produce usable output."""


class BaseAgent:
    name = "base"

    def __init__(self, client: GeminiClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._prompt_cache: dict[str, str] = {}

    def load_prompt(self, filename: str) -> str:
        if filename not in self._prompt_cache:
            path: Path = self.settings.prompts_dir / filename
            if not path.exists():
                raise AgentError(f"Prompt file not found: {path}")
            self._prompt_cache[filename] = path.read_text(encoding="utf-8")
        return self._prompt_cache[filename]


def validate_items(
    raw_items: Iterable[object],
    model: Type[T],
    *,
    context: str,
) -> list[T]:
    """Validate each raw dict into ``model``; skip (and log) invalid entries."""
    validated: list[T] = []
    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            log.debug("%s: item %d is not an object, skipping", context, idx)
            continue
        try:
            validated.append(model(**raw))
        except ValidationError as exc:
            log.debug(
                "%s: item %d failed validation (%s), skipping",
                context,
                idx,
                "; ".join(e["msg"] for e in exc.errors()[:2]),
            )
    return validated


def dedupe_by_title(items: Sequence[T]) -> list[T]:
    """Drop items with duplicate normalised titles, keeping first occurrence."""
    seen: set[str] = set()
    out: list[T] = []
    for item in items:
        key = getattr(item, "title", "").strip().lower()
        if key and key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
