# 11 — App & UI Guide: how it works and what is what

A walkthrough of every screen, every element on it, and why it looks the way
it does. Written for the project owner; a Bahasa Indonesia end-user version
for the office comes at pilot time.

## Starting the app

Double-click **`dev.bat`** in the project folder (or type `dev` in a terminal
there). It starts the development server; open **http://127.0.0.1:8000** in a
browser. Stop it with `Ctrl+C`. One-time setup if you haven't yet: create your
account with `.venv\Scripts\python manage.py createsuperuser`.

(For design work only: `dev css` in a second terminal rebuilds the stylesheet
live while templates are edited — see DESIGN.md.)

## Screen 1 — Masuk (login)

A centered white card on the brand-navy background, topped with the company
logo: username, password, one button. No self-registration — accounts are
created by the admin (you), which is the security model the company chose
(ADR-009: no roles, everyone sees everything). A wrong password shows one
plain-Indonesian error, deliberately not saying *which* field was wrong
(standard practice: don't help someone guessing usernames).

## Screen 2 — Ringkasan operasional (the dashboard, home page)

A wide (up to 1600px) operations layout with labeled sections, reading top to
bottom:

1. **Page header** — title, today's date, **"Data terakhir diubah …"** (the
   newest entry in the audit trail, so everyone knows how fresh the numbers
   are), and the quick actions *Data master* and *Voyage baru*.
2. **Voyage aktif** — one hero card per tugboat set, always "now" (they
   ignore the filters below). The voyage code is the biggest thing on the
   card (click it to open); the vessel names sit under it as secondary text.
   Then the **route line** (load port left, discharge port right, a sailboat
   marker positioned along it by phase — it bobs while the voyage runs), the
   **Muat → Berlayar → Bongkar** tracker with the current step highlighted,
   and a grouped detail list: current activity, and days at port versus
   contract with a progress bar (green within contract, red over).
3. **Pusat tindakan** — the action center, beside the cards on big screens.
   Each item is a priority card with a colored left edge and a severity chip
   — **Mendesak** (red, over contract), **Periksa** (amber, gap/overlap
   found), **Info** (blue, e.g. an activity running suspiciously long or a
   missing contract laytime) — plus a **"Buka V26xx"** button straight to the
   voyage. Everything is derived from real data on *ongoing* voyages only;
   the empty state says "Semua beres".
4. **KPI operasional** — four year-scoped stat cards with colored icon tiles
   and **trend arrows** against last year (a red ↑ on demurrage days is bad;
   a green ↑ on MT carried is good — the color follows the meaning, not the
   direction): voyages running now, demurrage days this year, the rupiah
   estimate of that demurrage, and MT carried this year.
5. **Semua voyage — filters** — search (code, contract, kwitansi, charterer),
   vessel, status, **pencharter**, **pelabuhan/jetty**, and a **date range**
   (Mulai dari / Sampai). Changing any filter updates *only the table* below
   — the page does not reload (HTMX swaps just that section, and the address
   bar still updates so a filtered view can be bookmarked or shared).
6. **The voyage table** — Voyage code first, one row per voyage, paginated at
   10. Routes show origin ◉ → destination ⌖ with the port names written out.
   **"Hari pelabuhan / kontrak"**: actual days in port versus the contract's
   allowed days, with a mini progress bar; over-contract rows get a red
   "+N hari lebih" badge — color never carries meaning alone. The **whole row
   is clickable** (the voyage code stays a real link for keyboard users).

## Screen 3 — Detail voyage

1. **Header** — voyage code + vessel, status chips (*Berjalan/Selesai*, and
   *Terkunci* when the voyage is closed), route, then the paper trail: contract
   number, kwitansi, contracted laytime, demurrage rate.
2. **The time ledger** (white card, one line per figure — styled like a
   well-kept register, which is what it is):
   - **Total Kegiatan Muat (A) / Bongkar (B)…** — time in port per port call,
     computed from timestamps. The small gray "di sheet: 19 | 1d 17:00" note
     underneath shows the same figure in the Excel sheet's two-column
     convention — provenance, so anyone can check the app against the old
     paper.
   - **Total waktu di pelabuhan** — the big number the company asked for
     ("keep track brp lama di port"). If it exceeds the contract it says so
     in words: *"+15 hari lebih dari kontrak"*.
   - **Prorata sesuai kontrak** — the allowed days from the contract.
   - **Demurrage** — extra days × the daily rate, with the rupiah estimate.
     Red when there's money on the line.
3. **Muatan** — the cargo parcels: commodity, tonnage, load jetty, shipper.
4. **Kegiatan (the timeline)** — the heart of the app; one row per logged
   activity with computed duration. What the visual marks mean:
   - **Blue-tinted row** = happening right now (no end time yet).
   - **Blue edge on the left** = a sailing leg (vessel moving, doesn't count
     as port time).
   - **Amber strip** after a row = *gap warning* (W1): "Ada jeda … yang belum
     tercatat" — more than 30 minutes unaccounted between activities. Not an
     error; a nudge that something may be missing.
   - **Red strip** = *overlap warning* (W2): the next activity starts before
     this one ended — almost always a date typo. This exact warning would
     have caught the error that inflated a real 2026 demurrage bill.
5. **Tambah kegiatan** — the entry row at the bottom (only on unlocked
   voyages). Built around the office's real workflow, transcribing a WhatsApp
   backlog: the start time is pre-filled with the previous activity's end,
   the activity type is pre-selected to what usually follows, and after
   *Simpan kegiatan* you land back here with the next row ready. An end time
   before the start is rejected on the spot with a plain message — the app
   physically will not store the error class found in the old sheets.

Completed voyages are **locked**: no entry form, and any attempt to change
them is refused with a message. Unlocking (later feature) will be logged.

## Data master

The sidebar's *Data master* opens Django's built-in admin — vessel/jetty/
charterer records, user accounts, and the full change history (who changed
what, when) recorded automatically on every save. It's the developer/backoffice
view; the office team normally never needs it.

## Why it looks the way it does

The v4 identity (`DESIGN.md`) is built with Tailwind CSS on the company's own
brand navy (sampled from the logo), informed by modern logistics-dashboard
references the owner picked, and verified screen-by-screen with rendered
screenshots before shipping:

- **Hierarchy from size and weight, not boxes.** White cards on a cool
  canvas; one action blue so highlights actually highlight.
- **Text left, numbers right, always tabular digits** so columns of durations
  line up like a printed register and are comparable at a glance.
- **Real numbers, never decoration** — progress bars always sit beside the
  figures they illustrate; no invented "82%" metrics.
- **Motion is purposeful and quiet**: cards rise in, bars fill, the current
  phase pulses, KPI numbers count up — and all of it switches off for users
  with reduced-motion set.
- **Every rule from the UX critique is binding** (docs/06): 16px base text,
  44px touch targets, no icon-only buttons, every action a labeled Indonesian
  word, color always paired with a word, keyboard focus visible everywhere.

## What intentionally doesn't exist yet

No dead buttons is a binding rule, so features that aren't built aren't
shown: CSV export, reports/recap pages, and the printable time sheet (V1.1).
They arrive in the next build steps, before the office pilot.
