"""Centralised, environment-driven configuration.

Every tunable lives here and is loaded from the environment so that nothing is
hardcoded in the agents or orchestrator. The single source of truth is the
``Settings`` dataclass produced by :func:`Settings.from_env`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env once, as early as possible, without overriding real env vars that
# were already exported by the shell / CI.
load_dotenv(override=False)

# Project root = directory containing this file. Used to resolve relative paths
# so the tool behaves the same regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _get_int(name: str, default: int) -> int:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _get_float(name: str, default: float) -> float:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _get_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Env value as a comma-separated list that EXTENDS the defaults."""
    raw = _get(name)
    extra = tuple(p.strip().lower() for p in raw.split(",") if p.strip()) if raw else ()
    return tuple(dict.fromkeys(default + extra))  # de-duped, order preserved


def _resolve_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


# High-authority outlets (substring match against the source name, case-insensitive).
DEFAULT_TIER1_SOURCES: tuple[str, ...] = (
    "reuters", "bloomberg", "financial times", "wall street journal", "wsj",
    "cnbc", "the guardian", "washington post", "new york times", "nytimes",
    "associated press", "ap news", "bbc", "the economist", "forbes",
    "marketwatch", "barron", "business insider", "trading economics",
    "s&p global", "moody", "fitch", "morningstar", "nikkei", "financial post",
    "imf", "world bank", "federal reserve", "bank indonesia",
    "tempo", "kompas", "kontan", "bisnis indonesia", "bisnis.com", "antara",
    "detik", "cnbc indonesia", "cnn indonesia", "jakarta post", "jakarta globe",
    "katadata", "investor daily", "the jakarta", "ojk",
)

# Low-authority / SEO / opinion-forecast sources to demote and flag.
DEFAULT_LOW_SOURCES: tuple[str, ...] = (
    "mitrade", "journalarta", "golden ark", "advisory group", "musings",
    "fxleaders", "fxstreet", "dailyforex", "litefinance", "capital.com",
    "blogspot", "medium.com", "substack", "seekingalpha",
    # Non-outlets / grounding placeholders that must never pass as a real source.
    "vertex ai", "google search", "grounding", "youtube", "unknown", "n/a",
)


@dataclass(frozen=True)
class AgentModelConfig:
    """Per-agent model/sampling configuration."""

    model: str
    max_tokens: int
    temperature: float


