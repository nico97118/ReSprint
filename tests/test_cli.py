from datetime import date

import pytest

from sprint_review.cli import _build_parser, _resolve_sprint


class UnusedJiraClient:
    def get_sprint(self, sprint_id: int) -> None:
        raise AssertionError(f"Unexpected agile sprint lookup for {sprint_id}")


def test_resolve_sprint_uses_cli_dates_without_agile_lookup() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--sprint-id",
            "456",
            "--sprint-start",
            "2026-05-01",
            "--sprint-end",
            "2026-05-15",
            "--sprint-name",
            "Sprint 42",
        ]
    )

    sprint = _resolve_sprint(args, UnusedJiraClient())

    assert sprint.id == 456
    assert sprint.name == "Sprint 42"
    assert sprint.start_date == date(2026, 5, 1)
    assert sprint.end_date == date(2026, 5, 15)


def test_resolve_sprint_requires_start_and_end_together() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--sprint-id",
            "456",
            "--sprint-start",
            "2026-05-01",
        ]
    )

    with pytest.raises(ValueError, match="sprint-start"):
        _resolve_sprint(args, UnusedJiraClient())
