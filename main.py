"""CLI entrypoint for the Weekly Market Insight multi-agent generator."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from config import ConfigError, Settings
from logging_utils import configure, get_logger

log = get_logger("cli")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Weekly Market Insight — multi-agent news analyst (Groq).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End of the reporting window, YYYY-MM-DD (default: today).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days back from end-date to cover (default: 7).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write the final JSON (default: output/weekly_insight_<start>_<end>.json).",
    )
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Reuse the saved harvest+score+full-text for this window (skips re-harvest/re-fetch).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def resolve_window(end_date_arg: str | None, days: int) -> tuple[date, date]:
    if days <= 0:
        raise SystemExit("--days must be a positive integer.")
    try:
        end_date = date.fromisoformat(end_date_arg) if end_date_arg else date.today()
    except ValueError:
        raise SystemExit(f"--end-date must be YYYY-MM-DD, got {end_date_arg!r}.")
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure(verbose=args.verbose)

    try:
        settings = Settings.from_env()
        settings.validate()
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 2

    start_date, end_date = resolve_window(args.end_date, args.days)

    # Import here so config/CLI errors don't require the Gemini SDK to be importable.
    from orchestrator import run_pipeline

    try:
        report = run_pipeline(
            settings, start_date, end_date, from_cache=args.from_cache
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Pipeline failed: %s", exc)
        if args.verbose:
            raise
        return 1

    output_path = (
        Path(args.output)
        if args.output
        else settings.output_dir / f"weekly_insight_{start_date}_{end_date}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Done. Output saved to: %s", output_path)
    print(str(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
