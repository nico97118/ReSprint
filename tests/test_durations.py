import json
import shutil
import subprocess
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pytest

from resprint.config import Settings
from resprint.durations import duration_display, seconds_to_days, validate_hours_per_day
from resprint.exporters.common import format_duration
from resprint.frontend.i18n import configure_language, current_language
from resprint.frontend.report.page import render_html
from resprint.models import Issue, IssueReviewItem, Sprint, SprintReview


@pytest.mark.parametrize("value", [0, -1, True, "7", float("nan"), float("inf"), 1e308])
def test_invalid_working_day_is_rejected(value):
    with pytest.raises(ValueError, match="hours_per_day"):
        validate_hours_per_day(value)


def test_nested_render_context_inherits_and_restores_day_length():
    assert seconds_to_days(25200) == 1
    with pytest.raises(RuntimeError), duration_display(7.5):
        assert seconds_to_days(27000) == 1
        with duration_display():
            assert seconds_to_days(27000) == 1
        with duration_display(8):
            assert seconds_to_days(28800) == 1
        assert seconds_to_days(27000) == 1
        raise RuntimeError()
    assert seconds_to_days(25200) == 1
    assert format_duration(None) == "-"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0m"),
        (30, "<1m"),
        (60, "1m"),
        (1800, "30m"),
        (3600, "1h"),
        (31500, "1j 1h 45m"),
        (-5400, "-1h 30m"),
    ],
)
def test_compact_duration_matches_dynamic_totals(seconds, expected):
    previous = current_language()
    configure_language("fr")
    try:
        assert format_duration(seconds) == expected
        if shutil.which("node"):
            source = Path("src/resprint/frontend/static/table.js").read_text()
            script = (
                "const document = {querySelectorAll: () => [], "
                "addEventListener: () => {}};\n"
                + source
                + f"\nconsole.log(formatDuration({seconds}, {{dataset: "
                '{secondsPerDay: "25200", durationUnit: "j"}}));'
            )
            result = subprocess.run(
                ["node", "-e", script], check=True, capture_output=True, text=True
            )
            assert result.stdout.strip() == expected
    finally:
        configure_language(previous)


def test_settings_accepts_fractional_day_and_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JIRA_API_TOKEN", "test")
    path = tmp_path / "settings.toml"
    base = '[jira]\nbase_url = "https://jira.test"\n'
    path.write_text(base)
    assert Settings.from_sources().hours_per_day == 7
    path.write_text(base + "[resprint]\nhours_per_day = 7.5\n")
    assert Settings.from_sources().hours_per_day == 7.5
    path.write_text(base + "[resprint]\nhours_per_day = nan\n")
    with pytest.raises(ValueError, match="hours_per_day"):
        Settings.from_sources()


class ReportData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.charts = {}
        self.tables = []
        self.export = ""
        self.in_export = False
        self.json_export = ""
        self.in_json = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-chart-config" in attrs:
            self.charts[attrs["id"]] = json.loads(attrs["data-chart-config"])
        if "data-seconds-per-day" in attrs:
            self.tables.append(attrs)
        if tag == "script":
            self.in_export = attrs.get("id") == "report-export-markdown"
            self.in_json = attrs.get("id") == "report-export-json"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_export = self.in_json = False

    def handle_data(self, data):
        if self.in_export:
            self.export += data
        if self.in_json:
            self.json_export += data


def test_custom_day_matches_tables_charts_and_embedded_exports():
    issue = Issue(
        "1",
        "A-1",
        "Issue",
        "Done",
        "done",
        None,
        issue_type="Story",
        original_estimate_seconds=54000,
    )
    review = SprintReview((IssueReviewItem(issue, 27000, 27000, 1),), (), ())
    sprint = Sprint(1, "Sprint", date(2026, 11, 1), date(2026, 11, 15))
    previous = current_language()
    configure_language("fr")
    try:
        html = render_html(review, sprint, "https://jira.test", hours_per_day=7.5)
        parsed = ReportData()
        parsed.feed(html)
        assert "1j" in html and "2j" in html
        assert 'data-sort-value="27000"' in html
        assert all(float(t["data-seconds-per-day"]) == 27000 for t in parsed.tables)
        assert all(t["data-duration-unit"] == "j" for t in parsed.tables)
        assert "1j" in parsed.export and "2j" in parsed.export
        comparison = parsed.charts["consumed-time-by-issue-type-chart"]
        assert comparison["data"]["datasets"][0]["data"] == [1.0]
        assert comparison["options"]["scales"]["x"]["title"]["text"] == "Jours"
        exported = json.loads(parsed.json_export)
        assert exported["completed"][0]["tempo_seconds"] == 27000
        assert exported["completed"][0]["tempo_hours"] == 7.5
        configure_language("en")
        assert "1d" in render_html(
            review, sprint, "https://jira.test", hours_per_day=7.5
        )
    finally:
        configure_language(previous)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_javascript_totals_use_the_rendered_day_length():
    source = Path("src/resprint/frontend/static/table.js").read_text()
    script = (
        "const document = {querySelectorAll: () => [], addEventListener: () => {}};\n"
        + source
        + "\nconsole.log(formatDuration(54000, {dataset: "
        '{secondsPerDay: "27000", durationUnit: "j"}}));'
    )
    result = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    assert result.stdout.strip() == "2j"


def test_concurrent_reports_keep_independent_day_lengths():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def render(hours):
        with duration_display(hours):
            barrier.wait(timeout=5)
            return seconds_to_days(25200)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(render, (7, 3.5)))
    assert results == [1, 2]
    assert seconds_to_days(25200) == 1
