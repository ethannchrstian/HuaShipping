# 05 — Excel Import Mapping (one-time historical import)

The importer is a management command run by the developer, not a user-facing
feature: each workbook is hand-formatted and needs human review. It is built
TDD-style with golden tests: real `.xlsx` in → expected structured data out
(see `tools/dump_timesheets.py` for the proven reading approach and
`docs/reference/timesheets-raw.json` for the raw ground truth).

## Source files

| Workbook | Sheets | Voyages |
|---|---|---|
| `Time Sheet TB. HN 1 & BG. PH 2401 Tahun 2025 (1).xlsx` | 1 | V2501 |
| `Time Sheet TB. HN 1 & BG. PH 2401 Tahun 2026.xlsx` | 7 | V2601–V2607 (V2607 ongoing) |
| `Time Sheet TB. HN 2 & BG. PH 2402 Tahun 2026.xlsx` | 3 | V2601–V2603 (V2603 ongoing) |

Sheet name pattern: `HN <n> PH 240<n> Voy. V<yy><nn>` → vessel + voyage code.
Voyage code also appears in the B2 title — cross-check both, flag mismatch.

## Cell mapping

### Header block (rows 3–9, label in B, value in C)
| Excel label (B) | Field | Normalization |
|---|---|---|
| `No. Kontrak` | `voyage.contract_no` | strip leading `: ` |
| `Kwitansi Nomor` | `voyage.invoice_no` | strip leading `: ` |
| `Muatan` | parcels (see below) | parse commodity + quantity + unit, any order: `CPO 4.000 MT`, `CPO 4.000.000 KG`, `4,000 MT CPO`, `CPO 4,130 MT`; KG ÷ 1000 → MT |
| `Lokasi Muat` | load jetties | split on `&`; match/create JETTY by fuzzy name (see jetty table below) |
| `Lokasi Bongkar` | `voyage.discharge_jetty` | same matching |
| `Lama Muat/Bongkar` | `laytime_days` (+ split fields) | `12 hari` → 12; `6 Hari Muat + 6 Hari Bongkar` → 6/6/12 |
| `Demurrage` | `demurrage_rate_idr` | `-` → null; `Rp. 20,000,000/hari` / `Rp. 25.000.000` / `Rp 20.000.000/hari` → integer IDR |

### Activity table (from row 13; label B, days C, time D, from E, start-date F, start-time G, to H, end-date I, end-time J)
- Row classification: label starting `Total` → subtotal (used for **verification only**, never imported); `Prorata…` → laytime cross-check; `DEMURRAGE` → demurrage-days cross-check; unlabeled row with numbers → grand-total pair (verification); `Dibuat/Diketahui` → stop.
- Activity label → `activity_type` mapping (case/space tolerant, prefix match):

| Label prefix | type |
|---|---|
| `Perjalanan ke lokasi muat` (first, or long-distance) | `ballast` |
| `Perjalanan ke lokasi muat` (between two load jetties) | `ballast` (block delimiter — position handles it) |
| `Tunggu info sandar` (before final laden leg) | `waiting_berth_load`, else `waiting_berth_discharge` |
| `Tunggu info muat` | `waiting_load` |
| `Kegiatan Muat` | `loading` (parenthetical like `(CPO 3,000 MT)` → activity note) |
| `Tunggu info cast off` | `waiting_cast_off` |
| `Shifting` | `shifting` |
| `Perjalanan ke lokasi bongkar` | `laden` |
| `Tunggu info bongkar` | `waiting_discharge` |
| `Kegiatan bongkar` | `discharging` (note keeps consignee e.g. `PT. EUP`) |
| `Persiapan` | `preparation` |

- `start_at` = combine(F date, G time); `end_at` = combine(I date, J time); empty end (ongoing voyages V2607, HN2-V2603) → null. All times WIB → stored UTC.
- E/H (berangkat/tiba locations) → `from_location` / `to_location` on sailing legs.
- Columns C/D (typed day/time totals) are **read but only for verification** against computed durations (C1 of the calc spec); never stored.

### Charterer
Not a header field — extract from `contract_no` / `invoice_no` party segment
(`HUAT-FPS` → FPS; `FN-HUAT` → FPS per prototype seed; `HUAT-PSCOI` → PSCOI;
`HUAT-PNLF` → PNLF; `HUAT-GGU` → GGU). Ambiguous → import as null + report line.

## Known data errors (importer must FLAG, never silently fix)

| Where | Error | Handling |
|---|---|---|
| V2501 row 15 | `Tunggu info muat` ends 13:15 before it starts 14:30 (same date — end date likely should be next day) | import with `end_at` null + note `IMPORT: jam selesai tidak valid (13:15 < 14:30)`; list in import report for Felicia to confirm |
| HN1-V2604 row 15 | same class: 2026-04-06 23:30 → 17:20 | same handling |
| V2501 header | `No. Kontrak` contains an invoice number (`001/INV/HUAT-FPS/I/2026`) and it's dated 2026 on a 2025 voyage | import as-is + report line |
| V2605, V2606 | multi-day unlogged gaps between activities | import as-is; W1 warnings will show in-app |
| HN2-V2602 rows 16–17 | **found by the oracle test (2026-07-10):** row 17's start date is typo'd one day early (≈24h overlap with loading), and row 16's HARI formula `=+I16-F16` (end date − start date = midnights crossed, not elapsed days) yields 1 while the hand-typed WAKTU (18:20) already holds the row's full duration — the day is double-counted. The printed block A (7 hari) and grand total are inflated, and the **7 demurrage days derived from them are overstated** (recomputed from timestamps: fewer). The HARI/WAKTU cells are a patchwork of hand-typed values and two different formulas, each wrong in a different edge case. | import as-is; W2 overlap warning shows in-app; raised with the company as open question |
| HN2-V2603 row 14 | zero-duration tunggu sandar (10:55 → 10:55) | **not an error** — a legitimate "no waiting" row; C1 allows zero duration |
| HN1-V2606 footer | free-text note "total kegiatan A + B + C adalah 17 hari 171 jam 05 menit" | ignore (verification uses the structured rows) |

## Verification step (built into the importer)

After importing each voyage, recompute all totals per `04-calculation-spec.md`
and diff against the sheet's printed subtotal/grand-total/prorata/demurrage
rows. Output a per-voyage report: `OK` or list of mismatches. Expected result:
all 11 voyages OK except the flagged error rows above. **This single step is
the app's acceptance test against 1.5 years of real history.**

## Import report

The command writes `import-report.md`: per voyage — created records, flagged
errors, verification result. Reviewed with Felicia before the data is declared
authoritative.
