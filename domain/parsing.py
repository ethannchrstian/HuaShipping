"""C9 — normalization of the free-text formats found in the real time sheets.

All separators in the real data are thousand separators ('4.000 MT',
'4,000 MT', '4.000.000 KG'); decimals do not occur. If they ever do, extend
here with tests first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

COMMODITIES = ("CPO", "RBD Palm Olein", "RBD Palm Stearin", "CPKO", "PFAD", "Palm Kernel Expeller")


@dataclass(frozen=True)
class Cargo:
    commodity: str
    quantity_mt: int


@dataclass(frozen=True)
class Laytime:
    total_days: int
    load_days: int | None = None
    discharge_days: int | None = None


def _digits(s: str) -> int:
    return int(re.sub(r"[.,\s]", "", s))


def parse_cargo(raw: str) -> Cargo:
    """'CPO 4.000 MT' / '4,000 MT CPO' / 'CPO 4.000.000 KG' -> Cargo('CPO', 4000)."""
    m = re.search(r"([\d][\d.,]*)\s*(MT|KG)", raw, re.IGNORECASE)
    if not m:
        raise ValueError(f"cannot parse cargo: {raw!r}")
    qty = _digits(m.group(1))
    if m.group(2).upper() == "KG":
        qty //= 1000
    commodity = (raw[: m.start()] + raw[m.end() :]).strip(" .,")
    if not commodity:
        raise ValueError(f"cargo has no commodity: {raw!r}")
    return Cargo(commodity=commodity, quantity_mt=qty)


def parse_laytime(raw: str) -> Laytime:
    """'12 hari' or '6 Hari Muat + 6 Hari Bongkar' (V2501 split form)."""
    split = re.search(r"(\d+)\s*hari\s*muat\s*\+\s*(\d+)\s*hari\s*bongkar", raw, re.IGNORECASE)
    if split:
        load, discharge = int(split.group(1)), int(split.group(2))
        return Laytime(total_days=load + discharge, load_days=load, discharge_days=discharge)
    m = re.search(r"(\d+)\s*hari", raw, re.IGNORECASE)
    if not m:
        raise ValueError(f"cannot parse laytime: {raw!r}")
    return Laytime(total_days=int(m.group(1)))


def parse_demurrage_rate(raw: str | None) -> int | None:
    """'Rp. 20,000,000/hari' -> 20000000; '-' -> None (no demurrage clause)."""
    if raw is None or raw.strip(" -.") == "":
        return None
    m = re.search(r"Rp\.?\s*([\d][\d.,]*)", raw, re.IGNORECASE)
    if not m:
        raise ValueError(f"cannot parse demurrage rate: {raw!r}")
    return _digits(m.group(1))
