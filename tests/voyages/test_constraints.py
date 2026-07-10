"""Database-level integrity constraints (docs/03-erd.md §Integrity constraints).

These prove PostgreSQL/SQLite itself refuses invalid rows — the last line of
defense behind form validation and the domain layer. Each rule mirrors a real
failure mode found in the Excel history.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError

from voyages.models import Activity, Parcel, Voyage


def ts(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


class TestActivityEndNotBeforeStart:
    """The V2501/V2604 error class: an activity that ends before it starts
    must be physically unstorable (calc spec C1)."""

    def test_end_before_start_rejected(self, voyage):
        with pytest.raises(IntegrityError):
            Activity.objects.create(
                voyage=voyage,
                activity_type_id="waiting_load",
                start_at=ts("2026-01-11 14:30"),
                end_at=ts("2026-01-11 13:15"),  # V2501 row 15, verbatim
            )

    def test_zero_duration_allowed(self, voyage):
        # HN2-V2603's real "no waiting" row: 10:55 -> 10:55 is legal
        a = Activity.objects.create(
            voyage=voyage,
            activity_type_id="waiting_berth_load",
            start_at=ts("2026-06-14 10:55"),
            end_at=ts("2026-06-14 10:55"),
        )
        assert a.pk is not None

    def test_ongoing_activity_allowed(self, voyage):
        a = Activity.objects.create(
            voyage=voyage,
            activity_type_id="loading",
            start_at=ts("2026-07-01 08:00"),
            end_at=None,
        )
        assert a.end_at is None

    def test_unknown_activity_type_rejected(self, voyage):
        # SQLite defers FK checks to commit; check_constraints() forces it now
        # (PostgreSQL would raise on create already). The savepoint discards
        # the bad row once the error fires.
        with pytest.raises(IntegrityError), transaction.atomic():
            Activity.objects.create(
                voyage=voyage,
                activity_type_id="not_a_real_type",
                start_at=ts("2026-07-01 08:00"),
            )
            connection.check_constraints()


class TestVoyageCodeUniquePerVessel:
    """Both real vessels have a V2601 — code is unique per vessel, not globally."""

    def test_same_code_same_vessel_rejected(self, vessel):
        Voyage.objects.create(code="V2601", vessel=vessel)
        with pytest.raises(IntegrityError):
            Voyage.objects.create(code="V2601", vessel=vessel)

    def test_same_code_other_vessel_allowed(self, vessel, vessel2):
        Voyage.objects.create(code="V2601", vessel=vessel)
        v = Voyage.objects.create(code="V2601", vessel=vessel2)
        assert v.pk is not None


class TestSplitLaytimeMustSum:
    """docs/03 rule 4: when laytime 6+6 and total are all set, they must agree."""

    def test_mismatch_rejected(self, vessel):
        with pytest.raises(IntegrityError):
            Voyage.objects.create(
                code="V2501",
                vessel=vessel,
                laytime_days=Decimal("13"),
                laytime_load_days=Decimal("6"),
                laytime_discharge_days=Decimal("6"),
            )

    def test_matching_sum_allowed(self, vessel):
        v = Voyage.objects.create(
            code="V2501",
            vessel=vessel,
            laytime_days=Decimal("12"),
            laytime_load_days=Decimal("6"),
            laytime_discharge_days=Decimal("6"),
        )
        assert v.pk is not None

    def test_combined_only_allowed(self, vessel):
        # 2026 contracts: just "12 hari", no split
        v = Voyage.objects.create(code="V2601", vessel=vessel, laytime_days=Decimal("12"))
        assert v.laytime_load_days is None


class TestMasterDataProtected:
    """FKs are PROTECT: master data in use cannot be deleted (docs/03 rule 3)."""

    def test_jetty_used_by_parcel_cannot_be_deleted(self, voyage, jetty):
        Parcel.objects.create(
            voyage=voyage, commodity="CPO", quantity_mt=Decimal("4000"), load_jetty=jetty
        )
        with pytest.raises(ProtectedError):
            jetty.delete()

    def test_vessel_with_voyages_cannot_be_deleted(self, voyage, vessel):
        with pytest.raises(ProtectedError):
            vessel.delete()

    def test_deleting_voyage_removes_its_children(self, voyage, jetty):
        Parcel.objects.create(
            voyage=voyage, commodity="CPO", quantity_mt=Decimal("4000"), load_jetty=jetty
        )
        Activity.objects.create(
            voyage=voyage, activity_type_id="ballast", start_at=ts("2026-01-07 17:00")
        )
        voyage.delete()
        assert Parcel.objects.count() == 0
        assert Activity.objects.count() == 0


class TestParcelQuantity:
    def test_zero_quantity_rejected(self, voyage, jetty):
        with pytest.raises(IntegrityError):
            Parcel.objects.create(
                voyage=voyage, commodity="CPO", quantity_mt=Decimal("0"), load_jetty=jetty
            )
