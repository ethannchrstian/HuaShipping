"""Django admin — developer/backoffice view of the raw data.

Not the end-user UI (that's built in the screens phase per docs/06); this is
for inspection during development and emergencies. SimpleHistoryAdmin adds a
"History" button showing every change with who/when.
"""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Activity, ActivityType, Charterer, Jetty, Parcel, Vessel, Voyage, VoyageCost


@admin.register(Vessel)
class VesselAdmin(SimpleHistoryAdmin):
    list_display = ("name", "tug_name", "barge_name", "active")


@admin.register(Jetty)
class JettyAdmin(SimpleHistoryAdmin):
    list_display = ("name", "port")
    search_fields = ("name", "port")


@admin.register(Charterer)
class ChartererAdmin(SimpleHistoryAdmin):
    list_display = ("code", "name")


@admin.register(ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "label_id", "phase", "is_sailing", "sort_hint")

    def has_add_permission(self, request):  # seeded lookup — edit via migration only
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ParcelInline(admin.TabularInline):
    model = Parcel
    extra = 0


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0


class VoyageCostInline(admin.TabularInline):
    model = VoyageCost
    extra = 0


@admin.register(Voyage)
class VoyageAdmin(SimpleHistoryAdmin):
    list_display = ("code", "vessel", "charterer", "status", "locked")
    list_filter = ("vessel", "status")
    search_fields = ("code", "contract_no", "invoice_no")
    inlines = [ParcelInline, ActivityInline, VoyageCostInline]


@admin.register(Activity)
class ActivityAdmin(SimpleHistoryAdmin):
    list_display = ("voyage", "activity_type", "start_at", "end_at")
    list_filter = ("activity_type",)
