import csv
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from . import presenters, reports
from .forms import (
    NEXT_TYPE,
    ActivityForm,
    ChartererForm,
    JettyForm,
    ParcelFormSet,
    VesselForm,
    VoyageForm,
    next_code,
)
from .models import Activity, Charterer, Jetty, Vessel, Voyage


def _filtered_voyages(request):
    """Apply the dashboard filters from GET params; returns (queryset, filters-dict)."""
    voyages = Voyage.objects.select_related("vessel", "charterer", "discharge_jetty").prefetch_related(
        "activities__activity_type", "parcels__load_jetty"
    )
    f = {
        "kapal": request.GET.get("kapal") or "",
        "status": request.GET.get("status") or "",
        "pencharter": request.GET.get("pencharter") or "",
        "pelabuhan": request.GET.get("pelabuhan") or "",
        "mulai_dari": request.GET.get("mulai_dari") or "",
        "mulai_sampai": request.GET.get("mulai_sampai") or "",
        "cari": (request.GET.get("cari") or "").strip(),
    }
    if f["kapal"]:
        voyages = voyages.filter(vessel_id=f["kapal"])
    if f["status"]:
        voyages = voyages.filter(status=f["status"])
    if f["pencharter"]:
        voyages = voyages.filter(charterer_id=f["pencharter"])
    if f["pelabuhan"]:
        voyages = voyages.filter(
            Q(parcels__load_jetty_id=f["pelabuhan"]) | Q(discharge_jetty_id=f["pelabuhan"])
        ).distinct()
    for key, lookup in (("mulai_dari", "gte"), ("mulai_sampai", "lte")):
        if f[key]:
            try:
                parsed = datetime.date.fromisoformat(f[key])
            except ValueError:
                f[key] = ""
                continue
            voyages = voyages.filter(**{f"activities__start_at__date__{lookup}": parsed}).distinct()
    if f["cari"]:
        q = f["cari"]
        voyages = voyages.filter(
            Q(code__icontains=q) | Q(contract_no__icontains=q)
            | Q(invoice_no__icontains=q) | Q(charterer__code__icontains=q)
        )
    return voyages, f


@login_required
def voyage_list(request):
    voyages, f = _filtered_voyages(request)

    rows = presenters.list_rows(voyages)
    per_page = request.GET.get("n")
    per_page = int(per_page) if per_page in {"10", "25", "50"} else 10
    paginator = Paginator(rows, per_page)
    page = paginator.get_page(request.GET.get("hal"))
    page_range = list(paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1))
    filter_params = request.GET.copy()
    filter_params.pop("hal", None)
    active_filters = sum(1 for v in f.values() if v)

    all_voyages = Voyage.objects.prefetch_related("activities__activity_type", "parcels")
    context = {
        "page": page,
        "page_range": page_range,
        "per_page": per_page,
        "filter_qs": filter_params.urlencode(),
        "active_filters": active_filters,
        "today": timezone.localtime(),
        "last_update": _last_update(),
        "cards": presenters.vessel_cards(Vessel.objects.filter(active=True)),
        "kpis": presenters.kpis(all_voyages, year=timezone.localtime().year),
        "alerts": presenters.alerts(all_voyages),
        "vessels": Vessel.objects.filter(active=True),
        "charterers": Charterer.objects.order_by("code"),
        "jetties": Jetty.objects.order_by("name"),
        "statuses": Voyage.Status.choices,
        "filters": f,
    }
    return render(request, "voyages/voyage_list.html", context)


@login_required
def voyage_cetak(request, pk):
    voyage = get_object_or_404(
        Voyage.objects.select_related("vessel", "charterer", "discharge_jetty"), pk=pk
    )
    return render(request, "voyages/cetak.html", presenters.print_sheet(voyage))


