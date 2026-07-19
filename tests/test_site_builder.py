"""Static-site generator tests (pure filesystem, no network)."""

import json

import pytest

from web.site_builder import build_site, load_reports


def _report_json(start, end, headline):
    return {
        "period_start": start,
        "period_end": end,
        "weekly_highlights": [
            {
                "title": f"Highlight for {start}",
                "date": start,
                "summary": "A factual summary of the market event this week.",
                "source": "Reuters",
                "indonesia_impact": "Pressures the rupiah and IHSG via foreign flows.",
            }
        ],
        "major_headline": {
            "title": headline,
            "summary": "The single most important development for markets this week.",
            "source": "Reuters",
        },
        "key_insight": {
            "summary": "A sufficiently long analytical paragraph about Indonesia and global markets.",
            "source": "Reuters",
        },
        "source_department": "Research and Education Department",
    }


@pytest.fixture
def reports_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    (d / "weekly_insight_2026-06-23_2026-06-30.json").write_text(
        json.dumps(_report_json("2026-06-23", "2026-06-30", "BI hikes rate")),
        encoding="utf-8",
    )
    (d / "weekly_insight_2026-07-05_2026-07-12.json").write_text(
        json.dumps(_report_json("2026-07-05", "2026-07-12", "Oil surges past $80")),
        encoding="utf-8",
    )
    # Files that are not reports must be ignored, not crash the build.
    (d / "cache_2026-07-05_2026-07-12.json").write_text("[]", encoding="utf-8")
    (d / "weekly_insight_broken.json").write_text("{not json", encoding="utf-8")
    return d


def test_load_reports_sorts_newest_first(reports_dir):
    issues = load_reports(reports_dir)
    assert len(issues) == 2
    assert issues[0].slug == "2026-07-05_2026-07-12"
    assert issues[1].slug == "2026-06-23_2026-06-30"


def test_build_site_writes_expected_files(tmp_path, reports_dir):
    site = tmp_path / "site"
    issues = build_site(reports_dir, site, base_url="https://example.com")

    assert len(issues) == 2
    for name in ("index.html", "404.html", "reports.json", "robots.txt", ".nojekyll", "sitemap.xml"):
        assert (site / name).exists(), name
    assert (site / "assets" / "style.css").exists()
    assert (site / "assets" / "app.js").exists()
    assert (site / "reports" / "2026-07-05_2026-07-12.html").exists()
    assert (site / "reports" / "2026-06-23_2026-06-30.html").exists()

    index = (site / "index.html").read_text(encoding="utf-8")
    # Newest issue is featured; older one appears in the archive list.
    assert "Oil surges past $80" in index
    assert "BI hikes rate" in index
    assert 'href="assets/style.css"' in index

    page = (site / "reports" / "2026-07-05_2026-07-12.html").read_text(encoding="utf-8")
    assert 'href="../assets/style.css"' in page
    assert 'href="../"' in page  # back to archive
    assert "Impact on Indonesia" in page
    assert "canonical" in page

    manifest = json.loads((site / "reports.json").read_text(encoding="utf-8"))
    assert manifest["issues"][0]["period_end"] == "2026-07-12"
    assert manifest["issues"][0]["url"] == "reports/2026-07-05_2026-07-12.html"


def test_build_site_without_base_url_skips_sitemap(tmp_path, reports_dir):
    site = tmp_path / "site"
    build_site(reports_dir, site)
    assert not (site / "sitemap.xml").exists()
    assert "Sitemap:" not in (site / "robots.txt").read_text(encoding="utf-8")


def test_build_site_with_no_reports(tmp_path):
    empty = tmp_path / "output"
    empty.mkdir()
    site = tmp_path / "site"
    issues = build_site(empty, site)
    assert issues == []
    assert "No issues published yet" in (site / "index.html").read_text(encoding="utf-8")


def test_rebuild_removes_stale_pages(tmp_path, reports_dir):
    site = tmp_path / "site"
    build_site(reports_dir, site)
    stale = site / "reports" / "2020-01-01_2020-01-08.html"
    stale.write_text("old", encoding="utf-8")

    build_site(reports_dir, site)  # clean=True by default
    assert not stale.exists()
