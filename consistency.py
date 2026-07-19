"""Cross-article factual consistency checks (P0-1).

Scans the finished report for contradictory numeric claims about the same entity
— the exact class of error found in the audit, where one highlight said the
BI-Rate was held at 6.00% while another said it was raised to 5.75%. Findings are
returned as human-readable flags so an editor can resolve them before publishing.

Deterministic and conservative: it only flags when the same tracked entity is
given two clearly different values in the same report.
"""

from __future__ import annotations

import re

from schemas import WeeklyMarketInsight

# Tracked entities → regex that matches a mention of them. Percentage figures
# appearing shortly after a mention are attributed to that entity.
_ENTITIES: tuple[tuple[str, str], ...] = (
    ("BI-Rate", r"bi[\s-]?rate|bank indonesia[^.]{0,30}?(?:benchmark|policy|7-day|reverse repo)[^.]{0,20}?rate"),
    ("Fed funds rate", r"fed funds|federal funds rate|the fed[^.]{0,25}?(?:target|benchmark|policy)[^.]{0,10}?rate"),
    ("ECB policy rate", r"ecb[^.]{0,30}?rate|european central bank[^.]{0,30}?rate"),
    ("BoJ policy rate", r"boj[^.]{0,25}?rate|bank of japan[^.]{0,25}?rate"),
)

# A percentage figure, e.g. "5.75%", "6,00 percent", "5.75 persen".
_PCT = r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:%|percent|persen)"


def _norm(value: str) -> float:
    return round(float(value.replace(",", ".")), 2)


def _report_text_segments(report: WeeklyMarketInsight) -> list[str]:
    segs = [report.major_headline.title, report.major_headline.summary]
    for h in report.weekly_highlights:
        segs.append(h.title)
        segs.append(h.summary)
    segs.append(report.key_insight.summary)
    return segs


def find_rate_conflicts(text: str) -> list[str]:
    """Return a flag per entity that is given >1 distinct percentage value."""
    flags: list[str] = []
    low = text.lower()
    for name, pattern in _ENTITIES:
        values: set[float] = set()
        for m in re.finditer(pattern, low):
            # Look at the ~60 chars following the mention for a percentage.
            window = low[m.end() : m.end() + 60]
            fig = re.search(_PCT, window)
            if fig:
                try:
                    values.add(_norm(fig.group(1)))
                except ValueError:
                    continue
        if len(values) > 1:
            shown = ", ".join(f"{v:.2f}%" for v in sorted(values))
            flags.append(
                f"Conflicting figures for {name}: {shown} appear in the same report."
            )
    return flags


def check(report: WeeklyMarketInsight) -> list[str]:
    """All consistency flags for a report (empty list == clean)."""
    text = "  ".join(_report_text_segments(report))
    return find_rate_conflicts(text)
