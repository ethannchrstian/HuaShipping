"""View tests for S1/S2/S3/S5 (docs/06) against the real imported history."""

import json
from pathlib import Path

import pytest
from django.contrib.auth.models import User

from voyages.importer import import_all
from voyages.models import Voyage

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


class TestAuth:
    def test_anonymous_redirected_to_login(self, client, db):
        response = client.get("/")
        assert response.status_code == 302
        assert response.url.startswith("/masuk/")

    def test_login_page_in_indonesian(self, client, db):
        html = client.get("/masuk/").content.decode()
        assert "Nama pengguna" in html and "Kata sandi" in html


class TestVoyageList:
    def test_shows_all_voyages(self, admin, data):
        html = admin.get("/").content.decode()
        for code in ["V2501", "V2601", "V2606", "V2607"]:
            assert code in html

    def test_vessel_cards_show_port_days(self, admin, data):
        html = admin.get("/").content.decode()
        assert "Hari pelabuhan" in html

    def test_filter_by_vessel(self, admin, data):
        hn2 = voyage("Navigator 2", "V2601").vessel_id
        html = admin.get(f"/?kapal={hn2}").content.decode()
        assert "V2603" in html  # HN2 has V2601-V2603
        # HN1 rows leave the table (V2605 is HN1-only); V2607 still shows in
        # the always-visible vessel status card, which is intended
        assert "V2605" not in html

    def test_search_by_contract(self, admin, data):
        html = admin.get("/?cari=PSCOI").content.decode()
        assert "V2602" in html and "V2605" not in html

    def test_filter_by_charterer(self, admin, data):
        pnlf = voyage("Navigator 1", "V2605").charterer_id
        html = admin.get(f"/?pencharter={pnlf}").content.decode()
        assert "V2605" in html and "V2602" not in html

    def test_filter_by_date_range(self, admin, data):
        # only V2501 starts in Dec 2025
        html = admin.get("/?mulai_dari=2025-12-01&mulai_sampai=2025-12-31").content.decode()
        assert "V2501" in html
        assert "dari 1 voyage" in html

    def test_invalid_date_ignored(self, admin, data):
        response = admin.get("/?mulai_dari=bukan-tanggal")
        assert response.status_code == 200


class TestCetakTimeSheet:
    def test_matches_sheet_layout_and_oracle_numbers(self, admin, data):
        # HN1 V2601: block A = 19 | 1d17:00, grand total 27 hari 5:53 (docs/04)
        v = voyage("Navigator 1", "V2601")
        html = admin.get(f"/voyage/{v.pk}/cetak/").content.decode()
        assert "TIME SHEET TB. HUA NAVIGATOR 1" in html
        assert "TABEL VOYAGE REPORT VOY. V2601" in html
        assert "Total Kegiatan Muat (A)" in html and "Total Kegiatan Bongkar (B)" in html
        assert "Prorata Muat - Bongkar Sesuai Kontrak" in html
        assert "DEMURRAGE" in html
        assert "Dibuat Oleh" in html and "Felicia" in html
        assert "Diketahui Oleh" in html and "Tjipta Lesmana Suwarto" in html
        # grand total: 27 days, 5:53 remainder — as HARI | WAKTU columns
        assert ">27<" in html and "5:53" in html

    def test_split_laytime_prints_2025_style(self, admin, data):
        v = voyage("Navigator 1", "V2501")
        html = admin.get(f"/voyage/{v.pk}/cetak/").content.decode()
        assert "Hari Muat" in html and "Hari Bongkar" in html

    def test_excel_visual_conventions(self, admin, data):
        # colored fills + KETERANGAN grid + [h]:mm subtotals, like the original
        v = voyage("Navigator 1", "V2501")
        html = admin.get(f"/voyage/{v.pk}/cetak/").content.decode()
        assert "KETERANGAN" in html and "BERANGKAT" in html and "PUKUL" in html
        assert "biru" in html and "hijau" in html and "kuning" in html
        # completed voyage: the flagged open-ended row prints "-", never "berjalan"
        assert "berjalan" not in html

    def test_ongoing_voyage_marked_as_draft(self, admin, data):
        v = voyage("Navigator 1", "V2607")
        html = admin.get(f"/voyage/{v.pk}/cetak/").content.decode()
        assert "DRAF" in html and "MASIH BERJALAN" in html

    def test_requires_login(self, client, data):
        v = voyage("Navigator 1", "V2601")
        assert client.get(f"/voyage/{v.pk}/cetak/").status_code == 302


