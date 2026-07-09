# 10 — Open Questions for the Company

Track answers here; each answer feeds back into requirements (02), ERD (03), or
calc spec (04). Keep the open list SHORT — the friend found the long version
overwhelming. Ask the top items opportunistically, not as a questionnaire.

## Answered

| # | Question | Answer (2026-07-09, via Melvin) |
|---|---|---|
| A1 | How does voyage info reach the office? | **WhatsApp from the ship crews (vessels have Starlink).** Office admins transcribe. → Data entry is after-the-fact transcription; activity form optimized for batch entry (prefill start = previous end). |
| A2 | Who uses the system? | **Only the office admins.** |
| A3 | Roles / who sees money fields? | **No roles needed** — every office admin sees everything. Single permission level + superuser for the developer. (ADR-009) |
| A4 | Anything beyond the time sheet to track? | **"Keep track how long at port"** (already core: port blocks per calc spec C2–C4 — surface prominently in list/detail/KPIs) **+ "stevedoring and all that stuff"** → per-voyage cost line items: stevedoring, port charges, agency, bunker… (ADR-010, V1.1) |

## Still open — top 4, ask when natural

| # | Question | Why it matters | Status |
|---|---|---|---|
| 1 | Demurrage days appear on V2605/V2606/HN2-V2602 — were these actually invoiced and paid? | Whether demurrage is revenue or informational | ⬜ |
| 2 | Confirm the counting convention we reverse-engineered: waiting counts toward laytime, persiapan doesn't, hours truncated for demurrage days | Locks calc spec C2–C5 (currently our best inference from the sheets) | ⬜ |
| 3 | What port/stevedoring costs exist per voyage, roughly? (stevedoring, port charges, agen, apa lagi?) | Seeds the cost-category list (ADR-010) | ⬜ |
| 4 | Import how far back — are there workbooks older than the 2025 one? | Import scope | ⬜ |

## Parked (ask only if the topic comes up)

Split-laytime per-side comparison (calc spec C5) · freight lumpsum vs per-MT ·
devices/office internet · recurring report the Direktur wants · vessel growth
plans · who pays hosting ~$5–15/mo + domain · kwitansi letterhead sample (V2
invoicing) · pilot the two ongoing voyages (HN1 V2607, HN2 V2603) live in-app.
