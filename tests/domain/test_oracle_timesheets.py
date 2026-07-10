"""Excel-as-oracle golden test (docs/07-test-plan.md L2).

Replays every real voyage from docs/reference/timesheets-raw.json through the
domain engine and asserts it reproduces the sheets' printed totals exactly:
per-block (HARI, WAKTU) pairs, the combined row, the normalized grand total,
prorata, and DEMURRAGE days.

Known exceptions (docs/05): two end-before-start rows the app must FLAG
instead of reproducing — their sheets get partial comparison (discharge block
only).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from domain.calculations import (
    SheetPair,
    block_sheet_pair,
    combined_sheet_pair,
    demurrage_days,
    split_port_blocks,
    total_port_time,
)
from domain.model import Activity
from domain.parsing import parse_laytime

DATA = Path(__file__).resolve().parents[2] / "docs" / "reference" / "timesheets-raw.json"

LABEL_TO_TYPE = [
    ("perjalanan ke lokasi muat", "ballast"),
    ("perjalanan ke lokasi bongkar", "laden"),
    ("shifting", "shifting"),
    ("persiapan", "preparation"),
    ("tunggu info sandar", "waiting_berth_load"),  # side irrelevant to totals
    ("tunggu info muat", "waiting_load"),
    ("kegiatan muat", "loading"),
    ("tunggu info cast off", "waiting_cast_off"),
    ("tunggu info bongkar", "waiting_discharge"),
    ("kegiatan bongkar", "discharging"),
]

# Real data-entry errors the engine must flag, not reproduce (docs/05 known-errors table):
# - V2501 & HN1-V2604: an activity ends before it starts (importer clears the end + flags)
# - HN2-V2602: row 17 start date typo'd a day early (24h overlap with loading) AND row 16's
#   HARI formula (=I-F, midnights crossed) double-counts a day whose duration is already in
#   the hand-typed WAKTU cell -> printed block A (and the demurrage billed from it) is
#   inflated; discovered by this oracle on 2026-07-10
END_BEFORE_START_SHEETS = {"HN 1 PH 2401 Voy. V2501", "HN 1 PH 2401 Voy. V2604"}
OVERLAP_SHEETS = {"HN 2 PH 2402 Voy. V2602"}
KNOWN_ERROR_SHEETS = END_BEFORE_START_SHEETS | OVERLAP_SHEETS


def sheets():
    return json.loads(DATA.read_text(encoding="utf-8"))


def type_for(label: str) -> str:
    low = label.lower().strip()
    for prefix, code in LABEL_TO_TYPE:
        if low.startswith(prefix):
            return code
    raise AssertionError(f"unmapped activity label: {label!r}")


def dt(date_iso: str | None, time_str: str | None) -> datetime | None:
    if not date_iso or not time_str:
        return None
    d = datetime.fromisoformat(date_iso)
    h, m = (int(x) for x in time_str.split(":")[:2])
    return d.replace(hour=h, minute=m)


def parse_pair(days, time_val) -> SheetPair | None:
    """Printed (HARI, WAKTU) pair from the JSON dump."""
    if days is None or time_val is None:
        return None
    if isinstance(time_val, dict) and "timedelta" in time_val:
        m = re.match(r"(\d+)d (\d+):(\d+)", time_val["timedelta"])
        td = timedelta(days=int(m.group(1)), hours=int(m.group(2)), minutes=int(m.group(3)))
    elif isinstance(time_val, str):
        h, mi = (int(x) for x in time_val.split(":")[:2])
        td = timedelta(hours=h, minutes=mi)
    else:
        return None
    return SheetPair(int(days), td)


def build_activities(sheet) -> tuple[list[Activity], list[str]]:
    """Activities from the sheet rows; returns (activities, flagged-error labels)."""
    acts, flagged = [], []
    for row in sheet["rows"]:
        if row["kind"] != "activity":
            continue
        start = dt(row["start_date"], row["start_time"])
        end = dt(row["end_date"], row["end_time"])
        if start is None:
            continue  # template row on an ongoing sheet
        if end is not None and end < start:
            flagged.append(row["label"])
            end = None  # importer convention (docs/05): keep row, clear invalid end
        acts.append(Activity(type_code=type_for(row["label"]), start_at=start, end_at=end))
    return acts, flagged


@pytest.mark.parametrize("sheet", sheets(), ids=lambda s: s["sheet_name"])
def test_engine_reproduces_printed_sheet(sheet):
    acts, flagged = build_activities(sheet)
    is_error_sheet = sheet["sheet_name"] in KNOWN_ERROR_SHEETS

    # 1. Bad rows are caught on exactly the expected sheets, and nowhere else
    if sheet["sheet_name"] in END_BEFORE_START_SHEETS:
        assert len(flagged) == 1, f"expected exactly one flagged row, got {flagged}"
    else:
        assert flagged == []
    if sheet["sheet_name"] in OVERLAP_SHEETS:
        from domain.warnings import log_warnings

        assert any(w.code == "overlap" for w in log_warnings(acts)), (
            "engine must detect the V2602 row-17 overlap"
        )

    if not acts:
        return

    rows = sheet["rows"]
    block_rows = [
        r for r in rows
        if r["kind"] == "subtotal" and "muat - bongkar" not in (r["label"] or "").lower()
        and r["total_days"] is not None
        and not (r["label"] or "").lower().startswith("total kegiatan a")  # V2606 stray note row
    ]
    combined_rows = [
        r for r in rows if r["kind"] == "subtotal" and "muat - bongkar" in (r["label"] or "").lower()
        and r["total_days"] is not None
    ]
    grand_rows = [r for r in rows if r["kind"] == "grand_total"]

    blocks = split_port_blocks(acts).in_order

    if is_error_sheet:
        # Partial comparison: the last (discharge) block is unaffected by the bad load row
        if block_rows:
            assert block_sheet_pair(blocks[-1]) == parse_pair(
                block_rows[-1]["total_days"], block_rows[-1]["total_time"]
            ), f"discharge block mismatch on {sheet['sheet_name']}"
        return

    # 2. Every printed block subtotal (A, B, C...) matches, in order
    assert len(block_rows) <= len(blocks)
    for printed_row, block in zip(block_rows, blocks, strict=False):
        printed = parse_pair(printed_row["total_days"], printed_row["total_time"])
        assert block_sheet_pair(block) == printed, (
            f"{sheet['sheet_name']}: block '{printed_row['label']}' printed {printed}, "
            f"computed {block_sheet_pair(block)}"
        )

    # 3. Combined (A + B ...) row
    for row in combined_rows:
        assert combined_sheet_pair(acts) == parse_pair(row["total_days"], row["total_time"])

    # 4. Normalized grand total
    for row in grand_rows:
        printed = parse_pair(row["total_days"], row["total_time"])
        if printed:
            assert combined_sheet_pair(acts).normalized() == printed

    # 5. Prorata & DEMURRAGE days
    laytime = None
    if sheet["header"].get("laytime"):
        laytime = parse_laytime(sheet["header"]["laytime"])
        for r in rows:
            if r["kind"] == "laytime_contract" and r["total_days"] is not None:
                assert laytime.total_days == int(r["total_days"])
    for r in rows:
        if r["kind"] == "demurrage" and isinstance(r["total_days"], int) and laytime:
            assert demurrage_days(total_port_time(acts), laytime.total_days) == r["total_days"], (
                f"{sheet['sheet_name']}: demurrage days"
            )
