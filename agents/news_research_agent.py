"""Agent 1 — News Research Analyst (uses Groq compound + web search)."""

from __future__ import annotations

from datetime import date

from agents.base import AgentError, BaseAgent, dedupe_by_title, validate_items
from gemini_client import is_capacity_error
from logging_utils import get_logger
from parsing import extract_list
from schemas import NewsCandidate

log = get_logger("news")


class NewsResearchAgent(BaseAgent):
    name = "news_research"

    def run(self, start_date: date, end_date: date) -> list[NewsCandidate]:
        cfg = self.settings.news
        system_prompt = self.load_prompt("news_research_system.md").format(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            target_candidates=self.settings.target_candidates,
        )
        user_prompt = (
            "Search Google now and harvest as many market-moving financial news items "
            f"as you can from the week of {start_date.isoformat()} to "
            f"{end_date.isoformat()} (the most recent 7 days). Run several focused "
            "searches (Fed/monetary policy, inflation/macro data, geopolitics, index & "
            "commodity moves, Indonesia/IDX). Include a working source url for each "
            "item, then return ONLY the JSON object of everything you found."
        )

        candidates = self._research(
            system_prompt, user_prompt, start_date, end_date, cfg
        )

        # Single, targeted retry if we fell short — never loop aggressively.
        if len(candidates) < self.settings.min_valid_candidates:
            log.warning(
                "Only %d valid candidate(s) (< %d); retrying once with a stricter prompt.",
                len(candidates),
                self.settings.min_valid_candidates,
            )
            retry_prompt = self.load_prompt("news_research_retry.md").format(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                target_candidates=self.settings.target_candidates,
                min_valid=self.settings.min_valid_candidates,
            )
            retried = self._research(
                system_prompt, retry_prompt, start_date, end_date, cfg
            )
            # Merge both attempts; the retry may surface different stories.
            candidates = dedupe_by_title(candidates + retried)

        if not candidates:
            raise AgentError(
                "News research returned no valid candidates within the date window."
            )
        if len(candidates) < self.settings.min_valid_candidates:
            log.warning(
                "Proceeding with %d candidate(s) (below target of %d).",
                len(candidates),
                self.settings.min_valid_candidates,
            )

        id_count = sum(1 for c in candidates if c.region == "indonesia")
        log.info(
            "Collected %d candidate news item(s) (%d Indonesian, %d global):",
            len(candidates),
            id_count,
            len(candidates) - id_count,
        )
        for c in candidates:
            log.info("  - [%s/%s] %s (%s)", c.region, c.category, c.title, c.published_date)
        return candidates

    def _research(
        self, system_prompt, user_prompt, start_date, end_date, cfg
    ) -> list[NewsCandidate]:
        """Try the primary news model; on a capacity error, fall back once to a
        lighter agentic model (e.g. groq/compound-mini) if configured."""
        try:
            return self._call_and_validate(
                cfg.model, system_prompt, user_prompt, start_date, end_date, cfg
            )
        except Exception as exc:  # noqa: BLE001
            fallback = self.settings.news_fallback_model
            if fallback and fallback != cfg.model and is_capacity_error(exc):
                log.warning(
                    "Primary news model %s hit a capacity limit (%s); "
                    "falling back to %s.",
                    cfg.model,
                    type(exc).__name__,
                    fallback,
                )
                return self._call_and_validate(
                    fallback, system_prompt, user_prompt, start_date, end_date, cfg
                )
            raise

    def _call_and_validate(
        self, model, system_prompt, user_prompt, start_date, end_date, cfg
    ) -> list[NewsCandidate]:
        result = self.client.complete(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            # Google Search grounding can't be combined with JSON mode, so we
            # parse the JSON out of the text response instead.
            json_mode=False,
            web_search=True,
        )
        if result.grounding_queries:
            log.info(
                "Research trail: %d Google Search querie(s) executed.",
                len(result.grounding_queries),
            )
            for q in result.grounding_queries:
                log.debug("  - search: %s", q)

        try:
            raw = extract_list(result.content)
        except ValueError:
            # The model returned prose / a refusal instead of JSON. Don't crash —
            # return nothing so the caller's single retry can take over.
            log.warning(
                "News model returned no parseable JSON (likely a refusal): %s",
                result.content[:160].replace("\n", " "),
            )
            return []
        items = validate_items(raw, NewsCandidate, context="news_research")
        # Keep only items strictly inside the requested window.
        in_window = [c for c in items if start_date <= c.published_date <= end_date]
        dropped = len(items) - len(in_window)
        if dropped:
            log.debug("Dropped %d item(s) outside %s..%s", dropped, start_date, end_date)
        return dedupe_by_title(in_window)
