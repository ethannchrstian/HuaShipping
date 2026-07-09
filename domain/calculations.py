"""Voyage time & money calculations — docs/04-calculation-spec.md.

Function names carry the rule number they implement. All timestamps are naive
here; timezone handling belongs to the persistence/UI layers (ADR-008).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.model import Activity, Phase


class ActivityEndBeforeStart(ValueError):
    """C1 validation: an activity must end strictly after it starts."""


def activity_duration(start_at: datetime, end_at: datetime | None) -> timedelta | None:
    """C1. Exact duration; None while ongoing. Zero duration is legal (a 'no waiting' row,
    real case HN2-V2603); ending before starting is not."""
    if end_at is None:
        return None
    if end_at < start_at:
        raise ActivityEndBeforeStart(f"end {end_at} is before start {start_at}")
    return end_at - start_at


def format_duration(duration: timedelta | None) -> str:
    """C1 display convention: '<whole days>d HH:MM' ('—' when unknown)."""
    if duration is None:
        return "—"
    minutes = int(duration.total_seconds() // 60)
    return f"{minutes // 1440}d {(minutes % 1440) // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class PortBlocks:
    """C2. Port blocks in log order: load blocks (A, B, ...) then discharge blocks."""

    load: list[list[Activity]]
    discharge: list[list[Activity]]

    @property
    def in_order(self) -> list[list[Activity]]:
        return self.load + self.discharge


def split_port_blocks(activities: list[Activity]) -> PortBlocks:
    """C2. Sailing legs delimit blocks; blocks before the final laden leg load, after it discharge."""
    acts = sorted(activities, key=lambda a: a.start_at)
    last_laden_start = max(
        (a.start_at for a in acts if a.type.phase is Phase.LADEN), default=None
    )
    load: list[list[Activity]] = []
    discharge: list[list[Activity]] = []
    run: list[Activity] = []

    def close_run():
        if not run:
            return
        is_discharge = last_laden_start is not None and run[0].start_at > last_laden_start
        (discharge if is_discharge else load).append(run.copy())
        run.clear()

    for a in acts:
        if a.type.is_sailing:
            close_run()
        else:
            run.append(a)
    close_run()
    return PortBlocks(load=load, discharge=discharge)


@dataclass(frozen=True)
class SheetPair:
    """C3 display convention: whole-day parts and HH:MM parts summed as separate columns."""

    days: int
    time: timedelta

    def normalized(self) -> SheetPair:
        return SheetPair(self.days + self.time.days, self.time - timedelta(days=self.time.days))

    def as_timedelta(self) -> timedelta:
        return timedelta(days=self.days) + self.time


def _countable(block: list[Activity]) -> list[Activity]:
    """Activities that count toward port time: completed, non-persiapan (C2/C3)."""
    return [a for a in block if a.end_at is not None and a.type.phase is not Phase.PREP]


def block_sheet_pair(block: list[Activity]) -> SheetPair:
    """C3. The sheet's (HARI, WAKTU) column pair for one block."""
    days = 0
    time = timedelta()
    for a in _countable(block):
        d = activity_duration(a.start_at, a.end_at)
        days += d.days
        time += d - timedelta(days=d.days)
    return SheetPair(days, time)


def block_port_time(block: list[Activity]) -> timedelta:
    """C3. True elapsed port time of one block."""
    return block_sheet_pair(block).as_timedelta()


def combined_sheet_pair(activities: list[Activity]) -> SheetPair:
    """C4. The sheet's 'Total Kegiatan Muat - Bongkar (A + B ...)' row."""
    days = 0
    time = timedelta()
    for block in split_port_blocks(activities).in_order:
        pair = block_sheet_pair(block)
        days += pair.days
        time += pair.time
    return SheetPair(days, time)


def total_port_time(activities: list[Activity]) -> timedelta | None:
    """C4. Total port time across all blocks; None when nothing is countable."""
    blocks = split_port_blocks(activities)
    if not any(_countable(b) for b in blocks.in_order):
        return None
    return combined_sheet_pair(activities).as_timedelta()


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
