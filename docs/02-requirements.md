# 02 — Requirements

## Problem

PT Hua Shipping Agro Trans tracks voyages in per-vessel, per-year Excel workbooks
(one sheet per voyage) passed around by WhatsApp. Consequences observed in the
real files: data-entry errors (activities ending before they start, an invoice
number typed into the contract field), inconsistent formats (MT vs KG, `4.000`
vs `4,000`, "12 hari" vs "6 Hari Muat + 6 Hari Bongkar"), no single source of
truth, and no history/search across voyages. Day totals and demurrage are
computed by fragile spreadsheet formulas.

## Goal

One shared web app where the operations team logs voyage activities with
timestamps and the system computes every derived number (day counts, laytime
comparison, demurrage) correctly, with an audit trail, search, and Excel export.

## Actors

| Actor | Today | Needs |
|---|---|---|
| **Operations admin** ("Operasional", e.g. Felicia) | Types time sheets in Excel from info relayed off the vessels | Fast, forgiving data entry; warnings when something is inconsistent; print/export |
| **Director** ("Direktur Utama") | Signs printed sheets, asks for recaps | Read-only overview: which vessel is where, voyage history, days & money summaries |
| **Other admin staff** (~10 total) | Share/read the Excels | Look up voyages without asking around |
| **Developer (Ethan)** | — | Maintainable solo; safe deploys; recoverable data |

Role model for V1: `staff` (read/write) and `viewer` (read-only). Money-field
visibility restrictions are an open question (see 10-questions.md #6) — the data
model must not preclude a later `finance` role.

## User stories

### V1 — core (build first)

| # | Story | Acceptance criteria |
|---|---|---|
| 1.1 | As staff, I sign in with my own account | Django auth; per-user accounts; no shared logins; session over HTTPS only |
| 1.2 | As staff, I manage master data (vessels, jetties, charterers) | CRUD; jetty has name + port; deletion blocked if referenced |
| 1.3 | As staff, I create a voyage (code, vessel, charterer, contract no, invoice no, load jetty/jetties, discharge jetty, laytime, demurrage rate, cargo parcels) | Voyage code unique per vessel; ≥1 load jetty; parcels have commodity + MT + jetty + optional shipper; laytime may be combined or split (load+discharge) |
| 1.4 | As staff, I log activities on a voyage (type, start, end, note, locations for sailing legs) | End optional while ongoing; **reject end ≤ start**; warn on overlap with existing activities; warn on gap > 30 min from previous activity |
| 1.5 | As anyone, I see computed durations and totals — never type them | Per-activity duration, muat/bongkar block subtotals, grand total, laytime comparison; all per `04-calculation-spec.md`; recomputed on read |
| 1.6 | As anyone, I browse/search voyages | Filter by vessel, status, charterer, year; free-text over code/contract/invoice/jetty; sortable columns |
| 1.7 | As anyone, I open a voyage detail | Header info, activity timeline with warnings, day-count summary, parcels |
| 1.8 | As staff, I mark a voyage completed, which locks it | Locked voyages are read-only; unlocking requires confirmation and is written to the audit log |
| 1.9 | As anyone, I export any list/detail to CSV/Excel | Voyage list and voyage detail (activities) export; opens correctly in Excel (UTF-8 BOM, `;` or locale handling decided in implementation) |
| 1.10 | As the developer, I import all historical voyages once | Importer per `05-import-mapping.md`; flags (not fixes) known data errors; app launches with full history |
| 1.11 | As anyone, I use the app in Indonesian on PC or phone | All UI strings Indonesian; responsive layout |

### V1.1 — money layer

| # | Story | Acceptance criteria |
|---|---|---|
| 2.1 | As staff, I record freight, bunker price, fuel used per voyage | Money as integer IDR; blank ≠ zero |
| 2.2 | As anyone, I see laytime overrun and demurrage estimate | Per calc spec: whole-day overrun × rate; only when rate present; clearly labeled *estimate* |
| 2.3 | As staff, I print a voyage time sheet | Print layout matching the current Excel sheet incl. signature block (Dibuat/Diketahui) |
| 2.4 | As the director, I see a per-voyage money recap | Freight vs bunker cost vs demurrage, per vessel/period |

### V2 — later (parked)

Analytics dashboard (waiting-time trends, utilization), invoice document
generation, monthly recap reports, notifications, finance role separation,
charterer portal (never?), AIS position integration (never?).

## Non-functional requirements

- **Correctness before features**: every derived number specified in
  `04-calculation-spec.md` and covered by tests before UI polish (TDD).
- **Auditability**: every write records who/when; history retained (django-simple-history).
- **Availability**: office hours matter; brief maintenance windows fine. 10 concurrent users max.
- **Durability**: nightly automated DB backups off the app host; restore procedure tested (see 08-ops.md).
- **Usability**: users are non-technical; forms must be forgiving (date pickers, sensible defaults like "start = previous activity's end"), warnings in plain Indonesian.
- **Security**: HTTPS only, Django deploy checklist enforced in CI, per-user accounts.
- **Portability**: no PaaS-proprietary features; standard Django + Postgres.
- **Data ownership**: CSV/Excel export everywhere; the company can always get their data out.
