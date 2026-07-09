"""Voyage time & money calculations — docs/04-calculation-spec.md.

Function names carry the rule number they implement. All timestamps are naive
here; timezone handling belongs to the persistence/UI layers (ADR-008).
"""

from __future__ import annotations

from datetime import datetime, timedelta


class ActivityEndBeforeStart(ValueError):
    """C1 validation: an activity must end strictly after it starts."""


def activity_duration(start_at: datetime, end_at: datetime | None) -> timedelta | None:
    """C1. Exact duration; None while the activity is ongoing."""
    if end_at is None:
        return None
    if end_at <= start_at:
        raise ActivityEndBeforeStart(f"end {end_at} is not after start {start_at}")
    return end_at - start_at


def format_duration(duration: timedelta | None) -> str:
    """C1 display convention: '<whole days>d HH:MM' ('—' when unknown)."""
    if duration is None:
        return "—"
    minutes = int(duration.total_seconds() // 60)
    return f"{minutes // 1440}d {(minutes % 1440) // 60:02d}:{minutes % 60:02d}"


def demurrage_days(total_port_time: timedelta | None, laytime_days: int | None) -> int | None:
    """C5. Whole days of port time minus laytime, hours truncated, floored at 0."""
    if total_port_time is None or laytime_days is None:
        return None
    return max(0, total_port_time.days - laytime_days)


def demurrage_amount_idr(
    total_port_time: timedelta | None,
    laytime_days: int | None,
    rate_idr: int | None,
) -> int | None:
    """C6. days x rate in integer rupiah; None when there is no rate or no answer."""
    days = demurrage_days(total_port_time, laytime_days)
    if days is None or rate_idr is None:
        return None
    return days * rate_idr
