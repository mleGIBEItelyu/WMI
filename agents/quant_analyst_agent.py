"""Agent 2 — Quant / Data Analyst (pure reasoning over Agent 1 output)."""

from __future__ import annotations

import json

from agents.base import AgentError, BaseAgent, dedupe_by_title, validate_items
from logging_utils import get_logger
from parsing import extract_list
from schemas import NewsCandidate, ScoredNews

log = get_logger("quant")


class QuantAnalystAgent(BaseAgent):
    name = "quant_analyst"

    def run(self, candidates: list[NewsCandidate]) -> list[ScoredNews]:
        if not candidates:
            raise AgentError("Quant analyst received no candidates to score.")

        cfg = self.settings.quant

        # Trim payload to cut TPM: drop the long `url` before sending. We restore
        # urls afterwards by matching titles, so the final schema stays complete.
        url_by_title = {c.title.strip().lower(): c.url for c in candidates}
        trimmed = [
            {
                "title": c.title,
                "published_date": c.published_date.isoformat(),
                "source": c.source,
                "raw_summary": c.raw_summary,
                "category": c.category,
                "region": c.region,
            }
            for c in candidates
        ]
        candidates_json = json.dumps(trimmed, ensure_ascii=False, indent=2)

        system_prompt = self.load_prompt("quant_analyst_system.md").format(
            news_candidates_json=candidates_json
        )
        user_prompt = (
            "Score every candidate above and return the JSON object with "
            '"scored_news" sorted by market_impact_score descending.'
        )

        result = self.client.complete(
            model=cfg.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            json_mode=True,
        )

        raw = extract_list(result.content)
        scored = validate_items(raw, ScoredNews, context="quant_analyst")

        # Restore urls dropped from the prompt payload.
        for s in scored:
            if not s.url:
                s.url = url_by_title.get(s.title.strip().lower())

        scored = dedupe_by_title(scored)
        if not scored:
            raise AgentError("Quant analyst produced no valid scored items.")

        # Defensive sort so downstream never depends on the model ordering.
        scored.sort(key=lambda s: s.market_impact_score, reverse=True)

        log.info("Scored %d item(s) (high -> low impact):", len(scored))
        for s in scored:
            log.info("  - %.1f  %s  %s", s.market_impact_score, s.title, s.affected_assets)
        return scored
