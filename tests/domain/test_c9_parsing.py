"""Calc spec C9 — unit normalization. Every test string is verbatim real data."""

import pytest

from domain.parsing import parse_cargo, parse_demurrage_rate, parse_laytime


class TestParseCargo:
    @pytest.mark.parametrize(
        ("raw", "commodity", "mt"),
        [
            ("CPO 4.000 MT", "CPO", 4000),  # HN1 2026, Indonesian thousand-dot
            ("CPO 4.000.000 KG ", "CPO", 4000),  # V2501, kilograms
            ("CPO 4,000 MT", "CPO", 4000),  # HN1 V2605, comma separator
            ("CPO 4,130 MT ", "CPO", 4130),  # HN2 V2602
            ("4,000 MT CPO", "CPO", 4000),  # HN2 V2603, order flipped
        ],
    )
    def test_real_variants(self, raw, commodity, mt):
        cargo = parse_cargo(raw)
        assert cargo.commodity == commodity
        assert cargo.quantity_mt == mt

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            parse_cargo("muatan campuran")


class TestParseLaytime:
    def test_combined(self):
        lt = parse_laytime("12 hari")
        assert (lt.total_days, lt.load_days, lt.discharge_days) == (12, None, None)

    def test_combined_capitalized(self):
        assert parse_laytime("7 Hari").total_days == 7

    def test_split_v2501(self):
        lt = parse_laytime("6 Hari Muat + 6 Hari Bongkar")
        assert (lt.total_days, lt.load_days, lt.discharge_days) == (12, 6, 6)


class TestParseDemurrageRate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("-", None),
            ("- ", None),
            ("Rp. 20,000,000/hari", 20_000_000),  # HN1 V2605
            ("Rp. 25.000.000", 25_000_000),  # HN1 V2606, no /hari
            ("Rp 20.000.000/hari", 20_000_000),  # HN2 V2603, no dot after Rp
            ("Rp. 15.000.000/hari", 15_000_000),  # HN2 V2602
        ],
    )
    def test_real_variants(self, raw, expected):
        assert parse_demurrage_rate(raw) == expected
