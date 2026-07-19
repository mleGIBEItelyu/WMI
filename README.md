# Weekly Market Insight — Multi-Agent News Analyst

A Python backend that runs a **multi-stage AI research pipeline** (via Google Gemini)
to analyse the past 7 days of economic/market news and produce a structured JSON
report ready to drop into the "Weekly Market Insight" design template
(GIBEI Telkom University × Phillip Sekuritas).

```
[1] Harvest      broad collection of the week's news (titles + snippets + urls)
        ↓                via live Google Search grounding
[2] Score        quantitative market-impact scoring of EVERY harvested item
        ↓
[3] Shortlist    keep the top N (default 10) most impactful stories
        ↓
[4] Read full    fetch + extract the FULL article body of those 10 (parallel)
        ↓
[5] Edit         analyse the full texts → 6 highlights, 1 major headline, 1 key insight
        ↓
              output/weekly_insight_<start>_<end>.json
```

The key idea: the editor writes from **real article text**, not just headlines —
so the analysis is grounded in facts, not hallucinated from titles. Stages 1, 2 and
5 are model calls; stage 4 fetches the shortlisted articles over HTTP.

**Indonesia focus:** the harvest covers national (Indonesian) and global news; the
quant stage scores each story's transmission to the Indonesian economy
(`indonesia_impact_score` + channel); the shortlist guarantees a minimum number of
Indonesian stories (`WMI_MIN_ID_SHORTLIST`); and every highlight carries an
`indonesia_impact` note correlating it with IHSG / rupiah / BI policy / exports,
with the Key Insight centred on what the week means for Indonesia.

## Output shape (`WeeklyMarketInsight`)

```jsonc
{
  "period_start": "2026-06-23",
  "period_end": "2026-06-30",
  "weekly_highlights": [
    { "title": "...", "date": "2026-06-27", "summary": "2-4 sentences", "source": "Reuters" }
    // exactly 3
  ],
  "major_headline": { "title": "...", "summary": "...", "source": "..." },
  "key_insight": { "summary": "5-8 sentence analysis", "source": "..." },
  "source_department": "Research and Education Department"
}
```

## Install

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate    |  macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your GOOGLE_API_KEY in .env
```

Get a free key at <https://aistudio.google.com/apikey>. (`GEMINI_API_KEY` also works.)

## Run

```bash
# last 7 days ending today
python main.py --days 7

# a specific window + custom output path
python main.py --end-date 2026-06-30 --days 7 --output output/test_run.json

# iterate on the editorial stage WITHOUT spending research quota
python main.py --end-date 2026-06-30 --days 7 --from-cache

# also write a Markdown and/or standalone HTML report next to the JSON
python main.py --days 7 --md --html

# verbose (debug) logging + full traceback on error
python main.py --days 7 -v
```

The terminal shows the reasoning trail for all three stages (Google Search queries →
candidates found → impact scores → final headline/highlights), then writes the JSON
file. The script also prints the output path on stdout (handy for piping in scripts).

## Web front-end (static site)

Every report in `output/` can be published as a static site — an archive index plus
one page per issue. No framework, no build step, no server:

```bash
python build_site.py                 # -> site/
python build_site.py --serve         # build + preview at http://127.0.0.1:8000
python build_site.py --base-url https://insight.example.com   # adds sitemap.xml + canonical links
```

```
site/
  index.html                  archive: latest issue featured + every past issue
  reports/<start>_<end>.html  one page per weekly report
  assets/style.css            shared stylesheet
  assets/app.js               theme toggle (light/dark, remembered)
  reports.json                machine-readable index
  404.html  robots.txt  sitemap.xml  .nojekyll
