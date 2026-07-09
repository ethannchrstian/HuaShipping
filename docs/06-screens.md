# 06 — Screen Inventory & Layout

**Visual reference: `prototype.html`.** It's an AI one-shot, but the look
(harbor-navy sidebar, card tables, status chips, passage progress line, phase
day-boxes) is good and the family already saw it — keep that visual language.
This doc lists the actual screens, what's on them, and where we deviate.
No Figma; deviations are annotated here and refined in the browser during build.

All UI text Bahasa Indonesia (strings from `01-glossary.md`). Responsive:
sidebar collapses to top bar < 760px (prototype already does this).

## S1. Masuk (login)
Plain Django login form, company name, Indonesian labels. No self-registration —
accounts created by admin.

## S2. Rekap voyage (home / voyage list)
Prototype's "Rekap voyage" view, kept almost as-is:
- KPI tiles: voyages this year, ongoing now (with current phase), total MT shipped, total demurrage days YTD
- Filters: vessel, status, charterer, year, free-text search
- Table: code · vessel · charterer · route (load → discharge) · start date · status chip (Berjalan + current phase / Selesai) · total days · demurrage days
- Row click → S3. Button: **+ Voyage baru** → S4. Button: **Ekspor CSV**
- *Deviation from prototype:* drop the mini progress bars in rows (noise); keep chips.

## S3. Detail voyage
Prototype's detail view, restructured:
- Header: code, vessel, charterer, contract/invoice numbers, route, status chip, **Terkunci** badge when locked
- **Kegiatan (activity timeline)** — the centerpiece: ordered rows with type, start → end, computed duration, note; gap/overlap warnings inline (red strip, W1/W2 wording from calc spec); ongoing activity highlighted; **+ Tambah kegiatan** (S5)
- Day summary strip: per-block totals (A/B/C…), grand total, prorata kontrak, demurrage days — sheet-style day+time pairs (calc spec C3–C5)
- Muatan (parcels) card: commodity, MT, jetty, shipper
- Money card (V1.1): freight, fuel used, **cost line items (stevedoring, port charges, agency, bunker…) with total**, demurrage estimate
- Port-time figure ("berapa lama di port") shown prominently — explicitly requested
- Actions: Selesaikan voyage (→ lock, W5 check), Ekspor, **Cetak time sheet** (S8, V1.1)

## S4. Form voyage (create/edit)
Modal or page: code (prefilled next in sequence per vessel), vessel, charterer,
contract no, invoice no, load jetty/jetties (ordered multi-select), discharge
jetty, laytime (combined **or** split muat/bongkar — toggle), demurrage rate,
parcels inline (commodity/MT/jetty/shipper rows). Server-side validation per
ERD constraints.

## S5. Form kegiatan (add/edit activity)
The most-used form — optimize hard:
- Type select ordered by the natural sequence; **default = the type that usually follows the previous activity**
- **Start prefilled with the previous activity's end** (the #1 data-entry accelerator; the sheets are always contiguous)
- End optional ("masih berjalan"); date+time pickers; sailing legs reveal from/to location fields
- On save: C1 block on end ≤ start (clear Indonesian message); W1/W2 warnings shown non-blocking

## S6. Data master
Three simple CRUD tabs: Kapal, Jetty, Pencharter. (Django admin can serve as
the v0 here; promote to styled pages only if the team finds admin confusing.)

## S7. Pengguna & audit (admin-only)
User management (Django admin) + per-voyage change history (simple-history
list: who/when/what).

## S8. Cetak time sheet (V1.1, print CSS)
Reproduces the current Excel printout: title with vessel + voyage, header block
(kontrak, kwitansi, muatan, lokasi, prorata, demurrage), activity table with
day+time pair columns, A/B/C subtotal rows, grand total, DEMURRAGE line,
signature block (Dibuat Oleh — Operasional / Diketahui Oleh — Direktur Utama).
Matching the familiar layout is deliberate: the printed sheet is what the
director signs today.

## Navigation
Sidebar: Rekap voyage · Data master · (V2: Analisis) · footer: user name, Keluar,
Ekspor data. Prototype's "Analisis" screen is V2 — do not build yet.