@login_required
def laporan(request):
    voyages = Voyage.objects.select_related("vessel", "charterer", "discharge_jetty").prefetch_related(
        "activities__activity_type", "parcels__load_jetty"
    )
    years = sorted(
        {y for v in voyages if (y := presenters.voyage_year(v)) is not None}, reverse=True
    )
    current = timezone.localtime().year
    try:
        year = int(request.GET.get("tahun", ""))
    except ValueError:
        year = current
    if year not in years and years:
        year = years[0] if current not in years else current
    vessels = Vessel.objects.filter(active=True).prefetch_related("voyages__activities__activity_type")
    n_voyages = sum(1 for v in voyages if presenters.voyage_year(v) == year)
    context = {
        "year": year,
        "years": years,
        "n_voyages": n_voyages,
        "breakdown": reports.time_breakdown(voyages, year),
        "jetties": reports.jetty_waiting(voyages, year),
        "charterers": reports.charterer_demurrage(voyages, year),
        "utilization": reports.utilization(vessels, year),
        "month_names": reports.MONTH_SHORT,
    }
    return render(request, "voyages/laporan.html", context)


@login_required
def export_csv(request):
    """Ekspor CSV of the voyage table, honoring the same filters as the dashboard."""
    voyages, _ = _filtered_voyages(request)
    stamp = timezone.localtime().strftime("%Y-%m-%d")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="voyage-{stamp}.csv"'
    response.write("﻿")  # BOM so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerows(presenters.export_rows(voyages))
    return response


def _last_update():
    """When data last changed (newest audit-trail entry), shown as 'sync' time."""
    stamps = [
        m.history.order_by("-history_date").values_list("history_date", flat=True).first()
        for m in (Activity, Voyage)
    ]
    return max((s for s in stamps if s), default=None)


def _detail_context(request, voyage, form=None, editing_activity=None):
    if form is None and not voyage.locked:
        if editing_activity is not None:
            form = ActivityForm(instance=editing_activity)
        else:
            last = voyage.activities.last()
            initial = {}
            if last is not None:
                initial["start_at"] = (last.end_at or last.start_at)
                initial["activity_type"] = NEXT_TYPE.get(last.activity_type_id)
            else:
                initial["activity_type"] = "ballast"
            form = ActivityForm(initial=initial)
    return {
        "voyage": voyage,
        "timeline": presenters.timeline(voyage),
        "summary": presenters.summary(voyage),
        "route": presenters.route(voyage),
        "parcels": voyage.parcels.select_related("load_jetty"),
        "demurrage_rate": (
            presenters.rupiah(voyage.demurrage_rate_idr) if voyage.demurrage_rate_idr else None
        ),
        "form": form,
        "editing_activity": editing_activity,
        "type_groups": presenters.activity_type_groups(),
        "can_delete": not voyage.activities.exists(),
    }


@login_required
def voyage_detail(request, pk):
    voyage = get_object_or_404(
        Voyage.objects.select_related("vessel", "charterer", "discharge_jetty"), pk=pk
    )
    return render(request, "voyages/voyage_detail.html", _detail_context(request, voyage))


# ---------------------------------------------------------------- S4 voyage form


@login_required
def voyage_create(request):
    first_vessel = Vessel.objects.filter(active=True).first()
    initial = {"vessel": first_vessel, "code": next_code(first_vessel) if first_vessel else ""}
    if request.method == "POST":
        form = VoyageForm(request.POST)
        formset = ParcelFormSet(request.POST)
        if form.is_valid():
            formset = ParcelFormSet(request.POST, instance=form.instance)
            if formset.is_valid():
                with transaction.atomic():
                    voyage = form.save()
                    formset.save()
                messages.success(request, f"Voyage {voyage.code} tersimpan.")
                return redirect("voyage_detail", pk=voyage.pk)
    else:
        form = VoyageForm(initial=initial)
        formset = ParcelFormSet()
    return render(
        request,
        "voyages/voyage_form.html",
        {"form": form, "formset": formset, "title": "Voyage baru", "voyage": None},
    )


@login_required
def voyage_edit(request, pk):
    voyage = get_object_or_404(Voyage, pk=pk)
    if voyage.locked:
        messages.error(request, "Voyage ini sudah terkunci — buka kunci dulu untuk mengubah.")
        return redirect("voyage_detail", pk=pk)
    if request.method == "POST":
        form = VoyageForm(request.POST, instance=voyage)
        formset = ParcelFormSet(request.POST, instance=voyage)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, f"Perubahan voyage {voyage.code} tersimpan.")
            return redirect("voyage_detail", pk=pk)
    else:
        form = VoyageForm(instance=voyage)
        formset = ParcelFormSet(instance=voyage)
    return render(
        request,
        "voyages/voyage_form.html",
        {"form": form, "formset": formset, "title": f"Ubah voyage {voyage.code}", "voyage": voyage},
    )


