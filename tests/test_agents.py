"""Agent-level tests using a fake Groq client (no network)."""

import json
from datetime import date

import pytest

from config import Settings
from gemini_client import ChatResult


@pytest.fixture
def settings(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("WMI_") or key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza_test")
    s = Settings.from_env()
    s.validate()
    return s


class FakeClient:
    """Returns queued responses in order; records the prompts it was given."""

    def __init__(self, *responses: str):
        self._responses = list(responses)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        content = self._responses.pop(0)
        return ChatResult(content=content, grounding_queries=[], model="fake", usage=None)


def _news_payload(n=6, start="2026-06-24"):
    items = [
        {
            "title": f"Market story number {i}",
            "published_date": start,
            "source": "Reuters",
            "url": f"https://example.com/{i}",
            "raw_summary": "A factual two sentence summary of an economic event. It moved markets.",
            "category": "macro",
        }
        for i in range(n)
    ]
    return json.dumps({"news": items})


def test_news_agent_filters_out_of_window(settings):
    from agents.news_research_agent import NewsResearchAgent

    payload = json.dumps(
        {
            "news": [
                {
                    "title": "In window story about the economy",
                    "published_date": "2026-06-25",
                    "source": "Reuters",
                    "raw_summary": "Something factual happened in the markets this week.",
                    "category": "macro",
                },
                {
                    "title": "Out of window story about the economy",
                    "published_date": "2020-01-01",
                    "source": "Reuters",
                    "raw_summary": "This is way outside the requested date window entirely.",
                    "category": "macro",
                },
            ]
        }
    )
    # Two responses queued because too-few-items triggers exactly one retry.
    client = FakeClient(payload, _news_payload(6))
    agent = NewsResearchAgent(client, settings)
    out = agent.run(date(2026, 6, 23), date(2026, 6, 30))
    assert all(date(2026, 6, 23) <= c.published_date <= date(2026, 6, 30) for c in out)
    assert len(out) >= 1


def test_quant_agent_sorts_and_restores_url(settings):
    from agents.news_research_agent import NewsResearchAgent
    from agents.quant_analyst_agent import QuantAnalystAgent
    from schemas import NewsCandidate

    candidates = [
        NewsCandidate(
            title="Low impact local story",
            published_date="2026-06-25",
            source="Reuters",
            url="https://example.com/low",
            raw_summary="A small local development that barely moved the market.",
            category="other",
        ),
        NewsCandidate(
            title="High impact fed decision",
            published_date="2026-06-26",
            source="Bloomberg",
            url="https://example.com/high",
            raw_summary="The Fed surprised markets with a policy pivot affecting everything.",
            category="monetary_policy",
        ),
    ]
    scored_payload = json.dumps(
        {
            "scored_news": [
                {
                    "title": "Low impact local story",
                    "published_date": "2026-06-25",
                    "source": "Reuters",
                    "raw_summary": "A small local development that barely moved the market.",
                    "category": "other",
                    "market_impact_score": 2,
                    "quantitative_evidence": "negligible",
                    "affected_assets": ["IHSG"],
                },
                {
                    "title": "High impact fed decision",
                    "published_date": "2026-06-26",
                    "source": "Bloomberg",
                    "raw_summary": "The Fed surprised markets with a policy pivot affecting everything.",
                    "category": "monetary_policy",
                    "market_impact_score": 9,
                    "quantitative_evidence": "DXY +1.2%",
                    "affected_assets": ["DXY", "S&P500"],
                },
            ]
        }
    )
    client = FakeClient(scored_payload)
    scored = QuantAnalystAgent(client, settings).run(candidates)
    assert scored[0].market_impact_score == 9  # sorted desc
    # url not in prompt payload but restored by title match
    assert scored[0].url == "https://example.com/high"


def test_editor_backfills_highlights(settings):
    from agents.lead_editor_agent import LeadEditorAgent
    from schemas import EnrichedNews

    scored = [
        EnrichedNews(
            title=f"Scored story {i} about the market",
            published_date="2026-06-26",
            source="Reuters",
            url=None,
            raw_summary="A factual summary describing the market event in two sentences.",
            category="macro",
            market_impact_score=9 - i,
            quantitative_evidence="some figures",
            affected_assets=["IHSG"],
            full_text="The full article body with lots of detail. " * 5,
            fetch_ok=True,
        )
        for i in range(8)
    ]
    # Editor returns only ONE highlight -> must be backfilled to highlight_count.
    editor_payload = json.dumps(
        {
            "weekly_highlights": [
                {
                    "title": "Scored story 0 about the market",
                    "date": "2026-06-26",
                    "summary": "A factual summary describing the market event in two sentences.",
                    "source": "Reuters",
                }
            ],
            "major_headline": {
                "title": "Scored story 0 about the market",
                "summary": "The single most important development of the week for markets.",
                "source": "Reuters",
            },
            "key_insight": {
                "summary": "A sufficiently long analytical paragraph that explains why the week mattered.",
                "source": "Reuters",
            },
        }
    )
    client = FakeClient(editor_payload)
    report = LeadEditorAgent(client, settings).run(scored, date(2026, 6, 23), date(2026, 6, 30))
    assert len(report.weekly_highlights) == settings.highlight_count
    assert report.period_start == date(2026, 6, 23)
    assert report.source_department == settings.source_department


def test_editor_attaches_provenance_and_flags(settings):
    from agents.lead_editor_agent import LeadEditorAgent
    from schemas import SOURCED_FULL, SOURCED_SNIPPET, EnrichedNews

    def enriched(title, source, url, fetch_ok, id_impact):
        return EnrichedNews(
            title=title,
            published_date="2026-07-08",
            source=source,
            url=url,
            raw_summary="A factual two-sentence description of the market event this week.",
            category="monetary_policy",
            region="indonesia",
            market_impact_score=8,
            quantitative_evidence="rate change",
            affected_assets=["IDR"],
            indonesia_impact_score=9,
            indonesia_impact=id_impact,
            full_text="Full body text. " * 40 if fetch_ok else None,
            fetch_ok=fetch_ok,
        )

    scored = [
        enriched("BI holds rate at 6.00 percent", "Reuters", "https://reuters.com/a", True, "Anchors IDR."),
        enriched("BI raises rate to 5.75 percent", "JournalArta", "https://journalarta.com/b", False, "Pressures SBN."),
    ]
    editor_payload = json.dumps(
        {
            "weekly_highlights": [
                {
                    "title": "BI holds rate at 6.00 percent",
                    "date": "2026-07-08",
                    "summary": "Bank Indonesia held the BI-Rate at 6.00% to defend the rupiah this week.",
                    "source": "Reuters",
                    "indonesia_impact": "Anchors IDR stability and SBN yields.",
                },
                {
                    "title": "BI raises rate to 5.75 percent",
                    "date": "2026-07-08",
                    "summary": "Bank Indonesia raised the BI-Rate to 5.75% amid global pressure.",
                    "source": "JournalArta",
                    "indonesia_impact": "Raises borrowing costs for Indonesian firms.",
                },
            ],
            "major_headline": {
                "title": "BI holds rate at 6.00 percent",
                "summary": "Bank Indonesia held the BI-Rate at 6.00% to defend the rupiah this week.",
                "source": "Reuters",
            },
            "key_insight": {
                "summary": "A sufficiently long analytical paragraph about Indonesia and the rupiah this week.",
                "source": "Reuters",
            },
        }
    )
    report = LeadEditorAgent(FakeClient(editor_payload), settings).run(
        scored, date(2026, 7, 5), date(2026, 7, 12)
    )

    by_title = {h.title: h for h in report.weekly_highlights}
    full = by_title["BI holds rate at 6.00 percent"]
    assert full.url == "https://reuters.com/a"
    assert full.sourced_from == SOURCED_FULL
    assert full.source_tier == "tier1"

    snip = by_title["BI raises rate to 5.75 percent"]
    assert snip.sourced_from == SOURCED_SNIPPET
    assert snip.source_tier == "low"

    # P0-1: the 5.75 vs 6.00 contradiction must trip the review gate.
    assert report.needs_review is True
    assert any("BI-Rate" in f for f in report.review_flags)
    assert any("low-authority" in f.lower() for f in report.review_flags)
