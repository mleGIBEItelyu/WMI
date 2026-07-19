"""Generate a deployable static site from the reports in the output directory.

Produces a plain folder of files — no server, no build step, no framework — so it
can be dropped on Netlify, Vercel, GitHub Pages, S3, or any static host:

    site/
      index.html                     archive: latest issue + every past issue
      reports/<start>_<end>.html     one page per weekly report
      assets/style.css               shared stylesheet
      assets/app.js                  theme toggle
      reports.json                   machine-readable index
      404.html
      robots.txt
      .nojekyll                      so GitHub Pages serves the files verbatim
      sitemap.xml                    only when a base URL is supplied

All internal links are relative, so the site also works from a sub-path
(e.g. a GitHub Pages project site).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from logging_utils import get_logger
from schemas import WeeklyMarketInsight
from web.assets import CSS, THEME_TOGGLE_JS
from web.render_html import (
    BRAND,
    SITE_TITLE,
    document,
    period_label,
    report_page,
    report_slug,
    truncate,
)

log = get_logger("site")

REPORT_GLOB = "weekly_insight_*.json"


@dataclass(frozen=True)
class Issue:
    report: WeeklyMarketInsight
    slug: str

    @property
    def href(self) -> str:
        return f"reports/{self.slug}.html"


def load_reports(output_dir: Path) -> list[Issue]:
    """Parse every weekly_insight_*.json, newest first. Bad files are skipped."""
    issues: list[Issue] = []
    for path in sorted(output_dir.glob(REPORT_GLOB)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            report = WeeklyMarketInsight(**data)
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping %s (not a valid report: %s)", path.name, exc)
            continue
        issues.append(Issue(report=report, slug=report_slug(report)))

    issues.sort(key=lambda i: i.report.period_end, reverse=True)
    return issues


def _issue_row(issue: Issue) -> str:
    r = issue.report
    chip = ' <span class="chip">Under review</span>' if r.needs_review else ""
    return f"""          <li>
            <a class="issue" href="{escape(issue.href)}">
              <span class="mono">{escape(period_label(r))}</span>
              <p class="title">{escape(r.major_headline.title)}{chip}</p>
              <span class="go">Read &rarr;</span>
            </a>
          </li>"""


def _index_body(issues: list[Issue], generated: str) -> str:
    if not issues:
        main = """    <section class="empty">
      <p>No issues published yet. Run <code>python main.py --days 7</code> to generate one.</p>
    </section>"""
    else:
        latest = issues[0]
        r = latest.report
        chip = ' <span class="chip">Under review</span>' if r.needs_review else ""
        featured = f"""    <section class="archive">
      <p class="label">Latest Issue</p>
      <article class="featured">
        <p class="mono">{escape(period_label(r))}{chip}</p>
        <h2 class="serif">{escape(r.major_headline.title)}</h2>
        <p class="body">{escape(truncate(r.key_insight.summary, 260))}</p>
        <a class="cta" href="{escape(latest.href)}">Read the issue &rarr;</a>
      </article>
    </section>"""

        rest = issues[1:]
        if rest:
            rows = "\n".join(_issue_row(i) for i in rest)
            archive = f"""    <section class="archive">
      <p class="label">Archive</p>
      <ul class="issues">
{rows}
      </ul>
    </section>"""
        else:
            archive = ""
        main = featured + ("\n\n" + archive if archive else "")

    count = len(issues)
    noun = "issue" if count == 1 else "issues"

    return f"""<div class="wmi">
  <div class="topbar">
    <span class="backlink" hidden></span>
    <button class="theme-toggle" type="button" data-theme-toggle>Dark mode</button>
  </div>

  <div class="sheet">
    <header class="masthead">
      <p class="eyebrow">{escape(BRAND)}</p>
      <h1 class="serif">{escape(SITE_TITLE)}</h1>
      <p class="mono">Weekly market research &nbsp;&middot;&nbsp; {count} {noun} published</p>
    </header>

{main}

    <footer>
      <p class="disclaimer">This publication is for educational purposes only and does not constitute financial advice.</p>
      <p class="mono">Generated {escape(generated)}</p>
    </footer>
  </div>
