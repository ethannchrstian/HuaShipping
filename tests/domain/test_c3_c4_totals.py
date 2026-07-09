"""Calc spec C3/C4 — block subtotals and total port time.

The sheet prints subtotals as a (whole-day parts, HH:MM parts) column pair,
summed separately and normalized only at the grand total — reproduced here
exactly so the printed documents can be regenerated (worked example: V2601).
"""

from datetime import timedelta

from domain.calculations import (
    SheetPair,
    block_port_time,
    block_sheet_pair,
    combined_sheet_pair,
    split_port_blocks,
    total_port_time,
)
from tests.domain.conftest import act, v2601_activities


class TestV2601WorkedExample:
    """docs/04-calculation-spec.md C3/C4 worked example, real numbers."""

    def setup_method(self):
        self.blocks = split_port_blocks(v2601_activities())

    def test_load_block_pair_prints_19_and_1d17h(self):
        assert block_sheet_pair(self.blocks.load[0]) == SheetPair(19, timedelta(days=1, hours=17))

    def test_load_block_port_time_normalized(self):
        assert block_port_time(self.blocks.load[0]) == timedelta(days=20, hours=17)

    def test_discharge_block_pair_excludes_persiapan(self):
        # 2d06:15 + 6:45 + 3d23:53 (persiapan 19:07 excluded) -> days 5, time 1d12:53
        expected = SheetPair(5, timedelta(days=1, hours=12, minutes=53))
        assert block_sheet_pair(self.blocks.discharge[0]) == expected

    def test_combined_pair_matches_sheet_a_plus_b_row(self):
        expected = SheetPair(24, timedelta(days=3, hours=5, minutes=53))
        assert combined_sheet_pair(v2601_activities()) == expected

    def test_normalized_grand_total(self):
        assert combined_sheet_pair(v2601_activities()).normalized() == SheetPair(
            27, timedelta(hours=5, minutes=53)
        )

    def test_total_port_time(self):
        assert total_port_time(v2601_activities()) == timedelta(days=27, hours=5, minutes=53)


class TestExclusions:
    def test_ongoing_activity_excluded_from_totals(self):
        acts = [
            act("ballast", "2026-06-20 08:00", "2026-06-22 08:00"),
            act("waiting_berth_load", "2026-06-22 08:00", "2026-06-22 20:00"),
            act("loading", "2026-06-22 20:00"),  # ongoing, no end
        ]
        assert total_port_time(acts) == timedelta(hours=12)

    def test_sailing_time_never_counts_as_port_time(self):
        acts = [
            act("ballast", "2026-01-01 00:00", "2026-01-03 00:00"),
            act("loading", "2026-01-03 00:00", "2026-01-04 00:00"),
            act("laden", "2026-01-04 00:00", "2026-01-06 00:00"),
            act("discharging", "2026-01-06 00:00", "2026-01-07 06:00"),
        ]
        assert total_port_time(acts) == timedelta(days=2, hours=6)

    def test_empty_log_has_no_port_time(self):
        assert total_port_time([]) is None
