"""Display-ready view of a voyage: raw models + domain math -> Indonesian strings.

Templates never compute; views never format. Everything here calls the proven
domain/ package (ADR-002: computed on read, never stored).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

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


def _segments(activities) -> list[dict]:
    """Sheet-style legs: one sailing activity + the port rows that follow it."""
    segs: list[dict] = []
    for i, a in enumerate(activities):
        if a.activity_type.is_sailing or not segs:
            segs.append({"start": i, "rows": 0, "from": a.from_location, "to": a.to_location})
        segs[-1]["rows"] += 1
    return segs


def _block_subtotals(activities, acts) -> dict[int, dict]:
    """Excel-style 'Total Kegiatan Muat (A)' rows, keyed by the activity index
    they print after (the end of the sheet segment containing the block)."""
    blocks = split_port_blocks(acts)
    letters = "ABCDEFG"
    segs = _segments(activities)
    block_last = {acts.index(block[-1]): idx for idx, block in enumerate(blocks.in_order)}
    out: dict[int, dict] = {}
    pending = None
    for i in range(len(activities)):
        if i in block_last:
            pending = block_last[i]
        if pending is not None and any(s["start"] + s["rows"] - 1 == i for s in segs):
            block = blocks.in_order[pending]
            side = "Muat" if block in blocks.load else "Bongkar"
            pair = block_sheet_pair(block)
            out[i] = {
                "label": f"Total Kegiatan {side} ({letters[pending]})",
                "hari": str(pair.days),
                "waktu": _waktu_jam(pair.time),
                "normalized": dur_id(pair.as_timedelta()),
            }
            pending = None
    return out


def timeline(voyage: Voyage) -> list[dict]:
    """Activity rows with computed durations, Excel-style block subtotal rows,
    and any warning that follows an activity."""
    activities = list(voyage.activities.select_related("activity_type"))
    acts = [a.to_domain() for a in activities]
    warns = {w.after_index: w for w in log_warnings(acts)}
    subtotals = _block_subtotals(activities, acts) if acts else {}
    rows = []
    for i, a in enumerate(activities):
        dur = activity_duration(acts[i].start_at, acts[i].end_at)
        rows.append(
            {
                "kind": "activity",
                "no": i + 1,
                "activity": a,
                "duration": dur_id(dur) if dur is not None else "berjalan",
                "ongoing": a.end_at is None,
                "is_sailing": a.activity_type.is_sailing,
                # blue tint on port work/waiting rows, like the Excel sheet
                "fill": not a.activity_type.is_sailing and a.activity_type.phase != "prep",
                "warning": warning_text(warns[i]) if i in warns else None,
                "warning_kind": warns[i].code if i in warns else None,
            }
        )
        if i in subtotals:
            rows.append({"kind": "subtotal", **subtotals[i]})
    return rows


# The kegiatan picker: pills grouped by phase, colors matching the timeline.
TYPE_GROUPS = (
    ("Berlayar", "ok", ("ballast", "laden", "shifting")),
    ("Muat", "info", ("waiting_berth_load", "waiting_load", "loading", "waiting_cast_off")),
    ("Bongkar", "live", ("waiting_berth_discharge", "waiting_discharge", "discharging")),
    ("Lainnya", "neutral", ("preparation",)),
)


def activity_type_groups() -> list[dict]:
    from domain.model import ACTIVITY_TYPES

    return [
        {
            "label": label,
            "kind": kind,
            "types": [{"code": c, "label": ACTIVITY_TYPES[c].label_id} for c in codes],
        }
        for label, kind, codes in TYPE_GROUPS
    ]


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
        if v.status != Voyage.Status.ONGOING:
            progress = 100
        elif acts:
            progress = PHASE_TRACK.get(acts[-1].type.phase.value, (0, 4))[1]
        else:
            progress = 0
        rows.append(
            {
                "voyage": v,
                "vessel_short": v.vessel.tug_name.replace("TB. HUA ", ""),
                "route": route(v),
                "route_from": frm,
                "route_to": to,
                "progress": progress,
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

# activity_type.phase -> (tracker step index, % progress through the voyage cycle)
PHASE_TRACK = {
    "ballast": (0, 6),
    "waiting_load": (0, 14),
    "load": (0, 22),
    "laden": (1, 50),
    "waiting_discharge": (2, 78),
    "discharge": (2, 86),
    "prep": (2, 94),
}

# current step -> the phase chip on cards/table (color always beside the word)
PHASE_CHIP = {0: ("Muat", "info"), 1: ("Berlayar", "ok"), 2: ("Bongkar", "live")}


def _hari_waktu(d: timedelta | None) -> tuple[str, str]:
    """One activity row's (HARI, WAKTU) pair as the sheets print it."""
    if d is None:
        return "-", "-"
    minutes = int(d.total_seconds()) // 60
    return str(minutes // 1440), f"{(minutes % 1440) // 60}:{minutes % 60:02d}"


def _waktu_jam(td: timedelta) -> str:
    """Excel's [h]:mm total-hours convention for subtotal WAKTU cells (43:30)."""
    minutes = int(td.total_seconds()) // 60
    return f"{minutes // 60}:{minutes % 60:02d}"


def print_sheet(voyage: Voyage) -> dict:
    """Everything the printable time sheet needs, laid out like the Excel original:
    KETERANGAN grid with merged Berangkat/Tiba per leg, colored fills, block
    subtotals (A/B/...), A+B pair + normalized rows, prorata, DEMURRAGE,
    signature block."""
    activities = list(voyage.activities.select_related("activity_type"))
    acts = [a.to_domain() for a in activities]
    blocks = split_port_blocks(acts)
    letters = "ABCDEFG"
    segments = _segments(activities)
    subtotal_after = _block_subtotals(activities, acts) if acts else {}
    seg_first = {s["start"]: s for s in segments}
    is_ongoing = voyage.status == Voyage.Status.ONGOING
    rows = []
    for i, a in enumerate(activities):
        dur = activity_duration(acts[i].start_at, acts[i].end_at)
        hari, waktu = _hari_waktu(dur)
        note = a.note if a.note and not a.note.startswith("IMPORT:") else ""
        seg = seg_first.get(i)
        rows.append(
            {
                "kind": "activity",
                "label": a.activity_type.label_id,
                "note": note,
                # blue fill on port work/waiting rows, like the sheet
                "fill": not a.activity_type.is_sailing and a.activity_type.phase != "prep",
                "hari": hari,
                # open end = running on an ongoing voyage; on a completed one it
                # is the imported end-before-start flag, printed as "-"
                "waktu": waktu if a.end_at else ("berjalan" if is_ongoing else "-"),
                "rowspan": seg["rows"] if seg else 0,
                "seg_from": seg["from"] if seg else "",
                "seg_to": seg["to"] if seg else "",
                "start": a.start_at,
                "end": a.end_at,
            }
        )
        if i in subtotal_after:
            rows.append({"kind": "subtotal", **subtotal_after[i]})

    port = total_port_time(acts)
    combined = combined_sheet_pair(acts) if acts else None
    laytime = int(voyage.laytime_days) if voyage.laytime_days is not None else None
    dem = demurrage_days(port, laytime)
    if voyage.laytime_load_days and voyage.laytime_discharge_days:
        laytime_label = (
            f"{int(voyage.laytime_load_days)} Hari Muat + "
            f"{int(voyage.laytime_discharge_days)} Hari Bongkar"
        )
    elif laytime is not None:
        laytime_label = f"{laytime} hari"
    else:
        laytime_label = "-"
    parcels = list(voyage.parcels.select_related("load_jetty"))
    load_jetties = list(dict.fromkeys(str(p.load_jetty) for p in parcels))
    grand_hari, grand_waktu = _hari_waktu(port)
    block_letters = " + ".join(letters[: len(blocks.in_order)])
    return {
        "combined": (
            {
                "label": f"Total Kegiatan Muat - Bongkar ({block_letters})",
                "hari": str(combined.days),
                "waktu": _waktu_jam(combined.time),
            }
            if combined and len(blocks.in_order) > 1
            else None
        ),
        "voyage": voyage,
        "title": (
            f"TIME SHEET {voyage.vessel.tug_name.upper()} & {voyage.vessel.barge_name.upper()}"
            f"  (TABEL VOYAGE REPORT VOY. {voyage.code})"
        ),
        "header": [
            ("No. Kontrak", voyage.contract_no or "-"),
            ("Kwitansi Nomor", voyage.invoice_no or "-"),
            ("Muatan", " & ".join(
                f"{p.commodity} {num_id(int(p.quantity_mt))} MT" for p in parcels
            ) or "-"),
            ("Lokasi Muat", " & ".join(load_jetties) or "-"),
            ("Lokasi Bongkar", str(voyage.discharge_jetty) if voyage.discharge_jetty else "-"),
            ("Lama Muat/Bongkar", laytime_label),
            ("Demurrage", f"{rupiah(voyage.demurrage_rate_idr)}/hari" if voyage.demurrage_rate_idr else "-"),
        ],
        "rows": rows,
        "grand": {"hari": grand_hari, "waktu": grand_waktu} if port else None,
        "prorata": str(laytime) if laytime is not None else "-",
        "demurrage": str(dem) if dem is not None else "-",
        "ongoing": voyage.status == Voyage.Status.ONGOING,
        "printed_at": timezone.localtime(),
        "signatures": {
            "made_by": ("Felicia", "Operasional"),
            "known_by": ("Tjipta Lesmana Suwarto", "Direktur Utama"),
        },
    }


def export_rows(voyages) -> list[list]:
    """Ekspor CSV: one row per voyage, header first, all figures recomputed."""
    out = [[
        "Kode", "Kapal", "Pencharter", "Dari", "Ke", "Mulai", "Status",
        "Hari pelabuhan", "Kontrak (hari)", "Lebih (hari)", "Hari demurrage",
        "Estimasi demurrage (Rp)", "Muatan (MT)", "No. kontrak", "Kwitansi",
    ]]
    for r in list_rows(voyages):
        v = r["voyage"]
        acts = v.domain_activities()
        port = total_port_time(acts)
        laytime = r["laytime"]
        dem = demurrage_days(port, laytime) if v.demurrage_rate_idr else None
        dem_idr = (
            demurrage_amount_idr(port, laytime, v.demurrage_rate_idr)
            if v.demurrage_rate_idr else None
        )
        mt = sum(p.quantity_mt for p in v.parcels.all())
        out.append([
            v.code,
            v.vessel.tug_name,
            v.charterer.code if v.charterer else "",
            r["route_from"] or "",
            r["route_to"] or "",
            r["start"].astimezone().strftime("%Y-%m-%d") if r["start"] else "",
            "Berjalan" if v.status == Voyage.Status.ONGOING else "Selesai",
            r["port_days"],
            laytime if laytime is not None else "",
            r["over_days"] if r["over"] else 0,
            dem if dem is not None else "",
            dem_idr if dem_idr is not None else "",
            int(mt) if mt else "",
            v.contract_no,
            v.invoice_no,
        ])
    return out


def vessel_cards(vessels) -> list[dict]:
    """One hero card per vessel set: latest voyage, phase tracker, key facts."""
    cards = []
    for vessel in vessels:
        v = vessel.voyages.order_by("code").last()
        if v is None:
            continue
        acts = v.domain_activities()
        last = v.activities.select_related("activity_type").last()
        port = total_port_time(acts)
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
        chip_label, chip_kind = ("Selesai", "ok") if done else PHASE_CHIP[step]
        mt = sum(p.quantity_mt for p in v.parcels.all())
        started = acts[0].start_at if acts else None
        started_days = (timezone.now() - started).days if started else None
        cards.append(
            {
                "vessel": vessel,
                "voyage": v,
                "phase": last.activity_type.label_id if last else "—",
                "phase_ongoing": last is not None and last.end_at is None,
                "chip_label": chip_label,
                "chip_kind": chip_kind,
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
                "cargo_mt": num_id(int(mt)) if mt else None,
                "started_days": started_days,
                "incomplete": laytime is None or not (frm or to),
            }
        )
    return cards


def voyage_year(v: Voyage) -> int | None:
    """V2601 -> 2026 (voyages are attributed to years by their code)."""
    if len(v.code) >= 3 and v.code[1:3].isdigit():
        return 2000 + int(v.code[1:3])
    return None


def _periode(v: Voyage) -> tuple:
    """(start, end) of a voyage from its activity log; end only when completed."""
    acts = list(v.activities.all())
    start = acts[0].start_at if acts else None
    end = None
    if acts and v.status != Voyage.Status.ONGOING:
        end = acts[-1].end_at or acts[-1].start_at
    return start, end


def _performa(port, laytime) -> dict:
    """Kontrak-performance chip — the honest stand-in for the mock's on-time %."""
    if laytime is None:
        return {"label": "Tanpa kontrak", "kind": "neutral"}
    if port is None:
        return {"label": "Belum ada catatan", "kind": "neutral"}
    over = port.days - laytime
    if over > 0:
        return {"label": f"Lebih {over} hari", "kind": "bad"}
    return {"label": "Sesuai kontrak", "kind": "ok"}


def _year_totals(voyages, year: int) -> dict:
    n = port_days = dem = 0
    mt = Decimal(0)
    for v in voyages:
        if voyage_year(v) != year:
            continue
        n += 1
        port = total_port_time(v.domain_activities())
        port_days += port.days if port else 0
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        if v.demurrage_rate_idr:
            dem += demurrage_days(port, laytime) or 0
        mt += sum((p.quantity_mt for p in v.parcels.all()), Decimal(0))
    return {"n_voyages": n, "mt": num_id(int(mt)), "port_days": port_days, "dem_days": dem}


def _tracker(voyage) -> list[dict]:
    """Muat→Berlayar→Bongkar steps with real dates from the activity log.
    Ongoing: steps before the current phase are done; completed: all done."""
    activities = list(voyage.activities.select_related("activity_type"))
    last = activities[-1] if activities else None
    if voyage.status != Voyage.Status.ONGOING:
        cur = len(PHASE_STEPS)
    elif last is not None:
        cur = PHASE_TRACK.get(last.activity_type.phase, (0, 4))[0]
    else:
        cur = None
    steps = []
    for i, label in enumerate(PHASE_STEPS):
        acts_i = [
            a for a in activities
            if PHASE_TRACK.get(a.activity_type.phase, (0, 0))[0] == i
        ]
        if cur is None or i > cur:
            steps.append({"label": label, "state": "todo", "note": "Belum mulai", "date": None})
        elif i < cur:
            end = (acts_i[-1].end_at or acts_i[-1].start_at) if acts_i else None
            steps.append({"label": label, "state": "done", "note": "Selesai", "date": end})
        else:
            start = acts_i[0].start_at if acts_i else None
            steps.append({"label": label, "state": "current", "note": "Berjalan", "date": start})
    return steps


def fleet_cards(vessels) -> list[dict]:
    """Armada page: per vessel — identity, posisi sekarang, this-year performa
    tiles, and the three latest voyages (full history lives on the riwayat page)."""
    year = timezone.localtime().year
    cards = []
    for vessel in vessels:
        voyages = sorted(
            vessel.voyages.prefetch_related("activities__activity_type", "parcels__load_jetty"),
            key=lambda v: v.code,
            reverse=True,
        )
        ongoing = next((v for v in voyages if v.status == Voyage.Status.ONGOING), None)
        now = {}
        if ongoing:
            last = ongoing.activities.select_related("activity_type").last()
            if last is None:
                doing, since = "Belum ada kegiatan tercatat", None
            elif last.activity_type.is_sailing and last.to_location:
                doing, since = f"{last.activity_type.label_id} menuju {last.to_location}", last.start_at
            else:
                doing, since = last.activity_type.label_id, last.start_at
            step, _ = PHASE_TRACK.get(last.activity_type.phase, (0, 4)) if last else (0, 4)
            chip_label, chip_kind = PHASE_CHIP[step]
            frm, to = route_ends(ongoing)
            start, _ = _periode(ongoing)
            mt = sum((p.quantity_mt for p in ongoing.parcels.all()), Decimal(0))
            now = {
                "doing": doing,
                "since_days": (timezone.now() - since).days if since else None,
                "chip_label": chip_label if last else None,
                "chip_kind": chip_kind if last else None,
                "step": step if last else None,
                "route_from": frm,
                "route_to": to,
                "started": start,
                "mt": num_id(int(mt)) if mt else None,
            }
        else:
            done = next((v for v in voyages if v.status != Voyage.Status.ONGOING), None)
            if done:
                _, end = _periode(done)
                port = total_port_time(done.domain_activities())
                laytime = int(done.laytime_days) if done.laytime_days is not None else None
                now = {
                    "idle_since": end,
                    "last_voyage": done,
                    "last_route": route(done),
                    "last_performa": _performa(port, laytime),
                }
        last3 = []
        for v in voyages[:3]:
            start, end = _periode(v)
            last3.append({"voyage": v, "route": route(v), "start": start, "end": end})
        tracker_voyage = ongoing or (voyages[0] if voyages else None)
        cards.append(
            {
                "vessel": vessel,
                "ongoing": ongoing,
                "now": now,
                "charterer": ongoing.charterer.code if ongoing and ongoing.charterer else None,
                "tracker": _tracker(tracker_voyage) if tracker_voyage else None,
                "tracker_voyage": tracker_voyage,
                "last3": last3,
                "year": year,
                **_year_totals(voyages, year),
            }
        )
    return cards


def vessel_history(vessel, year: int) -> dict:
    """Riwayat page: header totals + one recomputed row per voyage of `year`."""
    voyages = sorted(
        (
            v
            for v in vessel.voyages.prefetch_related(
                "activities__activity_type", "parcels__load_jetty"
            )
            if voyage_year(v) == year
        ),
        key=lambda v: v.code,
        reverse=True,
    )
    rows = []
    n_ok = n_kontrak = 0
    for v in voyages:
        acts = v.domain_activities()
        port = total_port_time(acts)
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        start, end = _periode(v)
        mt = sum((p.quantity_mt for p in v.parcels.all()), Decimal(0))
        dem = demurrage_days(port, laytime)
        completed = v.status != Voyage.Status.ONGOING
        if completed and laytime is not None and port is not None:
            n_kontrak += 1
            if port.days <= laytime:
                n_ok += 1
        rows.append(
            {
                "voyage": v,
                "route": route(v),
                "start": start,
                "end": end,
                "mt": num_id(int(mt)) if mt else None,
                "port_days": port.days if port else 0,
                "laytime": laytime,
                "dem": dem,
                "performa": _performa(port, laytime) if completed else None,
            }
        )
    pct = round(n_ok / n_kontrak * 100) if n_kontrak else None
    return {"rows": rows, "pct_kontrak": pct, **_year_totals(voyages, year)}


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
        "dem_amount_prev": rupiah(prev_b["dem_idr"]),
        "dem_amount_trend": trend(now_b["dem_idr"], prev_b["dem_idr"]),
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
                    "title": "Melebihi kontrak",
                    "action": "Tinjau",
                    "text": (
                        f"Waktu pelabuhan {port.days} / {laytime} hari — "
                        f"{port.days - laytime} hari lebih."
                    ),
                }
            )
        n_warns = len(log_warnings(acts))
        if n_warns:
            items.append(
                {
                    "kind": "warn",
                    "voyage": v,
                    "title": "Catatan waktu janggal",
                    "action": "Periksa",
                    "text": f"{n_warns} jeda atau tumpang tindih di log kegiatan.",
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
                        "title": "Kegiatan berjalan lama",
                        "action": "Cek status",
                        "text": (
                            f"“{last.activity_type.label_id}” sudah berjalan "
                            f"{running_days} hari — sudah selesai?"
                        ),
                    }
                )
        if laytime is None:
            items.append(
                {
                    "kind": "info",
                    "voyage": v,
                    "title": "Kontrak belum lengkap",
                    "action": "Lengkapi",
                    "text": "Lama kontrak belum diisi — demurrage tidak terhitung.",
                }
            )
    order = {"bad": 0, "warn": 1, "info": 2}
    items.sort(key=lambda a: order[a["kind"]])
    return items[:5]