</div>"""


def _not_found_body() -> str:
    return f"""<div class="wmi">
  <div class="topbar">
    <a class="backlink" href="./">&larr; All issues</a>
    <button class="theme-toggle" type="button" data-theme-toggle>Dark mode</button>
  </div>
  <div class="sheet">
    <header class="masthead">
      <p class="eyebrow">{escape(BRAND)}</p>
      <h1 class="serif">Page not found</h1>
      <p class="mono">The issue you are looking for does not exist.</p>
    </header>
    <section class="archive">
      <a class="cta" href="./">Back to all issues &rarr;</a>
    </section>
  </div>
</div>"""


def _sitemap(issues: list[Issue], base_url: str, today: date) -> str:
    base = base_url.rstrip("/")
    urls = [f"{base}/"] + [f"{base}/{i.href}" for i in issues]
    entries = "\n".join(
        f"  <url><loc>{escape(u)}</loc><lastmod>{today.isoformat()}</lastmod></url>"
        for u in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def build_site(
    output_dir: Path,
    site_dir: Path,
    *,
    base_url: str | None = None,
    clean: bool = True,
) -> list[Issue]:
    """Build the static site. Returns the issues that were published."""
    issues = load_reports(output_dir)

    if clean and site_dir.exists():
        shutil.rmtree(site_dir)
    (site_dir / "reports").mkdir(parents=True, exist_ok=True)
    (site_dir / "assets").mkdir(parents=True, exist_ok=True)

    # Shared assets.
    (site_dir / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    (site_dir / "assets" / "app.js").write_text(THEME_TOGGLE_JS, encoding="utf-8")

    # Report pages (nested one level down, hence the ../ asset paths).
    for issue in issues:
        canonical = (
            f"{base_url.rstrip('/')}/{issue.href}" if base_url else None
        )
        html = report_page(
            issue.report,
            css_href="../assets/style.css",
            js_href="../assets/app.js",
            back_href="../",
            canonical=canonical,
        )
        (site_dir / "reports" / f"{issue.slug}.html").write_text(html, encoding="utf-8")

    generated = datetime.now(timezone.utc).strftime("%d %b %Y")
    latest_desc = (
        truncate(issues[0].report.major_headline.title, 155)
        if issues
        else "Weekly market research from GIBEI Telkom University."
    )

    (site_dir / "index.html").write_text(
        document(
            title=SITE_TITLE,
            description=latest_desc,
            body=_index_body(issues, generated),
            css_href="assets/style.css",
            js_href="assets/app.js",
            canonical=f"{base_url.rstrip('/')}/" if base_url else None,
        ),
        encoding="utf-8",
    )

    (site_dir / "404.html").write_text(
        document(
            title=f"Not found · {SITE_TITLE}",
            description="Page not found.",
            body=_not_found_body(),
            css_href="assets/style.css",
            js_href="assets/app.js",
        ),
        encoding="utf-8",
    )

    # Machine-readable index (for embeds or a future SPA).
    (site_dir / "reports.json").write_text(
        json.dumps(
            {
                "title": SITE_TITLE,
                "brand": BRAND,
                "generated": generated,
                "issues": [
                    {
                        "period_start": i.report.period_start.isoformat(),
                        "period_end": i.report.period_end.isoformat(),
                        "period_label": period_label(i.report),
                        "major_headline": i.report.major_headline.title,
                        "highlight_count": len(i.report.weekly_highlights),
                        "needs_review": i.report.needs_review,
                        "url": i.href,
                    }
                    for i in issues
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (site_dir / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n"
        + (f"Sitemap: {base_url.rstrip('/')}/sitemap.xml\n" if base_url else ""),
        encoding="utf-8",
    )
    # GitHub Pages otherwise runs Jekyll and drops files it doesn't recognise.
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    if base_url:
        (site_dir / "sitemap.xml").write_text(
            _sitemap(issues, base_url, date.today()), encoding="utf-8"
        )

    log.info("Built %d issue page(s) into %s", len(issues), site_dir)
    for issue in issues:
        log.info("  - %s  %s", period_label(issue.report), issue.href)
    return issues


__all__ = ["build_site", "load_reports", "Issue"]
