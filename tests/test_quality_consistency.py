"""Tests for source_quality (P0-2) and consistency (P0-1)."""

import pytest

import consistency
import source_quality
from config import Settings
from schemas import (
    HighlightItem,
    KeyInsight,
    MajorHeadline,
    WeeklyMarketInsight,
)


@pytest.fixture
def settings(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("WMI_") or key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza_test")
    return Settings.from_env()


def test_classify_tiers(settings):
    assert source_quality.classify("Reuters", settings) == "tier1"
    assert source_quality.classify("KOMPAS.TV", settings) == "tier1"
    assert source_quality.classify("JournalArta", settings) == "low"
    assert source_quality.classify("Golden Ark Reserve", settings) == "low"
    assert source_quality.classify("Some Local Newspaper", settings) == "tier2"
    assert source_quality.classify("", settings) == "tier2"


def test_low_precedence_over_tier1(settings):
    # A low marker wins even if a trusted substring is present.
    assert source_quality.classify("Bloomberg Musings blog", settings) == "low"


def test_env_extends_lists(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("WMI_") or key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza_test")
    monkeypatch.setenv("WMI_SOURCE_LOW", "myblog")
    s = Settings.from_env()
    assert source_quality.classify("MyBlog Daily", s) == "low"


def _report(h1_summary, h2_summary):
    return WeeklyMarketInsight(
        period_start="2026-07-05",
        period_end="2026-07-12",
        weekly_highlights=[
            HighlightItem(title="BI decision one", date="2026-07-11", summary=h1_summary, source="Tempo"),
            HighlightItem(title="BI decision two", date="2026-07-08", summary=h2_summary, source="Kontan"),
        ],
        major_headline=MajorHeadline(
            title="Monetary policy in focus this week",
            summary="Central banks dominated the week's market narrative across regions.",
            source="Reuters",
        ),
        key_insight=KeyInsight(
            summary="A sufficiently long analytical paragraph about the week and Indonesia markets.",
            source="Reuters",
        ),
    )


def test_consistency_flags_conflicting_rates():
    r = _report(
        "Bank Indonesia held its BI-Rate at 6.00% to defend the rupiah.",
        "Bank Indonesia raised the BI-Rate to 5.75% amid pressure.",
    )
    flags = consistency.check(r)
    assert flags
    assert "BI-Rate" in flags[0]
    assert "6.00%" in flags[0] and "5.75%" in flags[0]


def test_consistency_clean_when_consistent():
    r = _report(
        "Bank Indonesia held its BI-Rate at 6.00% to defend the rupiah.",
        "The BI-Rate remained at 6.00% for the second month.",
    )
    assert consistency.check(r) == []
