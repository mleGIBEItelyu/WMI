"""Pydantic schemas shared across all agents.

These models are the contract between pipeline stages. Validation is strict on
purpose: malformed or out-of-spec LLM output should fail loudly here rather than
silently producing a broken report.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Allowed news categories. Kept as a constant so prompts and validation stay in
# sync from one place.
CATEGORIES = (
    "macro",
    "geopolitics",
    "equity",
    "commodity",
    "crypto",
    "monetary_policy",
    "other",
)


def _clean_str(value: str) -> str:
    return " ".join(value.split()).strip()


# Where a story is centred. "indonesia" items feed the national-news quota in the
# shortlist; everything else counts as global.
REGIONS = ("indonesia", "global")


class NewsCandidate(BaseModel):
    """A single researched news item (Agent 1 output)."""

    title: str = Field(min_length=3)
    published_date: date
    source: str = Field(min_length=2)
    url: Optional[str] = None
    raw_summary: str = Field(min_length=10)
    category: str
    region: str = "global"

    @field_validator("title", "source", "raw_summary", mode="before")
    @classmethod
    def _strip_text(cls, v: object) -> object:
        return _clean_str(v) if isinstance(v, str) else v

    @field_validator("region", mode="before")
    @classmethod
    def _normalise_region(cls, v: object) -> object:
        if not isinstance(v, str):
            return "global"
        v = v.strip().lower()
        if v in ("indonesia", "id", "idn", "national", "domestic", "lokal", "nasional"):
            return "indonesia"
        return "global"

    @field_validator("category", mode="before")
    @classmethod
    def _normalise_category(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        v = v.strip().lower().replace(" ", "_").replace("-", "_")
        return v if v in CATEGORIES else "other"

    @field_validator("url", mode="before")
    @classmethod
    def _blank_url_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ScoredNews(NewsCandidate):
    """A news item enriched with quantitative impact assessment (Agent 2)."""

    market_impact_score: float = Field(ge=0.0, le=10.0)
    quantitative_evidence: str = Field(min_length=1)
    affected_assets: List[str] = Field(default_factory=list)
    # Indonesia lens: how strongly this story transmits to the Indonesian economy
    # (IHSG, IDR, BI policy, exports, inflation) and through which channel.
    indonesia_impact_score: float = Field(default=0.0, ge=0.0, le=10.0)
    indonesia_impact: str = ""

    @field_validator("market_impact_score", "indonesia_impact_score", mode="before")
    @classmethod
    def _coerce_score(cls, v: object) -> object:
        # LLMs sometimes return "7", "7/10", or "7.5 (high)". Extract the number.
        if isinstance(v, str):
            import re

            m = re.search(r"-?\d+(?:\.\d+)?", v)
            if m:
                return float(m.group())
        return v

    @field_validator("affected_assets", mode="before")
    @classmethod
    def _coerce_assets(cls, v: object) -> object:
        if isinstance(v, str):
            return [part.strip() for part in v.split(",") if part.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return v


class EnrichedNews(ScoredNews):
    """A shortlisted item whose full article body has been fetched (Stage 3)."""

    full_text: Optional[str] = None
    fetch_ok: bool = False

    @field_validator("full_text", mode="before")
    @classmethod
    def _blank_text_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


# Provenance: whether the editor wrote from the full article body or only a snippet.
SOURCED_FULL = "full_article"
SOURCED_SNIPPET = "summary_only"


class HighlightItem(BaseModel):
    title: str = Field(min_length=3)
    date: date
    summary: str = Field(min_length=10)
    source: str = Field(min_length=2)
    # 1-2 sentences correlating the story with the Indonesian economy/markets.
    indonesia_impact: Optional[str] = None
    # Provenance (attached deterministically by the orchestrator, not the LLM).
    url: Optional[str] = None
    sourced_from: str = SOURCED_SNIPPET  # full_article | summary_only
    source_tier: str = "tier2"           # tier1 | tier2 | low

    @field_validator("title", "summary", "source", "indonesia_impact", mode="before")
    @classmethod
    def _strip_text(cls, v: object) -> object:
        return _clean_str(v) if isinstance(v, str) else v

    @field_validator("indonesia_impact", mode="after")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        return v or None


class MajorHeadline(BaseModel):
    title: str = Field(min_length=3)
    summary: str = Field(min_length=10)
    source: str = Field(min_length=2)
    url: Optional[str] = None
    sourced_from: str = SOURCED_SNIPPET
    source_tier: str = "tier2"

    @field_validator("title", "summary", "source", mode="before")
    @classmethod
    def _strip_text(cls, v: object) -> object:
        return _clean_str(v) if isinstance(v, str) else v


class KeyInsight(BaseModel):
    summary: str = Field(min_length=30)
    source: str = Field(min_length=2)

    @field_validator("summary", "source", mode="before")
    @classmethod
    def _strip_text(cls, v: object) -> object:
        return _clean_str(v) if isinstance(v, str) else v


class WeeklyMarketInsight(BaseModel):
    """Final report (Agent 3 output)."""

    period_start: date
    period_end: date
    weekly_highlights: List[HighlightItem]
    major_headline: MajorHeadline
    key_insight: KeyInsight
    source_department: str = "Research and Education Department"
    # Editorial QA (P0-1): consistency / source flags the editor should resolve.
    review_flags: List[str] = Field(default_factory=list)
    needs_review: bool = False

    @model_validator(mode="after")
    def _check_period(self) -> "WeeklyMarketInsight":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self