class TestExportCsv:
    def test_csv_has_all_voyages_and_indonesian_headers(self, admin, data):
        response = admin.get("/ekspor.csv")
        assert response["Content-Disposition"].startswith("attachment")
        body = response.content.decode("utf-8-sig")
        lines = body.strip().splitlines()
        assert lines[0].startswith("Kode,Kapal,Pencharter")
        assert len(lines) == 1 + Voyage.objects.count()
        assert any("V2605" in line for line in lines)

    def test_csv_respects_filters(self, admin, data):
        hn2 = voyage("Navigator 2", "V2601").vessel_id
        body = admin.get(f"/ekspor.csv?kapal={hn2}").content.decode("utf-8-sig")
        assert "V2603" in body and "V2605" not in body

    def test_csv_requires_login(self, client, data):
        response = client.get("/ekspor.csv")
        assert response.status_code == 302

    def test_over_laytime_marked_with_word_not_just_color(self, admin, data):
        # binding rule 5: color never carries meaning alone
        html = admin.get("/").content.decode()
        assert "Lebih" in html


class TestVoyageDetail:
    def test_computed_totals_match_the_sheet(self, admin, data):
        # HN1 V2601: A = 19 | 1d 17:00, grand total 27d 5:53 (docs/04 worked example)
        v = voyage("Navigator 1", "V2601")
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert "Total Kegiatan Muat (A)" in html
        assert "19 | 1 hari 17:00" in html
        assert "27 hari 5:53" in html

    def test_demurrage_shown_with_amount(self, admin, data):
        # V2605: 3 days x Rp 20jt = Rp 60jt
        v = voyage("Navigator 1", "V2605")
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert "3 hari" in html and "Rp 60.000.000" in html

    def test_gap_warning_visible_in_indonesian(self, admin, data):
        v = voyage("Navigator 1", "V2605")  # real 2-day unlogged gap
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert "jeda" in html and "belum tercatat" in html

    def test_overlap_warning_on_hn2_v2602(self, admin, data):
        v = voyage("Navigator 2", "V2602")  # the row-17 date typo
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert "Tumpang tindih" in html

    def test_locked_voyage_shows_no_entry_form(self, admin, data):
        v = voyage("Navigator 1", "V2601")
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert "Terkunci" in html
        assert "Simpan kegiatan" not in html


