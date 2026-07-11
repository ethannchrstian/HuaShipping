"""Laporan page aggregations: raw activity logs -> chart-ready rows.

Everything is recomputed from timestamps on read (ADR-002). Open-ended
activities are clipped at 'now'; utilization clips activities to calendar
months in local time (Asia/Jakarta).
"""

from __future__ import annotations

import calendar
import datetime

from django.utils import timezone

from domain.calculations import demurrage_amount_idr, demurrage_days, total_port_time
from domain.model import ACTIVITY_TYPES

from .models import Voyage
from .presenters import dur_id, num_id, route_ends, rupiah, voyage_year

# Display order = palette slot order (validated); Lainnya renders neutral gray.
CATEGORIES = [
    ("muat", "Muat"),
    ("tunggu", "Tunggu"),
    ("bongkar", "Bongkar"),
    ("berlayar", "Berlayar"),
    ("lainnya", "Lainnya"),
]


def categorize(type_code: str) -> str:
    """Bucket an activity type into the Laporan time categories."""
    t = ACTIVITY_TYPES[type_code]
    if t.is_sailing:
        return "berlayar"
    phase = t.phase.value
    if phase in ("waiting_load", "waiting_discharge"):
        return "tunggu"
    if phase == "load":
        return "muat"
    if phase == "discharge":
        return "bongkar"
    return "lainnya"


def _spans(voyage: Voyage, now):
    """(category, start, end) per activity.

    An open end means "still running" only on an ongoing voyage — there it is
    clipped at now. On a completed voyage an open end is an imported, flagged
    data error (end-before-start in the source sheet); counting it as running
    would smear that voyage across every later month, so it is skipped.
    """
    ongoing = voyage.status == Voyage.Status.ONGOING
    for a in voyage.domain_activities():
        end = a.end_at or (now if ongoing else None)
        if end is not None and end > a.start_at:
            yield categorize(a.type_code), a.start_at, end


def time_breakdown(voyages, year: int) -> dict:
    """Per-voyage stacked composition of where the time went."""
    now = timezone.now()
    rows = []
    totals = dict.fromkeys([k for k, _ in CATEGORIES], datetime.timedelta())
    for v in voyages:
        if voyage_year(v) != year:
            continue
        sums = dict.fromkeys([k for k, _ in CATEGORIES], datetime.timedelta())
        for cat, start, end in _spans(v, now):
            sums[cat] += end - start
        total = sum(sums.values(), datetime.timedelta())
        if not total:
            continue
        for k in totals:
            totals[k] += sums[k]
        rows.append(
            {
                "voyage": v,
                "vessel_short": v.vessel.tug_name.replace("TB. HUA ", ""),
                "ongoing": v.status == Voyage.Status.ONGOING,
                "total_label": dur_id(total),
                "parts": [
                    {
                        "key": k,
                        "label": label,
                        "pct": sums[k] / total * 100,
                        # CSS numbers must use dot decimals; template floats localize to commas
                        "pct_css": f"{sums[k] / total * 100:.2f}",
                        "days": round(sums[k].total_seconds() / 86400, 1),
                        "dur": dur_id(sums[k]),
                    }
                    for k, label in CATEGORIES
                    if sums[k]
                ],
                "parts_all": [dur_id(sums[k]) if sums[k] else "—" for k, _ in CATEGORIES],
            }
        )
    grand = sum(totals.values(), datetime.timedelta())
    return {
        "rows": rows,
        "legend": [
            {
                "key": k,
                "label": label,
                "days": round(totals[k].total_seconds() / 86400, 1),
                "pct": (totals[k] / grand * 100) if grand else 0,
            }
            for k, label in CATEGORIES
        ],
    }