# ------------------------------------------------- complete / unlock (S3 actions)


@login_required
def voyage_complete(request, pk):
    """Proper confirmation page, never a browser confirm() (binding rule 3)."""
    voyage = get_object_or_404(Voyage, pk=pk)
    if request.method == "POST":
        voyage.status = Voyage.Status.COMPLETED
        voyage.locked = True
        voyage.save(update_fields=["status", "locked"])
        messages.success(request, f"Voyage {voyage.code} selesai dan terkunci.")
        return redirect("voyage_detail", pk=pk)
    last = voyage.activities.last()
    cautions = []
    if last is None:
        cautions.append("Voyage ini belum punya kegiatan sama sekali.")
    elif last.end_at is None:
        cautions.append(
            f"Kegiatan terakhir ({last.activity_type.label_id}) masih berjalan — belum ada jam selesai."
        )
    return render(
        request,
        "voyages/confirm.html",
        {
            "voyage": voyage,
            "title": f"Selesaikan voyage {voyage.code}?",
            "body": "Voyage akan dikunci: kegiatan dan datanya tidak bisa diubah sampai kunci dibuka lagi.",
            "cautions": cautions,
            "confirm_label": "Selesaikan voyage",
        },
    )


@login_required
def voyage_unlock(request, pk):
    voyage = get_object_or_404(Voyage, pk=pk)
    if request.method == "POST":
        voyage.status = Voyage.Status.ONGOING
        voyage.locked = False
        voyage.save(update_fields=["status", "locked"])  # simple-history records who/when
        messages.success(request, f"Kunci voyage {voyage.code} dibuka — perubahan tercatat di riwayat.")
        return redirect("voyage_detail", pk=pk)
    return render(
        request,
        "voyages/confirm.html",
        {
            "voyage": voyage,
            "title": f"Buka kunci voyage {voyage.code}?",
            "body": (
                "Voyage kembali berstatus berjalan dan bisa diubah. "
                "Pembukaan kunci tercatat di riwayat perubahan."
            ),
            "cautions": [],
            "confirm_label": "Buka kunci",
        },
    )


@login_required
def voyage_delete(request, pk):
    """Delete a voyage that has no activities yet (mis-clicks on 'Voyage baru').
    Anything with recorded kegiatan must be kept — that data is the time sheet."""
    voyage = get_object_or_404(Voyage, pk=pk)
    if voyage.activities.exists():
        messages.error(
            request,
            f"Voyage {voyage.code} sudah punya kegiatan tercatat — tidak bisa dihapus.",
        )
        return redirect("voyage_detail", pk=pk)
    if request.method == "POST":
        code = voyage.code
        voyage.delete()
        messages.success(request, f"Voyage {code} dihapus.")
        return redirect("rekap")
    return render(
        request,
        "voyages/confirm.html",
        {
            "voyage": voyage,
            "title": f"Hapus voyage {voyage.code}?",
            "body": (
                "Voyage ini belum punya kegiatan, jadi aman dihapus. "
                "Data kapal dan pencharter tidak ikut terhapus."
            ),
            "cautions": [],
            "confirm_label": "Hapus voyage",
            "danger": True,
        },
    )


# ---------------------------------------------------------------- S5 activities


@login_required
@require_POST
def activity_add(request, pk):
    voyage = get_object_or_404(Voyage, pk=pk)
    if voyage.locked:
        messages.error(request, "Voyage ini sudah terkunci — buka kunci dulu untuk mengubah.")
        return redirect("voyage_detail", pk=pk)
    form = ActivityForm(request.POST)
    if not form.is_valid():
        context = _detail_context(request, voyage, form=form)
        return render(request, "voyages/voyage_detail.html", context)
    activity = form.save(commit=False)
    activity.voyage = voyage
    activity.save()
    messages.success(
        request, f"Kegiatan “{activity.activity_type.label_id}” tersimpan."
    )
    # back to the timeline with the next entry row ready (S5 batch loop)
    return redirect(reverse("voyage_detail", args=[pk]) + "#entri")


