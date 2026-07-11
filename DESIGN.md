# DESIGN — Visual identity (v6)

Governed by PRODUCT.md ("tenang, jelas, terpercaya") and the binding UI rules
in docs/06-screens.md. prototype.html remains an anti-reference.

**v4 (2026-07-11):** rebuilt on Tailwind CSS against an owner-supplied
reference mockup (`inspo.png`, local only), deliberately *not* copied 1:1 —
see "Deviations" below. Brand navy is sampled from the company logo.
Standing rule: **no styling ships without being looked at** — screenshot via
Playwright (`scratchpad/shoot.py` flow), inspect, iterate.

**v5 (2026-07-11, enterprise pass):** dashboard widened to a 1600px
operations layout with uppercase section headers (Voyage aktif / Pusat
tindakan / KPI operasional / Semua voyage); greeting replaced by a functional
header (title, date, "Data terakhir diubah" from the audit trail, quick
actions); action center = priority cards with severity chips + "Buka V26xx"
buttons; KPI cards get colored icon tiles + trend arrows vs last year (color
follows meaning: red ↑ demurrage, green ↑ tonnage); filters expanded
(pencharter, pelabuhan/jetty, date range) and swap **only the table** via
self-hosted HTMX (`hx-select` on the same URL — no partial templates, URL
stays shareable); table rows fully clickable with the code link kept for
keyboard. Other screens stay at 1160px via the `container` template block.

**v6 (2026-07-11, exampleUI.png rebuild):** dashboard remade to the owner's
target mock with honest data substitutions (no invented ETAs/expiries —
"Dimulai N hari lalu", real alert types, phase-based Progres %, vs-tahun-lalu
deltas). Voyage aktif = one container card with two inner voyage cards (ship
illustration `ship.png`, phase chip, pin-to-pin route, dot tracker on a line,
4-cell fact grid, bottom-pinned footer; incomplete data = one amber
"Lengkapi" line). Pusat tindakan = tinted severity rows with action buttons.
KPI cards with colored icon tiles + arrows. Filter bar single-row w/ grouped
date-range control and "Hapus saringan (n)". Table: dot + code + phase %,
two-line KONTRAK column, "Sesuai kontrak / Lebih N hari" chips, chevron rows,
elided pagination + rows-per-page. Ekspor CSV button (real endpoint
/ekspor.csv, filter-aware, UTF-8 BOM for Excel). Lesson enforced: **primary
screenshot judgment width is 1920 full-page**; the v5 dead zone shipped
because review stopped at 1536.

## Build (Tailwind v4, standalone CLI — no Node)

- Source of truth: `voyages/static/voyages/src/app.tailwind.css`
  (`@theme` tokens + small `@layer components`). Templates carry utilities.
- Built output `voyages/static/voyages/app.css` is **committed**; deploys and
  CI never need the CLI.
- CLI: `tools/tailwindcss.exe` (gitignored). Download:
  <https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-windows-x64.exe>
- Rebuild once:
  `tools\tailwindcss.exe -i voyages\static\voyages\src\app.tailwind.css -o voyages\static\voyages\app.css --minify`
- While designing: `dev css` (watch mode) alongside `dev`.

## Feel

A calm, confident operations dashboard: brand-navy sidebar with the company
logo on a white tile, white cards on a cool canvas, one action blue, statuses
in emerald/amber/red always paired with Indonesian words. Numbers are the
heroes; the signature element is each vessel card's **route line** with a
sailboat marker positioned by voyage phase.

## Tokens (in `@theme`)

| Token | Value | Use |
|---|---|---|
| `--color-brand` | `#13264b` | sidebar — exact navy sampled from Logo-Ori.png |
| `--color-canvas` | `#f0f3f8` | page background |
| `--color-card` / `--color-line` / `--color-line-soft` | `#ffffff / #e4e7ee / #edf0f5` | surfaces and edges |
| `--color-ink / -soft / -faint` | `#1b2733 / #667085 / #98a2b3` | text tiers |
| `--color-action / -deep / -tint` | `#1d4ed8 / #1e40af / #eff4ff` | buttons, links, current-phase |
| `--color-ok-* / live-* / info-* / bad-*` | Untitled-UI-style tints | Selesai / Berlangsung / Berjalan / over-contract & errors |

Type: self-hosted InterVariable, base 16px, `tabular-nums` wherever numbers
align. Icons: **Lucide**, inline SVG, monochrome, always beside text.

## Deviations from the inspo (deliberate)

- No pastel icon-circle rainbow — icon tiles are neutral; color stays semantic.
- No fake "Progress 82%" — progress is always real numbers (hari / kontrak).
- No icon-only actions (eye/kebab) — text links ("Lihat", "Ubah") per rule 1.
- 2 hero vessel cards (the company has 2 vessel sets), not 3 small ones.
- Alerts panel ("Perlu perhatian") derives from real data: over-contract,
  gap/overlap findings, long-running open activities, missing laytime.

## Motion ("Livelier" package — all honor `prefers-reduced-motion`)

- Cards rise in with a 60–100ms stagger (`animate-rise` + `animation-delay`).
- Progress bars and the route line fill from zero (`animate-fill`).
- Current-phase dot pulses (`animate-pulse-soft`); the sailboat marker bobs
  while a voyage is ongoing (`animate-bob`).
- KPI numbers count up (~700ms, vanilla JS in voyage_list.html; static values
  remain without JS).
- Hover: card shadow lift, 150ms color eases. Banned: bounce, spinners.

## Components (in `@layer components`)

`.card`, `.btn` (+`-primary/-secondary/-danger`), `.chip` (+`-ok/-live/-info/-bad`,
dot + word), `.message` (+ tags), `.btn-ghost`/`.undo-form` (flash undo).
Django form widgets are styled at the element level in `@layer base`
(inputs, selects with data-URI chevron) since they render class-less.

## Layout

Sidebar 248px sticky (collapses to a top bar <1024px). Content column
max 1160px, centered. Tables: uppercase 12px tracked headers, roomy rows,
right-aligned tabular numbers, mini progress bars always beside the numbers.
Dashboard grid: 2 vessel cards + alerts panel / KPI band / filters / table
with pagination (10/page).

## Voice

Bahasa Indonesia everywhere, sentence case, no jargon, no exclamation
points. Time-of-day greeting on the dashboard. Every status color carries an
Indonesian word.
