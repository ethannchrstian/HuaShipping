# 00 — Project Overview: what has been built, and how

**Read this document first.** It explains everything that exists in this repo so far,
why it exists, and how it works — written to be understandable without prior context.
Each section links to the detailed document it summarizes.

---

## 1. The problem we're solving

PT Hua Shipping Agro Trans ships palm oil (CPO) between Indonesian ports using
tugboat + barge pairs (e.g. "TB HUA Navigator 1" + "BG Palm Hero 2401"). For every
voyage, the office keeps a **Time Sheet** in Excel: a log of timestamped activities
(sailing, waiting, loading, discharging) from which they compute how long the vessel
spent in port — because port time is money:

- The contract gives the charterer a number of allowed days in port (**laytime**,
  e.g. "12 hari").
- If the vessel is held longer, each extra day is billed (**demurrage**, e.g.
  Rp 20.000.000/day).

Today ~10 admin staff maintain these sheets by hand: one workbook per vessel per
year, one sheet per voyage, all durations typed manually. Typed numbers drift from
their own timestamps — we found real errors in the sheets (see §8). We're replacing
this with a small web app where **staff enter only timestamps and the software
computes every number**.

## 2. The roadmap, and where we are

The project follows a deliberate order (correctness first, screens last):

| Phase | What | Status |
|---|---|---|
| 1 | Planning documents (`docs/01`–`10`) | ✅ done |
| 2 | Extract the real Excel data into machine-readable ground truth | ✅ done |
| 3 | **Calculation engine** — pure Python, test-driven, proven against all 11 real voyages | ✅ done (65 tests green) |
| 4 | Database models + one-time importer for the historical voyages | ⬜ next |
| 5 | First screens (voyage list, voyage detail, activity entry), fresh design | ⬜ |
| 6 | Deploy + pilot in parallel with Excel | ⬜ |

The unusual choice — building the math before the database or any screen — is
deliberate: the calculations are the part that "messes up the finances" if wrong,
so they were built first, alone, where they're easiest to test (§5).

## 3. Map of the repository

```
docs/                         Planning documents 01–10 (see §4)
docs/reference/
  timesheets-raw.json         Faithful dump of all 11 real voyage sheets — the "ground truth"
tools/
  dump_timesheets.py          Script that produced that dump from the Excel files
domain/                       ★ The calculation engine (pure Python, no Django) — see §5–6
  model.py                    What an "activity" is; the 11 activity types
  calculations.py             All the math: durations, port blocks, totals, demurrage
  warnings.py                 Gap/overlap detection in an activity log
  parsing.py                  Turning header strings ("CPO 4.000 MT", "Rp. 20,000,000/hari") into numbers
tests/domain/                 The tests that prove the engine correct — see §7
config/, manage.py            Django project skeleton (settings only; no app code yet)
.github/workflows/ci.yml      CI: every push runs lint (ruff) + all tests automatically
PRODUCT.md                    Product strategy: who the users are, design principles
Time Sheet *.xlsx, *.jpeg     Real business files — local only, gitignored, never committed
```

## 4. Phase 1 — the planning documents

Before writing code, ten documents were written so every later decision has a
source of truth. One line each:

| Doc | What it is |
|---|---|
| `01-glossary.md` | Indonesian domain terms ↔ English code names (muat=load, bongkar=discharge, sandar=berth…) |
| `02-requirements.md` | User stories with acceptance criteria, scoped V1 / V1.1 / V2 |
| `03-erd.md` | Database design (entities: Vessel, Jetty, Charterer, Voyage, Parcel, Activity) + a data dictionary with real examples |
| `04-calculation-spec.md` | **The correctness bible.** Every computed number defined as a rule C1–C9 with worked examples from real voyages |
| `05-import-mapping.md` | Exactly which Excel cell maps to which field, plus every known error in the historical data |
| `06-screens.md` | Screen inventory + binding UI rules (no icon-only buttons, inline batch entry, 16px type…) |
| `07-test-plan.md` | The testing strategy this repo follows (unit tests → oracle test → view tests) |
| `08-ops.md` | Hosting, backups, Django security checklist |
| `09-decisions.md` | ADR log — every architectural decision with its rationale (see §9) |
| `10-questions.md` | Short list of open questions for the company |

**Why docs first?** Because the hardest part of this project isn't code — it's
correctly understanding *their* conventions. Example: the industry standard says
some waiting time doesn't count toward laytime; this company counts **all**
waiting but excludes "persiapan" (preparation). Getting that wrong in code would
silently produce wrong demurrage bills. The spec pins it down before any code
depends on it.

## 5. Phase 2 — turning the Excel files into ground truth