```

All links are relative and the pages are responsive, keyboard-accessible,
print-friendly, and load no external assets (CSP-safe, works offline).

### Deploy to Vercel (recommended)

The repo is Vercel-ready — `vercel.json` tells Vercel to build the site **from the
committed report JSON** (`output/weekly_insight_*.json`), using only the two light
deps in `requirements-site.txt` (no AI keys needed at build time):

1. Push this repo to GitHub/GitLab.
2. In Vercel: **New Project → import the repo → Deploy.** No settings to change —
   Vercel reads `vercel.json` (build command `python3 build_site.py`, output `site/`).
3. Every future push (e.g. after generating a new weekly report and committing its
   JSON) redeploys automatically.

Or from the CLI: `npm i -g vercel && vercel --prod`.

**Publishing a new week:** `python main.py --days 7`, commit the new
`output/weekly_insight_*.json`, and push — Vercel rebuilds the site. (Only the JSON
is the site's content; the `.md`/`.html` exports and caches are gitignored.)

Any other static host works too: run `python build_site.py` locally and upload the
`site/` folder. A single report can also be exported as one self-contained HTML file
with `python main.py --days 7 --html` (everything inlined — emailable, opens from disk).

## Automated weekly publishing (GitHub Actions)

`.github/workflows/weekly-insight.yml` runs the pipeline on a schedule, commits the
new report JSON, and pushes it — which triggers Vercel to redeploy the front-end.
**Every Friday 22:00 WIB (Asia/Jakarta) a fresh issue appears automatically.**

One-time setup:

1. Push the repo to GitHub and connect it to Vercel (see above).
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**,
   name `GOOGLE_API_KEY`, value = your AI Studio key.
3. Done. The workflow is scheduled; it also has a **Run workflow** button
   (workflow_dispatch) with optional `end_date` / `days` inputs for a manual run.

Notes:
- Schedule is `cron: "0 15 * * 5"` (15:00 UTC = 22:00 WIB). GitHub may start scheduled
  runs a few minutes late, and only runs them on the default branch.
- If the pipeline fails (e.g. a rate limit) the job fails and nothing is published —
  the previous issue stays live.
- Reports flagged `needs_review` are still published, with the review banner visible
  (the flag is transparency, not a hard gate).
- Optional: set a `VERCEL_DEPLOY_HOOK` secret to also ping a Vercel Deploy Hook
  (only needed if your project isn't connected to the repo via Git).
- `.github/workflows/ci.yml` runs the offline test suite + a site build on every
  push/PR.

## Configuration

Everything is environment-driven — **nothing is hardcoded**. Only `GOOGLE_API_KEY`
is required; all other knobs have sensible defaults and live in `.env.example`.
Highlights:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WMI_NEWS_MODEL` | `gemini-2.5-flash` | Agent 1 model (Google Search grounding) |
| `WMI_QUANT_MODEL` / `WMI_EDITOR_MODEL` | `gemini-2.5-flash` | Agents 2 & 3 |
| `WMI_NEWS_FALLBACK_MODEL` | `gemini-flash-lite-latest` | used if the news model hits a 429 |
| `WMI_MIN_ID_SHORTLIST` | 3 | guaranteed Indonesian stories read in full |
| `WMI_MAX_LOW_HIGHLIGHTS` | 1 | more low-authority highlights than this → review flag |
| `WMI_THINKING_BUDGET` | `0` | Gemini "thinking" tokens (0 = off: fast, no truncation) |
| `WMI_*_MAX_TOKENS` | 2500 / 3000 / 2500 | per-agent max output tokens |
| `WMI_TARGET_CANDIDATES` | 20 | how many items the harvester aims to gather |
| `WMI_SHORTLIST_COUNT` | 10 | top-impact stories whose full article is read |
| `WMI_MIN_ID_SHORTLIST` | 3 | guaranteed Indonesian stories in the shortlist |
| `WMI_HIGHLIGHT_COUNT` | 6 | highlights chosen (diversely) from the shortlist |
| `WMI_FETCH_TIMEOUT` / `WMI_FETCH_WORKERS` | 20 / 6 | per-article timeout, parallelism |
| `WMI_FETCH_MAX_CHARS` | 6000 | cap on extracted article text (editor token control) |
| `WMI_MAX_RETRIES` / `WMI_RETRY_MAX_WAIT` | 4 / 60 | rate-limit backoff |

If a Gemini model is renamed, just override the relevant `WMI_*_MODEL` — no code change.

## Why Gemini (and how the free tier is handled)

