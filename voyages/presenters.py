"""Display-ready view of a voyage: raw models + domain math -> Indonesian strings.

Templates never compute; views never format. Everything here calls the proven
domain/ package (ADR-002: computed on read, never stored).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from domain.calculations import (
    SheetPair,
    activity_duration,
    block_sheet_pair,
    combined_sheet_pair,
    demurrage_amount_idr,
    demurrage_days,
    split_port_blocks,
    total_port_time,
)
from domain.warnings import log_warnings

from .models import Voyage


def dur_id(d: timedelta | None) -> str:
    """4d15h -> '4 hari 15:00'; under a day -> '6:53'; None -> '—'."""
    if d is None:
        return "—"
    minutes = int(d.total_seconds()) // 60
    days, rest = divmod(minutes, 1440)
    hhmm = f"{rest // 60}:{rest % 60:02d}"
    return f"{days} hari {hhmm}" if days else hhmm


def pair_id(sp: SheetPair) -> str:
    """Sheet-style HARI | WAKTU pair, as printed on the Excel sheets."""
    return f"{sp.days} | {dur_id(sp.time)}"


def num_id(n: int) -> str:
    """40130 -> '40.130' (Indonesian thousand separators)."""
    return f"{n:,}".replace(",", ".")


def rupiah(amount: int) -> str:
    return f"Rp {num_id(amount)}"


def warning_text(w) -> str:
    """Blame-free, explains and suggests (PRODUCT.md principle 4)."""
    if w.code == "gap":
        return (
            f"Ada jeda {dur_id(w.amount)} yang belum tercatat setelah kegiatan ini — "
            f"mungkin ada kegiatan yang terlewat."
        )
    return (
        f"Tumpang tindih {dur_id(w.amount)} dengan kegiatan berikutnya — "
        f"periksa kembali tanggal atau jamnya."
    )


def timeline(voyage: Voyage) -> list[dict]:
    """Activity rows with computed duration and any warning that follows them."""
    activities = list(voyage.activities.select_related("activity_type"))
    acts = [a.to_domain() for a in activities]
    warns = {w.after_index: w for w in log_warnings(acts)}
    rows = []
    for i, a in enumerate(activities):
        dur = activity_duration(acts[i].start_at, acts[i].end_at)
        rows.append(
            {
                "activity": a,
                "duration": dur_id(dur) if dur is not None else "berjalan",
                "ongoing": a.end_at is None,
                "is_sailing": a.activity_type.is_sailing,
                "warning": warning_text(warns[i]) if i in warns else None,
                "warning_kind": warns[i].code if i in warns else None,
            }
        )
    return rows


def summary(voyage: Voyage) -> dict:
    """The day-summary strip: per-block pairs, grand total, laytime, demurrage."""
    acts = voyage.domain_activities()
    if not acts:
        return {"blocks": [], "port_time": None}
    blocks = split_port_blocks(acts)
    letters = "ABCDEFG"
    block_rows = []
    for i, block in enumerate(blocks.in_order):
        side = "Muat" if block in blocks.load else "Bongkar"
        pair = block_sheet_pair(block)
        block_rows.append(
            {
                "label": f"Total Kegiatan {side} ({letters[i]})",
                "pair": pair_id(pair),
                "normalized": dur_id(pair.as_timedelta()),
            }
        )
    port_time = total_port_time(acts)
    laytime = int(voyage.laytime_days) if voyage.laytime_days is not None else None
    over_days = None
    if port_time is not None and laytime is not None:
        over_days = port_time.days - laytime
    dem_days = demurrage_days(port_time, laytime)
    dem_amount = demurrage_amount_idr(port_time, laytime, voyage.demurrage_rate_idr)
    return {
        "blocks": block_rows,
        "combined": pair_id(combined_sheet_pair(acts)) if len(block_rows) > 1 else None,
        "port_time": dur_id(port_time),
        "laytime": laytime,
        "over_days": over_days,
        "over_text": (
            f"+{over_days} hari lebih dari kontrak" if over_days and over_days > 0
            else ("sesuai kontrak" if over_days is not None else None)
        ),
        "demurrage_days": dem_days,
        "demurrage_amount": rupiah(dem_amount) if dem_amount else None,
    }


def route_ends(voyage: Voyage) -> tuple[str | None, str | None]:
    """Short names of the load jetty and discharge jetty (None when unknown)."""
    parcels = list(voyage.parcels.select_related("load_jetty"))
    frm = parcels[0].load_jetty if parcels else None
    to = voyage.discharge_jetty
    def short(j):
        return (j.port or j.name) if j else None
    return short(frm), short(to)


def route(voyage: Voyage) -> str:
    frm, to = route_ends(voyage)
    if frm is None and to is None:
        return "—"
    return f"{frm or '?'} → {to or '?'}"


def list_rows(voyages) -> list[dict]:
    rows = []
    for v in voyages:
        acts = v.domain_activities()
        port = total_port_time(acts)
        start = acts[0].start_at if acts else None
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        frm, to = route_ends(v)
        rows.append(
            {
                "voyage": v,
                "vessel_short": v.vessel.tug_name.replace("TB. HUA ", ""),
                "route": route(v),
                "route_from": frm,
                "route_to": to,
                "start": start,
                "port_days": port.days if port else 0,
                "laytime": laytime,
                "over": port is not None and laytime is not None and port.days > laytime,
                "over_days": (port.days - laytime) if port is not None and laytime is not None else 0,
                "bar_pct": (
                    min(round((port.days if port else 0) / laytime * 100), 100) if laytime else None
                ),
            }
        )
    return rows


PHASE_STEPS = ("Muat", "Berlayar", "Bongkar")

# activity_type.phase -> (tracker step index, vessel-marker % along the route line)
PHASE_TRACK = {
    "ballast": (0, 6),
    "waiting_load": (0, 14),
    "load": (0, 22),
    "laden": (1, 50),
    "waiting_discharge": (2, 78),
    "discharge": (2, 86),
    "prep": (2, 94),
}


def vessel_cards(vessels) -> list[dict]:
    """One hero card per vessel set: latest voyage, route line, phase tracker."""
    cards = []
    for vessel in vessels:
        v = vessel.voyages.order_by("code").last()
        if v is None:
            continue
        last = v.activities.select_related("activity_type").last()
        port = total_port_time(v.domain_activities())
        port_days = port.days if port else 0
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        done = v.status != Voyage.Status.ONGOING
        step, marker = PHASE_TRACK.get(last.activity_type.phase, (0, 4)) if last else (0, 4)
        if done:
            step, marker = len(PHASE_STEPS) - 1, 100
        steps = [
            {
                "label": label,
                "state": "done" if (done or i < step) else ("current" if i == step else "todo"),
            }
            for i, label in enumerate(PHASE_STEPS)
        ]
        frm, to = route_ends(v)
        over = laytime is not None and port_days > laytime
        cards.append(
            {
                "vessel": vessel,
                "voyage": v,
                "phase": last.activity_type.label_id if last else "—",
                "phase_ongoing": last is not None and last.end_at is None,
                "steps": steps,
                "marker_pct": marker,
                "route_known": frm is not None or to is not None,
                "route_from": frm or "?",
                "route_to": to or "?",
                "port_days": port_days,
                "laytime": laytime,
                "over": over,
                "over_days": (port_days - laytime) if over else 0,
                "progress_pct": min(round(port_days / laytime * 100), 100) if laytime else None,
            }
        )
    return cards


def voyage_year(v: Voyage) -> int | None:
    """V2601 -> 2026 (voyages are attributed to years by their code)."""
    if len(v.code) >= 3 and v.code[1:3].isdigit():
        return 2000 + int(v.code[1:3])
    return None


def kpis(voyages, year: int) -> dict:
    """Dashboard stat tiles, scoped to `year` with last year as honest comparison."""
    ongoing = 0
    per_year: dict[int, dict] = {}
    for v in voyages:
        if v.status == Voyage.Status.ONGOING:
            ongoing += 1
        vy = voyage_year(v)
        if vy is None:
            continue
        b = per_year.setdefault(vy, {"dem_days": 0, "dem_idr": 0, "mt": 0})
        port = total_port_time(v.domain_activities())
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        if v.demurrage_rate_idr:  # counted only when a rate exists (calc spec C6)
            b["dem_days"] += demurrage_days(port, laytime) or 0
            b["dem_idr"] += demurrage_amount_idr(port, laytime, v.demurrage_rate_idr) or 0
        b["mt"] += sum(p.quantity_mt for p in v.parcels.all())
    empty = {"dem_days": 0, "dem_idr": 0, "mt": 0}
    now_b, prev_b = per_year.get(year, empty), per_year.get(year - 1, empty)

    def trend(now_v, prev_v):
        if now_v > prev_v:
            return "up"
        return "down" if now_v < prev_v else "flat"

    return {
        "year": year,
        "ongoing": ongoing,
        "dem_days": now_b["dem_days"],
        "dem_days_prev": prev_b["dem_days"],
        "dem_trend": trend(now_b["dem_days"], prev_b["dem_days"]),
        "dem_delta": abs(now_b["dem_days"] - prev_b["dem_days"]),
        "dem_amount": rupiah(now_b["dem_idr"]),
        "mt": int(now_b["mt"]),
        "mt_fmt": num_id(int(now_b["mt"])),
        "mt_prev": int(prev_b["mt"]),
        "mt_prev_fmt": num_id(int(prev_b["mt"])),
        "mt_trend": trend(int(now_b["mt"]), int(prev_b["mt"])),
        "mt_delta_fmt": num_id(abs(int(now_b["mt"]) - int(prev_b["mt"]))),
    }


def alerts(voyages) -> list[dict]:
    """'Perlu perhatian' panel — actionable findings on ongoing voyages only.

    Each item: kind (bad/warn/info), voyage, and a plain Indonesian sentence.
    """
    items = []
    for v in voyages:
        if v.status != Voyage.Status.ONGOING:
            continue
        acts = v.domain_activities()
        port = total_port_time(acts)
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        if laytime is not None and port is not None and port.days > laytime:
            items.append(
                {
                    "kind": "bad",
                    "voyage": v,
                    "text": (
                        f"{v.code} sudah {port.days - laytime} hari melebihi kontrak "
                        f"({port.days} / {laytime} hari)."
                    ),
                }
            )
        n_warns = len(log_warnings(acts))
        if n_warns:
            items.append(
                {
                    "kind": "warn",
                    "voyage": v,
                    "text": (
                        f"Ada {n_warns} catatan waktu yang perlu diperiksa di {v.code} "
                        f"(jeda atau tumpang tindih)."
                    ),
                }
            )
        last = v.activities.select_related("activity_type").last()
        if last is not None and last.end_at is None:
            running_days = (timezone.now() - last.start_at).days
            if running_days >= 3:
                items.append(
                    {
                        "kind": "info",
                        "voyage": v,
                        "text": (
                            f"“{last.activity_type.label_id}” di {v.code} sudah berjalan "
                            f"{running_days} hari — sudah selesai?"
                        ),
                    }
                )
        if laytime is None:
            items.append(
                {
                    "kind": "info",
                    "voyage": v,
                    "text": f"{v.code} belum punya lama kontrak — lengkapi agar demurrage terhitung.",
                }
            )
    order = {"bad": 0, "warn": 1, "info": 2}
    items.sort(key=lambda a: order[a["kind"]])
    return items[:5]
