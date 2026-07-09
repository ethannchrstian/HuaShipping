---
target: prototype.html
total_score: 21
p0_count: 0
p1_count: 3
timestamp: 2026-07-09T17-20-19Z
slug: prototype-html
---
# Critique — prototype.html (voyage-tracking prototype)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Saves are silent; no toast/confirmation anywhere |
| 2 | Match System / Real World | 3 | Excellent domain Indonesian; English leaks ("Export CSV", "Reset ke data asli") |
| 3 | User Control and Freedom | 1 | No undo; native confirm()/alert(); no Esc-to-close; permanent deletes |
| 4 | Consistency and Standards | 3 | "Selesaikan" means both finish-activity and complete-voyage |
| 5 | Error Prevention | 2 | Raw datetime-local, no end>start form validation; saveVoyage silently no-ops on empty code |
| 6 | Recognition Rather Than Recall | 2 | Icon-only ✎/✕/🔒; entry modal covers the timeline being extended |
| 7 | Flexibility and Efficiency | 2 | Prefill/nextTypeGuess good; no batch entry — one modal round-trip per activity |
| 8 | Aesthetic and Minimalist Design | 3 | Home table: 11 columns incl. derived ratios; overloads non-technical users |
| 9 | Error Recovery | 1 | Silent no-op save paths; alert() only; no field-level messages |
| 10 | Help and Documentation | 2 | Dismissible intro + inline hints; nothing contextual beyond |
| **Total** | | **21/40** | **Acceptable (lower bound)** |

## Anti-Patterns Verdict
LLM: reads as a designed dashboard, not obvious slop; product-register tells are display font in UI chrome, emoji as icons, uppercase micro-eyebrow labels everywhere. Detector: 1 warning (width transition on progress fill, line 111) — cosmetics are not the problem; UX depth is. Browser overlay skipped: no browser automation in session.

## Priority Issues
- **[P1] Timestamp entry is the weakest where it matters most.** Raw datetime-local in a modal, no inline end>start validation, silent no-op saves. Fix in real app: S5 as first-class inline row/page, Indonesian field-level errors, never silent.
- **[P1] Icon-only micro-buttons + no undo + native confirms.** ✎/✕ at 2×6px padding, adjacent; confirm() in browser chrome. Fix: labeled text buttons ≥44px, Indonesian confirm dialogs, soft-delete with undo.
- **[P1] No batch transcription.** Real workflow is a WhatsApp backlog of N timestamps; prototype needs N modal round-trips. Fix: inline add-row at timeline bottom, tab-through, auto-chained start times.
- **[P2] Home overload:** 11 columns + 4 KPIs + intro banner. Fix: ~7 default columns; move ratios to detail/analytics.
- **[P2] Type sizes below older-user threshold:** 13px table, 12px hints, 11px sub-cells, 10.5px labels. Fix: 16px base, ≥14px tables.
- **[P2] Color-only semantics** (red/green numbers) and borderline amber chip contrast at 11px. Fix: pair color with text/sign/icon; recheck contrast.
- **[P2] Mouse-only interactions:** clickable <tr> not focusable, <th> sort not buttons, modal without focus trap.

## Persona Red Flags
- Older first-timer admin: icon-only buttons, EN browser confirms, 11px text → hesitates, self-blames, abandons.
- Felicia (daily transcriber): modal-per-activity + no keyboard flow → keeps Excel open "because faster".
- Keyboard/screen-reader user: cannot open a voyage or sort at all.

## Minor Observations
- Language mixing (EN button labels) breaks the Indonesian-only rule.
- "2026" hardcoded in KPI sub-labels; no year/date filters.
- Economics card's "result after fuel" reads like profit; needs cost line items (already planned, ADR-010).
- localStorage single-device persistence: fine for prototype, irrelevant for real app.
- Missing: login identity on log entries, insert/reorder activities, pagination for years of data, save feedback.

## Questions to Consider
- What if activity entry never left the timeline (inline rows), so the WhatsApp transcription loop is type-tab-type?
- Should completed voyages celebrate (verification summary: "27d 05:53 — cocok dengan kontrak") instead of just locking?
- Could the home page lead with "the two vessels now" (status cards) instead of a table?
