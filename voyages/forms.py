"""Forms: S4 voyage form + S5 inline activity entry (docs/06)."""

from datetime import date

from django import forms
from django.forms import inlineformset_factory

from .models import Activity, ActivityType, Charterer, Jetty, Parcel, Vessel, Voyage

DATETIME_LOCAL = "%Y-%m-%dT%H:%M"

# after saving X, the type that usually follows in the real sheets
NEXT_TYPE = {
    "ballast": "waiting_berth_load",
    "waiting_berth_load": "waiting_load",
    "waiting_load": "loading",
    "loading": "waiting_cast_off",
    "waiting_cast_off": "laden",
    "shifting": "waiting_berth_load",
    "laden": "waiting_berth_discharge",
    "waiting_berth_discharge": "waiting_discharge",
    "waiting_discharge": "discharging",
    "discharging": "preparation",
    "preparation": "ballast",
}


def next_code(vessel: Vessel) -> str:
    """Next voyage code in this vessel's sequence, e.g. V2607 -> V2608."""
    year = date.today().strftime("%y")
    prefix = f"V{year}"
    numbers = [
        int(c[3:]) for c in vessel.voyages.filter(code__startswith=prefix).values_list("code", flat=True)
        if c[3:].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:02d}"


class VoyageForm(forms.ModelForm):
    class Meta:
        model = Voyage
        fields = [
            "vessel", "code", "charterer", "contract_no", "invoice_no",
            "discharge_jetty", "laytime_days", "laytime_load_days",
            "laytime_discharge_days", "demurrage_rate_idr", "notes",
        ]
        labels = {
            "vessel": "Kapal",
            "code": "Kode voyage",
            "charterer": "Pencharter",
            "contract_no": "No. kontrak",
            "invoice_no": "Kwitansi nomor",
            "discharge_jetty": "Jetty bongkar",
            "laytime_days": "Prorata total (hari)",
            "laytime_load_days": "Prorata muat (hari)",
            "laytime_discharge_days": "Prorata bongkar (hari)",
            "demurrage_rate_idr": "Tarif demurrage (Rp/hari)",
            "notes": "Catatan",
        }
        help_texts = {
            "laytime_days": "Isi total saja, atau isi muat + bongkar (total dihitung sendiri)",
            "demurrage_rate_idr": "Kosongkan bila kontrak menulis “-”",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_vessel(self):
        """One boat, one voyage: refuse a new voyage while another is berjalan."""
        vessel = self.cleaned_data["vessel"]
        qs = vessel.voyages.filter(status=Voyage.Status.ONGOING)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        ongoing = qs.order_by("code").last()
        if ongoing:
            last = ongoing.activities.select_related("activity_type").last()
            if last is None:
                doing = "belum ada kegiatan tercatat"
            elif last.activity_type.is_sailing and last.to_location:
                doing = f"sedang {last.activity_type.label_id} menuju {last.to_location}"
            else:
                doing = f"sedang {last.activity_type.label_id}"
            raise forms.ValidationError(
                f"{vessel.tug_name} masih menjalankan voyage {ongoing.code} — {doing}. "
                f"Selesaikan voyage itu terlebih dahulu sebelum membuat voyage baru."
            )
        return vessel

    def clean(self):
        cleaned = super().clean()
        load = cleaned.get("laytime_load_days")
        discharge = cleaned.get("laytime_discharge_days")
        total = cleaned.get("laytime_days")
        if (load is None) != (discharge is None):
            self.add_error(
                "laytime_load_days" if load is None else "laytime_discharge_days",
                "Prorata terpisah harus diisi keduanya (muat dan bongkar).",
            )
        elif load is not None and discharge is not None:
            if total is None:
                cleaned["laytime_days"] = load + discharge
            elif total != load + discharge:
                self.add_error(
                    "laytime_days",
                    f"Total {total} tidak sama dengan muat + bongkar ({load + discharge}).",
                )
        return cleaned


ParcelFormSet = inlineformset_factory(
    Voyage,
    Parcel,
    fields=["commodity", "quantity_mt", "load_jetty", "shipper"],
    labels={
        "commodity": "Komoditas",
        "quantity_mt": "Jumlah (MT)",
        "load_jetty": "Jetty muat",
        "shipper": "Pengirim",
    },
    extra=2,
    can_delete=True,
)


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["activity_type", "start_at", "end_at", "from_location", "to_location", "note"]
        labels = {
            "activity_type": "Kegiatan",
            "start_at": "Mulai",
            "end_at": "Selesai",
            "from_location": "Berangkat dari",
            "to_location": "Tiba di",
            "note": "Catatan",
        }
        help_texts = {
            "end_at": "Kosongkan bila masih berjalan",
            "from_location": "Hanya untuk pelayaran",
        }
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["activity_type"].queryset = ActivityType.objects.all()
        self.fields["activity_type"].label_from_instance = lambda t: t.label_id
        self.fields["start_at"].input_formats = [DATETIME_LOCAL]
        self.fields["end_at"].input_formats = [DATETIME_LOCAL]
        self.fields["end_at"].required = False

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_at"), cleaned.get("end_at")
        if start and end and end < start:
            # calc spec C1 — the exact error class found in the real sheets
            self.add_error(
                "end_at",
                "Jam selesai lebih awal dari jam mulai — periksa kembali tanggalnya.",
            )
        return cleaned


class VesselForm(forms.ModelForm):
    """Data master: admins add tug+barge sets themselves; the combined name is
    composed automatically so the pair is always displayed consistently."""

    class Meta:
        model = Vessel
        fields = ["tug_name", "barge_name", "active"]
        labels = {
            "tug_name": "Nama tugboat",
            "barge_name": "Nama tongkang",
            "active": "Masih aktif beroperasi",
        }
        help_texts = {
            "tug_name": "Contoh: TB. HUA Navigator 3",
            "barge_name": "Contoh: BG. Palm Hero 2403",
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.name = f"{obj.tug_name} & {obj.barge_name}"
        if commit:
            obj.save()
        return obj


class JettyForm(forms.ModelForm):
    class Meta:
        model = Jetty
        fields = ["name", "port"]
        labels = {"name": "Nama jetty", "port": "Kota / pelabuhan"}
        help_texts = {
            "name": "Contoh: Jetty PT. Sahabat Mewah Makmur",
            "port": "Contoh: Belitung — dipakai sebagai nama singkat rute",
        }


class ChartererForm(forms.ModelForm):
    class Meta:
        model = Charterer
        fields = ["code", "name"]
        labels = {"code": "Kode singkat", "name": "Nama lengkap"}
        help_texts = {
            "code": "Contoh: FPS — kode yang tertulis di kontrak",
            "name": "Boleh dikosongkan",
        }