def jetty_waiting(voyages, year: int) -> list[dict]:
    """Total & average waiting time attributed to each jetty (load side to the
    first load jetty, discharge side to the discharge jetty)."""
    now = timezone.now()
    buckets: dict[str, dict] = {}
    for v in voyages:
        if voyage_year(v) != year:
            continue
        frm, to = route_ends(v)
        ongoing = v.status == Voyage.Status.ONGOING
        for a in v.domain_activities():
            t = ACTIVITY_TYPES[a.type_code]
            if t.is_sailing or t.phase.value not in ("waiting_load", "waiting_discharge"):
                continue
            place = frm if t.phase.value == "waiting_load" else to
            # open end = running only on an ongoing voyage; on a completed one
            # it is the imported end-before-start flag — skip (see _spans)
            end = a.end_at or (now if ongoing else None)
            if place is None or end is None or end <= a.start_at:
                continue
            b = buckets.setdefault(place, {"total": datetime.timedelta(), "voyages": set()})
            b["total"] += end - a.start_at
            b["voyages"].add(v.pk)
    rows = [
        {
            "place": place,
            "total": b["total"],
            "total_label": dur_id(b["total"]),
            "calls": len(b["voyages"]),
            "avg_hours": b["total"].total_seconds() / 3600 / len(b["voyages"]),
            "avg_label": dur_id(b["total"] / len(b["voyages"])),
        }
        for place, b in buckets.items()
    ]
    rows.sort(key=lambda r: r["avg_hours"], reverse=True)
    top = rows[0]["avg_hours"] if rows else 0
    for r in rows:
        r["pct_css"] = f"{(r['avg_hours'] / top * 100) if top else 0:.1f}"
    return rows


def charterer_demurrage(voyages, year: int) -> list[dict]:
    """Per charterer: voyages, MT, over-contract days, demurrage days & Rp."""
    buckets: dict[str, dict] = {}
    for v in voyages:
        if voyage_year(v) != year:
            continue
        code = v.charterer.code if v.charterer else "—"
        b = buckets.setdefault(
            code, {"n": 0, "mt": 0, "over": 0, "dem_days": 0, "dem_idr": 0}
        )
        b["n"] += 1
        b["mt"] += sum(p.quantity_mt for p in v.parcels.all())
        port = total_port_time(v.domain_activities())
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        if port is not None and laytime is not None and port.days > laytime:
            b["over"] += port.days - laytime
        if v.demurrage_rate_idr:
            b["dem_days"] += demurrage_days(port, laytime) or 0
            b["dem_idr"] += demurrage_amount_idr(port, laytime, v.demurrage_rate_idr) or 0
    rows = [
        {
            "charterer": code,
            "n": b["n"],
            "mt": num_id(int(b["mt"])),
            "over": b["over"],
            "dem_days": b["dem_days"],
            "dem_idr": b["dem_idr"],
            "dem_rp": rupiah(b["dem_idr"]) if b["dem_idr"] else "—",
        }
        for code, b in buckets.items()
    ]
    rows.sort(key=lambda r: (-r["dem_idr"], -r["over"], r["charterer"]))
    return rows


def utilization(vessels, year: int) -> list[dict]:
    """Per vessel per month: days sailing / in port / idle, clipped to months."""
    now = timezone.localtime()
    tz = now.tzinfo
    out = []
    for vessel in vessels:
        spans = []
        for v in vessel.voyages.all():
            spans.extend(_spans(v, timezone.now()))
        months = []
        for m in range(1, 13):
            days_in_month = calendar.monthrange(year, m)[1]
            m_start = datetime.datetime(year, m, 1, tzinfo=tz)
            m_end = m_start + datetime.timedelta(days=days_in_month)
            if m_start > now:
                months.append({"month": m, "future": True})
                continue
            sail = port = datetime.timedelta()
            for cat, start, end in spans:
                lo, hi = max(start, m_start), min(end, m_end)
                if hi <= lo:
                    continue
                if cat == "berlayar":
                    sail += hi - lo
                else:
                    port += hi - lo
            visible = min(m_end, now) - m_start
            idle = max(visible - sail - port, datetime.timedelta())
            total = days_in_month * 86400
            months.append(
                {
                    "month": m,
                    "future": False,
                    "sail_days": round(sail.total_seconds() / 86400, 1),
                    "port_days": round(port.total_seconds() / 86400, 1),
                    "idle_days": round(idle.total_seconds() / 86400, 1),
                    "sail_css": f"{sail.total_seconds() / total * 100:.1f}",
                    "port_css": f"{port.total_seconds() / total * 100:.1f}",
                    "idle_css": f"{idle.total_seconds() / total * 100:.1f}",
                }
            )
        out.append({"vessel": vessel, "months": months})
    return out


MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
