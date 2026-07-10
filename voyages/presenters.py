"""Display-ready view of a voyage: raw models + domain math -> Indonesian strings.

Templates never compute; views never format. Everything here calls the proven
domain/ package (ADR-002: computed on read, never stored).
"""

from __future__ import annotations

from datetime import timedelta

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


def rupiah(amount: int) -> str:
    return f"Rp {amount:,}".replace(",", ".")


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


def route(voyage: Voyage) -> str:
    parcels = list(voyage.parcels.select_related("load_jetty"))
    frm = parcels[0].load_jetty if parcels else None
    to = voyage.discharge_jetty
    def short(j):
        return (j.port or j.name) if j else "?"
    if frm is None and to is None:
        return "—"
    return f"{short(frm)} → {short(to)}"


def list_rows(voyages) -> list[dict]:
    rows = []
    for v in voyages:
        acts = v.domain_activities()
        port = total_port_time(acts)
        start = acts[0].start_at if acts else None
        laytime = int(v.laytime_days) if v.laytime_days is not None else None
        rows.append(
            {
                "voyage": v,
                "route": route(v),
                "start": start,
                "port_days": port.days if port else 0,
                "laytime": laytime,
                "over": port is not None and laytime is not None and port.days > laytime,
            }
        )
    return rows


def vessel_cards(vessels) -> list[dict]:
    cards = []
    for vessel in vessels:
        v = vessel.voyages.order_by("code").last()
        if v is None:
            continue
        last = v.activities.select_related("activity_type").last()
        port = total_port_time(v.domain_activities())
        cards.append(
            {
                "vessel": vessel,
                "voyage": v,
                "phase": last.activity_type.label_id if last else "—",
                "phase_ongoing": last is not None and last.end_at is None,
                "port_days": port.days if port else 0,
            }
        )
    return cards