Gemini 2.5 Flash on the AI Studio free tier has a generous per-minute token budget
and a built-in **Google Search grounding** tool, so the research agent gets
real-time news without a separate search API. Design choices around the limits:

1. **3 model calls per run** — one per agent.
2. **Grounding ≠ JSON mode.** Gemini can't combine Google Search with the strict
   JSON response mode, so Agent 1 runs in plain mode and we parse the JSON out of
   its text (see robustness notes). Agents 2 & 3 use strict JSON mode.
3. **Thinking disabled by default** (`WMI_THINKING_BUDGET=0`) so thinking tokens
   never eat into the output budget and truncate the JSON. Raise it for deeper
   reasoning if you want.
4. **Explicit `max_output_tokens`** on every call, configurable per agent.
5. **`retryDelay`-aware backoff** via `tenacity` — on a 429 we wait the time Gemini
   asks for (plus a small buffer); we never retry aggressively.
6. **Automatic model fallback**: if the news model hits a capacity limit, the agent
   retries once on `gemini-2.5-flash-lite` (configurable / disable-able).
7. **Full-article reading**: the shortlisted stories are fetched and parsed to plain
   text (`trafilatura`) in parallel, so the editor analyses real content. Any article
   that can't be fetched (paywall/bot-block/JS-only) gracefully falls back to its
   snippet and is flagged `fetch_ok=false`.
8. **Enriched-shortlist cache** per date range (`output/cache_<start>_<end>.json`)
   stores harvest+score+full-text. Re-run the editorial stage freely with
   `--from-cache` (no re-harvest, no re-fetch).

## Robustness notes (the "find the loopholes" pass)

- **Lenient JSON extraction** (`parsing.py`): recovers JSON even when the model wraps
  it in markdown fences, prose, or grounding citations — without breaking on braces
  inside strings.
- **Strict per-item validation** (`schemas.py`): out-of-range scores, bad dates, and
  short text are rejected; invalid items are dropped (and logged) rather than crashing
  the run. Categories and scores are coerced/normalised (`"7/10"` → `7.0`).
- **Date-window enforcement**: Agent 1 results outside the requested window are dropped.
- **Authoritative metadata**: the period and department in the final report come from
  the orchestrator, not the model, so they can't drift.
- **Guaranteed highlight count**: if the editor returns too many/few highlights, they
  are trimmed or back-filled from the top-scored news.
- **Empty-response guard**: a blocked/empty Gemini response raises a clear error
  (with finish reason) instead of silently producing an empty report.
- **Atomic cache writes**: cache is written to a temp file then renamed.
- **Graceful config errors**: missing/invalid config exits with a clear message
  (code 2) before any API call.

## Project layout

```
main.py                 pipeline entrypoint (generate a report)
build_site.py           front-end entrypoint (build / preview the web site)
vercel.json             Vercel build config      requirements*.txt  deps (run / dev / site)

config.py               env-driven Settings (no hardcode)
schemas.py              pydantic models (the inter-stage contract)
orchestrator.py         5-stage pipeline + caching + Indonesia-quota shortlist
gemini_client.py        resilient Gemini wrapper (grounding / JSON mode / retry)
article_fetcher.py      parallel full-article fetch + text extraction (stage 4)
parsing.py              robust JSON extraction
source_quality.py       source-authority tiering (P0-2)
consistency.py          cross-article fact-consistency checks (P0-1)
logging_utils.py        rich logging

agents/                 harvester, quant scorer, lead editor
prompts/                system prompt templates (editable, not in code)
web/                    front-end: renderers (md/html), shared assets, site builder
docs/                   PROJECT_BRIEF.md (original spec), AUDIT.md (readiness audit)
output/                 report JSON (committed) + local caches/exports (gitignored)
tests/                  pytest suite (51 tests, fully offline)
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The suite runs fully offline (a fake Gemini client drives the agent/pipeline tests)
— no API key or network needed.

## Notes

- This tool produces editorial market commentary, **not financial advice** — the
  editor prompt explicitly forbids buy/sell recommendations.
- Free-tier limits reset over time; if you hit a 429, the tool waits and retries
  automatically. For heavy/automated use, consider a paid Gemini API tier.
```
