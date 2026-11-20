"""Working-day conversion scoped to one report rendering operation."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from math import isfinite

DEFAULT_HOURS_PER_DAY = 7.0
_hours_per_day: ContextVar[float] = ContextVar(
    "resprint_hours_per_day", default=DEFAULT_HOURS_PER_DAY
)


def validate_hours_per_day(value: object) -> float:
    """Accept finite, positive TOML numbers for the working-day length."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("[resprint] hours_per_day must be a positive finite number")
    hours = float(value)
    if not isfinite(hours) or hours <= 0 or not isfinite(hours * 3600):
        raise ValueError("[resprint] hours_per_day must be a positive finite number")
    return hours


@contextmanager
def duration_display(hours_per_day: float | None = None) -> Iterator[None]:
    """Apply a day length to nested renderers and restore it, even on failure.

    A missing value inherits the enclosing render's setting. Context variables
    isolate concurrent requests and keep embedded Markdown exports consistent.
    """
    hours = _hours_per_day.get() if hours_per_day is None else hours_per_day
    token = _hours_per_day.set(validate_hours_per_day(hours))
    try:
        yield
    finally:
        _hours_per_day.reset(token)


def seconds_per_day() -> float:
    """Seconds in the working day used by the current report."""
    return _hours_per_day.get() * 3600


def seconds_to_days(seconds: int | float) -> float:
    """Convert a duration without rounding the underlying report data."""
    return seconds / seconds_per_day()
