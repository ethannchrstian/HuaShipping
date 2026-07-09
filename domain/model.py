"""Domain vocabulary: activity types and the Activity value object (docs/03-erd.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Phase(Enum):
    BALLAST = "ballast"
    WAITING_LOAD = "waiting_load"
    LOAD = "load"
    LADEN = "laden"
    WAITING_DISCHARGE = "waiting_discharge"
    DISCHARGE = "discharge"
    PREP = "prep"


@dataclass(frozen=True)
class ActivityType:
    code: str
    label_id: str  # Indonesian UI label
    phase: Phase
    is_sailing: bool = False


ACTIVITY_TYPES: dict[str, ActivityType] = {
    t.code: t
    for t in [
        ActivityType("ballast", "Perjalanan ke lokasi muat", Phase.BALLAST, is_sailing=True),
        ActivityType("waiting_berth_load", "Tunggu info sandar (muat)", Phase.WAITING_LOAD),
        ActivityType("waiting_load", "Tunggu info muat", Phase.WAITING_LOAD),
        ActivityType("loading", "Kegiatan muat", Phase.LOAD),
        ActivityType("waiting_cast_off", "Tunggu info cast off", Phase.WAITING_LOAD),
        ActivityType("shifting", "Shifting antar jetty", Phase.WAITING_LOAD, is_sailing=True),
        ActivityType("laden", "Perjalanan ke lokasi bongkar", Phase.LADEN, is_sailing=True),
        ActivityType("waiting_berth_discharge", "Tunggu info sandar (bongkar)", Phase.WAITING_DISCHARGE),
        ActivityType("waiting_discharge", "Tunggu info bongkar", Phase.WAITING_DISCHARGE),
        ActivityType("discharging", "Kegiatan bongkar", Phase.DISCHARGE),
        ActivityType("preparation", "Persiapan / lain-lain", Phase.PREP),
    ]
}


@dataclass(frozen=True)
class Activity:
    """One timestamped log entry. end_at None = still ongoing."""

    type_code: str
    start_at: datetime
    end_at: datetime | None = None
    note: str = ""

    def __post_init__(self):
        if self.type_code not in ACTIVITY_TYPES:
            raise ValueError(f"unknown activity type: {self.type_code!r}")

    @property
    def type(self) -> ActivityType:
        return ACTIVITY_TYPES[self.type_code]
