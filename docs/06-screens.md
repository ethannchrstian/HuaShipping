# 06 — Screen Inventory & Layout

**Visual reference: `prototype.html` — for its look only, not its interactions.**
A full UX critique (2026-07-10, scored 21/40, snapshot in
`.impeccable/critique/`) confirmed: keep the visual language (harbor-navy,
status chips, phase day-boxes) and the core interaction principle (computed
numbers, prefilled start times, blame-free inline warnings); replace the
interaction layer per the binding rules below.

All UI text Bahasa Indonesia (strings from `01-glossary.md`). Responsive:
sidebar collapses to top bar < 760px (prototype already does this).
Strategic principles live in `PRODUCT.md`.

## Binding UI rules (from the critique — every screen must comply)

1. **No icon-only controls.** Every action is a labeled Indonesian text button
   ("Ubah", "Hapus kegiatan"), target ≥44px. No emoji as icons.
2. **No silent outcomes.** Every save shows confirmation (toast/inline);
   every validation failure shows a field-level Indonesian message. A button
   that does nothing is a bug.
3. **No browser-native `confirm()`/`alert()`.** Proper dialogs in Indonesian;
   destructive actions get soft-delete + undo where feasible.
4. **Type scale for older users:** base 16px, tables ≥14px, no text below 12px.
5. **Color never carries meaning alone** — pair with sign/word ("+3 hr lebih").
6. **Keyboard operability:** voyage rows are links, sort headers are buttons,
   dialogs trap focus and close on Esc.
7. **One word, one meaning:** "Selesaikan kegiatan" vs "Tutup voyage" — never
   the same verb for both.
8. **All-Indonesian:** no "Export CSV" ("Ekspor CSV"), no mixed strings.

## S1. Masuk (login)
Plain Django login form, company name, Indonesian labels. No self-registration —
accounts created by admin.

## S2. Rekap voyage (home / voyage list)
Prototype's view, simplified per the critique (its 11-column table overloads
non-technical users):
- **Lead with two vessel status cards** ("where are my boats now"): vessel,
  current voyage, current phase chip, days at port so far
- KPI tiles (max 4): ongoing voyages, port days this year, demurrage days YTD, MT shipped
- Filters: vessel, status, charterer, **year** (prototype hardcoded 2026), free-text search
- Table, **~7 default columns**: vessel · code · charterer · route · start ·
  port days / laytime · status chip. Waiting-% and other ratios live in S3 and
  V2 analytics, not here. Rows are real links (keyboard-operable)
- Buttons: **+ Voyage baru** → S4 · **Ekspor CSV**

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

## S5. Entri kegiatan (add/edit activity) — the adoption-deciding screen
**Not a modal.** The critique's biggest finding: the real workflow is
transcribing a WhatsApp backlog of N timestamps, so entry must be an **inline
add-row at the bottom of the timeline** — the log stays visible while typing
(no working-memory bridge), and saving one row immediately opens the next with
start prefilled. Loop: type → tab → type → Enter → next row.
- Type select ordered by the natural sequence; **default = the type that usually follows the previous activity**
- **Start prefilled with the previous activity's end** (the #1 accelerator; the sheets are always contiguous)
- End optional ("masih berjalan"); sailing legs reveal from/to location fields
- On save: block end ≤ start with a field-level Indonesian message (calc spec C1); W1/W2 warnings shown non-blocking; save confirms visibly
- Editing an existing activity uses the same inline row swapped in place

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
