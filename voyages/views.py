from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import presenters
from .forms import NEXT_TYPE, ActivityForm
from .models import Vessel, Voyage


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


def _detail_context(request, voyage, form=None):
    if form is None and not voyage.locked:
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
    }


@login_required
def voyage_detail(request, pk):
    voyage = get_object_or_404(
        Voyage.objects.select_related("vessel", "charterer", "discharge_jetty"), pk=pk
    )
    return render(request, "voyages/voyage_detail.html", _detail_context(request, voyage))


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
