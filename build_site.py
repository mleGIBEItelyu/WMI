"""CLI: build the deployable static site from the generated reports.

    python build_site.py                       # -> ./site
    python build_site.py --serve               # build, then preview at :8000
    python build_site.py --base-url https://gibei.example.com   # adds sitemap.xml
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import sys
from pathlib import Path

from config import ConfigError, PROJECT_ROOT
from logging_utils import configure, get_logger
from web.site_builder import build_site

log = get_logger("cli")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Weekly Market Insight static site.",
    )
    parser.add_argument(
        "--reports",
        type=str,
        default=None,
        help="Directory holding weekly_insight_*.json (default: output/, or WMI_OUTPUT_DIR).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Directory to write the site into (default: site/, or WMI_SITE_DIR).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Public URL of the deployed site; enables sitemap.xml and canonical links.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve the built site locally for preview.",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for --serve (default: 8000)."
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging.")
    return parser.parse_args(argv)


def _resolve(value: str | None, env: str, default: str) -> Path:
    raw = value or os.getenv(env) or default
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def serve(site_dir: Path, port: int) -> None:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(site_dir)
    )
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        log.info("Serving %s at http://127.0.0.1:%d  (Ctrl+C to stop)", site_dir, port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            log.info("Stopped.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure(verbose=args.verbose)

    reports_dir = _resolve(args.reports, "WMI_OUTPUT_DIR", "output")
    site_dir = _resolve(args.out, "WMI_SITE_DIR", "site")
    base_url = args.base_url or os.getenv("WMI_SITE_BASE_URL") or None

    if not reports_dir.is_dir():
        log.error("Reports directory not found: %s", reports_dir)
        return 2

    try:
        issues = build_site(reports_dir, site_dir, base_url=base_url)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    if not issues:
        log.warning(
            "No reports found in %s. Run `python main.py --days 7` first.", reports_dir
        )

    print(str(site_dir / "index.html"))

    if args.serve:
        serve(site_dir, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
