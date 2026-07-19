"""Renderer tests: Markdown and HTML output from a WeeklyMarketInsight."""

from web.render_html import to_html
from web.render_markdown import to_markdown
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


def test_markdown_contains_sections():
    md = to_markdown(_report())
    assert "# Weekly Market Insight" in md
    assert "Impact on Indonesia" in md
    assert "BI holds rate" in md


def test_html_standalone_and_fragment():
    r = _report()
    full = to_html(r)
    assert full.startswith("<!doctype html>")
    assert "Weekly Market Insight" in full
    # Model text must be escaped.
    assert "<after>" not in full and "&lt;after&gt;" in full
    assert "Impact on Indonesia" in full

    frag = to_html(r, standalone=False)
    assert not frag.startswith("<!doctype")
    assert "<style>" in frag and "class=\"wmi\"" in frag


def test_html_omits_empty_impact():
    r = _report()
    r.weekly_highlights[0].indonesia_impact = None
    html = to_html(r)
    assert "Impact on Indonesia" not in html


def test_html_shows_provenance():
    html = to_html(_report())
    assert "Full article" in html
    assert "Trusted source" in html
    assert 'href="https://tempo.co/a"' in html
    assert "View source" in html


def test_html_review_banner_only_when_needed():
    clean = to_html(_report(needs_review=False))
    assert "Editorial review needed" not in clean

    flagged = to_html(
        _report(needs_review=True, flags=["Conflicting figures for BI-Rate: 5.75%, 6.00%."])
    )
    assert "Editorial review needed" in flagged
    assert "Conflicting figures for BI-Rate" in flagged


def test_markdown_shows_provenance_and_review():
    md = to_markdown(_report(needs_review=True, flags=["Conflicting figures for BI-Rate."]))
    assert "Full article" in md
    assert "View source" in md
    assert "Editorial review needed" in md
