# HuaShipping — Voyage Tracking System

Voyage-tracking web app for **PT Hua Shipping Agro Trans**: palm-oil (CPO) shipping
between Indonesian ports with tugboat + barge sets. Replaces per-vessel Excel
"Time Sheets" with a shared database, computed day counts, and laytime/demurrage
tracking, for a ~10-person admin team.

> **PRIVATE DATA — this repository contains real business data (contracts,
> invoices, rates) in the Excel files and `docs/reference/`. Keep it private.**

## Status

Planning phase — no application code yet. The planning documents in `docs/`
are the current deliverable; code starts only after they're reviewed.

## Layout

| Path | What |
|---|---|
| `docs/01…10-*.md` | Planning documents (glossary → ERD → calc spec → … → open questions) |
| `docs/reference/timesheets-raw.json` | Faithful dump of all real voyage sheets (ground truth for specs & oracle tests) |
| `tools/dump_timesheets.py` | Script that produces the dump from the `.xlsx` files |
| `Time Sheet *.xlsx` | The company's real time sheets — **local only, gitignored, never committed** |
| `prototype.html` | Early throwaway mock — feature reference only, not a design reference (ADR-011) |

## Stack (decided)

Django 5.x + HTMX · PostgreSQL · pytest (TDD, correctness first) ·
UI in Bahasa Indonesia, code/docs in English · PaaS hosting (Railway/Render,
Singapore region) with managed Postgres backups.

Full rationale and architecture: see `docs/09-decisions.md` and the docs folder generally.
