"""Agent 3 — Lead Market Analyst / Writer & Financial Editor (final synthesis)."""

from __future__ import annotations

import json
from datetime import date
from difflib import SequenceMatcher

import consistency
import source_quality
from agents.base import AgentError, BaseAgent
from logging_utils import get_logger
from parsing import extract_object
from schemas import (
    SOURCED_FULL,
    SOURCED_SNIPPET,
    EnrichedNews,
    HighlightItem,
    WeeklyMarketInsight,
)

log = get_logger("editor")


class LeadEditorAgent(BaseAgent):
    name = "lead_editor"

    def run(
        self, scored: list[EnrichedNews], start_date: date, end_date: date
    ) -> WeeklyMarketInsight:
        if not scored:
            raise AgentError("Lead editor received no scored news to synthesise.")

        cfg = self.settings.editor
        n = self.settings.highlight_count

        # Editor reads the FULL article text where it was successfully fetched,
        # falling back to the snippet otherwise. (Urls are dropped to save tokens.)
        trimmed = [
            {
                "title": s.title,
                "date": s.published_date.isoformat(),
                "source": s.source,
                "category": s.category,
                "region": s.region,
                "market_impact_score": s.market_impact_score,
                "quantitative_evidence": s.quantitative_evidence,
                "affected_assets": s.affected_assets,
                "indonesia_impact_score": s.indonesia_impact_score,
                "indonesia_impact": s.indonesia_impact,
                "source_authority": source_quality.classify(s.source, self.settings),
                "text_source": "full_article" if s.fetch_ok else "snippet_only",
                "article_text": s.full_text if s.fetch_ok else s.raw_summary,
            }
            for s in scored
        ]
        scored_json = json.dumps(trimmed, ensure_ascii=False, indent=2)

        system_prompt = self.load_prompt("lead_editor_system.md").format(
            scored_news_json=scored_json,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            highlight_count=n,
            source_department=self.settings.source_department,
        )
        user_prompt = (
            f"Produce the final Weekly Market Insight JSON for {start_date.isoformat()} "
            f"to {end_date.isoformat()} with exactly {n} highlights."
        )

        result = self.client.complete(
            model=cfg.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            json_mode=True,
        )

        obj = extract_object(result.content)

        # Authoritative metadata comes from the orchestrator, not the model — this
        # prevents the LLM from drifting the period or department label.
        obj["period_start"] = start_date.isoformat()
        obj["period_end"] = end_date.isoformat()
        obj["source_department"] = self.settings.source_department

        obj["weekly_highlights"] = self._reconcile_highlights(
            obj.get("weekly_highlights"), scored, n
        )

        # P0-3: attach provenance (real url + full/snippet + source tier) from our
        # own data, matched to the source story — never trust the LLM for these.
        for h in obj["weekly_highlights"]:
            self._attach_provenance(h, scored)
        if isinstance(obj.get("major_headline"), dict):
            self._attach_provenance(obj["major_headline"], scored)

        try:
            report = WeeklyMarketInsight(**obj)
        except Exception as exc:  # noqa: BLE001
            raise AgentError(f"Final report failed schema validation: {exc}") from exc

        if len(report.weekly_highlights) != n:
            log.warning(
                "Final report has %d highlight(s) instead of %d — not enough "
                "distinct scored news was available to fill the quota.",
                len(report.weekly_highlights),
                n,
            )

        # P0-1 + P0-2: editorial QA flags (consistency + source authority).
        report.review_flags = self._qa_flags(report)
        report.needs_review = self._blocking(report)

        log.info("Final report ready:")
        log.info("  Major headline: %s [%s]", report.major_headline.title, report.major_headline.source_tier)
        for h in report.weekly_highlights:
            log.info("  Highlight: %s [%s / %s]", h.title, h.source_tier, h.sourced_from)
        if report.review_flags:
            log.warning("Editorial review flags (%d):", len(report.review_flags))
            for f in report.review_flags:
                log.warning("  ! %s", f)
        return report

    # ── Provenance & QA ──────────────────────────────────────────────────

    def _attach_provenance(self, entry: dict, scored: list[EnrichedNews]) -> None:
        match = self._best_match(
            str(entry.get("title", "")), str(entry.get("source", "")), scored
        )
        if match is not None:
            entry["url"] = match.url
            entry["sourced_from"] = SOURCED_FULL if match.fetch_ok else SOURCED_SNIPPET
            entry["source_tier"] = source_quality.classify(match.source, self.settings)
        else:
            entry.setdefault("sourced_from", SOURCED_SNIPPET)
            entry["source_tier"] = source_quality.classify(
                str(entry.get("source", "")), self.settings
            )

    def _best_match(
        self, title: str, source: str, scored: list[EnrichedNews]
    ) -> EnrichedNews | None:
        t = title.strip().lower()
        src = source.strip().lower()
        best: EnrichedNews | None = None
        best_score = 0.0
        for s in scored:
            r = SequenceMatcher(None, t, s.title.strip().lower()).ratio()
            s_src = s.source.strip().lower()
            if src and s_src and (src in s_src or s_src in src):
                r += 0.15
            if r > best_score:
                best, best_score = s, r
        return best if best_score >= 0.55 else None

    def _qa_flags(self, report: WeeklyMarketInsight) -> list[str]:
        flags = list(consistency.check(report))

        if source_quality.is_low(report.major_headline.source_tier):
            flags.append(
                f"Major headline uses a low-authority source "
                f"({report.major_headline.source}); prefer a trusted outlet."
            )
        low_items = [
            h for h in report.weekly_highlights if source_quality.is_low(h.source_tier)
        ]
        if low_items:
            names = ", ".join(dict.fromkeys(h.source for h in low_items))
            flags.append(
                f"{len(low_items)} highlight(s) rely on low-authority sources: {names}."
            )
        snippet = sum(
            1 for h in report.weekly_highlights if h.sourced_from != SOURCED_FULL
        )
        if snippet:
            flags.append(
                f"{snippet} of {len(report.weekly_highlights)} highlights are "
                "summary-only (full article could not be read)."
            )
        return flags

    def _blocking(self, report: WeeklyMarketInsight) -> bool:
        """True when a human editor must resolve something before publishing."""
        if consistency.check(report):
            return True  # contradictory facts
        if source_quality.is_low(report.major_headline.source_tier):
            return True  # spotlight rests on a weak source
        low = sum(
            1 for h in report.weekly_highlights if source_quality.is_low(h.source_tier)
        )
        return low > self.settings.max_low_highlights

    def _reconcile_highlights(
        self, raw_highlights: object, scored: list[EnrichedNews], n: int
    ) -> list[dict]:
        """Guarantee exactly ``n`` highlights, backfilling from top scored news."""
        highlights: list[dict] = []
        if isinstance(raw_highlights, list):
            for h in raw_highlights:
                if isinstance(h, dict):
                    highlights.append(h)

        if len(highlights) > n:
            log.debug("Editor returned %d highlights; trimming to %d.", len(highlights), n)
            highlights = highlights[:n]

        if len(highlights) < n:
            log.warning(
                "Editor returned %d highlight(s); backfilling to %d from top scored news.",
                len(highlights),
                n,
            )
            used = {str(h.get("title", "")).strip().lower() for h in highlights}
            for s in scored:
                if len(highlights) >= n:
                    break
                if s.title.strip().lower() in used:
                    continue
                highlights.append(
                    HighlightItem(
                        title=s.title,
                        date=s.published_date,
                        summary=s.raw_summary,
                        source=s.source,
                        indonesia_impact=s.indonesia_impact or None,
                    ).model_dump(mode="json")
                )
                used.add(s.title.strip().lower())

        return highlights
