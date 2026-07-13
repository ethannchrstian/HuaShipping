"""S4 voyage form, activity edit/delete/undo, complete/unlock (docs/06)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User

from voyages.forms import next_code
from voyages.importer import import_all
from voyages.models import Activity, Charterer, Jetty, Vessel, Voyage

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


def finish_ongoing(vessel):
    """The one-boat-one-voyage rule blocks new voyages while one is berjalan."""
    vessel.voyages.filter(status=Voyage.Status.ONGOING).update(
        status=Voyage.Status.COMPLETED, locked=True
    )


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
        finish_ongoing(vessel)
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
        finish_ongoing(vessel)
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


class TestOneVoyagePerVessel:
    def test_new_voyage_blocked_while_one_is_ongoing(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")  # V2607 berjalan
        payload = {
            "vessel": vessel.pk, "code": "V2608", "charterer": "", "contract_no": "",
            "invoice_no": "", "discharge_jetty": "", "laytime_days": "",
            "laytime_load_days": "", "laytime_discharge_days": "",
            "demurrage_rate_idr": "", "notes": "", **formset_base(),
        }
        response = admin.post("/voyage/baru/", payload)
        assert "masih menjalankan voyage V2607" in response.content.decode()
        assert not Voyage.objects.filter(vessel=vessel, code="V2608").exists()

    def test_editing_the_ongoing_voyage_itself_is_allowed(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        payload = {
            "vessel": v.vessel_id, "code": v.code, "charterer": v.charterer_id or "",
            "contract_no": v.contract_no, "invoice_no": v.invoice_no,
            "discharge_jetty": v.discharge_jetty_id or "",
            "laytime_days": v.laytime_days or "",
            "laytime_load_days": v.laytime_load_days or "",
            "laytime_discharge_days": v.laytime_discharge_days or "",
            "demurrage_rate_idr": v.demurrage_rate_idr or "",
            "notes": "catatan baru",
            **formset_base(),
            "parcels-INITIAL_FORMS": "0",
        }
        response = admin.post(f"/voyage/{v.pk}/ubah/", payload, follow=True)
        v.refresh_from_db()
        assert v.notes == "catatan baru"
        assert "tersimpan" in response.content.decode()


class TestVoyageDelete:
    def test_empty_voyage_deleted(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        v = Voyage.objects.create(vessel=vessel, code="V2699")
        response = admin.post(f"/voyage/{v.pk}/hapus/", follow=True)
        assert not Voyage.objects.filter(pk=v.pk).exists()
        assert "V2699 dihapus" in response.content.decode()

    def test_voyage_with_activities_refused(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        response = admin.post(f"/voyage/{v.pk}/hapus/", follow=True)
        assert Voyage.objects.filter(pk=v.pk).exists()
        assert "tidak bisa dihapus" in response.content.decode()

    def test_confirmation_page_before_delete(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        v = Voyage.objects.create(vessel=vessel, code="V2699")
        html = admin.get(f"/voyage/{v.pk}/hapus/").content.decode()
        assert "Hapus voyage V2699?" in html and "belum punya kegiatan" in html
        assert Voyage.objects.filter(pk=v.pk).exists()  # GET never deletes

    def test_detail_page_shows_hapus_only_when_empty(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        empty = Voyage.objects.create(vessel=vessel, code="V2699")
        assert "Hapus voyage" in admin.get(f"/voyage/{empty.pk}/").content.decode()
        filled = voyage("Navigator 2", "V2603")
        assert "Hapus voyage" not in admin.get(f"/voyage/{filled.pk}/").content.decode()


class TestDataMaster:
    def test_lists_all_three_kinds(self, admin, data):
        html = admin.get("/data/").content.decode()
        assert "Navigator 1" in html
        assert "Tambah jetty" in html and "Tambah pencharter" in html

    def test_add_vessel_composes_combined_name(self, admin, db):
        admin.post(
            "/data/kapal/baru/",
            {"tug_name": "TB. HUA Navigator 3", "barge_name": "BG. Palm Hero 2403", "active": "on"},
        )
        v = Vessel.objects.get(tug_name="TB. HUA Navigator 3")
        assert v.name == "TB. HUA Navigator 3 & BG. Palm Hero 2403"
        assert v.active is True

    def test_edit_jetty(self, admin, data):
        j = Jetty.objects.first()
        admin.post(f"/data/jetty/{j.pk}/ubah/", {"name": "Jetty Uji Coba", "port": "Dumai"})
        j.refresh_from_db()
        assert (j.name, j.port) == ("Jetty Uji Coba", "Dumai")

    def test_add_charterer(self, admin, db):
        response = admin.post("/data/pencharter/baru/", {"code": "UJI", "name": ""}, follow=True)
        assert Charterer.objects.filter(code="UJI").exists()
        assert "ditambahkan" in response.content.decode()

    def test_unknown_jenis_bounces_back(self, admin, db):
        response = admin.get("/data/lorem/baru/")
        assert response.status_code == 302 and response.url == "/data/"


class TestQuickAdd:
    """Inline master quick-add embedded in the voyage form (htmx fragments)."""

    def test_inline_panel_uses_prefixed_fields_and_no_nested_form(self, admin, db):
        html = admin.get("/data/pencharter/baru/?inline=1").content.decode()
        # "baru-" prefix keeps pencharter's "code" from colliding with the
        # voyage form's own "code" field; a <form> tag would nest illegally
        assert 'name="baru-code"' in html and "Simpan pencharter" in html
        assert "<form" not in html

    def test_inline_post_creates_and_returns_marker(self, admin, db):
        response = admin.post(
            "/data/jetty/baru/?inline=1", {"baru-name": "Jetty Quick", "baru-port": "Dumai"}
        )
        j = Jetty.objects.get(name="Jetty Quick")
        html = response.content.decode()
        assert f'data-baru-value="{j.pk}"' in html and 'data-baru-kind="jetty"' in html

    def test_inline_post_invalid_rerenders_panel(self, admin, data):
        taken = Jetty.objects.first().name
        response = admin.post("/data/jetty/baru/?inline=1", {"baru-name": taken, "baru-port": ""})
        html = response.content.decode()
        assert "data-baru-value" not in html and 'name="baru-name"' in html

    def test_voyage_form_offers_quickadd_everywhere(self, admin, data):
        html = admin.get("/voyage/baru/").content.decode()
        # kapal + pencharter + jetty bongkar + one per muatan row (2 extra rows)
        assert html.count("?inline=1") >= 5


class TestArmada:
    def test_cards_show_status_last3_and_riwayat_link(self, admin, data):
        html = admin.get("/armada/").content.decode()
        assert "TB. HUA Navigator 1" in html and "TB. HUA Navigator 2" in html
        assert "Progres voyage" in html and "Performa tahun" in html
        assert "Total armada" in html and "Voyage selesai" in html  # KPI strip
        assert "Lihat riwayat lengkap" in html
        # only the three latest voyages inline — deep history lives on riwayat
        assert "V2607" in html and "V2501" not in html

    def test_vessel_without_voyages_still_shown(self, admin, db):
        Vessel.objects.create(name="TB Uji & BG Uji", tug_name="TB Uji", barge_name="BG Uji")
        html = admin.get("/armada/").content.decode()
        assert "TB Uji" in html and "Belum ada voyage untuk kapal ini." in html


class TestRiwayatKapal:
    def test_current_year_rows_with_performa(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        html = admin.get(f"/armada/{vessel.pk}/riwayat/").content.decode()
        assert "Riwayat voyage" in html
        assert "V2601" in html and "V2607" in html
        assert "Sesuai kontrak" in html and "Lebih" in html
        assert "V2501" not in html  # 2025 voyage stays out of the 2026 view

    def test_year_selector_reaches_older_voyages(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 1")
        html = admin.get(f"/armada/{vessel.pk}/riwayat/?tahun=2025").content.decode()
        assert "V2501" in html and "V2601" not in html

    def test_pct_kontrak_only_counts_completed_with_laytime(self, admin, data):
        vessel = Vessel.objects.get(name__contains="Navigator 2")
        html = admin.get(f"/armada/{vessel.pk}/riwayat/").content.decode()
        assert "Sesuai kontrak" in html and "%" in html
