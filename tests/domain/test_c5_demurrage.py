"""Calc spec C5/C6 — demurrage days and amount.

Company convention (verified 4x against real sheets): demurrage days =
whole days of total port time minus contract laytime, hours truncated,
never negative, only meaningful when the contract has a rate.
"""

from datetime import timedelta

from domain.calculations import demurrage_amount_idr, demurrage_days


def td(days, hours=0, minutes=0):
    return timedelta(days=days, hours=hours, minutes=minutes)


class TestDemurrageDays:
    def test_v2605_three_days(self):
        assert demurrage_days(td(13, 19, 30), laytime_days=10) == 3

    def test_v2606_seventeen_days(self):
        assert demurrage_days(td(24, 3, 5), laytime_days=7) == 17

    def test_hn2_v2602_seven_days(self):
        assert demurrage_days(td(21, 20, 0), laytime_days=14) == 7

    def test_v2501_under_laytime_is_zero(self):
        assert demurrage_days(td(11, 8, 35), laytime_days=12) == 0

    def test_exactly_on_laytime_is_zero(self):
        assert demurrage_days(td(10), laytime_days=10) == 0

    def test_no_laytime_means_no_answer(self):
        assert demurrage_days(td(20), laytime_days=None) is None

    def test_no_port_time_means_no_answer(self):
        assert demurrage_days(None, laytime_days=10) is None


class TestDemurrageAmount:
    def test_v2605_rp60jt(self):
        # 3 days x Rp 20,000,000/day
        assert demurrage_amount_idr(td(13, 19, 30), laytime_days=10, rate_idr=20_000_000) == 60_000_000

    def test_no_rate_means_no_claim(self):
        assert demurrage_amount_idr(td(27, 5, 53), laytime_days=12, rate_idr=None) is None

    def test_zero_days_means_zero_claim(self):
        assert demurrage_amount_idr(td(11, 8, 35), laytime_days=12, rate_idr=20_000_000) == 0
