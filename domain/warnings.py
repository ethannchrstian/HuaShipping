"""C7 — non-blocking data-quality warnings over a voyage's activity log."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from domain.model import Activity

GAP_TOLERANCE = timedelta(minutes=30)


@dataclass(frozen=True)
class LogWarning:
    code: str  # "gap" (W1) | "overlap" (W2)
    after_index: int  # index (in start-sorted order) of the activity the issue follows
    amount: timedelta


def log_warnings(activities: list[Activity], gap_tolerance: timedelta = GAP_TOLERANCE) -> list[LogWarning]:
    """W1 unlogged gaps beyond tolerance, W2 overlapping activities."""
    acts = sorted(activities, key=lambda a: a.start_at)
    out: list[LogWarning] = []
    for i in range(len(acts) - 1):
        prev, nxt = acts[i], acts[i + 1]
        if prev.end_at is None:
            continue  # ongoing: nothing to compare yet
        delta = nxt.start_at - prev.end_at
        if delta > gap_tolerance:
            out.append(LogWarning("gap", i, delta))
        elif delta < timedelta():
            out.append(LogWarning("overlap", i, -delta))
    return out
