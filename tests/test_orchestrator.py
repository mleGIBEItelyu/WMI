"""End-to-end pipeline wiring test with a fake Groq client (no network)."""

import json
from datetime import date

import pytest

import orchestrator
from config import Settings
from gemini_client import ChatResult

START, END = date(2026, 6, 23), date(2026, 6, 30)


def _news_json():
    return json.dumps(
        {
            "news": [
                {
                    "title": f"Market moving story {i} this week",
                    "published_date": "2026-06-26",
                    "source": "Reuters",
                    "url": f"https://example.com/{i}",
                    "raw_summary": "A factual two-sentence description of an economic event affecting markets.",
                    "category": "macro",
                }
                for i in range(8)
            ]
        }
    )


def _scored_json():
    return json.dumps(
        {
            "scored_news": [
                {
                    "title": f"Market moving story {i} this week",
                    "published_date": "2026-06-26",
                    "source": "Reuters",
                    "raw_summary": "A factual two-sentence description of an economic event affecting markets.",
                    "category": "macro",
                    "market_impact_score": 9 - i,
                    "quantitative_evidence": "index moved 1.5%",
                    "affected_assets": ["IHSG", "DXY"],
                }
                for i in range(6)
            ]
        }
    )


def _editor_json():
    highlights = [
        {
            "title": f"Market moving story {i} this week",
            "date": "2026-06-26",
            "summary": "A factual two-sentence description of an economic event affecting markets.",
            "source": "Reuters",
        }
        for i in range(3)
    ]
    return json.dumps(
        {
            "weekly_highlights": highlights,
            "major_headline": {
                "title": "Market moving story 0 this week",
                "summary": "The single most important development for markets this week by far.",
                "source": "Reuters",
            },
            "key_insight": {
                "summary": "A sufficiently long analytical paragraph explaining why this week's news matters for markets and investors.",
                "source": "Reuters",
            },
        }
    )


class FakeClient:
    def __init__(self, settings):
        self._queue = [_news_json(), _scored_json(), _editor_json()]
        self.call_count = 0

    def complete(self, **kwargs):
        self.call_count += 1
        content = self._queue.pop(0)
        return ChatResult(content=content, grounding_queries=[], model="fake", usage=None)


class CacheOnlyClient(FakeClient):
    """Only the editor call should happen when running --from-cache."""

    def __init__(self, settings):
        self._queue = [_editor_json()]
        self.call_count = 0


@pytest.fixture
def settings(tmp_path, monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("WMI_") or key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza_test")
    monkeypatch.setenv("WMI_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("WMI_CACHE_DIR", str(tmp_path / "out"))
    s = Settings.from_env()
    s.validate()
    return s


class FakeFetcher:
    """Returns snippet-only enriched items without touching the network."""

    def __init__(self, settings):
        pass

    def run(self, items):
        from schemas import EnrichedNews

        return [
            EnrichedNews(**it.model_dump(), full_text=None, fetch_ok=False)
            for it in items
        ]


def _make_scored(i, region, score, id_score=0.0):
    from schemas import ScoredNews

    return ScoredNews(
        title=f"Story {i} about markets and the economy",
        published_date="2026-06-26",
        source="Reuters",
        raw_summary="A factual two-sentence description of the market event.",
        category="macro",
        region=region,
        market_impact_score=score,
        quantitative_evidence="some figures",
        affected_assets=["IHSG"],
        indonesia_impact_score=id_score,
        indonesia_impact="Affects IDR and IHSG via foreign flows.",
    )


def test_select_shortlist_enforces_indonesia_quota():
    scored = [_make_scored(i, "global", 10 - i) for i in range(5)]
    scored += [_make_scored(10 + i, "indonesia", 3 - i, id_score=8 - i) for i in range(3)]
    out = orchestrator.select_shortlist(scored, n=5, min_indonesia=2)
    assert len(out) == 5
    assert sum(1 for s in out if s.region == "indonesia") == 2
    # The strongest global stories must survive the swap.
    assert out[0].market_impact_score == 10


def test_select_shortlist_without_indonesian_items():
    scored = [_make_scored(i, "global", 10 - i) for i in range(6)]
    out = orchestrator.select_shortlist(scored, n=4, min_indonesia=3)
    assert len(out) == 4
    assert all(s.region == "global" for s in out)


def test_full_pipeline_and_cache(settings, monkeypatch):
    monkeypatch.setattr(orchestrator, "GeminiClient", FakeClient)
    monkeypatch.setattr(orchestrator, "ArticleFetcher", FakeFetcher)
    report = orchestrator.run_pipeline(settings, START, END, from_cache=False)

    assert len(report.weekly_highlights) == settings.highlight_count
    assert report.period_start == START
    assert report.period_end == END
    assert report.major_headline.title

    # Cache should now exist.
    cache = orchestrator.cache_path_for(settings, START, END)
    assert cache.exists()

    # Re-run from cache: only the editor call should fire (1 call).
    monkeypatch.setattr(orchestrator, "GeminiClient", CacheOnlyClient)
    report2 = orchestrator.run_pipeline(settings, START, END, from_cache=True)
    assert len(report2.weekly_highlights) == settings.highlight_count
