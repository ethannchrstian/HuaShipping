"""Shared helpers for domain tests."""

from datetime import datetime

from domain.model import Activity


def act(type_code: str, start: str, end: str | None = None, note: str = "") -> Activity:
    """Build an Activity from 'YYYY-MM-DD HH:MM' strings."""
    parse = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M")  # noqa: E731
    return Activity(type_code=type_code, start_at=parse(start), end_at=parse(end) if end else None, note=note)


def v2601_activities() -> list[Activity]:
    """Real HN1 V2601 log (docs/reference/timesheets-raw.json)."""
    return [
        act("ballast", "2026-01-04 23:30", "2026-01-09 14:30"),
        act("waiting_berth_load", "2026-01-09 14:30", "2026-01-21 08:20"),
        act("waiting_load", "2026-01-21 08:20", "2026-01-22 09:30"),
        act("loading", "2026-01-22 09:30", "2026-01-28 15:50"),
        act("waiting_cast_off", "2026-01-28 15:50", "2026-01-30 07:30"),
        act("laden", "2026-01-30 07:30", "2026-02-07 04:45"),
        act("waiting_berth_discharge", "2026-02-07 04:45", "2026-02-09 11:00"),
        act("waiting_discharge", "2026-02-09 11:00", "2026-02-09 17:45"),
        act("discharging", "2026-02-09 17:45", "2026-02-13 17:38"),
        act("preparation", "2026-02-13 17:38", "2026-02-14 12:45"),
    ]