@login_required
def activity_edit(request, pk):
    activity = get_object_or_404(Activity.objects.select_related("voyage"), pk=pk)
    voyage = activity.voyage
    if voyage.locked:
        messages.error(request, "Voyage ini sudah terkunci — buka kunci dulu untuk mengubah.")
        return redirect("voyage_detail", pk=voyage.pk)
    if request.method == "POST":
        form = ActivityForm(request.POST, instance=activity)
        if form.is_valid():
            form.save()
            messages.success(request, "Perubahan kegiatan tersimpan.")
            return redirect(reverse("voyage_detail", args=[voyage.pk]) + "#entri")
        context = _detail_context(request, voyage, form=form, editing_activity=activity)
        return render(request, "voyages/voyage_detail.html", context)
    context = _detail_context(request, voyage, editing_activity=activity)
    return render(request, "voyages/voyage_detail.html", context)


@login_required
@require_POST
def activity_delete(request, pk):
    activity = get_object_or_404(Activity.objects.select_related("voyage"), pk=pk)
    voyage = activity.voyage
    if voyage.locked:
        messages.error(request, "Voyage ini sudah terkunci — buka kunci dulu untuk mengubah.")
        return redirect("voyage_detail", pk=voyage.pk)
    label = activity.activity_type.label_id
    activity_id = activity.pk
    activity.delete()
    undo_url = reverse("activity_restore", args=[activity_id])
    messages.success(
        request,
        format_html(
            "Kegiatan “{}” dihapus. <form method='post' action='{}' class='undo-form'>"
            "<input type='hidden' name='csrfmiddlewaretoken' value='{}'>"
            "<button type='submit' class='btn-ghost undo-link'>Batalkan</button></form>",
            label,
            undo_url,
            get_token(request),
        ),
    )
    return redirect("voyage_detail", pk=voyage.pk)


@login_required
@require_POST
def activity_restore(request, pk):
    """Undo a delete by replaying the last historical record (blame-free &
    reversible, PRODUCT.md principle 4)."""
    record = (
        Activity.history.filter(id=pk, history_type="-").order_by("-history_date").first()
    )
    if record is None:
        messages.error(request, "Tidak ada kegiatan terhapus yang bisa dipulihkan.")
        return redirect("rekap")
    restored = record.instance
    restored.save()
    messages.success(request, f"Kegiatan “{restored.activity_type.label_id}” dipulihkan.")
    return redirect(reverse("voyage_detail", args=[restored.voyage_id]) + "#entri")


# ---------------------------------------------------------------- Data master
# The admins run the fleet themselves: kapal, jetty, and pencharter are added
# in-app here, never through the Django admin.

MASTER = {
    "kapal": (Vessel, VesselForm, "Kapal"),
    "jetty": (Jetty, JettyForm, "Jetty"),
    "pencharter": (Charterer, ChartererForm, "Pencharter"),
}


@login_required
def data_master(request):
    context = {
        "vessels": Vessel.objects.order_by("-active", "name"),
        "jetties": Jetty.objects.order_by("port", "name"),
        "charterers": Charterer.objects.order_by("code"),
    }
    return render(request, "voyages/data_master.html", context)


@login_required
def master_edit(request, jenis, pk=None):
    if jenis not in MASTER:
        return redirect("data_master")
    model, form_class, label = MASTER[jenis]
    obj = get_object_or_404(model, pk=pk) if pk else None
    if request.method == "POST":
        form = form_class(request.POST, instance=obj)
        if form.is_valid():
            saved = form.save()
            verb = "diubah" if obj else "ditambahkan"
            messages.success(request, f"{label} “{saved}” {verb}.")
            return redirect("data_master")
    else:
        form = form_class(instance=obj)
    title = f"Ubah {label.lower()}" if obj else f"Tambah {label.lower()}"
    return render(
        request,
        "voyages/master_form.html",
        {"form": form, "title": title, "label": label, "obj": obj},
    )
