# 09 — Decision Log (ADRs)

Append-only. Newest last. Format: context → decision → consequences.

## ADR-001 · 2026-07-09 · Stack: Django + HTMX + PostgreSQL
Solo dev, equal TS/Python skill, CRUD-heavy forms-and-tables app that must run
for years with minimal maintenance. Django supplies auth, ORM, migrations,
admin, i18n out of the box; pytest gives the TDD ergonomics; HTMX covers the
modest interactivity (the prototype is tables/forms/chips). Trade-off accepted:
weaker rich-client capability than React — not needed here.
**Consequence:** revisit only if a genuinely app-like UI becomes a requirement.

## ADR-002 · 2026-07-09 · Day counts computed, never stored
The Excel stores typed day counts and contains real errors (end-before-start
rows in V2501/V2604). All durations/totals/demurrage derive from timestamps at
read time per `04-calculation-spec.md`. **Consequence:** slightly more compute
per page (trivial at this scale); zero possibility of stale totals.

## ADR-003 · 2026-07-09 · Money as integer IDR
No floats for money anywhere; IDR has no sub-unit in practice. bigint columns
(demurrage rates are 8-digit numbers × days). **Consequence:** formatting layer
renders `Rp 20.000.000`; any future non-IDR requirement forces a schema change
(accepted — company operates domestically).

## ADR-004 · 2026-07-09 · Company conventions over textbook laytime
Their laytime counting includes waiting time, excludes persiapan, and truncates
hours for demurrage days (reverse-engineered and verified against 11 real
sheets — see calc spec). The app encodes THEIR practice, because it must
reproduce documents the director signs. **Consequence:** if a charterer ever
disputes a convention, the calc spec is the single place to change + tests.

## ADR-005 · 2026-07-09 · UI Bahasa Indonesia, code English, via Django i18n
Users are non-technical Indonesians; developer works in English. All strings
through gettext from day 1 (cheap now, painful to retrofit).
**Consequence:** glossary (`01-glossary.md`) is a maintained artifact.

## ADR-006 · 2026-07-09 · PaaS first (Railway/Render SG), VPS as exit path
New solo dev + data-safety fear → managed Postgres with automatic backups beats
$5/mo savings. No PaaS-proprietary features allowed in the app.
**Consequence:** see `08-ops.md`; review cost yearly.

## ADR-007 · 2026-07-09 · Historical import is a developer-run command
Hand-formatted workbooks need judgment; errors are flagged, never auto-fixed.
Import verification doubles as the acceptance test against real history.
**Consequence:** future sheets are entered in-app, not imported; the command is
retired after go-live (kept for reference/tests).

## ADR-008 · 2026-07-09 · Timestamps stored UTC, displayed WIB
Every port in the data is UTC+7. **Consequence:** if operations ever extend to
WITA/WIT ports, add a per-activity timezone display rule — storage unaffected.

## ADR-009 · 2026-07-10 · No roles — single permission level
The company answered: office admins only, everyone may see and edit everything.
Per-user accounts remain (audit trail), plus a developer superuser. Guards
against accidents are the voyage lock + history, not permissions.
**Consequence:** no permission checks beyond login anywhere in V1; revisit only
if the company itself asks.

## ADR-010 · 2026-07-10 · Voyage costs as line items, not fixed columns
The company asked to track "stevedoring and all that stuff". Instead of adding
a column per cost type, V1.1 gets `VOYAGE_COST` line items (category + amount
IDR + note; seeded categories: stevedoring, port charges, agency, bunker,
other). `freight_idr` (revenue) and `fuel_used_liters` (operational stat) stay
as voyage columns. **Consequence:** new cost types are data, not migrations;
the exact category list is open question #3.

## ADR-011 · 2026-07-10 · Prototype is a feature reference, not a design reference
The AI one-shot prototype.html reads as AI-made (condensed display font in UI
chrome, emoji icons, uppercase micro-label scaffolding, default dashboard
grammar) and its interaction layer scored 21/40 in review. Decision: keep its
**feature set and domain ideas** (computed numbers, prefilled entry, warnings,
phase summaries, print sheet) and design a **new professional-grade visual
identity from scratch** when UI work starts, via a deliberate design pass
(DESIGN.md seeded then, not now) governed by PRODUCT.md's principles and the
binding UI rules in docs/06. **Consequence:** no CSS is copied from
prototype.html; it is used only to enumerate features.

## ADR-012 · 2026-07-10 · Load jetties derive from parcels; no duplicate list on voyage
The ERD sketched both `parcel.load_jetty` and an ordered load-jetty list on
VOYAGE, flagging the duplication for an implementation-time decision. Decision:
keep **only** `parcel.load_jetty` — every real multi-jetty voyage (HN2-V2601,
HN1-V2606) has one parcel per load jetty, so the list is fully derivable, and
two writable copies of the same fact could disagree (the exact failure mode
this system exists to remove). **Consequence:** load-jetty display order comes
from the voyage's parcels/port blocks; if a voyage ever loads one parcel across
two jetties, revisit.
