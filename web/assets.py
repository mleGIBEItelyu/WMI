"""Shared front-end assets: stylesheet and theme-toggle script.

Kept in one place so the standalone report (``--html``) and the generated static
site render identically. No external fonts or scripts — the pages work offline
and under a strict CSP.
"""

from __future__ import annotations

CSS = """
:root {
  --paper: #F2F5F9;
  --card: #FFFFFF;
  --ink: #182338;
  --muted: #5B6B84;
  --line: #D4DCE7;
  --blue: #234E9D;
  --red: #C62828;
  --red-soft: #FBF1EF;
  --panel: #1C2C4A;
  --panel-ink: #E8EEF8;
  --panel-muted: #9FB0CC;
  --shadow: 0 1px 2px rgba(24, 35, 56, .05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0E1524;
    --card: #16203A;
    --ink: #E4EAF5;
    --muted: #93A3BE;
    --line: #2A3A57;
    --blue: #8AB0F0;
    --red: #EF7B6B;
    --red-soft: #2A1D22;
    --panel: #141F36;
    --panel-ink: #DDE6F5;
    --panel-muted: #8FA2C2;
    --shadow: none;
  }
}
:root[data-theme="dark"] {
  --paper: #0E1524;
  --card: #16203A;
  --ink: #E4EAF5;
  --muted: #93A3BE;
  --line: #2A3A57;
  --blue: #8AB0F0;
  --red: #EF7B6B;
  --red-soft: #2A1D22;
  --panel: #141F36;
  --panel-ink: #DDE6F5;
  --panel-muted: #8FA2C2;
  --shadow: none;
}
:root[data-theme="light"] {
  --paper: #F2F5F9;
  --card: #FFFFFF;
  --ink: #182338;
  --muted: #5B6B84;
  --line: #D4DCE7;
  --blue: #234E9D;
  --red: #C62828;
  --red-soft: #FBF1EF;
  --panel: #1C2C4A;
  --panel-ink: #E8EEF8;
  --panel-muted: #9FB0CC;
  --shadow: 0 1px 2px rgba(24, 35, 56, .05);
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; }

.wmi {
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 1rem;
  line-height: 1.65;
  min-height: 100vh;
  padding: clamp(1.25rem, 4vw, 3rem) clamp(1rem, 5vw, 2rem) 3rem;
}
.wmi .sheet {
  max-width: 62rem;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: clamp(2rem, 5vw, 3.25rem);
}

.wmi .serif {
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
}
.wmi .mono {
  font-family: ui-monospace, "Cascadia Mono", Consolas, "Courier New", monospace;
  font-size: 0.78rem;
  letter-spacing: 0.02em;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

a { color: var(--blue); }
:focus-visible {
  outline: 2px solid var(--blue);
  outline-offset: 3px;
  border-radius: 2px;
}

/* ── Top bar (nav + theme toggle) ─────────────────────────── */
.wmi .topbar {
  max-width: 62rem;
  margin: 0 auto clamp(1.5rem, 4vw, 2.25rem);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.wmi .backlink {
  text-decoration: none;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-weight: 600;
  color: var(--muted);
}
.wmi .backlink:hover { color: var(--blue); }
.wmi .backlink[hidden] { visibility: hidden; }

.wmi .theme-toggle {
  appearance: none;
  border: 1px solid var(--line);
  background: var(--card);
  color: var(--muted);
  font: inherit;
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  box-shadow: var(--shadow);
}
.wmi .theme-toggle:hover { color: var(--ink); border-color: var(--muted); }

/* ── Masthead ─────────────────────────────────────────────── */
.wmi .masthead {
  text-align: center;
  border-bottom: 3px double var(--line);
  padding-bottom: 1.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.wmi .eyebrow {
  margin: 0;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  color: var(--blue);
  font-weight: 600;
}
.wmi .masthead h1 {
  margin: 0;
  font-size: clamp(2.1rem, 6vw, 3.4rem);
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.1;
  text-wrap: balance;
}

/* ── Section labels ───────────────────────────────────────── */
.wmi .label {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-weight: 700;
  color: var(--blue);
}
.wmi .label::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--line);
}

/* ── Lead story ───────────────────────────────────────────── */
.wmi .lead { display: flex; flex-direction: column; gap: 0.9rem; }
.wmi .lead h2 {
  margin: 0;
  font-size: clamp(1.5rem, 4vw, 2.15rem);
  line-height: 1.22;
  font-weight: 700;
  text-wrap: balance;
  max-width: 46rem;
}
.wmi .lead .body { margin: 0; max-width: 44rem; font-size: 1.06rem; }

/* ── Highlights ───────────────────────────────────────────── */
.wmi .highlights { display: flex; flex-direction: column; gap: 1.25rem; }
.wmi .grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}
@media (max-width: 44rem) {
  .wmi .grid { grid-template-columns: 1fr; }
}
.wmi .card {
  background: var(--card);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  padding: 1.4rem 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}
.wmi .card h3 {
  margin: 0;
  font-size: 1.18rem;
  line-height: 1.3;
  font-weight: 700;
  text-wrap: balance;
}
.wmi .card .body { margin: 0; font-size: 0.95rem; }
.wmi .card .meta { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 0; }
.wmi .card .no { color: var(--red); font-weight: 700; }

/* ── Provenance (source link + full/summary + authority badges) ───────── */
.wmi .prov {
  margin: 0.15rem 0 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.wmi .prov-link {
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
  border-bottom: 1px solid currentColor;
  padding-bottom: 1px;
}
.wmi .badge {
  font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
  font-size: 0.64rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  white-space: nowrap;
}
.wmi .badge--full { color: var(--blue); border-color: color-mix(in srgb, var(--blue) 45%, transparent); }
.wmi .badge--summary { color: var(--muted); border-style: dashed; }
.wmi .badge--trusted { color: #1E7A4B; border-color: #1E7A4B55; }
.wmi .badge--low { color: var(--red); border-color: color-mix(in srgb, var(--red) 45%, transparent); background: var(--red-soft); }
@media (prefers-color-scheme: dark) { .wmi .badge--trusted { color: #5FCB93; border-color: #5FCB9355; } }
:root[data-theme="dark"] .wmi .badge--trusted { color: #5FCB93; border-color: #5FCB9355; }

/* ── Editorial review banner (consistency / source-quality flags) ─────── */
.wmi .review {
  border: 1px solid color-mix(in srgb, var(--red) 40%, var(--line));
  border-left: 4px solid var(--red);
  background: var(--red-soft);
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.wmi .review-title {
  margin: 0;
  font-weight: 700;
  color: var(--red);
  font-size: 0.9rem;
}
.wmi .review ul { margin: 0; padding-left: 1.1rem; display: flex; flex-direction: column; gap: 0.25rem; }
.wmi .review li { font-size: 0.86rem; line-height: 1.5; }

/* ── Archive "under review" chip ──────────────────────────────────────── */
.wmi .chip {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.62rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  color: var(--red);
  border: 1px solid color-mix(in srgb, var(--red) 45%, transparent);
  background: var(--red-soft);
  white-space: nowrap;
}

.wmi .impact {
  margin-top: 0.25rem;
  border-left: 3px solid var(--red);
  background: var(--red-soft);
  padding: 0.7rem 0.9rem;
  font-size: 0.88rem;
  line-height: 1.55;
}
.wmi .impact strong {
  display: block;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--red);
  margin-bottom: 0.25rem;
}

/* ── Key insight panel ────────────────────────────────────── */
.wmi .insight {
  background: var(--panel);
  color: var(--panel-ink);
  padding: clamp(1.5rem, 4vw, 2.5rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.wmi .insight .label { color: var(--panel-muted); }
.wmi .insight .label::after { background: rgba(159, 176, 204, .35); }
.wmi .insight .body { margin: 0; font-size: 1.05rem; line-height: 1.75; }
.wmi .insight .mono { color: var(--panel-muted); }

.wmi .source { margin: 0; }

/* ── Archive (index page) ─────────────────────────────────── */
.wmi .featured {
  background: var(--card);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-top: 3px solid var(--red);
  padding: clamp(1.5rem, 4vw, 2.25rem);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.wmi .featured h2 {
  margin: 0;
  font-size: clamp(1.4rem, 3.6vw, 2rem);
  line-height: 1.25;
  text-wrap: balance;
}
.wmi .featured .body { margin: 0; max-width: 44rem; }
.wmi .cta {
  align-self: flex-start;
  margin-top: 0.4rem;
  text-decoration: none;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--blue);
  border-bottom: 2px solid var(--blue);
  padding-bottom: 2px;
}
.wmi .cta:hover { color: var(--ink); border-color: var(--ink); }

.wmi .archive { display: flex; flex-direction: column; gap: 1.25rem; }
.wmi .issues { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.wmi .issues li { border-bottom: 1px solid var(--line); }
.wmi .issues li:first-child { border-top: 1px solid var(--line); }
.wmi .issue {
  display: grid;
  grid-template-columns: 11rem 1fr auto;
  align-items: baseline;
  gap: 1rem;
  padding: 1rem 0.25rem;
  text-decoration: none;
  color: inherit;
}
.wmi .issue:hover { background: var(--card); }
.wmi .issue .title { margin: 0; font-size: 1rem; font-weight: 600; line-height: 1.4; }
.wmi .issue .go { color: var(--blue); font-size: 0.8rem; }
@media (max-width: 44rem) {
  .wmi .issue { grid-template-columns: 1fr; gap: 0.35rem; }
  .wmi .issue .go { display: none; }
}

.wmi .empty {
  border: 1px dashed var(--line);
  padding: 2rem;
  text-align: center;
  color: var(--muted);
}

/* ── Footer ───────────────────────────────────────────────── */
.wmi footer {
  border-top: 1px solid var(--line);
  padding-top: 1.25rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.wmi footer p { margin: 0; font-size: 0.8rem; color: var(--muted); }
.wmi footer .disclaimer { font-style: italic; }

@media print {
  .wmi .topbar { display: none; }
  .wmi { background: #fff; }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
"""

# Applied before first paint so a stored theme never flashes the wrong palette.
THEME_BOOT_JS = """
(function () {
  try {
    var t = localStorage.getItem('wmi-theme');
    if (t === 'dark' || t === 'light') {
      document.documentElement.setAttribute('data-theme', t);
    }
  } catch (e) {}
})();
"""

THEME_TOGGLE_JS = """
(function () {
  var root = document.documentElement;
  var btn = document.querySelector('[data-theme-toggle]');
  if (!btn) return;

  function current() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function paint() {
    var mode = current();
    var next = mode === 'dark' ? 'Light' : 'Dark';
    btn.textContent = next + ' mode';
    btn.setAttribute('aria-label', 'Switch to ' + next.toLowerCase() + ' mode');
  }
  btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('wmi-theme', next); } catch (e) {}
    paint();
  });
  paint();
})();
"""
