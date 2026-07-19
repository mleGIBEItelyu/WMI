"""Stage 3 — fetch and extract the full body text of shortlisted articles.

The shortlisted stories (selected from titles + snippets) are read in full here so
the editor analyses real article content rather than hallucinating from headlines.
Fetching is parallel and fault-tolerant: any article that can't be retrieved or
extracted (paywall, bot-block, JS-only page) gracefully falls back to its snippet
and is flagged ``fetch_ok=False``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx
import trafilatura

from config import Settings
from logging_utils import get_logger
from schemas import EnrichedNews, ScoredNews

log = get_logger("fetch")


class ArticleFetcher:
    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.fetch

    def run(self, items: list[ScoredNews]) -> list[EnrichedNews]:
        if not items:
            return []
        log.info("Fetching full article text for %d shortlisted item(s)...", len(items))
        headers = {"User-Agent": self.cfg.user_agent, "Accept": "text/html,*/*"}
        with httpx.Client(
            follow_redirects=True,
            timeout=self.cfg.timeout,
            headers=headers,
        ) as client:
            with ThreadPoolExecutor(max_workers=self.cfg.max_workers) as pool:
                # map preserves input order (already sorted by impact score).
                enriched = list(pool.map(lambda it: self._fetch_one(client, it), items))

        ok = sum(1 for e in enriched if e.fetch_ok)
        log.info("Full text read for %d/%d article(s).", ok, len(enriched))
        for e in enriched:
            mark = "OK " if e.fetch_ok else "snippet-only"
            chars = len(e.full_text) if e.full_text else 0
            log.info("  - [%s] %s (%d chars)", mark, e.title, chars)
        return enriched

    def _fetch_one(self, client: httpx.Client, item: ScoredNews) -> EnrichedNews:
        base = item.model_dump()
        full_text: str | None = None
        fetch_ok = False

        if not item.url:
            log.debug("No url for %r; using snippet.", item.title)
            return EnrichedNews(**base, full_text=None, fetch_ok=False)

        try:
            resp = client.get(item.url)
            resp.raise_for_status()
            extracted = trafilatura.extract(
                resp.text,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            text = (extracted or "").strip()
            if len(text) >= self.cfg.min_chars:
                full_text = text[: self.cfg.max_chars]
                fetch_ok = True
            else:
                log.debug(
                    "Extracted only %d chars from %s; using snippet.",
                    len(text),
                    item.title,
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("Failed to fetch %r (%s); using snippet.", item.title, exc)

        return EnrichedNews(**base, full_text=full_text, fetch_ok=fetch_ok)
