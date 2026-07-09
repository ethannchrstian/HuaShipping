"""Calc spec C1 — activity duration.

Worked examples use real numbers from docs/reference/timesheets-raw.json.
"""

from datetime import datetime, timedelta

import pytest

from domain.calculations import ActivityEndBeforeStart, activity_duration, format_duration


class TestActivityDuration:
    def test_v2601_ballast_is_4d_15h(self):
        # HN1 V2601 first leg: 2026-01-04 23:30 -> 2026-01-09 14:30 (sheet: HARI=4, WAKTU=15:00)
        d = activity_duration(datetime(2026, 1, 4, 23, 30), datetime(2026, 1, 9, 14, 30))
        assert d == timedelta(days=4, hours=15)

    def test_same_day_activity(self):
        # V2601 tunggu info bongkar: 2026-02-09 11:00 -> 17:45 (sheet: 0 hari, 6:45)
        d = activity_duration(datetime(2026, 2, 9, 11, 0), datetime(2026, 2, 9, 17, 45))
        assert d == timedelta(hours=6, minutes=45)

    def test_ongoing_activity_has_no_duration(self):
        assert activity_duration(datetime(2026, 6, 29, 16, 48), None) is None

    def test_end_before_start_rejected_real_case_v2604(self):
        # Real error in HN1 V2604 tunggu-muat: 2026-04-06 23:30 -> 2026-04-06 17:20
        with pytest.raises(ActivityEndBeforeStart):
            activity_duration(datetime(2026, 4, 6, 23, 30), datetime(2026, 4, 6, 17, 20))

    def test_end_before_start_rejected_real_case_v2501(self):
        # Real error in V2501 row 15: 2025-12-14 14:30 -> 13:15 same day
        with pytest.raises(ActivityEndBeforeStart):
            activity_duration(datetime(2025, 12, 14, 14, 30), datetime(2025, 12, 14, 13, 15))

    def test_zero_duration_allowed_real_case_hn2_v2603(self):
        # HN2 V2603 row 14: tunggu info sandar 2026-06-17 10:55 -> 10:55 ("no waiting")
        t = datetime(2026, 6, 17, 10, 55)
        assert activity_duration(t, t) == timedelta(0)


class TestFormatDuration:
    def test_days_and_time(self):
        assert format_duration(timedelta(days=4, hours=15)) == "4d 15:00"

    def test_under_one_day(self):
        assert format_duration(timedelta(hours=6, minutes=45)) == "0d 06:45"

    def test_none_is_dash(self):
        assert format_duration(None) == "—"
