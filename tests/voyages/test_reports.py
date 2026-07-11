"""Laporan aggregation tests against the real imported history."""

import datetime
import json
from pathlib import Path

import pytest

from voyages import reports
from voyages.importer import import_all
from voyages.models import Vessel, Voyage

DATA = Path(__file__).resolve().parents[2] / "docs" / "reference" / "timesheets-raw.json"


@pytest.fixture
def data(db):
    import_all(json.loads(DATA.read_text(encoding="utf-8")))


def qs():
    return Voyage.objects.select_related("vessel", "charterer", "discharge_jetty").prefetch_related(
        "activities__activity_type", "parcels__load_jetty"
    )


class TestCategorize:
    def test_sailing_and_waiting_and_work(self):
        assert reports.categorize("ballast") == "berlayar"
        assert reports.categorize("laden") == "berlayar"
        assert reports.categorize("shifting") == "berlayar"  # is_sailing wins
        assert reports.categorize("waiting_load") == "tunggu"
        assert reports.categorize("waiting_cast_off") == "tunggu"
        assert reports.categorize("waiting_berth_discharge") == "tunggu"
        assert reports.categorize("loading") == "muat"
        assert reports.categorize("discharging") == "bongkar"
        assert reports.categorize("preparation") == "lainnya"


class TestTimeBreakdown:
    def test_parts_sum_to_activity_span(self, data):
        b = reports.time_breakdown(qs(), 2026)
        row = next(r for r in b["rows"] if r["voyage"].code == "V2601" and r["vessel_short"] == "Navigator 1")
        # completed voyage: category days must sum to the full logged span
        v = row["voyage"]
        acts = v.domain_activities()
        span_days = (acts[-1].end_at - acts[0].start_at).total_seconds() / 86400
        assert sum(p["days"] for p in row["parts"]) == pytest.approx(span_days, abs=0.3)

    def test_year_scoping(self, data):
        b2025 = reports.time_breakdown(qs(), 2025)
        assert [r["voyage"].code for r in b2025["rows"]] == ["V2501"]

    def test_legend_totals_cover_all_rows(self, data):
        b = reports.time_breakdown(qs(), 2026)
        legend_days = sum(item["days"] for item in b["legend"])
        row_days = sum(p["days"] for r in b["rows"] for p in r["parts"])
        assert legend_days == pytest.approx(row_days, abs=0.5)


class TestJettyWaiting:
    def test_attributes_waiting_to_places(self, data):
        rows = reports.jetty_waiting(qs(), 2026)
        assert rows, "2026 voyages have waiting time"
        places = {r["place"] for r in rows}
        assert "Dumai" in places  # discharge waiting on the Belitung->Dumai runs
        for r in rows:
            assert r["calls"] >= 1 and r["total"] > datetime.timedelta()
        # sorted by average waiting, descending
        avgs = [r["avg_hours"] for r in rows]
        assert avgs == sorted(avgs, reverse=True)

    def test_jetty_totals_bounded_by_global_waiting(self, data):
        # regression: V2604's flagged open-ended activity must not smear
        # waiting time until 'now' (it is a completed voyage)
        rows = reports.jetty_waiting(qs(), 2026)
        jetty_total = sum((r["total"] for r in rows), datetime.timedelta())
        b = reports.time_breakdown(qs(), 2026)
        global_tunggu = next(x for x in b["legend"] if x["key"] == "tunggu")["days"]
        assert jetty_total.total_seconds() / 86400 <= global_tunggu + 0.5


class TestChartererDemurrage:
    def test_pnlf_matches_oracle(self, data):
        rows = reports.charterer_demurrage(qs(), 2026)
        pnlf = next(r for r in rows if r["charterer"] == "PNLF")
        # PNLF 2026 = V2604, HN2-V2603 (no demurrage) + V2605 (3 days x Rp 20jt, docs/04)
        assert pnlf["n"] == 3
        assert pnlf["dem_days"] == 3
        assert pnlf["dem_idr"] == 60_000_000

    def test_sorted_by_money_first(self, data):
        rows = reports.charterer_demurrage(qs(), 2026)
        idrs = [r["dem_idr"] for r in rows]
        assert idrs == sorted(idrs, reverse=True)


class TestUtilization:
    def test_months_account_for_all_days(self, data):
        u = reports.utilization(Vessel.objects.filter(active=True), 2026)
        assert len(u) == 2
        for vessel_row in u:
            assert len(vessel_row["months"]) == 12
            for m in vessel_row["months"]:
                if m["future"]:
                    continue
                assert m["idle_days"] >= 0
                assert m["sail_days"] >= 0 and m["port_days"] >= 0

    def test_full_past_month_sums_to_month_length(self, data):
        u = reports.utilization(Vessel.objects.filter(active=True), 2026)
        march = next(m for m in u[0]["months"] if m["month"] == 3)
        assert march["sail_days"] + march["port_days"] + march["idle_days"] == pytest.approx(31, abs=0.3)


class TestLaporanView:
    def test_requires_login(self, client, db):
        assert client.get("/laporan/").status_code == 302

    def test_renders_all_sections(self, client, data):
        from django.contrib.auth.models import User

        client.force_login(User.objects.create_user("felicia"))
        html = client.get("/laporan/?tahun=2026").content.decode()
        for text in [
            "Ke mana waktu pergi", "Tunggu per pelabuhan",
            "Demurrage per pencharter", "Pemakaian kapal per bulan",
            "Berlayar", "Menganggur",
        ]:
            assert text in html
