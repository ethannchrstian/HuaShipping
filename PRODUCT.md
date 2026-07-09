# Product

## Register

product

## Users

~10 office admins at PT Hua Shipping Agro Trans, non-technical, several older
("boomer" per the brief), working on office PCs and sometimes phones. Primary
daily job: transcribing voyage activity timestamps from ship crews' WhatsApp
messages (vessels have Starlink) into the voyage log, then looking up voyages,
port time, and demurrage. Secondary user: the Director, who reads recaps and
signs printed time sheets. See docs/02-requirements.md.

## Product Purpose

Replace per-vessel Excel time sheets with one shared database where day counts,
laytime comparisons, and demurrage are computed from timestamps, never typed.
Success = the admins stop opening Excel, and every printed time sheet's numbers
are reproducible and correct. See docs/ 01–10 for full plans.

## Brand Personality

Tenang, jelas, terpercaya (calm, clear, trustworthy). A professional back-office
tool with a quiet maritime identity, designed from scratch at UI-build time
(ADR-011 — the AI prototype's styling is explicitly not the reference). It
should feel like well-organized paperwork, not like a startup dashboard.

## Anti-references

- **prototype.html's styling** — condensed display font in UI chrome, emoji
  icons, uppercase micro-label scaffolding: the AI-dashboard look (ADR-011).
- Trading-terminal density: tiny mono numbers, 11-column tables, ratio soup.
- Consumer-app trendiness: gradients, animations, icon-only minimalism.
- Anything requiring discovery: hidden menus, hover-only actions, gestures.

## Design Principles

1. **Numbers are computed, never typed.** The UI's job is capturing timestamps
   pleasantly and showing derived numbers with their provenance.
2. **Every control is a labeled word.** No icon-only buttons; actions say what
   they do in Indonesian ("Hapus kegiatan", not ✕).
3. **Transcription is the workflow.** Entering a batch of WhatsApp timestamps
   must be fast, keyboard-friendly, and keep the log visible while typing.
4. **Blame-free and reversible.** Warnings explain and suggest; destructive
   actions are undoable or softly confirmed in plain Indonesian; saves confirm
   visibly.
5. **Familiar over clever.** Standard tables, forms, and navigation; the tool
   disappears into the task.

## Accessibility & Inclusion

WCAG 2.1 AA. Base font ≥16px, table text ≥14px; touch targets ≥44px; full
keyboard operability (rows, sorting, dialogs); color never the sole carrier of
meaning (pair with text/icons); visible focus states; `prefers-reduced-motion`
respected. All UI text Bahasa Indonesia.
