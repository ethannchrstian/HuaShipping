"""One-time historical import per docs/05-import-mapping.md.

Consumes the structured sheet dumps produced by tools/dump_timesheets.py
(docs/reference/timesheets-raw.json — the committed ground truth), creates the
database records, FLAGS known data errors (never fixes them), and verifies
every voyage by recomputing all totals and diffing against the printed rows.

Entry point: import_all(sheets) -> ImportReport. The management command
`import_timesheets` wraps it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from domain.calculations import (
    SheetPair,
    block_sheet_pair,
    combined_sheet_pair,
    demurrage_days,
    split_port_blocks,
    total_port_time,
)
from domain.parsing import parse_cargo, parse_demurrage_rate, parse_laytime

from .models import Activity, Charterer, Jetty, Parcel, Vessel, Voyage

WIB = ZoneInfo("Asia/Jakarta")

# 'FN-HUAT' is FPS per the prototype seed (docs/05 §Charterer)
CHARTERER_ALIASES = {"FN": "FPS"}

# label prefix (lowercased) -> activity type; sandar side resolved by position
LABEL_TO_TYPE = [
    ("persiapan", "preparation"),
    ("perjalanan ke lokasi muat", "ballast"),
    ("perjalanan ke lokasi bongkar", "laden"),
    ("shifting", "shifting"),
    ("tunggu info sandar", "_sandar"),  # -> waiting_berth_load / _discharge
    ("tunggu info muat", "waiting_load"),
    ("tunggu info cast off", "waiting_cast_off"),
    ("tunggu info bongkar", "waiting_discharge"),
    ("kegiatan muat", "loading"),
    ("kegiatan bongkar", "discharging"),
]


@dataclass
class SheetResult:
    sheet_name: str
    voyage_code: str
    vessel_name: str
    created_activities: int = 0
    created_parcels: int = 0
    flags: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return "MISMATCH" if self.mismatches else "OK"


@dataclass
class ImportReport:
    results: list[SheetResult] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ["# Import report", ""]
        for r in self.results:
            lines.append(f"## {r.sheet_name} — {r.verdict}")
            lines.append(
                f"- {r.created_activities} activities, {r.created_parcels} parcels"
            )
            for f in r.flags:
                lines.append(f"- ⚑ {f}")
            for m in r.mismatches:
                lines.append(f"- ✗ {m}")
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------- helpers


def vessel_for(sheet_name: str) -> Vessel:
    m = re.match(r"HN (\d) PH (\d+)", sheet_name)
    if not m:
        raise ValueError(f"cannot derive vessel from sheet name {sheet_name!r}")
    tug = f"TB. HUA Navigator {m.group(1)}"
    barge = f"BG. Palm Hero {m.group(2)}"
    vessel, _ = Vessel.objects.get_or_create(
        name=f"{tug} & {barge}", defaults={"tug_name": tug, "barge_name": barge}
    )
    return vessel


def _jetty_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("jetty", "").replace("pt.", ""))


def get_jetty(raw_segment: str) -> Jetty:
    """Fuzzy get-or-create: 'Jetty PT. Parna Agro Mas (PAM), Sekadau' matches
    an existing 'Jetty Parna Agromas (PAM)' via a normalized key."""
    seg = raw_segment.strip()
    name, port = seg, ""
    if "," in seg:
        name, port = (p.strip() for p in seg.rsplit(",", 1))
    key = _jetty_key(name)
    for j in Jetty.objects.all():
        if _jetty_key(j.name) == key:
            return j
    return Jetty.objects.create(name=name, port=port)


def charterer_for(contract_no: str | None) -> Charterer | None:
    if not contract_no:
        return None
    m = re.search(r"([A-Z]{2,})-HUAT|HUAT-([A-Z]{2,})", contract_no)
    if not m:
        return None
    code = m.group(1) or m.group(2)
    code = CHARTERER_ALIASES.get(code, code)
    charterer, _ = Charterer.objects.get_or_create(code=code)
    return charterer


def map_label(label: str, before_last_laden: bool) -> tuple[str, str]:
    """-> (type_code, note). The remainder after the prefix (consignee,
    per-jetty cargo parenthetical...) is kept verbatim as the note."""
    low = label.lower().strip()
    for prefix, code in LABEL_TO_TYPE:
        if low.startswith(prefix):
            if code == "_sandar":
                code = "waiting_berth_load" if before_last_laden else "waiting_berth_discharge"
            note = label[len(prefix):].strip(" -")
            return code, note
    raise ValueError(f"unmapped activity label: {label!r}")


def wib(date_iso: str | None, time_str: str | None) -> datetime | None:
    if not date_iso or not time_str:
        return None
    d = datetime.fromisoformat(date_iso)
    h, m = (int(x) for x in time_str.split(":")[:2])
    return d.replace(hour=h, minute=m, tzinfo=WIB)


def parse_printed_pair(days, time_val) -> SheetPair | None:
    """A printed (HARI, WAKTU) pair from the JSON dump; None if unusable."""
    if days is None or time_val is None or not isinstance(days, int | float):
        return None
    if isinstance(time_val, dict) and "timedelta" in time_val:
        m = re.match(r"(\d+)d (\d+):(\d+)", time_val["timedelta"])
        td = timedelta(days=int(m.group(1)), hours=int(m.group(2)), minutes=int(m.group(3)))
    elif isinstance(time_val, str):
        h, mi = (int(x) for x in time_val.split(":")[:2])
        td = timedelta(hours=h, minutes=mi)
    else:
        return None  # e.g. excel_duration_artifact — not comparable
    return SheetPair(int(days), td)


# ---------------------------------------------------------------- import


def import_sheet(sheet: dict) -> SheetResult:
    sheet_name = sheet["sheet_name"]
    m = re.search(r"Voy\.?\s*(V\d+)", sheet_name, re.I)
    code = m.group(1)
    vessel = vessel_for(sheet_name)
    result = SheetResult(sheet_name=sheet_name, voyage_code=code, vessel_name=vessel.name)

    if sheet.get("voyage_code") and sheet["voyage_code"] != code:
        result.flags.append(
            f"kode voyage beda: sheet {code!r} vs judul {sheet['voyage_code']!r}"
        )

    header = sheet["header"]
    laytime = parse_laytime(header["laytime"]) if header.get("laytime") else None
    discharge_jetty = get_jetty(header["discharge_location"]) if header.get("discharge_location") else None

    voyage = Voyage.objects.create(
        code=code,
        vessel=vessel,
        charterer=charterer_for(header.get("contract_no")),
        contract_no=(header.get("contract_no") or "").strip(),
        invoice_no=(header.get("invoice_no") or "").strip(),
        discharge_jetty=discharge_jetty,
        laytime_days=laytime.total_days if laytime else None,
        laytime_load_days=laytime.load_days if laytime else None,
        laytime_discharge_days=laytime.discharge_days if laytime else None,
        demurrage_rate_idr=parse_demurrage_rate(header.get("demurrage")),
    )

    _create_activities(sheet, voyage, result)
    _create_parcels(sheet, voyage, header, result)

    # status: a voyage still at sea/at work has an open-ended last activity
    last = voyage.activities.last()
    ongoing = last is not None and last.end_at is None and not any(
        f.startswith("jam selesai") for f in result.flags
    )
    if not ongoing:
        voyage.status = Voyage.Status.COMPLETED
        voyage.locked = True
        voyage.save(update_fields=["status", "locked"])

    result.mismatches = verify_sheet(sheet, voyage)
    return result


def _create_activities(sheet: dict, voyage: Voyage, result: SheetResult) -> None:
    rows = [r for r in sheet["rows"] if r["kind"] == "activity" and r["start_date"]]
    last_laden_idx = max(
        (i for i, r in enumerate(rows) if r["label"].lower().startswith("perjalanan ke lokasi bongkar")),
        default=len(rows),
    )
    for i, row in enumerate(rows):
        type_code, note = map_label(row["label"], before_last_laden=i < last_laden_idx)
        start = wib(row["start_date"], row["start_time"])
        end = wib(row["end_date"], row["end_time"])
        if end is not None and end < start:
            # docs/05: keep the row, clear the invalid end, flag for review
            note = (
                f"IMPORT: jam selesai tidak valid "
                f"({end:%H:%M} < {start:%H:%M}) — perlu dicek. {note}".strip()
            )
            result.flags.append(
                f"jam selesai sebelum jam mulai di baris {row['excel_row']} ({row['label']}); "
                f"jam selesai dikosongkan"
            )
            end = None
        is_sailing = type_code in ("ballast", "laden", "shifting")
        Activity.objects.create(
            voyage=voyage,
            activity_type_id=type_code,
            start_at=start,
            end_at=end,
            from_location=(row.get("from_location") or "") if is_sailing else "",
            to_location=(row.get("to_location") or "") if is_sailing else "",
            note=note[:200],
        )
        result.created_activities += 1


def _create_parcels(sheet: dict, voyage: Voyage, header: dict, result: SheetResult) -> None:
    if not header.get("cargo"):
        return
    cargo = parse_cargo(header["cargo"])
    load_jetties = [get_jetty(seg) for seg in header.get("load_location", "").split("&") if seg.strip()]
    if not load_jetties:
        result.flags.append("lokasi muat kosong — parcel tanpa jetty tidak dibuat")
        return

    if len(load_jetties) == 1:
        Parcel.objects.create(
            voyage=voyage, commodity=cargo.commodity, quantity_mt=cargo.quantity_mt,
            load_jetty=load_jetties[0],
        )
        result.created_parcels = 1
        return

    # multi-jetty: split by the per-lot parentheticals on the loading rows,
    # e.g. 'Kegiatan Muat (CPO 2,000 MT PT. TBSM)'
    lots = []
    for a in voyage.activities.filter(activity_type_id="loading"):
        qm = re.search(r"([\d][\d.,]*)\s*MT", a.note)
        if qm:
            sm = re.search(r"(PT\.?\s*\w+)", a.note)
            lots.append((int(re.sub(r"[.,]", "", qm.group(1))), sm.group(1) if sm else ""))
    if not lots:
        result.flags.append("multi-jetty tanpa rincian muat per jetty — total di jetty pertama")
        lots = [(cargo.quantity_mt, "")]

    for i, (qty, shipper) in enumerate(lots):
        jetty = _match_jetty_for_shipper(shipper, load_jetties)
        if jetty is None:
            jetty = load_jetties[i] if len(lots) == len(load_jetties) else load_jetties[0]
            if shipper:
                result.flags.append(f"jetty untuk pengirim {shipper!r} tidak pasti — pakai {jetty.name!r}")
        Parcel.objects.create(
            voyage=voyage, commodity=cargo.commodity, quantity_mt=qty,
            load_jetty=jetty, shipper=shipper,
        )
        result.created_parcels += 1

    total = sum(q for q, _ in lots)
    if total != cargo.quantity_mt:
        result.flags.append(f"jumlah parcel {total} MT ≠ muatan header {cargo.quantity_mt} MT")


def _match_jetty_for_shipper(shipper: str, jetties: list[Jetty]) -> Jetty | None:
    """'PT. TBSM' -> 'Jetty Tintin Boyok Sawit Makmur' (initials) or a jetty
    whose name carries the same (ABBREV) parenthetical."""
    abbrev = re.sub(r"^PT\.?\s*", "", shipper).strip().upper()
    if not abbrev:
        return None
    for j in jetties:
        if f"({abbrev})" in j.name.upper():
            return j
        words = re.sub(r"\(.*?\)|jetty|pt\.", "", j.name, flags=re.I).split()
        if "".join(w[0].upper() for w in words if w) == abbrev:
            return j
    return None


# ---------------------------------------------------------------- verify


def fmt_pair(sp: SheetPair) -> str:
    """SheetPair(4, 1d19:30) -> '4 | 1d 19:30' (the sheet's HARI | WAKTU columns)."""
    minutes = int(sp.time.total_seconds()) // 60
    d, rest = divmod(minutes, 1440)
    prefix = f"{d}d " if d else ""
    return f"{sp.days} | {prefix}{rest // 60:02d}:{rest % 60:02d}"


def verify_sheet(sheet: dict, voyage: Voyage) -> list[str]:
    """Recompute all totals per docs/04 and diff against the printed rows.
    Same comparison the oracle test proved against all 11 sheets."""
    mismatches: list[str] = []
    acts = voyage.domain_activities()
    if not acts:
        return mismatches
    rows = sheet["rows"]
    blocks = split_port_blocks(acts).in_order

    def printed(row):
        return parse_printed_pair(row["total_days"], row["total_time"])

    block_rows = [
        r for r in rows
        if r["kind"] == "subtotal"
        and "muat - bongkar" not in (r["label"] or "").lower()
        and not (r["label"] or "").lower().startswith("total kegiatan a")  # V2606 stray note
        and printed(r) is not None
    ]
    for row, block in zip(block_rows, blocks, strict=False):
        computed = block_sheet_pair(block)
        if computed != printed(row):
            mismatches.append(
                f"{row['label']}: tertulis {fmt_pair(printed(row))}, hitung ulang {fmt_pair(computed)}"
            )

    for row in rows:
        if row["kind"] == "subtotal" and "muat - bongkar" in (row["label"] or "").lower():
            if printed(row) is not None and combined_sheet_pair(acts) != printed(row):
                mismatches.append(
                    f"{row['label']}: tertulis {fmt_pair(printed(row))}, "
                    f"hitung ulang {fmt_pair(combined_sheet_pair(acts))}"
                )
        elif row["kind"] == "grand_total":
            if printed(row) is not None and combined_sheet_pair(acts).normalized() != printed(row):
                mismatches.append(
                    f"total akhir: tertulis {fmt_pair(printed(row))}, "
                    f"hitung ulang {fmt_pair(combined_sheet_pair(acts).normalized())}"
                )
        elif row["kind"] == "laytime_contract" and isinstance(row["total_days"], int):
            if voyage.laytime_days is not None and int(voyage.laytime_days) != row["total_days"]:
                mismatches.append(
                    f"prorata: tertulis {row['total_days']}, header {voyage.laytime_days}"
                )
        elif row["kind"] == "demurrage" and isinstance(row["total_days"], int):
            computed_days = demurrage_days(
                total_port_time(acts),
                int(voyage.laytime_days) if voyage.laytime_days is not None else None,
            )
            if computed_days != row["total_days"]:
                mismatches.append(
                    f"DEMURRAGE: tertulis {row['total_days']} hari, hitung ulang {computed_days}"
                )
    return mismatches


def import_all(sheets: list[dict]) -> ImportReport:
    report = ImportReport()
    for sheet in sheets:
        report.results.append(import_sheet(sheet))
    return report
