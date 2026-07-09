# 07 — Test Plan (TDD)

Correctness is the product. Order of battle: write the failing test, make it
pass, refactor. No domain logic gets written without a test that demanded it.

## Architecture for testability

```
domain/          pure Python: durations, blocks, totals, laytime, demurrage,
                 warnings, unit parsing. NO Django imports. Fast tests.
apps/*/models.py thin persistence + DB constraints
apps/*/views.py  thin: parse request → call domain → render
importer/        management command built on domain + golden files
```

## Test layers

### L1 — Domain unit tests (the bulk; run in milliseconds)
One test module per calc-spec rule: `test_c1_duration.py` … `test_c9_units.py`.
- Every worked example in `04-calculation-spec.md` is a test case with the real numbers (V2601 A=19/41:00, grand 27d05:53; V2605 demurrage 3; V2606 17; V2602 7; V2501 0…)
- Edge cases: ongoing activity, single-activity voyage, voyage with no laden leg yet, zero-length gap tolerance (±2 min), month/year boundaries, KG↔MT, all three demurrage-rate string formats
- Property-based tests (hypothesis) for invariants: Σ block durations ≤ voyage duration; demurrage_days ≥ 0; parsing is total (any string → value or explicit error, never exception)

### L2 — Excel-as-oracle golden tests
The real workbooks are **kept locally only, never committed** (gitignored;
real business documents). The committed `docs/reference/timesheets-raw.json`
carries the extracted ground truth for tests; tests needing the raw `.xlsx`
skip with a clear message when the files are absent. Test: parse each of the
11 voyages → run domain calculations → assert equality with the sheets'
printed subtotal/grand/prorata/demurrage rows, *except* the enumerated
known-error rows (`05-import-mapping.md`), which must instead produce flags.
**1.5 years of real history as a regression suite.**

### L3 — Model & validation tests (pytest-django, DB)
DB constraints actually reject bad data (end ≤ start raises IntegrityError;
duplicate voyage code per vessel; FK PROTECT). Locking behavior: locked voyage
rejects writes; unlock writes audit entry.

### L4 — View tests (pytest-django client)
Per screen: auth required; list filters; create/edit happy path + validation
errors render in Indonesian; CSV export content-type and delimiter; permissions
(viewer cannot POST).

### L5 — End-to-end smoke (Playwright, ~5 flows, run pre-deploy)
1. Login → create voyage → add 3 activities → totals correct on detail page
2. Enter end-before-start → see the Indonesian error, nothing saved
3. Leave a 2-day gap → warning strip appears
4. Complete + lock a voyage → edit attempt blocked → unlock → audit entry visible
5. Export voyage list CSV → file downloads and parses

## CI gate (GitHub Actions)
On every push: ruff (lint) → mypy (domain/ at least) → L1–L4 → `manage.py
check --deploy` → `manage.py makemigrations --check` (no drifting migrations).
Playwright on main before deploy. A red build never deploys.

## Definition of done (per feature)
Failing test first · Indonesian UI strings via i18n (no hardcoded English) ·
validation shows a human message · covered in CSV export if it's list data ·
audit history verified for writes.
