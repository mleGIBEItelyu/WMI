"""ArticleFetcher tests with a fake HTTP client (no network)."""

import pytest

import article_fetcher
from article_fetcher import ArticleFetcher
from config import Settings
from schemas import ScoredNews


@pytest.fixture
def settings(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("WMI_") or key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza_test")
    return Settings.from_env()


def _scored(url):
    return ScoredNews(
        title="A market story about the economy",
        published_date="2026-06-26",
        source="Reuters",
        url=url,
        raw_summary="A factual two-sentence snippet about the market event today.",
        category="macro",
        market_impact_score=7,
        quantitative_evidence="DXY +1%",
        affected_assets=["DXY"],
    )


def test_no_url_falls_back_to_snippet(settings):
    out = ArticleFetcher(settings).run([_scored(None)])
    assert out[0].fetch_ok is False
    assert out[0].full_text is None


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        return _FakeResp("<html><body><article>ignored</article></body></html>")


def test_successful_extraction(settings, monkeypatch):
    monkeypatch.setattr(article_fetcher.httpx, "Client", _FakeClient)
    monkeypatch.setattr(
        article_fetcher.trafilatura, "extract", lambda *a, **k: "Full article. " * 200
    )
    out = ArticleFetcher(settings).run([_scored("https://example.com/a")])
    assert out[0].fetch_ok is True
    assert out[0].full_text
    # Respects the max_chars cap.
    assert len(out[0].full_text) <= settings.fetch.max_chars


def test_short_extraction_falls_back(settings, monkeypatch):
    monkeypatch.setattr(article_fetcher.httpx, "Client", _FakeClient)
    monkeypatch.setattr(article_fetcher.trafilatura, "extract", lambda *a, **k: "tiny")
    out = ArticleFetcher(settings).run([_scored("https://example.com/a")])
    assert out[0].fetch_ok is False
    assert out[0].full_text is None


def test_fetch_exception_falls_back(settings, monkeypatch):
    class _BoomClient(_FakeClient):
        def get(self, url):
            raise RuntimeError("network down")

    monkeypatch.setattr(article_fetcher.httpx, "Client", _BoomClient)
    out = ArticleFetcher(settings).run([_scored("https://example.com/a")])
    assert out[0].fetch_ok is False
