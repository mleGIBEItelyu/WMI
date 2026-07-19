"""Tests for the HTML report renderer used by the static site."""

from web.render_html import report_body
from schemas import (
    HighlightItem,
    KeyInsight,
    MajorHeadline,
    WeeklyMarketInsight,
)


def _report(needs_review=False, flags=None):
    highlight = HighlightItem(
        title="BI holds rate at 6.00% to defend the rupiah",
        date="2026-07-11",
        summary="Bank Indonesia kept its benchmark rate unchanged citing rupiah stability.",
        source="Tempo",
        indonesia_impact="Directly anchors IDR stability and SBN yields.",
        url="https://tempo.co/a",
        sourced_from="full_article",
        source_tier="tier1",
    )
    return WeeklyMarketInsight(
        period_start="2026-07-05",
        period_end="2026-07-12",
        weekly_highlights=[highlight],
        major_headline=MajorHeadline(
            title="Oil surges past $80 <after> Hormuz attacks",
            summary="Brent jumped nearly 6% after tanker attacks near the strait.",
            source="The Guardian",
            url="https://theguardian.com/b",
            sourced_from="full_article",
            source_tier="tier1",
        ),
        key_insight=KeyInsight(
            summary="A long analytical paragraph about what this means for Indonesian investors and markets.",
            source="The Guardian; Tempo",
        ),
        review_flags=flags or [],
        needs_review=needs_review,
    )


def test_renders_core_sections():
    html = report_body(_report())
    assert "Weekly Market Insight" in html
    assert "Major Headline" in html
    assert "Weekly Highlights" in html
    assert "Key Insight" in html


def test_escapes_model_text():
    html = report_body(_report())
    assert "<after>" not in html
    assert "&lt;after&gt;" in html


def test_shows_provenance():
    html = report_body(_report())
    assert "Full article" in html
    assert "Trusted source" in html
    assert 'href="https://tempo.co/a"' in html
    assert "View source" in html


def test_review_banner_only_when_needed():
    assert "Editorial review needed" not in report_body(_report(needs_review=False))

    flagged = report_body(
        _report(needs_review=True, flags=["Conflicting figures for BI-Rate: 5.75%, 6.00%."])
    )
    assert "Editorial review needed" in flagged
    assert "Conflicting figures for BI-Rate" in flagged


def test_omits_empty_indonesia_impact():
    r = _report()
    r.weekly_highlights[0].indonesia_impact = None
    assert "Impact on Indonesia" not in report_body(r)
