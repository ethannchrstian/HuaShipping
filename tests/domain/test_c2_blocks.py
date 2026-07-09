"""Calc spec C2 — port-block segmentation.

Sailing legs (ballast / laden / shifting) split the sorted log into port
blocks; blocks before the final laden leg are load blocks, after it discharge
blocks. Verified against the real multi-block voyages HN2-V2601 and HN1-V2606.
"""

from domain.calculations import split_port_blocks
from tests.domain.conftest import act, v2601_activities


class TestSimpleVoyage:
    def test_v2601_one_load_one_discharge_block(self):
        blocks = split_port_blocks(v2601_activities())
        assert len(blocks.load) == 1
        assert len(blocks.discharge) == 1
        assert [a.type_code for a in blocks.load[0]] == [
            "waiting_berth_load",
            "waiting_load",
            "loading",
            "waiting_cast_off",
        ]
        # persiapan belongs to the discharge block (its time is excluded later, C3)
        assert [a.type_code for a in blocks.discharge[0]] == [
            "waiting_berth_discharge",
            "waiting_discharge",
            "discharging",
            "preparation",
        ]


class TestMultiJettyLoading:
    def test_second_ballast_leg_splits_load_blocks_like_hn2_v2601(self):
        # HN2 V2601: load at PAM, short "perjalanan ke lokasi muat" leg to TBSM, load again
        acts = [
            act("ballast", "2026-04-03 20:20", "2026-04-12 04:40"),
            act("waiting_berth_load", "2026-04-12 04:40", "2026-04-14 10:10"),
            act("loading", "2026-04-14 17:05", "2026-04-15 19:30"),
            act("ballast", "2026-04-16 10:20", "2026-04-16 15:40"),  # inter-jetty leg
            act("waiting_berth_load", "2026-04-16 15:40", "2026-04-20 08:00"),
            act("loading", "2026-04-20 15:50", "2026-04-21 09:30"),
            act("laden", "2026-04-25 08:40", "2026-04-30 02:30"),
            act("discharging", "2026-05-05 23:30", "2026-05-07 18:30"),
        ]
        blocks = split_port_blocks(acts)
        assert len(blocks.load) == 2
        assert len(blocks.discharge) == 1

    def test_shifting_splits_load_blocks_like_hn1_v2606(self):
        acts = [
            act("ballast", "2026-05-17 21:00", "2026-05-23 09:10"),
            act("loading", "2026-05-28 23:30", "2026-05-29 12:00"),
            act("shifting", "2026-06-01 08:00", "2026-06-01 12:30"),
            act("loading", "2026-06-03 11:10", "2026-06-04 09:00"),
            act("laden", "2026-06-05 05:00", "2026-06-10 09:00"),
            act("discharging", "2026-06-12 10:00", "2026-06-14 02:00"),
        ]
        blocks = split_port_blocks(acts)
        assert len(blocks.load) == 2
        assert len(blocks.discharge) == 1


class TestEdgeCases:
    def test_no_laden_leg_yet_means_all_blocks_are_load(self):
        acts = [
            act("ballast", "2026-06-20 08:00", "2026-06-22 10:00"),
            act("waiting_berth_load", "2026-06-22 10:00", "2026-06-23 09:00"),
            act("loading", "2026-06-23 09:00"),  # ongoing
        ]
        blocks = split_port_blocks(acts)
        assert len(blocks.load) == 1
        assert blocks.discharge == []

    def test_empty_log(self):
        blocks = split_port_blocks([])
        assert blocks.load == [] and blocks.discharge == []

    def test_activities_are_sorted_by_start(self):
        acts = list(reversed(v2601_activities()))
        blocks = split_port_blocks(acts)
        assert [a.type_code for a in blocks.load[0]][0] == "waiting_berth_load"
