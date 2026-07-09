"""Calc spec C7 — non-blocking log warnings (W1 gaps, W2 overlaps)."""

from datetime import timedelta

from domain.warnings import log_warnings
from tests.domain.conftest import act


class TestGapWarningsW1:
    def test_v2605_real_two_day_gap_before_laden(self):
        # Real case: waiting_cast_off ends 2026-04-29 07:00, laden starts 2026-05-01 08:30
        acts = [
            act("waiting_cast_off", "2026-04-28 18:00", "2026-04-29 07:00"),
            act("laden", "2026-05-01 08:30", "2026-05-05 09:00"),
        ]
        (w,) = log_warnings(acts)
        assert w.code == "gap"
        assert w.after_index == 0
        assert w.amount == timedelta(days=2, hours=1, minutes=30)

    def test_gap_at_threshold_is_tolerated(self):
        acts = [
            act("loading", "2026-01-01 08:00", "2026-01-01 12:00"),
            act("waiting_cast_off", "2026-01-01 12:30", "2026-01-01 15:00"),
        ]
        assert log_warnings(acts) == []

    def test_contiguous_log_is_clean(self):
        acts = [
            act("loading", "2026-01-01 08:00", "2026-01-01 12:00"),
            act("waiting_cast_off", "2026-01-01 12:00", "2026-01-01 15:00"),
        ]
        assert log_warnings(acts) == []


class TestOverlapWarningsW2:
    def test_overlapping_activities_flagged(self):
        acts = [
            act("loading", "2026-01-01 08:00", "2026-01-01 12:00"),
            act("waiting_cast_off", "2026-01-01 10:00", "2026-01-01 15:00"),
        ]
        (w,) = log_warnings(acts)
        assert w.code == "overlap"
        assert w.amount == timedelta(hours=2)

    def test_ongoing_previous_activity_not_compared(self):
        acts = [
            act("loading", "2026-01-01 08:00"),  # ongoing
            act("waiting_cast_off", "2026-01-01 10:00", "2026-01-01 15:00"),
        ]
        assert log_warnings(acts) == []
