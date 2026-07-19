"""Thin, resilient wrapper around the Google Gemini API (google-genai SDK).

Responsibilities:
* construct a single shared client from :class:`config.Settings`;
* run generations with conservative retry/backoff that honours the ``retryDelay``
  Gemini returns on 429 (RESOURCE_EXHAUSTED);
* expose web-search *grounding* (Google Search) for the research agent, the JSON
  response mode for the reasoning agents, and the grounding query trail for
  transparency/logging.

Note: Gemini does not allow combining Google Search grounding with the JSON
response mode in a single call, so the research agent runs WITHOUT JSON mode and
relies on prompt instructions + the robust parser in ``parsing.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import errors, types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from config import Settings
from logging_utils import get_logger

log = get_logger("gemini")


class EmptyResponseError(RuntimeError):
    """Model returned no usable text (safety block, or the whole output budget
    was consumed by the grounding/tool loop). Transient in practice — retryable."""


@dataclass
class ChatResult:
    content: str
    grounding_queries: list[str]
    model: str
    usage: dict[str, Any] | None


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    # Some SDK errors expose the status on a nested response.
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _is_retryable(exc: BaseException) -> bool:
    """Retry on rate limits (429), transient server errors (5xx), and empty output."""
    if isinstance(exc, (errors.ServerError, EmptyResponseError)):
        return True
    code = _status_code(exc)
    if code is None:
        return False
    return code == 429 or 500 <= code < 600


def is_capacity_error(exc: BaseException) -> bool:
    """True when a model can't handle a request right now (warrants fallback)."""
    code = _status_code(exc)
    return code in (429, 413, 503)


_RETRY_PATTERNS = (
    re.compile(r"retryDelay['\"]?\s*[:=]\s*['\"]?([\d.]+)s", re.IGNORECASE),
    re.compile(r"try again in\s+([\d.]+)\s*s", re.IGNORECASE),
    re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE),
)


def _retry_after_seconds(exc: BaseException) -> float | None:
    text = str(exc)
    for pattern in _RETRY_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(timeout=settings.request_timeout * 1000),
        )

    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool = True,
        web_search: bool = False,
    ) -> ChatResult:
        settings = self._settings

        def _wait(retry_state) -> float:  # type: ignore[no-untyped-def]
            exc = retry_state.outcome.exception() if retry_state.outcome else None
            hinted = _retry_after_seconds(exc) if exc else None
            if hinted is not None:
                hinted += 2.0  # small buffer so we land after the window clears
            backoff = wait_exponential(multiplier=2, min=2, max=settings.retry_max_wait)(
                retry_state
            )
            wait = min(max(hinted or 0.0, backoff), float(settings.retry_max_wait))
            log.warning(
                "Gemini call failed (%s); retrying in %.1fs (attempt %d/%d)",
                type(exc).__name__ if exc else "?",
                wait,
                retry_state.attempt_number,
                settings.max_retries,
            )
            return wait

        @retry(
            retry=retry_if_exception(_is_retryable),
            wait=_wait,
            stop=stop_after_attempt(settings.max_retries),
            reraise=True,
        )
        def _call() -> ChatResult:
            config = self._build_config(
                system_prompt, max_tokens, temperature, json_mode, web_search
            )
            try:
                resp = self._client.models.generate_content(
                    model=model, contents=user_prompt, config=config
                )
            except errors.ClientError as exc:
                # Some model generations reject the thinking_budget knob (older
                # ones don't support thinking, newer ones use thinking_level).
                # Retry once without it before treating the attempt as failed.
                if "thinking" in str(exc).lower():
                    log.info(
                        "Model %s rejected thinking config; retrying without it.",
                        model,
                    )
                    config = self._build_config(
                        system_prompt,
                        max_tokens,
                        temperature,
                        json_mode,
                        web_search,
                        include_thinking=False,
                    )
                    resp = self._client.models.generate_content(
                        model=model, contents=user_prompt, config=config
                    )
                else:
                    raise
            content = (resp.text or "").strip()
            if not content:
                # Empty text usually means a safety block or the grounding loop
                # ate the whole output budget. Raise retryable so tenacity re-runs.
                reason = _finish_reason(resp)
                raise EmptyResponseError(
                    f"Gemini returned empty content (finish_reason={reason})."
                )
            return ChatResult(
                content=content,
                grounding_queries=_grounding_queries(resp),
                model=model,
                usage=_usage(resp),
            )

        return _call()

    def _build_config(
        self,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        web_search: bool,
        include_thinking: bool = True,
    ) -> "types.GenerateContentConfig":
        kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if include_thinking:
            kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=self._settings.thinking_budget
            )
        if web_search:
            # Grounding cannot be combined with JSON response mode.
            kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        elif json_mode:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs)


def _finish_reason(resp: Any) -> str:
    try:
        return str(resp.candidates[0].finish_reason)
    except Exception:  # noqa: BLE001
        return "unknown"


def _grounding_queries(resp: Any) -> list[str]:
    try:
        meta = resp.candidates[0].grounding_metadata
        queries = getattr(meta, "web_search_queries", None)
        return list(queries) if queries else []
    except Exception:  # noqa: BLE001
        return []


def _usage(resp: Any) -> dict[str, Any] | None:
    meta = getattr(resp, "usage_metadata", None)
    if meta is None:
        return None
    try:
        return {
            "prompt_tokens": getattr(meta, "prompt_token_count", None),
            "output_tokens": getattr(meta, "candidates_token_count", None),
            "total_tokens": getattr(meta, "total_token_count", None),
        }
    except Exception:  # noqa: BLE001
        return None
