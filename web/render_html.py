"""Render a WeeklyMarketInsight report as an HTML page for the static site.

``report_page(...)`` builds a full page (linked stylesheet/script + archive nav);
``report_body(...)`` returns just the article markup. Both are used by
``site_builder.py`` to generate the site.
"""

from __future__ import annotations

from datetime import date
from html import escape

from schemas import SOURCED_FULL, WeeklyMarketInsight
from web.assets import CSS, THEME_BOOT_JS, THEME_TOGGLE_JS

BRAND = "GIBEI Telkom University × Phillip Sekuritas"
SITE_TITLE = "Weekly Market Insight"

# A tab icon that needs no extra file: the report's red/navy chart mark.
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' fill='%231C2C4A'/%3E"
    "%3Cpath d='M6 22l6-7 5 4 9-11' stroke='%23C62828' stroke-width='3' fill='none'"
    " stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
)


def fmt_date(d: date) -> str:
    return d.strftime("%d %b %Y")


def period_label(report: WeeklyMarketInsight) -> str:
    return f"{fmt_date(report.period_start)} – {fmt_date(report.period_end)}"


def report_slug(report: WeeklyMarketInsight) -> str:
    return f"{report.period_start.isoformat()}_{report.period_end.isoformat()}"


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _impact(text: str | None) -> str:
    if not text:
        return ""
    return (
        '<aside class="impact"><strong>Impact on Indonesia</strong>'
        f"{escape(text)}</aside>"
    )


def _provenance(item) -> str:
    """Source link + full/summary + authority badges (P0-2, P0-3)."""
    badges: list[str] = []
    if getattr(item, "sourced_from", None) == SOURCED_FULL:
        badges.append('<span class="badge badge--full">Full article</span>')
    else:
        badges.append('<span class="badge badge--summary">Summary only</span>')

    tier = getattr(item, "source_tier", "tier2")
    if tier == "tier1":
        badges.append('<span class="badge badge--trusted">Trusted source</span>')
    elif tier == "low":
        badges.append('<span class="badge badge--low">Low-authority</span>')

    link = ""
    if getattr(item, "url", None):
        link = (
            f'<a class="prov-link" href="{escape(item.url)}" target="_blank" '
            f'rel="noopener noreferrer">View source &#8599;</a>'
        )
    return f'<p class="prov">{link}{"".join(badges)}</p>'


def _card(i: int, h) -> str:
    return f"""        <article class="card">
          <p class="meta mono"><span class="no">{i:02d}</span><span>{fmt_date(h.date)}</span><span>&middot;</span><span>{escape(h.source)}</span></p>
          <h3 class="serif">{escape(h.title)}</h3>
          <p class="body">{escape(h.summary)}</p>
          {_impact(h.indonesia_impact)}
          {_provenance(h)}
        </article>"""


def _review_banner(report: WeeklyMarketInsight) -> str:
    if not report.needs_review or not report.review_flags:
        return ""
    items = "\n".join(f"        <li>{escape(f)}</li>" for f in report.review_flags)
    return f"""    <aside class="review" role="alert">
      <p class="review-title">&#9888; Editorial review needed before publishing</p>
      <ul>
{items}
      </ul>
    </aside>
"""


def report_body(report: WeeklyMarketInsight, back_href: str | None = None) -> str:
    """The report markup (topbar + article), without <style>/<script> wrappers."""
    mh, ki = report.major_headline, report.key_insight
    cards = "\n".join(
        _card(i, h) for i, h in enumerate(report.weekly_highlights, start=1)
    )
    back = (
        f'<a class="backlink" href="{escape(back_href)}">&larr; All issues</a>'
        if back_href
        else '<span class="backlink" hidden></span>'
    )

    return f"""<div class="wmi">
  <div class="topbar">
    {back}
    <button class="theme-toggle" type="button" data-theme-toggle>Dark mode</button>
  </div>

  <div class="sheet">
    <header class="masthead">
      <p class="eyebrow">{escape(BRAND)}</p>
      <h1 class="serif">{escape(SITE_TITLE)}</h1>
      <p class="mono">{escape(period_label(report))} &nbsp;&middot;&nbsp; {escape(report.source_department)}</p>
    </header>

{_review_banner(report)}
    <section class="lead">
      <p class="label">Major Headline</p>
      <h2 class="serif">{escape(mh.title)}</h2>
      <p class="body">{escape(mh.summary)}</p>
      <p class="source mono">Source: {escape(mh.source)}</p>
      {_provenance(mh)}
    </section>

    <section class="highlights">
      <p class="label">Weekly Highlights</p>
      <div class="grid">
{cards}
      </div>
    </section>

    <section class="insight">
      <p class="label">Key Insight</p>
      <p class="body serif">{escape(ki.summary)}</p>
      <p class="source mono">Source: {escape(ki.source)}</p>
    </section>

    <footer>
      <p class="disclaimer">This publication is for educational purposes only and does not constitute financial advice.</p>
      <p class="mono">{escape(report.source_department)}</p>
    </footer>
  </div>
</div>"""


def document(
    *,
    title: str,
    description: str,
    body: str,
    css_href: str | None = None,
    js_href: str | None = None,
    canonical: str | None = None,
) -> str:
    """Wrap ``body`` in a complete HTML document.

    With ``css_href``/``js_href`` the assets are linked (static site); without
    them the CSS and JS are inlined (self-contained file).
    """
    head_css = (
        f'<link rel="stylesheet" href="{escape(css_href)}">'
        if css_href
        else f"<style>{CSS}</style>"
    )
    tail_js = (
        f'<script src="{escape(js_href)}" defer></script>'
        if js_href
        else f"<script>{THEME_TOGGLE_JS}</script>"
    )
    link_canonical = (
        f'\n<link rel="canonical" href="{escape(canonical)}">' if canonical else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta name="twitter:card" content="summary">{link_canonical}
<link rel="icon" href="{FAVICON}">
<script>{THEME_BOOT_JS}</script>
{head_css}
</head>
<body>
{body}
{tail_js}
</body>
</html>"""


def report_page(
    report: WeeklyMarketInsight,
    *,
    css_href: str,
    js_href: str,
    back_href: str,
    canonical: str | None = None,
) -> str:
    """Report page for the static site (linked assets + archive nav)."""
    return document(
        title=f"{SITE_TITLE} · {period_label(report)}",
        description=truncate(report.major_headline.title, 155),
        body=report_body(report, back_href=back_href),
        css_href=css_href,
        js_href=js_href,
        canonical=canonical,
    )
