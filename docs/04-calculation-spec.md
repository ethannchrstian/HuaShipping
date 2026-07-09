# 04 — Calculation Specification (the correctness document)

Every number the app derives is defined here with formula, rounding rule, and a
worked example from the **real** sheets (`docs/reference/timesheets-raw.json`).
This file doubles as the unit-test specification: each numbered rule becomes at
least one test in `domain/`. If the app and this spec ever disagree, one of them
has a bug — fix before shipping.

Conventions were **reverse-engineered from the 11 real sheets and verified
against their printed totals** — they encode the company's own practice, which
differs from textbook laytime (their waiting time counts fully).

## C1. Activity duration

`duration = end_at − start_at` (exact minutes internally; never rounded for storage).

- Display: `<whole days>d HH:MM` (e.g. `4d 15:00`).
- Ongoing activity (`end_at` null): duration computed against "now", displayed with an "ongoing" marker; excluded from completed-voyage totals.
- **Zero duration is legal** — a "no waiting" row; real case HN2-V2603 row 14 (tunggu sandar 10:55 → 10:55).
- **Validation (block):** `end_at < start_at` is rejected. Real error cases that must fail: HN1-V2604 `waiting_load` (2026-04-06 23:30 → 2026-04-06 17:20), V2501 row 15 (14:30 → 13:15 same date).

Worked example (V2601 ballast): 2026-01-04 23:30 → 2026-01-09 14:30 = **4d 15:00** ✓ matches sheet (HARI=4, WAKTU=15:00).

## C2. Port-block segmentation

Sort a voyage's activities by `start_at`. **Sailing activities** (`ballast`,
`laden`, `shifting`) delimit blocks:

- A **port block** = maximal run of consecutive non-sailing activities.
- Blocks that occur **before the final `laden` leg** are **load blocks** (A, B, … in sheet order).
- Blocks **after the final `laden` leg** are **discharge blocks**.
- `preparation` (persiapan) activities are **excluded from port-time totals** (verified: V2601 block B prints 1d 12:53 = waiting 6:15 + 6:45 + discharge 23:53, persiapan 19:07 excluded) but still displayed in the timeline.

Verified against HN2-V2601 (two load jetties → blocks A, B, then discharge C) and
HN1-V2606 (`shifting` as the delimiter between load blocks).

## C3. Port-block subtotal ("Total Kegiatan Muat (A)" etc.)

`block_port_time = Σ duration(activity)` over the block's non-PREP activities.

- Display in the sheet's columnar style: sum of whole-day parts, plus sum of HH:MM parts (which may exceed 24h) — normalization happens only at the grand total. The app may display normalized (`20d 17:00`) with the sheet-style pair available for the printed time sheet.
- Intra-block **gaps** (next.start ≠ prev.end) are NOT silently added; they trigger a warning (C7) so the operator fixes the log. (In all 11 real sheets, in-block rows are contiguous.)

Worked example (V2601, load block A): waiting_berth 11d 17:50 + waiting_load 1d 01:10 + loading 6d 06:20 + waiting_cast_off 1d 15:40 = day-parts 19, time-parts 41:00 → sheet prints **A = 19 hari / 1d 17:00** ✓; normalized = **20d 17:00**.

## C4. Total port time (grand total, "Total Kegiatan Muat - Bongkar")

`total_port_time = Σ block_port_time` over all load + discharge blocks.

Worked example (V2601): A (19 / 41:00) + B (5 / 36:53) → 24 days + 77:53 → normalized **27d 05:53** ✓ matches the sheet's final pair (27, 05:53).

## C5. Laytime comparison & demurrage days

- `laytime_days` from the contract; when the contract splits it ("6 Hari Muat + 6 Hari Bongkar"), the split values are stored but the comparison uses the **sum** (verified: V2501 prints prorata **12**). *(Open question #5: should the app also compare per-side? Parked until the friend answers.)*
- `overrun_days = floor_to_whole_days(total_port_time) − laytime_days`
- `demurrage_days = max(0, overrun_days)` — **whole days; leftover hours are truncated** (company convention, verified 3×):

| Voyage | total_port_time | laytime | sheet DEMURRAGE | formula check |
|---|---|---|---|---|
| HN1-V2605 | 13d 19:30 | 10 | **3** | floor(13) − 10 = 3 ✓ |
| HN1-V2606 | 24d 03:05 | 7 | **17** | 24 − 7 = 17 ✓ |
| HN2-V2602 | 21d 20:00 | 14 | **7** | 21 − 14 = 7 ✓ |
| V2501 | 11d 08:35 | 12 (6+6) | **0** | max(0, 11−12) = 0 ✓ |
| HN1-V2601 | 27d 05:53 | 12 | "-" | rate absent → no claim (C6) |

## C6. Demurrage amount (V1.1)

`demurrage_amount_idr = demurrage_days × demurrage_rate_idr` — only when the
voyage has a rate; otherwise display "-" (no demurrage clause). Integer rupiah,
no rounding needed. Labeled **estimate** in the UI; a human reviews before any
claim/invoice leaves the company.

Worked example (V2605): 3 × 20,000,000 = **Rp 60,000,000**.

## C7. Warnings (computed on read, never blocking saves except C1)

| Code | Condition | Message (ID) |
|---|---|---|
| W1 | gap > 30 min between consecutive activities | "Ada waktu tidak tercatat (X jam) antara …" |
| W2 | overlap: `next.start_at < prev.end_at` | "Kegiatan tumpang tindih" |
| W3 | `total_port_time > laytime` on ongoing voyage | "Waktu di pelabuhan sudah melewati prorata kontrak" |
| W4 | first activity of a voyage starts before the previous voyage's last activity ends (same vessel) | "Voyage bertumpuk dengan voyage sebelumnya" |
| W5 | voyage marked COMPLETED with an activity missing `end_at` | "Masih ada kegiatan berjalan" |

Real cases the tests must flag: V2605 has a ~2-day unlogged gap (2026-04-29
07:00 → laden starts 2026-05-01 08:30); V2606 has multi-day gaps around the
second load jetty.

## C8. Whole-voyage stats (app-only, not on the printed sheet)

- `voyage_duration = last end_at − first start_at`
- Per-phase totals: Σ duration grouped by activity phase (BALLAST / WAITING_LOAD / LOAD / LADEN / WAITING_DISCHARGE / DISCHARGE / PREP) — feeds the V2 analytics ("how much time do we lose waiting?").
- Decimal-day displays for analytics: round **half-up to 1 decimal** at display time only.

## C9. Unit normalization (import & forms)

- Cargo quantity: stored MT with 3 decimals. `4.000 MT` (ID thousand-dot) = `4,000 MT` (EN thousand-comma) = `4000`; `4.000.000 KG` → ÷1000 → `4000`. Order variants parsed too (`4,000 MT CPO` vs `CPO 4,000 MT`).
- Demurrage rate: `Rp. 20,000,000/hari`, `Rp. 25.000.000`, `Rp 20.000.000/hari` all → `20000000` / `25000000` integer IDR per day.
- Laytime: `12 hari` → 12; `6 Hari Muat + 6 Hari Bongkar` → load 6, discharge 6, total 12.

## Test oracle

For each of the 11 real voyages, the domain functions fed the imported
activities must reproduce the sheet's printed values exactly: each block's
(day-parts, time-parts) pair, the grand-total pair, prorata, and DEMURRAGE
days. Known exceptions (sheet errors the app must instead *flag*): the
end-before-start rows in V2501 and HN1-V2604. Any other mismatch = bug until
proven otherwise.
