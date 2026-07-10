from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from . import presenters
from .forms import NEXT_TYPE, ActivityForm, ParcelFormSet, VoyageForm, next_code
from .models import Activity, Vessel, Voyage


@login_required
def voyage_list(request):
    voyages = Voyage.objects.select_related("vessel", "charterer", "discharge_jetty").prefetch_related(
        "activities__activity_type", "parcels__load_jetty"
    )
    vessel_id = request.GET.get("kapal") or ""
    status = request.GET.get("status") or ""
    year = request.GET.get("tahun") or ""
    q = (request.GET.get("cari") or "").strip()
    if vessel_id:
        voyages = voyages.filter(vessel_id=vessel_id)
    if status:
        voyages = voyages.filter(status=status)
    if year:
        voyages = voyages.filter(code__startswith=f"V{year[-2:]}")
    if q:
        voyages = voyages.filter(
            Q(code__icontains=q) | Q(contract_no__icontains=q)
            | Q(invoice_no__icontains=q) | Q(charterer__code__icontains=q)
        )

    rows = presenters.list_rows(voyages)
    all_voyages = Voyage.objects.prefetch_related("activities__activity_type", "parcels")
    years = sorted({f"20{v.code[1:3]}" for v in all_voyages if len(v.code) >= 3}, reverse=True)
    context = {
        "rows": rows,
        "cards": presenters.vessel_cards(Vessel.objects.filter(active=True)),
        "kpis": _kpis(all_voyages),
        "vessels": Vessel.objects.filter(active=True),
        "years": years,
        "statuses": Voyage.Status.choices,
        "filters": {"kapal": vessel_id, "status": status, "tahun": year, "cari": q},
    }
    return render(request, "voyages/voyage_list.html", context)


def _kpis(voyages) -> dict:
    from domain.calculations import demurrage_days, total_port_time

    ongoing = port_days = dem_days = mt = 0
    for v in voyages:
        acts = v.domain_activities()
        port = total_port_time(acts)
        if v.status == Voyage.Status.ONGOING:
            ongoing += 1
        if port:
            port_days += port.days
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        if v.demurrage_rate_idr:  # counted only when a rate exists (calc spec C6)
            dem_days += demurrage_days(port, laytime) or 0
        mt += sum(p.quantity_mt for p in v.parcels.all())
    return {"ongoing": ongoing, "port_days": port_days, "dem_days": dem_days, "mt": int(mt)}


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
