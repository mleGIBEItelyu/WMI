"""Robust extraction of JSON payloads from LLM text output.

LLMs — even in JSON mode — occasionally wrap their answer in prose, markdown
code fences, or a top-level object when a list was requested. These helpers
recover the intended structure without crashing the pipeline.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)

# Keys a model commonly uses to wrap a list (e.g. {"news": [...]}).
_LIST_WRAPPER_KEYS = (
    "news",
    "candidates",
    "news_candidates",
    "items",
    "results",
    "data",
    "scored_news",
    "articles",
    "list",
)


def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _find_balanced(text: str, open_ch: str, close_ch: str) -> str | None:
    """Return the first balanced ``open_ch..close_ch`` span, respecting strings."""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _loads(candidate: str) -> Any:
    return json.loads(candidate)


def parse_json(text: str) -> Any:
    """Best-effort parse of any JSON value embedded in ``text``."""
    if text is None:
        raise ValueError("Cannot parse JSON from empty response")
    cleaned = _strip_fences(text)

    # 1) straight parse
    try:
        return _loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2) first balanced array, then first balanced object
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        span = _find_balanced(cleaned, open_ch, close_ch)
        if span:
            try:
                return _loads(span)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No valid JSON found in response: {text[:200]!r}...")


def _salvage_objects(text: str) -> list[dict[str, Any]]:
    """Recover all complete top-level ``{...}`` objects from (possibly truncated)
    text. Used as a fallback when a JSON array was cut off mid-stream."""
    objects: list[dict[str, Any]] = []
    i = 0
    n = len(text)
    while i < n:
        start = text.find("{", i)
        if start == -1:
            break
        span = _find_balanced(text[start:], "{", "}")
        if span is None:
            # Unbalanced from here (e.g. the truncated final item, or the outer
            # wrapper object). Skip this brace and look for inner objects.
            i = start + 1
            continue
        try:
            obj = json.loads(span)
            if isinstance(obj, dict):
                objects.append(obj)
        except json.JSONDecodeError:
            pass
        i = start + len(span)
    return objects


def extract_list(text: str) -> list[Any]:
    """Extract a JSON list, unwrapping a single-list object if needed."""
    try:
        parsed = parse_json(text)
    except ValueError:
        # The payload may be a truncated array; salvage whatever complete
        # objects we can rather than losing everything.
        salvaged = _salvage_objects(_strip_fences(text))
        if salvaged:
            return salvaged
        raise
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        # Prefer well-known wrapper keys, then fall back to the first list value.
        for key in _LIST_WRAPPER_KEYS:
            if isinstance(parsed.get(key), list):
                return parsed[key]
        for value in parsed.values():
            if isinstance(value, list):
                return value
        # A single object => treat as a one-element list.
        return [parsed]
    raise ValueError(f"Expected a JSON list, got {type(parsed).__name__}")


def extract_object(text: str) -> dict[str, Any]:
    """Extract a JSON object."""
    parsed = parse_json(text)
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    raise ValueError(f"Expected a JSON object, got {type(parsed).__name__}")
