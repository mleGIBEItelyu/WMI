"""Classify a news source into an authority tier (P0-2).

Deterministic, substring-based matching against the tier lists in ``Settings``
(env-overridable). Used to keep low-authority / SEO / forecast blogs out of the
Major Headline slot and to surface a caution to the reader.

Tiers:
  tier1 — high-authority outlet (Reuters, Bloomberg, Tempo, Kompas, ...)
  low   — low-authority / SEO / opinion-forecast source (flag + demote)
  tier2 — everything else (ordinary/unknown; neither promoted nor flagged)
"""

from __future__ import annotations

from config import Settings

TIER1 = "tier1"
TIER2 = "tier2"
LOW = "low"

_LABELS = {
    TIER1: "Trusted source",
    TIER2: "Standard source",
    LOW: "Low-authority source",
}


def classify(source: str, settings: Settings) -> str:
    s = (source or "").strip().lower()
    if not s:
        return TIER2
    # Low-authority takes precedence: a weak outlet stays weak even if its name
    # happens to contain a trusted substring.
    if any(marker in s for marker in settings.low_sources):
        return LOW
    if any(marker in s for marker in settings.tier1_sources):
        return TIER1
    return TIER2


def label(tier: str) -> str:
    return _LABELS.get(tier, _LABELS[TIER2])


def is_low(tier: str) -> bool:
    return tier == LOW
