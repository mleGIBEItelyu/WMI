"""Sequential multi-stage pipeline with caching.

Flow:
  [1] Harvest      — broad collection of news (titles + snippets + urls) for the week
  [2] Score        — quantitative market-impact scoring of every harvested item
  [3] Shortlist    — keep the top ``shortlist_count`` most impactful stories
  [4] Read full    — fetch + extract the full article body of those stories
  [5] Edit         — analyse the full texts and write the final report

Stages 1-4 are the expensive/slow part (live search + web fetching). Their combined
output (the enriched shortlist) is cached per date range so the editorial stage can
be re-run via ``--from-cache`` without re-harvesting or re-fetching.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from agents.base import AgentError
from agents.lead_editor_agent import LeadEditorAgent
from agents.news_research_agent import NewsResearchAgent
from agents.quant_analyst_agent import QuantAnalystAgent
from article_fetcher import ArticleFetcher
from config import Settings
from gemini_client import GeminiClient
from logging_utils import get_logger
from schemas import EnrichedNews, ScoredNews, WeeklyMarketInsight

log = get_logger("pipeline")


def select_shortlist(
    scored: list[ScoredNews], n: int, min_indonesia: int
) -> list[ScoredNews]:
    """Top-``n`` by market impact, guaranteeing ``min_indonesia`` Indonesian items.

    If the plain top-n lacks Indonesian coverage, the lowest-ranked global items
    are swapped out for the best remaining Indonesian stories (ranked by their
    Indonesia impact). If the harvest simply has too few Indonesian items, we take
    what exists — never fabricate.
    """
    top = scored[:n]
    have = sum(1 for s in top if s.region == "indonesia")
    if have >= min_indonesia:
        return top

    extra_id = [s for s in scored[n:] if s.region == "indonesia"]
    extra_id.sort(
        key=lambda s: (s.indonesia_impact_score, s.market_impact_score), reverse=True
    )
    to_add = extra_id[: min_indonesia - have]
    if not to_add:
        return top

    result = list(top)
    removable = [s for s in reversed(result) if s.region != "indonesia"]
    for victim in removable[: len(to_add)]:
        result.remove(victim)
    result.extend(to_add)
    result.sort(key=lambda s: s.market_impact_score, reverse=True)
    log.info(
        "Shortlist quota: swapped in %d Indonesian stor(ies) to guarantee coverage.",
        len(to_add),
    )
    return result[:n]


def cache_path_for(settings: Settings, start_date: date, end_date: date) -> Path:
    return settings.cache_dir / f"cache_{start_date}_{end_date}.json"


def _load_cache(path: Path) -> list[EnrichedNews]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise AgentError(f"Cache file {path} is malformed (expected a JSON list).")
    return [EnrichedNews(**item) for item in data]


def _save_cache(path: Path, items: list[EnrichedNews]) -> None:
    payload = [s.model_dump(mode="json") for s in items]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)  # atomic on the same filesystem


def run_pipeline(
    settings: Settings,
    start_date: date,
    end_date: date,
    from_cache: bool = False,
) -> WeeklyMarketInsight:
    settings.ensure_dirs()
    cache_path = cache_path_for(settings, start_date, end_date)

    client = GeminiClient(settings)
    editor = LeadEditorAgent(client, settings)

    enriched: list[EnrichedNews]
    if from_cache and cache_path.exists():
        log.info("[1-4] Using cached harvest+score+full-text from %s", cache_path.name)
        enriched = _load_cache(cache_path)
        log.info("Loaded %d enriched item(s) from cache.", len(enriched))
    else:
        if from_cache:
            log.warning(
                "--from-cache requested but no cache at %s; running full pipeline.",
                cache_path,
            )
        news = NewsResearchAgent(client, settings)
        quant = QuantAnalystAgent(client, settings)
        fetcher = ArticleFetcher(settings)

        log.info("[1/5] Harvest: searching %s .. %s", start_date, end_date)
        candidates = news.run(start_date, end_date)

        log.info("[2/5] Score: assessing impact of %d candidate(s)", len(candidates))
        scored = quant.run(candidates)

        n = settings.shortlist_count
        shortlist = select_shortlist(scored, n, settings.min_indonesia_shortlist)
        id_count = sum(1 for s in shortlist if s.region == "indonesia")
        log.info(
            "[3/5] Shortlist: keeping top %d of %d (%d Indonesian, %d global)",
            len(shortlist),
            len(scored),
            id_count,
            len(shortlist) - id_count,
        )

        log.info("[4/5] Read full articles for the shortlist")
        enriched = fetcher.run(shortlist)

        _save_cache(cache_path, enriched)
        log.info("Cached enriched shortlist to %s", cache_path.name)

    log.info("[5/5] Lead Editor: composing final report from full article text")
    return editor.run(enriched, start_date, end_date)