`tools/dump_timesheets.py` reads the three real workbooks (using the `openpyxl`
library) and writes everything — headers, every activity row, every printed
subtotal — into one JSON file: `docs/reference/timesheets-raw.json`.

Why this matters:

- The `.xlsx` files contain contracts and rates, so they stay **out of git**; the
  JSON dump is the committed, reviewable ground truth derived from them.
- That JSON is the input to the most important test in the repo (the *oracle
  test*, §7): "given the real timestamps, does our engine reproduce the totals
  printed on the real sheets?"

## 6. Phase 3 — the calculation engine (`domain/`)

This is the heart of what's been built. Concepts first, then the pieces.

### 6.1 Why "pure" Python with no Django

`domain/` imports nothing from Django or any database. It's plain functions:
data in → numbers out. Two reasons:

1. **Testability.** A function like `demurrage_days(port_time, laytime)` can be
   tested in a millisecond with no database or web server. All 65 tests run in
   about a second, so they get run constantly.
2. **Separation of concerns.** Django's job (later) is storing and displaying
   data. Math lives here. If we ever changed frameworks, the math — the part
   that must never break — moves along untouched.

This is often called the *functional core / imperative shell* pattern.

### 6.2 The data model (`model.py`)

An **Activity** is one row of a time sheet: a type, a start timestamp, and an
optional end timestamp (ongoing activities have no end yet):

```python
Activity(type_code="loading", start_at=datetime(2026, 1, 12, 8, 0), end_at=None)
```

It's a *frozen dataclass* — Python for "a record whose fields can never be
modified after creation." Immutability means no function can accidentally alter
an activity while computing with it; to change something you build a new one.
Validation lives in the constructor, so an invalid Activity (e.g. end before
start) **cannot exist** — bad data is rejected at the border, not checked
everywhere it might appear.

There are 11 **activity types** (the same ones the Excel sheets use): sailing
legs (`ballast` = empty toward the load port, `laden` = full toward the discharge
port, `shifting`), five kinds of waiting, `loading`, `discharging`, and
`preparation`. Each type carries flags the math needs, e.g. `is_sailing=True`.

### 6.3 The calculation rules (`calculations.py`)

Every rule has a number (C1, C2, …) matching `docs/04-calculation-spec.md`, and
every rule has tests using real voyage data.

**C1 — Duration** of one activity = `end − start`. Zero duration is legal (a
real sheet has a "waited 0 minutes" row); end before start is an error.

**C2 — Port blocks.** A voyage's activity log is one long list, but the sheet
totals it in blocks: "Total Muat (A)" for time at the loading port, "Total
Bongkar (B)" at the discharge port. `split_port_blocks()` recovers those blocks
from the list using one observation: **sailing legs are the separators.**
Everything between sailing legs is one port block; blocks before the final
`laden` leg are load blocks, blocks after it are discharge blocks. This handles
the tricky real case where a voyage loads at *two* jetties (blocks A and B) with
a sailing leg between them.

**C3/C4 — Totals the way the sheet prints them.** This is the strangest and
most important part. The Excel sheet writes each activity's duration in **two
columns**: whole days ("HARI") and leftover hours:minutes ("WAKTU"). An activity
lasting 2 days 6 h 15 m appears as `2 | 6:15`. When the sheet totals a block, it
sums each column **separately** — and never carries hours into days until the
very end. So a block can legitimately print as:

```
Total Muat (A):  19 | 1d 17:00     ← the WAKTU column summed past 24h and nobody carried it
```

The engine models this with a `SheetPair(days, time)` value that mirrors the two
columns, plus a `.normalized()` step used only at the grand total, where
`24 | 3d 5:53` finally becomes `27 | 5:53` — i.e. **27 days 5 h 53 m**, exactly
what voyage V2601's sheet prints. Why imitate a quirky convention instead of
just summing durations? Because the final totals are equal either way, but the
*intermediate printed rows* are not — and matching the printed paper
character-for-character is how we prove, and how the staff can *see*, that the
app agrees with 1.5 years of documents they trust. Two more of their conventions
are encoded here: `preparation` time never counts, and ongoing (no-end)
activities are excluded until finished.

**C5/C6 — Demurrage.** `total port time` (load + discharge blocks combined,
normalized) minus laytime, in **whole days with leftover hours dropped**
(their convention — 27d 5:53 against 12 days laytime = 15 demurrage days, not
15.25). Multiply by the contract's daily rate for the amount. Money is handled
as **integer rupiah** — never floating-point, because floats can't represent
amounts exactly (the classic finance bug: `0.1 + 0.2 ≠ 0.3` in floats).

