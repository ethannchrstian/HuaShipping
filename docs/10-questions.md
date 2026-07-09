# 10 — Open Questions for the Company

Track answers here; each answer feeds back into requirements (02), ERD (03), or
calc spec (04). Status: ⬜ open · ✅ answered (with date + answer).

## Critical — blocks V1 details

| # | Question (asking in Indonesian is fine — bring this list to the chat) | Why it matters | Status |
|---|---|---|---|
| 1 | How does voyage info reach the office today? (Kapten kirim jam-jam kegiatan via WhatsApp? Siapa yang catat, kapan?) | Decides whether data entry is live per-event or after-the-fact batch → shapes the activity form | ⬜ |
| 2 | Who are the 2–3 people who would type into the system daily? (Felicia + who?) | Pilot users; accounts; training | ⬜ |
| 3 | Demurrage: V2605/V2606/HN2-V2602 show computed demurrage days — **were these actually invoiced and paid?** | Whether demurrage is a real revenue item or informational | ⬜ |
| 4 | Confirm the counting convention: waiting time (tunggu sandar/muat/bongkar) counts toward laytime, persiapan doesn't, hours are truncated for demurrage days — correct? (We reverse-engineered this from the sheets) | Locks calc spec C2–C5 | ⬜ |
| 5 | 2025 contract had split laytime (6 muat + 6 bongkar) but the sheet compares the combined 12 — is per-side comparison ever needed? | Calc spec C5 open point | ⬜ |

## Shapes V1 scope

| # | Question | Why | Status |
|---|---|---|---|
| 6 | Should everyone in the office see money fields (freight, demurrage rate), or only certain people? | Roles/permissions design | ⬜ |
| 7 | Freight: lumpsum per voyage or per-MT? Always IDR? | Voyage money fields | ⬜ |
| 8 | Bunker/fuel: recorded per voyage or bought in bulk? Where do the numbers come from? | Whether fuel fields are per-voyage facts or allocations | ⬜ |
| 9 | Devices: office PCs only or also phones? How reliable is office internet? | Responsive priority; offline tolerance expectations | ⬜ |
| 10 | What recap/report does the Direktur ask for repeatedly? (monthly? per charterer? per vessel?) | First report to build in V1.1/V2 | ⬜ |

## Logistics

| # | Question | Why | Status |
|---|---|---|---|
| 11 | Vessel plans: staying at 2 tug+barge sets, or adding more soon? | Scale assumptions (nothing breaks either way) | ⬜ |
| 12 | Import how far back? (We have 2025 V2501 + 2026; are there older workbooks?) | Import scope | ⬜ |
| 13 | Hosting ~US$5–15/month + domain ~$15/yr — who pays, and is a company domain wanted? | Ops | ⬜ |
| 14 | If invoice generation is wanted later: sample of the current kwitansi/letterhead | V2 scope | ⬜ |
| 15 | Are the two currently-ongoing voyages (HN1 V2607, HN2 V2603) good pilot candidates to enter live in the app once V1 exists? | Pilot plan | ⬜ |
