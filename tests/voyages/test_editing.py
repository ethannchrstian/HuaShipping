"""S4 voyage form, activity edit/delete/undo, complete/unlock (docs/06)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User

from voyages.forms import next_code
from voyages.importer import import_all
from voyages.models import Activity, Jetty, Vessel, Voyage

DATA = Path(__file__).resolve().parents[2] / "docs" / "reference" / "timesheets-raw.json"


@pytest.fixture
def data(db):
    import_all(json.loads(DATA.read_text(encoding="utf-8")))


@pytest.fixture
def admin(client, db):
    user = User.objects.create_user("felicia", password="rahasia-kantor")
    client.force_login(user)
    return client


def voyage(vessel_hint, code):
    return Voyage.objects.get(vessel__name__contains=vessel_hint, code=code)


def formset_base(n=0):
    return {
        "parcels-TOTAL_FORMS": str(n),
        "parcels-INITIAL_FORMS": "0",
        "parcels-MIN_NUM_FORMS": "0",
        "parcels-MAX_NUM_FORMS": "1000",
    }


class TestNextCode:
    def test_continues_the_vessel_sequence(self, data):
        hn1 = Vessel.objects.get(name__contains="Navigator 1")
        assert next_code(hn1) == "V2608"  # after real V2607

    def test_fresh_vessel_starts_at_one(self, db):
        v = Vessel.objects.create(name="TB Baru", tug_name="TB Baru", barge_name="BG Baru")
        assert next_code(v) == "V2601"


class TestVoyageCreate:
    def test_form_prefills_next_code(self, admin, data):
        html = admin.get("/voyage/baru/").content.decode()
        assert "V2608" in html and "Simpan voyage" in html

    def test_create_with_parcel(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        jetty = Jetty.objects.first()
        payload = {
            "vessel": vessel.pk,
            "code": "V2608",
            "charterer": "",
            "contract_no": "010/HUAT-FPS/VII/2026",
            "invoice_no": "",
            "discharge_jetty": "",
            "laytime_days": "12",
            "laytime_load_days": "",
            "laytime_discharge_days": "",
            "demurrage_rate_idr": "20000000",
            "notes": "",
            **formset_base(1),
            "parcels-0-commodity": "CPO",
            "parcels-0-quantity_mt": "4000",
            "parcels-0-load_jetty": str(jetty.pk),
            "parcels-0-shipper": "",
        }
        response = admin.post("/voyage/baru/", payload, follow=True)
        v = voyage("Navigator 1", "V2608")
        assert v.parcels.get().quantity_mt == Decimal("4000")
        assert "tersimpan" in response.content.decode()

    def test_split_laytime_autofills_total(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 2")
        payload = {
            "vessel": vessel.pk, "code": "V2604", "charterer": "", "contract_no": "",
            "invoice_no": "", "discharge_jetty": "", "laytime_days": "",
            "laytime_load_days": "6", "laytime_discharge_days": "6",
            "demurrage_rate_idr": "", "notes": "", **formset_base(),
        }
        admin.post("/voyage/baru/", payload)
        assert voyage("Navigator 2", "V2604").laytime_days == Decimal("12")

    def test_split_laytime_mismatch_rejected_with_message(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 2")
        payload = {
            "vessel": vessel.pk, "code": "V2604", "charterer": "", "contract_no": "",
            "invoice_no": "", "discharge_jetty": "", "laytime_days": "13",
            "laytime_load_days": "6", "laytime_discharge_days": "6",
            "demurrage_rate_idr": "", "notes": "", **formset_base(),
        }
        response = admin.post("/voyage/baru/", payload)
        assert "tidak sama dengan muat + bongkar" in response.content.decode()
        assert not Voyage.objects.filter(code="V2604", vessel=vessel).exists()

    def test_duplicate_code_rejected(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        payload = {
            "vessel": vessel.pk, "code": "V2601", "charterer": "", "contract_no": "",
            "invoice_no": "", "discharge_jetty": "", "laytime_days": "",
            "laytime_load_days": "", "laytime_discharge_days": "",
            "demurrage_rate_idr": "", "notes": "", **formset_base(),
        }
        response = admin.post("/voyage/baru/", payload)
        assert response.status_code == 200  # re-rendered with error, nothing saved
        assert Voyage.objects.filter(code="V2601", vessel=vessel).count() == 1


class TestVoyageEditLock:
    def test_locked_voyage_edit_refused(self, admin, data):
        v = voyage("Navigator 1", "V2601")
        response = admin.get(f"/voyage/{v.pk}/ubah/", follow=True)
        assert "terkunci" in response.content.decode()

    def test_unlock_then_complete_roundtrip(self, admin, data):
        v = voyage("Navigator 1", "V2601")
        admin.post(f"/voyage/{v.pk}/buka-kunci/")
        v.refresh_from_db()
        assert v.locked is False and v.status == Voyage.Status.ONGOING
        admin.post(f"/voyage/{v.pk}/selesaikan/")
        v.refresh_from_db()
        assert v.locked is True and v.status == Voyage.Status.COMPLETED

    def test_complete_confirmation_warns_about_ongoing_activity(self, admin, data):
        v = voyage("Navigator 2", "V2603")  # last activity still running
        html = admin.get(f"/voyage/{v.pk}/selesaikan/").content.decode()
        assert "masih berjalan" in html and "Selesaikan voyage" in html


class TestActivityEdit:
    def test_edit_form_bound_to_row(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        act = v.activities.first()
        html = admin.get(f"/kegiatan/{act.pk}/ubah/").content.decode()
        assert "Ubah kegiatan" in html and "Simpan perubahan" in html

    def test_edit_saves_changes(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        act = v.activities.filter(end_at__isnull=False).first()
        response = admin.post(
            f"/kegiatan/{act.pk}/ubah/",
            {
                "activity_type": act.activity_type_id,
                "start_at": act.start_at.strftime("%Y-%m-%dT%H:%M"),
                "end_at": act.end_at.strftime("%Y-%m-%dT%H:%M"),
                "from_location": "", "to_location": "",
                "note": "dikoreksi sesuai WhatsApp",
            },
            follow=True,
        )
        act.refresh_from_db()
        assert act.note == "dikoreksi sesuai WhatsApp"
        assert "tersimpan" in response.content.decode()

    def test_locked_voyage_activity_edit_refused(self, admin, data):
        v = voyage("Navigator 1", "V2601")
        act = v.activities.first()
        response = admin.get(f"/kegiatan/{act.pk}/ubah/", follow=True)
        assert "terkunci" in response.content.decode()


class TestActivityDeleteUndo:
    def test_delete_then_undo_restores_identical_row(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        act = v.activities.last()
        pk, note, start = act.pk, act.note, act.start_at
        response = admin.post(f"/kegiatan/{pk}/hapus/", follow=True)
        assert not Activity.objects.filter(pk=pk).exists()
        assert "Batalkan" in response.content.decode()

        response = admin.post(f"/kegiatan/{pk}/pulihkan/", follow=True)
        restored = Activity.objects.get(pk=pk)
        assert (restored.note, restored.start_at) == (note, start)
        assert "dipulihkan" in response.content.decode()

    def test_restore_without_deleted_row_is_friendly(self, admin, data):
        response = admin.post("/kegiatan/999999/pulihkan/", follow=True)
        assert "Tidak ada kegiatan terhapus" in response.content.decode()
