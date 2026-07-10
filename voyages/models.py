"""Database schema per docs/03-erd.md.

Models store raw facts only — timestamps, names, contract numbers, rates.
Every day count and money outcome is computed on read by the domain/ package
(ADR-002): use Activity.to_domain() / Voyage.domain_activities() as the bridge.
"""

from django.db import models
from django.db.models import F, Q
from simple_history.models import HistoricalRecords

from domain import model as domain_model


class Vessel(models.Model):
    """A tugboat + barge set, e.g. TB. HUA Navigator 1 & BG. Palm Hero 2401."""

    name = models.CharField(max_length=120, unique=True)
    tug_name = models.CharField(max_length=60)
    barge_name = models.CharField(max_length=60)
    capacity_mt = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    active = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.name


class Jetty(models.Model):
    name = models.CharField(max_length=120, unique=True)
    port = models.CharField(max_length=80, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name_plural = "jetties"

    def __str__(self):
        return f"{self.name}, {self.port}" if self.port else self.name


class Charterer(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=120, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.code


class ActivityType(models.Model):
    """Fixed lookup seeded from domain.model.ACTIVITY_TYPES (see 0002 migration).

    The domain registry is the source of truth; this table exists so the DB can
    enforce referential integrity and the UI can query Indonesian labels.
    """

    code = models.CharField(primary_key=True, max_length=30)
    label_id = models.CharField("Indonesian label", max_length=60)
    phase = models.CharField(max_length=20)
    is_sailing = models.BooleanField(default=False)
    sort_hint = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["sort_hint"]

    def __str__(self):
        return self.label_id


class Voyage(models.Model):
    class Status(models.TextChoices):
        ONGOING = "ONGOING", "Berjalan"
        COMPLETED = "COMPLETED", "Selesai"

    code = models.CharField(max_length=10)
    vessel = models.ForeignKey(Vessel, on_delete=models.PROTECT, related_name="voyages")
    charterer = models.ForeignKey(
        Charterer, on_delete=models.PROTECT, null=True, blank=True, related_name="voyages"
    )
    contract_no = models.CharField(max_length=60, blank=True)
    invoice_no = models.CharField(max_length=60, blank=True)
    discharge_jetty = models.ForeignKey(
        Jetty, on_delete=models.PROTECT, null=True, blank=True, related_name="discharging_voyages"
    )
    laytime_days = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    laytime_load_days = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    laytime_discharge_days = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    demurrage_rate_idr = models.BigIntegerField(null=True, blank=True)  # per day; null = clause "-"
    freight_idr = models.BigIntegerField(null=True, blank=True)  # V1.1
    fuel_used_liters = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)  # V1.1
    status = models.CharField(max_length=10, choices=Status, default=Status.ONGOING)
    locked = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["vessel", "code"]
        constraints = [
            # both real vessels have a V2601 — unique per vessel, not globally
            models.UniqueConstraint(fields=["vessel", "code"], name="voyage_code_unique_per_vessel"),
            # split laytime (2025 contracts) must agree with the total when all three are set
            models.CheckConstraint(
                condition=Q(laytime_days__isnull=True)
                | Q(laytime_load_days__isnull=True)
                | Q(laytime_discharge_days__isnull=True)
                | Q(laytime_days=F("laytime_load_days") + F("laytime_discharge_days")),
                name="voyage_split_laytime_sums",
            ),
        ]

    def __str__(self):
        return f"{self.vessel} — {self.code}"

    def domain_activities(self) -> list[domain_model.Activity]:
        """The voyage's log as domain values, ready for domain.calculations."""
        return [a.to_domain() for a in self.activities.all()]


class Parcel(models.Model):
    """One cargo lot on a voyage; quantity always stored in MT (KG ÷ 1000 on entry)."""

    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, related_name="parcels")
    commodity = models.CharField(max_length=40, default="CPO")
    quantity_mt = models.DecimalField(max_digits=10, decimal_places=3)
    load_jetty = models.ForeignKey(Jetty, on_delete=models.PROTECT, related_name="loaded_parcels")
    shipper = models.CharField(max_length=120, blank=True)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity_mt__gt=0), name="parcel_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.commodity} {self.quantity_mt} MT"


class Activity(models.Model):
    """One timestamped log row. end_at null = still ongoing."""

    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.ForeignKey(ActivityType, on_delete=models.PROTECT, related_name="+")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    from_location = models.CharField(max_length=120, blank=True)  # sailing legs only
    to_location = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=200, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["start_at"]
        verbose_name_plural = "activities"
        constraints = [
            # calc spec C1: end may equal start (real "no waiting" row) but never precede it
            models.CheckConstraint(
                condition=Q(end_at__isnull=True) | Q(end_at__gte=F("start_at")),
                name="activity_end_not_before_start",
            ),
        ]

    def __str__(self):
        return f"{self.activity_type_id} @ {self.start_at:%Y-%m-%d %H:%M}"

    def to_domain(self) -> domain_model.Activity:
        return domain_model.Activity(
            type_code=self.activity_type_id,
            start_at=self.start_at,
            end_at=self.end_at,
            note=self.note,
        )


class VoyageCost(models.Model):
    """Per-voyage cost line item — 'stevedoring and all that stuff' (ADR-010, V1.1)."""

    class Category(models.TextChoices):
        STEVEDORING = "STEVEDORING", "Stevedoring"
        PORT_CHARGES = "PORT_CHARGES", "Biaya pelabuhan"
        AGENCY = "AGENCY", "Agen"
        BUNKER = "BUNKER", "Bunker"
        OTHER = "OTHER", "Lainnya"

    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, related_name="costs")
    category = models.CharField(max_length=20, choices=Category)
    amount_idr = models.BigIntegerField()
    note = models.CharField(max_length=200, blank=True)
    incurred_on = models.DateField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount_idr__gte=0), name="voyage_cost_not_negative"),
        ]

    def __str__(self):
        return f"{self.get_category_display()}: Rp {self.amount_idr:,}"
