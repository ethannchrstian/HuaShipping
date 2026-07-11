"""Dashboard presenter tests (UI v4): phase tracker, year-scoped KPIs, alerts."""

import json
from pathlib import Path

import pytest

from voyages import presenters
from voyages.importer import import_all
from voyages.models import Vessel, Voyage

DATA = Path(__file__).resolve().parents[2] / "docs" / "reference" / "timesheets-raw.json"


@pytest.fixture
def data(db):
    import_all(json.loads(DATA.read_text(encoding="utf-8")))


def test_num_id_thousand_separators():
    assert presenters.num_id(40130) == "40.130"
    assert presenters.num_id(0) == "0"


def test_voyage_year_from_code(data):
    assert presenters.voyage_year(Voyage.objects.get(code="V2501")) == 2025
    assert {presenters.voyage_year(v) for v in Voyage.objects.filter(code="V2601")} == {2026}


class TestVesselCards:
    def cards(self):
        return {c["vessel"].tug_name: c for c in presenters.vessel_cards(Vessel.objects.all())}

    def test_discharging_voyage_marks_bongkar_current(self, data):
        # HN2's latest voyage V2603 is mid-discharge (last activity: kegiatan bongkar, open)
        card = self.cards()["TB. HUA Navigator 2"]
        states = {s["label"]: s["state"] for s in card["steps"]}
        assert states == {"Muat": "done", "Berlayar": "done", "Bongkar": "current"}
        assert card["phase_ongoing"] is True
        assert card["marker_pct"] > 50  # marker sits on the discharge side

    def test_ballast_voyage_marks_muat_current(self, data):
        # HN1's latest voyage V2607 just departed (perjalanan ke lokasi muat)
        card = self.cards()["TB. HUA Navigator 1"]
        states = {s["label"]: s["state"] for s in card["steps"]}
        assert states == {"Muat": "current", "Berlayar": "todo", "Bongkar": "todo"}
        assert card["route_known"] is False  # no parcels or discharge jetty yet

    def test_progress_uses_laytime(self, data):
        card = self.cards()["TB. HUA Navigator 2"]
        assert card["laytime"] == 10
        assert card["progress_pct"] == round(card["port_days"] / 10 * 100)


class TestKpis:
    def test_year_scoping_and_prev_year(self, data):
        k = presenters.kpis(Voyage.objects.prefetch_related("activities__activity_type", "parcels"), 2026)
        assert k["year"] == 2026
        assert k["ongoing"] == 2  # V2607 and V2603 (HN2)
        # 2025 has exactly one voyage, V2501 (4.000 MT, no demurrage rate)
        assert k["mt_prev"] == 4000
        assert k["dem_days_prev"] == 0
        # 2026 demurrage: V2605 alone bills 3 days at Rp 20jt (docs/04); total >= that
        assert k["dem_days"] >= 3
        assert k["dem_amount"].startswith("Rp ")

    def test_mt_formatted_indonesian(self, data):
        k = presenters.kpis(Voyage.objects.prefetch_related("activities__activity_type", "parcels"), 2026)
        assert k["mt_fmt"] == presenters.num_id(k["mt"])


class TestAlerts:
    def test_only_ongoing_voyages_alerted(self, data):
        items = presenters.alerts(Voyage.objects.prefetch_related("activities__activity_type"))
        assert items, "imported history has ongoing voyages with findings"
        assert all(a["voyage"].status == Voyage.Status.ONGOING for a in items)

    def test_missing_laytime_flagged_in_indonesian(self, data):
        items = presenters.alerts(Voyage.objects.prefetch_related("activities__activity_type"))
        texts = " | ".join(a["text"] for a in items)
        assert "V2607 belum punya lama kontrak" in texts

    def test_severity_order_and_cap(self, data):
        items = presenters.alerts(Voyage.objects.prefetch_related("activities__activity_type"))
        order = {"bad": 0, "warn": 1, "info": 2}
        ranks = [order[a["kind"]] for a in items]
        assert ranks == sorted(ranks)
        assert len(items) <= 5
