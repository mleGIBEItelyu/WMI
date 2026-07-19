"""Render a WeeklyMarketInsight report as a human-readable Markdown document."""

from __future__ import annotations

from datetime import date

from schemas import SOURCED_FULL, WeeklyMarketInsight

_TIER_LABEL = {"tier1": "Trusted source", "low": "Low-authority source"}


def _fmt_date(d: date) -> str:
    return d.strftime("%d %b %Y")


def _provenance(item) -> str:
    read = "Full article" if getattr(item, "sourced_from", None) == SOURCED_FULL else "Summary only"
    parts = [read]
    tier = _TIER_LABEL.get(getattr(item, "source_tier", "tier2"))
    if tier:
        parts.append(tier)
    if getattr(item, "url", None):
        parts.append(f"[View source]({item.url})")
    return " · ".join(parts)


def to_markdown(report: WeeklyMarketInsight) -> str:
    period = f"{_fmt_date(report.period_start)} – {_fmt_date(report.period_end)}"
    lines: list[str] = []

    lines.append("# Weekly Market Insight")
    lines.append("")
    lines.append(f"**Period:** {period}  ")
    lines.append(f"**Source:** {report.source_department}")
    lines.append("")

    # Editorial review flags (P0-1 / P0-2)
    if report.needs_review and report.review_flags:
        lines.append("> ⚠️ **Editorial review needed before publishing**")
        for f in report.review_flags:
            lines.append(f"> - {f}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Major headline
    mh = report.major_headline
    lines.append("## 📌 Major Headline")
    lines.append("")
    lines.append(f"### {mh.title}")
    lines.append("")
    lines.append(mh.summary)
    lines.append("")
    lines.append(f"*Source: {mh.source}*  ")
    lines.append(f"`{_provenance(mh)}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Weekly highlights
    lines.append("## 📰 Weekly Highlights")
    lines.append("")
    for i, h in enumerate(report.weekly_highlights, start=1):
        lines.append(f"### {i}. {h.title}")
        lines.append("")
        lines.append(f"*{_fmt_date(h.date)} · {h.source}*")
        lines.append("")
        lines.append(h.summary)
        lines.append("")
        if h.indonesia_impact:
            lines.append(f"> 🇮🇩 **Impact on Indonesia:** {h.indonesia_impact}")
            lines.append("")
        lines.append(f"`{_provenance(h)}`")
        lines.append("")
    lines.append("---")
    lines.append("")

    # Key insight
    ki = report.key_insight
    lines.append("## 💡 Key Insight")
    lines.append("")
    lines.append(ki.summary)
    lines.append("")
    lines.append(f"*Source: {ki.source}*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "> _This publication is for educational purposes only and does not "
        "constitute financial advice._"
    )
    lines.append("")

    return "\n".join(lines)
