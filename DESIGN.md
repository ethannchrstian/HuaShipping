# DESIGN — Visual identity

Seeded at UI-build time per ADR-011. Governed by PRODUCT.md ("tenang, jelas,
terpercaya" — feels like well-organized paperwork, not a startup dashboard) and
the binding UI rules in docs/06-screens.md. prototype.html is an
anti-reference: no condensed display fonts, no emoji icons, no uppercase
micro-labels, no gradients.

## Feel

Ledger on good paper. Warm paper background, white cards with hairline borders
(no drop shadows), generous 44px touch targets, calm deep-sea blue as the only
brand color. Numbers are the heroes; chrome recedes.

## Type

- System humanist stack: `"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
  — office PCs, zero font downloads, instantly familiar.
- Base **16px**, tables **15px**, captions 13px, nothing under 12px (binding rule 4).
- Numbers use `font-variant-numeric: tabular-nums` so columns align.
- Weight does the hierarchy (600 for headings/values), not size explosions.

## Color

| Token | Value | Use |
|---|---|---|
| `--paper` | `#f6f5f1` | page background (warm, not gray) |
| `--card` | `#ffffff` | cards, table bodies |
| `--line` | `#e2dfd6` | hairline borders, row separators |
| `--ink` | `#22303a` | body text |
| `--ink-soft` | `#5d6b76` | captions, secondary text |
| `--sea` | `#155e75` | primary actions, links, focus, ongoing status |
| `--sea-deep` | `#0e4256` | hover/active |
| `--ok-bg / --ok-ink` | `#eef4ee` / `#2e5e3a` | "Selesai", verified states |
| `--warn-bg / --warn-ink` | `#fdf3e0` / `#8a5a00` | W1 gap warnings |
| `--bad-bg / --bad-ink` | `#fdecea` / `#8f2f24` | W2 overlap, validation errors |

Color never carries meaning alone (rule 5): every status/warning pairs the
color with an Indonesian word ("Berjalan", "+3 hari lebih", "Tumpang tindih").

## Components

- **Card**: white, 1px `--line` border, 8px radius, 16–20px padding. No shadow.
- **Status chip**: 8px dot + word ("● Berjalan"), 4px radius, tinted background.
- **Buttons**: primary = filled `--sea`, white text; secondary = white with
  `--line` border. Min height 44px, always a labeled Indonesian word (rule 1).
- **Tables**: 15px, left-aligned text / right-aligned numbers, 44px rows,
  row = real link with visible focus ring (rule 6), zebra off, hover tint.
- **Inputs**: 44px, white, 1px border, 2px `--sea` focus ring; labels above,
  field-level errors in `--bad-ink` under the field (rule 2).
- **Warning strip**: full-width tinted row inside the timeline, colored border
  left + plain-Indonesian sentence explaining and suggesting (blame-free).
- **Sidebar**: 216px, paper-colored, text links; collapses to a top bar <760px.

## Layout

8px spacing grid; content max-width 1080px; page = title row, then cards.
Focus states: 2px solid `--sea`, 2px offset, everywhere.
`prefers-reduced-motion` honored (no animation is the default anyway).

## Voice

Bahasa Indonesia everywhere (rule 8), sentence case, no jargon, no
exclamation points. Verbs are specific and consistent (rule 7): "Simpan
kegiatan", "Selesaikan voyage", "Ekspor CSV".
