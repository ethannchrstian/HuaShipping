# HuaShipping — Voyage Tracking System

Voyage-tracking web app for **PT Hua Shipping Agro Trans**: palm-oil (CPO) shipping
between Indonesian ports with tugboat + barge sets. Replaces per-vessel Excel
"Time Sheets" with a shared database, computed day counts, and laytime/demurrage
tracking, for a ~10-person admin team.

> **PRIVATE DATA — this repository contains real business data (contracts,
> invoices, rates) in the Excel files and `docs/reference/`. Keep it private.**

## Status

Calculation engine complete (65 tests green; oracle test reproduces all 11 real
voyages' printed totals). Next: Django models + historical importer, then the
first screens.

**New here? Start with [`docs/00-overview.md`](docs/00-overview.md)** — it
explains everything built so far and how it works.

## Layout

| Path | What |
|---|---|
| `docs/00-overview.md` | **Start here** — master explanation of the project so far |
| `docs/01…10-*.md` | Planning documents (glossary → ERD → calc spec → … → open questions) |
| `domain/` | The calculation engine — pure Python, no Django (model, calculations, warnings, parsing) |
| `tests/domain/` | Unit tests + the Excel-as-oracle golden test |
| `docs/reference/timesheets-raw.json` | Faithful dump of all real voyage sheets (ground truth for specs & oracle tests) |
| `tools/dump_timesheets.py` | Script that produces the dump from the `.xlsx` files |
| `Time Sheet *.xlsx` | The company's real time sheets — **local only, gitignored, never committed** |

## Stack (decided)

Django 5.x + HTMX · PostgreSQL · pytest (TDD, correctness first) ·
UI in Bahasa Indonesia, code/docs in English · PaaS hosting (Railway/Render,
Singapore region) with managed Postgres backups.

Full rationale and architecture: see `docs/09-decisions.md` and the docs folder generally.