**C7 — Warnings (`warnings.py`).** A correct log is continuous: each activity
starts when the previous one ended. The engine flags a **gap** (more than 30
minutes unaccounted for) or an **overlap** (next activity starts before the
previous ended). These are warnings, not errors — real operations have gaps —
but they catch exactly the kind of typo described in §8.

**C9 — Parsing (`parsing.py`).** The Excel headers are typed free text in
several inconsistent formats. Small parsers normalize them:
`"CPO 4.000 MT"` / `"4,000 MT CPO"` / `"CPO 4.000.000 KG"` → 4000 MT of CPO;
`"6 Hari Muat + 6 Hari Bongkar"` → laytime 12 (split 6/6);
`"Rp. 20,000,000/hari"` → 20 000 000; `"-"` → no demurrage rate.

## 7. How it was tested (this is the part worth learning)

The whole engine was built with **TDD — test-driven development**:

1. **Red** — write a small test asserting what the code *should* do, run it,
   watch it fail (proves the test actually tests something).
2. **Green** — write the minimum code to pass it.
3. **Refactor** — clean up with the tests as a safety net.

Two things make the tests here stronger than typical:

**Real numbers, not invented ones.** Every unit test in `tests/domain/` uses
verbatim data from the real sheets. Example from `test_c3_c4_totals.py`: voyage
V2601's load block must equal `SheetPair(19, 1d 17:00)` — the exact pair printed
on the company's paper.

**The oracle test** (`test_oracle_timesheets.py`) — the acceptance test for the
whole engine. An "oracle" in testing is an independent source of correct
answers; here the oracle is the company's own Excel output. The test replays
**all 11 real voyages** from `timesheets-raw.json` through the engine and
asserts every printed number matches: each block subtotal, the combined row, the
normalized grand total, the laytime cross-check, and the demurrage days. One
test function runs 11 times (pytest's `parametrize` feature), once per voyage.

The rule when the oracle disagrees: **the engine is wrong until proven
otherwise.** Both kinds happened:

- Voyage HN2-V2603 has a `10:55 → 10:55` row. The engine rejected zero-duration
  activities; investigation showed it's a legitimate "no waiting" entry → the
  engine's rule was relaxed. *The sheet was right.*
- Voyage HN2-V2602 wouldn't match either — and this time the **sheet** was
  wrong (§8).

Every push to GitHub re-runs all 65 tests plus a linter (ruff) via GitHub
Actions (`.github/workflows/ci.yml`), so a regression can't land unnoticed.

## 8. What the tests already caught: the V2602 discovery

While making the oracle pass, the engine refused to reproduce HN2 voyage
V2602's printed load total (we computed 6 days where the sheet prints 7).
Manual inspection proved the *sheet* is wrong: one row's start date is typo'd a
day early (creating a ~24-hour overlap with the loading activity — exactly what
the C7 overlap warning flags), and another row's typed day-count contradicts its
own timestamps. Those errors inflate the printed total — and the **7 demurrage
days billed from it at Rp 15.000.000/day are overstated**.

That's potentially tens of millions of rupiah on one voyage, found by an
automated check before the app has a single screen. It's recorded in
`docs/05-import-mapping.md` (known errors) and raised as question #5 in
`docs/10-questions.md`. It is also the entire pitch for this project in one
example: *computed-from-timestamps can't drift; hand-typed numbers can.*

## 9. Key decisions and why (full log: `docs/09-decisions.md`)

| Decision | Why |
|---|---|
| Django + HTMX + PostgreSQL (ADR-001) | Boring, battle-tested, batteries included (auth, admin, migrations); HTMX keeps the frontend simple for a solo dev |
| **Computed, never stored** (ADR-002) | Day counts / totals / demurrage are always recalculated from timestamps on display. Nothing to get out of sync — the V2602 error class becomes impossible |
| Money as integer IDR (ADR-003) | No floating-point money, ever |
| Company's own laytime convention (ADR-004) | Waiting counts, persiapan doesn't, hours truncate — reverse-engineered from and verified against all 11 sheets |
| UI in Bahasa Indonesia, code in English (ADR-005) | Users are Indonesian admins; code stays conventional |
| No roles (ADR-009) | Company said so: every office admin sees everything |
| Prototype = feature reference only (ADR-011) | `prototype.html` (an AI one-shot) defines *what* features exist, not how anything looks; visual design is done fresh at UI-build time |

## 10. What happens next

**Phase 4:** Django models per `docs/03-erd.md` — the database tables, with
constraints so invalid data physically can't be stored — then the one-time
importer (`docs/05`) that loads all 11 historical voyages and re-verifies every
total against the printed sheets. **Phase 5:** the first screens. From that
point on, the app shows real company history on day one.
