from datetime import date

import pytest
from pydantic import ValidationError

from schemas import (
    HighlightItem,
    KeyInsight,
    MajorHeadline,
    NewsCandidate,
    ScoredNews,
    WeeklyMarketInsight,
)


def _candidate(**over):
    base = dict(
        title="Fed holds rates steady",
        published_date="2026-06-28",
        source="Reuters",
        url="https://example.com/a",
        raw_summary="The Federal Reserve kept its benchmark rate unchanged.",
        category="monetary_policy",
    )
    base.update(over)
    return base


def test_news_candidate_valid():
    c = NewsCandidate(**_candidate())
    assert c.category == "monetary_policy"
    assert c.published_date == date(2026, 6, 28)


def test_category_normalised_and_fallback():
    assert NewsCandidate(**_candidate(category="Monetary Policy")).category == "monetary_policy"
    assert NewsCandidate(**_candidate(category="weird")).category == "other"


def test_blank_url_becomes_none():
    assert NewsCandidate(**_candidate(url="   ")).url is None


def test_text_whitespace_collapsed():
    c = NewsCandidate(**_candidate(title="  Fed   holds   rates  "))
    assert c.title == "Fed holds rates"


def test_title_too_short_rejected():
    with pytest.raises(ValidationError):
        NewsCandidate(**_candidate(title="x"))


def test_scored_news_score_coercion():
    s = ScoredNews(
        **_candidate(),
        market_impact_score="7.5/10",
        quantitative_evidence="rate unchanged at 4.5%",
        affected_assets="DXY, US10Y",
    )
    assert s.market_impact_score == 7.5
    assert s.affected_assets == ["DXY", "US10Y"]


def test_scored_news_score_out_of_range():
    with pytest.raises(ValidationError):
        ScoredNews(
            **_candidate(),
            market_impact_score=11,
            quantitative_evidence="x",
            affected_assets=[],
        )


def test_weekly_insight_period_order():
    highlight = HighlightItem(
        title="A market story", date="2026-06-28", summary="Something happened in markets.", source="Reuters"
    )
    with pytest.raises(ValidationError):
        WeeklyMarketInsight(
            period_start="2026-06-30",
            period_end="2026-06-01",
            weekly_highlights=[highlight],
            major_headline=MajorHeadline(
                title="Big one", summary="The biggest story of the week.", source="Reuters"
            ),
            key_insight=KeyInsight(
                summary="A sufficiently long analytical paragraph about markets and why it matters.",
                source="Reuters",
            ),
        )
