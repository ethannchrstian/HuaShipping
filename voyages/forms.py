"""S5 — the inline activity entry form (docs/06)."""

from django import forms

from .models import Activity, ActivityType

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