class TestActivityEntry:
    """S5 — the adoption-deciding batch-entry loop."""

    def test_start_prefilled_with_previous_end(self, admin, data):
        v = voyage("Navigator 1", "V2607")  # ongoing, last activity has no end
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert 'name="start_at"' in html and "Simpan kegiatan" in html

    def test_add_activity_and_confirmation(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        n = v.activities.count()
        response = admin.post(
            f"/voyage/{v.pk}/kegiatan/tambah/",
            {
                "activity_type": "waiting_cast_off",
                "start_at": "2026-07-09T11:00",
                "end_at": "2026-07-09T15:30",
                "from_location": "",
                "to_location": "",
                "note": "",
            },
            follow=True,
        )
        assert v.activities.count() == n + 1
        assert "dicatat" in response.content.decode()

    def test_end_before_start_shows_field_error(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        n = v.activities.count()
        response = admin.post(
            f"/voyage/{v.pk}/kegiatan/tambah/",
            {
                "activity_type": "loading",
                "start_at": "2026-07-09T14:30",
                "end_at": "2026-07-09T13:15",  # the V2501 error class
                "from_location": "",
                "to_location": "",
                "note": "",
            },
        )
        assert v.activities.count() == n
        assert "lebih awal dari jam mulai" in response.content.decode()

    def test_locked_voyage_rejects_post(self, admin, data):
        v = voyage("Navigator 1", "V2601")
        n = v.activities.count()
        response = admin.post(
            f"/voyage/{v.pk}/kegiatan/tambah/",
            {"activity_type": "loading", "start_at": "2026-07-09T14:30"},
            follow=True,
        )
        assert v.activities.count() == n
        assert "terkunci" in response.content.decode()


class TestEntryLoop:
    """The seamless batch loop: auto-close, confirm strip, undo, tandai selesai."""

    @staticmethod
    def _add(admin, v, start_local, **extra):
        payload = {
            "activity_type": "waiting_cast_off",
            "start_at": start_local,
            "end_at": "",
            "from_location": "",
            "to_location": "",
            "note": "",
        }
        payload.update(extra)
        return admin.post(f"/voyage/{v.pk}/kegiatan/tambah/", payload)

    def test_add_auto_closes_running_activity(self, admin, data):
        from datetime import timedelta

        from django.utils import timezone

        v = voyage("Navigator 2", "V2603")
        open_act = v.activities.filter(end_at__isnull=True).last()
        assert open_act is not None
        start = timezone.localtime(open_act.start_at + timedelta(hours=6))
        response = self._add(admin, v, start.strftime("%Y-%m-%dT%H:%M"))
        assert response.status_code == 302
        assert "baru=" in response.url and f"tutup={open_act.pk}" in response.url
        open_act.refresh_from_db()
        assert open_act.end_at is not None

    def test_confirm_strip_highlight_and_autoclose_note(self, admin, data):
        from datetime import timedelta

        from django.utils import timezone

        v = voyage("Navigator 2", "V2603")
        open_act = v.activities.filter(end_at__isnull=True).last()
        start = timezone.localtime(open_act.start_at + timedelta(hours=6))
        response = self._add(admin, v, start.strftime("%Y-%m-%dT%H:%M"))
        html = admin.get(response.url).content.decode()
        assert "dicatat — total langsung diperbarui" in html
        assert "ditutup otomatis" in html
        assert "Urungkan" in html
        assert "baris-baru" in html

    def test_undo_add_removes_row_and_reopens(self, admin, data):
        from datetime import timedelta
        from urllib.parse import parse_qs, urlparse

        from django.utils import timezone

        v = voyage("Navigator 2", "V2603")
        open_act = v.activities.filter(end_at__isnull=True).last()
        start = timezone.localtime(open_act.start_at + timedelta(hours=6))
        response = self._add(admin, v, start.strftime("%Y-%m-%dT%H:%M"))
        params = parse_qs(urlparse(response.url).query)
        baru, tutup = params["baru"][0], params["tutup"][0]
        n = v.activities.count()
        admin.post(f"/kegiatan/{baru}/urungkan/", {"tutup": tutup})
        assert v.activities.count() == n - 1
        open_act.refresh_from_db()
        assert open_act.end_at is None

    def test_tandai_selesai_prefills_end(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        open_act = v.activities.filter(end_at__isnull=True).last()
        detail = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert "Tandai selesai" in detail
        html = admin.get(f"/kegiatan/{open_act.pk}/ubah/?selesai=1").content.decode()
        import re

        end_input = re.search(r'name="end_at"[^>]*value="([^"]+)"', html)
        assert end_input, "end_at should be prefilled with the current time"

    def test_location_fields_are_selects_from_master(self, admin, data):
        v = voyage("Navigator 2", "V2603")
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert '<select name="from_location"' in html
        assert '<select name="to_location"' in html
        assert 'label="Jetty"' in html  # optgroup from the master data
        assert "Jetty baru" in html  # inline quick-add

    def test_timeline_block_headers_and_bands(self, admin, data):
        v = voyage("Navigator 1", "V2605")  # completed: one muat + one bongkar block
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert ">Kegiatan Muat (A)<" in html  # header row, not the subtotal
        assert ">Kegiatan Bongkar (B)<" in html

    def test_multi_jetty_load_gets_third_block_header(self, admin, data):
        v = voyage("Navigator 2", "V2601")  # loads at PAM + TBSM before discharging
        html = admin.get(f"/voyage/{v.pk}/").content.decode()
        assert ">Kegiatan Muat (A)<" in html
        assert ">Kegiatan Muat (B)<" in html
        assert ">Kegiatan Bongkar (C)<" in html
