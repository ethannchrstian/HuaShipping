"""Golden test for the historical importer (docs/05-import-mapping.md).

Feeds the committed ground-truth dump (docs/reference/timesheets-raw.json)
through voyages.importer.import_all and asserts the resulting database matches
the real sheets: counts, header normalization, WIB->UTC storage, flagged
errors (never silently fixed), and the built-in verification report.
"""

import json
from datetime import UTC
from decimal import Decimal
from pathlib import Path

import pytest

from voyages.importer import import_all
from voyages.models import Activity, Charterer, Parcel, Vessel, Voyage

DATA = Path(__file__).resolve().parents[2] / "docs" / "reference" / "timesheets-raw.json"

KNOWN_ERROR_SHEETS = {
    "HN 1 PH 2401 Voy. V2501",  # end-before-start row
    "HN 1 PH 2401 Voy. V2604",  # end-before-start row
    "HN 2 PH 2402 Voy. V2602",  # row-16 phantom day + row-17 date typo
}


@pytest.fixture
def report(db):
    return import_all(json.loads(DATA.read_text(encoding="utf-8")))


def voyage(vessel_hint: str, code: str) -> Voyage:
    return Voyage.objects.get(vessel__name__contains=vessel_hint, code=code)


class TestInventory:
    def test_all_voyages_imported(self, report):
        assert Voyage.objects.count() == 11
        assert Vessel.objects.count() == 2

    def test_both_vessels_have_their_v2601(self, report):
        assert Voyage.objects.filter(code="V2601").count() == 2

    def test_charterers_extracted_from_contract_numbers(self, report):
        assert set(Charterer.objects.values_list("code", flat=True)) == {
            "FPS", "PSCOI", "PNLF", "GGU", "SIP"
        }

    def test_fn_huat_maps_to_fps(self, report):
        # docs/05: 'FN-HUAT' is FPS per the prototype seed
        assert voyage("Navigator 1", "V2601").charterer.code == "FPS"


class TestHeaderNormalization:
    def test_v2501_split_laytime(self, report):
        v = voyage("Navigator 1", "V2501")
        assert (v.laytime_load_days, v.laytime_discharge_days, v.laytime_days) == (
            Decimal("6"), Decimal("6"), Decimal("12")
        )

    def test_v2501_cargo_kg_normalized_to_mt(self, report):
        p = voyage("Navigator 1", "V2501").parcels.get()
        assert (p.commodity, p.quantity_mt) == ("CPO", Decimal("4000"))

    def test_demurrage_rates(self, report):
        assert voyage("Navigator 2", "V2602").demurrage_rate_idr == 15_000_000
        assert voyage("Navigator 1", "V2605").demurrage_rate_idr == 20_000_000
        assert voyage("Navigator 1", "V2501").demurrage_rate_idr is None  # clause '-'

    def test_v2607_empty_header_imports_as_nulls(self, report):
        v = voyage("Navigator 1", "V2607")
        assert v.charterer is None and v.laytime_days is None
        assert v.parcels.count() == 0


class TestTimestamps:
    def test_wib_stored_as_utc(self, report):
        # HN1 V2601 ballast starts 2026-01-04 23:30 WIB = 16:30 UTC same day
        ballast = voyage("Navigator 1", "V2601").activities.get(activity_type_id="ballast")
        start = ballast.start_at.astimezone(UTC)
        assert (start.day, start.hour, start.minute) == (4, 16, 30)

    def test_activity_counts(self, report):
        assert voyage("Navigator 1", "V2601").activities.count() == 10


class TestFlaggedErrors:
    """docs/05: the importer flags bad rows, never silently fixes them."""

    @pytest.mark.parametrize("code", ["V2501", "V2604"])
    def test_end_before_start_cleared_and_noted(self, report, code):
        v = voyage("Navigator 1", code)
        bad = [a for a in v.activities.all() if a.note.startswith("IMPORT:")]
        assert len(bad) == 1
        assert bad[0].end_at is None

    def test_flags_reported(self, report):
        flagged = {r.sheet_name for r in report.results if r.flags}
        assert "HN 1 PH 2401 Voy. V2501" in flagged
        assert "HN 1 PH 2401 Voy. V2604" in flagged


class TestStatus:
    def test_ongoing_voyages(self, report):
        assert voyage("Navigator 1", "V2607").status == Voyage.Status.ONGOING
        assert voyage("Navigator 2", "V2603").status == Voyage.Status.ONGOING

    def test_completed_voyages_are_locked(self, report):
        done = Voyage.objects.filter(status=Voyage.Status.COMPLETED)
        assert done.count() == 9
        assert all(v.locked for v in done)


class TestMultiJettyParcels:
    def test_hn2_v2601_two_parcels_from_loading_quantities(self, report):
        v = voyage("Navigator 2", "V2601")
        quantities = sorted(p.quantity_mt for p in v.parcels.all())
        assert quantities == [Decimal("1000"), Decimal("3000")]
        assert v.parcels.values("load_jetty").distinct().count() == 2

    def test_hn1_v2606_three_shipper_parcels(self, report):
        v = voyage("Navigator 1", "V2606")
        assert v.parcels.count() == 3
        assert sum(p.quantity_mt for p in v.parcels.all()) == Decimal("4000")
        shippers = {p.shipper for p in v.parcels.all()}
        assert {"PT. TBSM", "PT. PAM", "PT. GUM"} <= shippers


class TestVerification:
    """The acceptance test inside the importer: recompute everything and diff
    against the printed sheets. Only the three known-error sheets may differ."""

    def test_only_known_error_sheets_mismatch(self, report):
        mismatching = {r.sheet_name for r in report.results if r.mismatches}
        assert mismatching == KNOWN_ERROR_SHEETS

    def test_clean_sheets_verify_ok(self, report):
        clean = [r for r in report.results if r.sheet_name not in KNOWN_ERROR_SHEETS]
        assert len(clean) == 8
        assert all(not r.mismatches for r in clean)

    def test_report_renders(self, report):
        md = report.as_markdown()
        assert "V2601" in md and "OK" in md


class TestNoDataInvented:
    def test_every_activity_belongs_to_a_voyage_and_type(self, report):
        assert not Activity.objects.filter(voyage__isnull=True).exists()

    def test_no_parcel_without_jetty(self, report):
        assert not Parcel.objects.filter(load_jetty__isnull=True).exists()
