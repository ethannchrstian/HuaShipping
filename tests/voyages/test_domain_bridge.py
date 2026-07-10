"""The seam between storage and math: models hold raw facts, all computed
numbers come from the already-proven domain/ package via Activity.to_domain().
"""

from datetime import UTC, datetime, timedelta

import pytest

from domain.calculations import SheetPair, combined_sheet_pair, total_port_time
from domain.model import ACTIVITY_TYPES
from voyages.models import Activity, ActivityType


def ts(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


class TestActivityTypeSeed:
    """The DB lookup table must mirror domain.model.ACTIVITY_TYPES exactly —
    one source of truth, the migration only copies it."""

    def test_all_types_seeded(self, db):
        assert set(ActivityType.objects.values_list("code", flat=True)) == set(ACTIVITY_TYPES)

    @pytest.mark.parametrize("code", sorted(ACTIVITY_TYPES))
    def test_row_matches_domain(self, db, code):
        row, dom = ActivityType.objects.get(code=code), ACTIVITY_TYPES[code]
        assert (row.label_id, row.phase, row.is_sailing) == (dom.label_id, dom.phase.value, dom.is_sailing)


class TestToDomain:
    def test_model_activity_converts(self, voyage):
        a = Activity.objects.create(
            voyage=voyage,
            activity_type_id="ballast",
            start_at=ts("2026-01-07 17:00"),
            end_at=ts("2026-01-12 08:00"),
            note="dari Dumai",
        )
        d = a.to_domain()
        assert d.type_code == "ballast"
        assert d.end_at - d.start_at == timedelta(days=4, hours=15)
        assert d.note == "dari Dumai"

    def test_voyage_totals_computed_by_domain_engine(self, voyage):
        rows = [
            ("ballast", "2026-06-20 08:00", "2026-06-22 08:00"),
            ("waiting_berth_load", "2026-06-22 08:00", "2026-06-22 20:00"),
            ("loading", "2026-06-22 20:00", "2026-06-23 20:00"),
            ("laden", "2026-06-23 20:00", "2026-06-25 20:00"),
            ("discharging", "2026-06-25 20:00", "2026-06-26 08:00"),
        ]
        for type_code, start, end in rows:
            Activity.objects.create(
                voyage=voyage, activity_type_id=type_code, start_at=ts(start), end_at=ts(end)
            )
        acts = voyage.domain_activities()
        assert total_port_time(acts) == timedelta(days=2)
        assert combined_sheet_pair(acts).normalized() == SheetPair(2, timedelta(0))