@dataclass(frozen=True)
class FetchConfig:
    """Full-article fetching/extraction configuration."""

    timeout: int
    max_workers: int
    max_chars: int
    min_chars: int
    user_agent: str


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration for the whole pipeline."""

    api_key: str

    news: AgentModelConfig
    news_fallback_model: str | None
    quant: AgentModelConfig
    editor: AgentModelConfig

    thinking_budget: int

    fetch: FetchConfig

    min_valid_candidates: int
    target_candidates: int
    shortlist_count: int
    min_indonesia_shortlist: int
    highlight_count: int
    max_low_highlights: int

    request_timeout: int
    max_retries: int
    retry_max_wait: int

    output_dir: Path
    cache_dir: Path
    prompts_dir: Path

    source_department: str

    tier1_sources: tuple[str, ...]
    low_sources: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        # Google AI Studio keys live under either name; accept both.
        api_key = _get("GOOGLE_API_KEY") or _get("GEMINI_API_KEY")
        if not api_key:
            raise ConfigError(
                "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
                "key from https://aistudio.google.com/apikey"
            )

        return cls(
            api_key=api_key,
            news=AgentModelConfig(
                model=_get("WMI_NEWS_MODEL", "gemini-flash-latest"),
                max_tokens=_get_int("WMI_NEWS_MAX_TOKENS", 12000),
                temperature=_get_float("WMI_NEWS_TEMPERATURE", 0.3),
            ),
            # Lighter model used automatically if the news model hits a capacity
            # limit (429). The -latest alias tracks whatever lite model Google
            # currently serves, so it survives deprecations. Blank disables fallback.
            news_fallback_model=_get("WMI_NEWS_FALLBACK_MODEL", "gemini-flash-lite-latest"),
            quant=AgentModelConfig(
                model=_get("WMI_QUANT_MODEL", "gemini-flash-latest"),
                max_tokens=_get_int("WMI_QUANT_MAX_TOKENS", 4000),
                temperature=_get_float("WMI_QUANT_TEMPERATURE", 0.2),
            ),
            editor=AgentModelConfig(
                model=_get("WMI_EDITOR_MODEL", "gemini-flash-latest"),
                max_tokens=_get_int("WMI_EDITOR_MAX_TOKENS", 2500),
                temperature=_get_float("WMI_EDITOR_TEMPERATURE", 0.4),
            ),
            thinking_budget=_get_int("WMI_THINKING_BUDGET", 0),
            fetch=FetchConfig(
                timeout=_get_int("WMI_FETCH_TIMEOUT", 20),
                max_workers=_get_int("WMI_FETCH_WORKERS", 6),
                max_chars=_get_int("WMI_FETCH_MAX_CHARS", 6000),
                min_chars=_get_int("WMI_FETCH_MIN_CHARS", 250),
                user_agent=_get(
                    "WMI_FETCH_USER_AGENT",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                ),
            ),
            min_valid_candidates=_get_int("WMI_MIN_VALID_CANDIDATES", 8),
            target_candidates=_get_int("WMI_TARGET_CANDIDATES", 20),
            shortlist_count=_get_int("WMI_SHORTLIST_COUNT", 10),
            # Guarantee national coverage: at least this many Indonesian stories
            # make the shortlist (when the harvest found enough of them).
            min_indonesia_shortlist=_get_int("WMI_MIN_ID_SHORTLIST", 3),
            highlight_count=_get_int("WMI_HIGHLIGHT_COUNT", 6),
            # More low-authority highlights than this trips the review gate.
            max_low_highlights=_get_int("WMI_MAX_LOW_HIGHLIGHTS", 1),
            request_timeout=_get_int("WMI_REQUEST_TIMEOUT", 120),
            max_retries=_get_int("WMI_MAX_RETRIES", 4),
            retry_max_wait=_get_int("WMI_RETRY_MAX_WAIT", 60),
            output_dir=_resolve_path(_get("WMI_OUTPUT_DIR", "output")),
            cache_dir=_resolve_path(_get("WMI_CACHE_DIR", "output")),
            prompts_dir=_resolve_path(_get("WMI_PROMPTS_DIR", "prompts")),
            source_department=_get(
                "WMI_SOURCE_DEPARTMENT", "Research and Education Department"
            ),
            tier1_sources=_get_list("WMI_SOURCE_TIER1", DEFAULT_TIER1_SOURCES),
            low_sources=_get_list("WMI_SOURCE_LOW", DEFAULT_LOW_SOURCES),
        )

    def validate(self) -> None:
        """Fail fast on logically impossible configuration."""
        problems: list[str] = []
        if self.target_candidates < self.min_valid_candidates:
            problems.append(
                f"WMI_TARGET_CANDIDATES ({self.target_candidates}) must be >= "
                f"WMI_MIN_VALID_CANDIDATES ({self.min_valid_candidates})"
            )
        if self.highlight_count < 1:
            problems.append("WMI_HIGHLIGHT_COUNT must be >= 1")
        if self.shortlist_count < self.highlight_count:
            problems.append(
                f"WMI_SHORTLIST_COUNT ({self.shortlist_count}) must be >= "
                f"WMI_HIGHLIGHT_COUNT ({self.highlight_count})"
            )
        if self.target_candidates < self.shortlist_count:
            problems.append(
                f"WMI_TARGET_CANDIDATES ({self.target_candidates}) must be >= "
                f"WMI_SHORTLIST_COUNT ({self.shortlist_count})"
            )
        if not 0 <= self.min_indonesia_shortlist <= self.shortlist_count:
            problems.append(
                f"WMI_MIN_ID_SHORTLIST ({self.min_indonesia_shortlist}) must be "
                f"between 0 and WMI_SHORTLIST_COUNT ({self.shortlist_count})"
            )
        if self.min_valid_candidates < self.highlight_count:
            problems.append(
                f"WMI_MIN_VALID_CANDIDATES ({self.min_valid_candidates}) must be "
                f">= WMI_HIGHLIGHT_COUNT ({self.highlight_count}) so the editor has "
                "enough material"
            )
        if self.thinking_budget < 0:
            problems.append("WMI_THINKING_BUDGET must be >= 0")
        if self.fetch.max_workers < 1:
            problems.append("WMI_FETCH_WORKERS must be >= 1")
        for label, cfg in (("news", self.news), ("quant", self.quant), ("editor", self.editor)):
            if cfg.max_tokens <= 0:
                problems.append(f"{label} max_tokens must be > 0")
            if not 0.0 <= cfg.temperature <= 2.0:
                problems.append(f"{label} temperature must be within [0, 2]")
        if problems:
            raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(problems))

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
