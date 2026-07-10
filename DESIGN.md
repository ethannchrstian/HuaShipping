# DESIGN — Visual identity (v3)

Governed by PRODUCT.md ("tenang, jelas, terpercaya") and the binding UI rules
in docs/06-screens.md. prototype.html remains an anti-reference (no emoji
icons, no uppercase micro-labels, no gradients).

**v3 (2026-07-11):** redesigned against rendered screenshots and owner-chosen
reference UIs (modern logistics dashboards). v1/v2's "borderless paper" look
read as unstyled; the fix was a dark anchored sidebar, real elevation, and
confident hierarchy. Rule learned the hard way: **no styling ships without
being looked at** — screenshot via Playwright (`scratchpad/shoot.py` flow),
inspect, iterate.

## Feel

A calm, professional operations tool: dark navy sidebar anchoring the screen,
white cards floating with soft shadows on a cool-gray canvas, one confident
teal for actions, generous 44px targets. Numbers are the heroes.

## Type

- **Inter** (self-hosted variable font, `static/voyages/fonts/`), fallback
  Segoe UI. Base **16px**, tables **15px**, captions 13px, nothing under 12px.
- Hierarchy by size *and* weight: page titles 28px/700 with tight tracking,
  section titles 17px/650, values 650, labels 500 gray.
- `font-variant-numeric: tabular-nums` everywhere numbers align.

## Color

| Token | Value | Use |
|---|---|---|
| `--navy` | `#10273f` | sidebar background |
| `--canvas` | `#eef1f5` | page background (cool gray) |
| `--card` | `#ffffff` | cards, tables |
| `--line / --line-soft` | `#e6e9ef / #eef0f4` | card edges, row separators |
| `--ink / --ink-soft / --ink-faint` | `#1b2733 / #667085 / #98a2b3` | text tiers |
| `--sea / --sea-deep / --sea-tint` | `#155e75 / #0e4256 / #e3eef2` | actions, links, ongoing |
| `--ok-*` | `#e5f3e9 / #1e6b3a` | Selesai |
| `--warn-*` | `#fdf3dd / #8a5a00` | W1 gap strips |
| `--bad-*` | `#fdebe8 / #b42318` | W2 overlap, errors, demurrage |
| `--shadow` | `0 1px 2px …05, 0 1px 3px …08` | card elevation |

Color never carries meaning alone (rule 5): every status/warning pairs the
color with an Indonesian word ("Berjalan", "+3 hari lebih", "Tumpang tindih").

## Components

- **Sidebar**: 240px sticky navy column; white brand block; nav items 44px,
  `rgba(255,255,255,.72)` text, active = 14% white pill; footer (user, Keluar)
  above a hairline. Collapses to a top bar <760px.
- **Card**: white, 12px radius, `--shadow`, 1px `--line` edge.
- **Status pills**: dot + word, tinted background, 999px radius.
- **Buttons**: primary filled `--sea` with shadow; secondary white with
  `#d0d5dd` border. Always a labeled Indonesian word.
- **Tables**: `#f9fafb` header band with 13px gray-600 labels; 14–16px cell
  padding; `white-space: nowrap` by default with `.wrap` opt-out (routes,
  notes); hover `#f6f8fb`; numbers right-aligned tabular.
- **KPI cards**: label on top (gray 13.5px), number below (30px/700).
- **Vessel cards**: 3px `--sea` top accent; voyage code 24px/700.
- **Ledger** (voyage summary): one figure per line — label left gray, value
  right 650 tabular, faint provenance note ("di sheet: …") beneath; total row
  22px, demurrage in `--bad-ink`.
- **Timeline marks**: ongoing row = `--sea-tint` fill; sailing leg = 3px
  muted-blue inset left edge; W1/W2 = tinted full-width strips with a plain
  Indonesian sentence.
- **Entry panel (S5)**: `#f8fafc` inset panel inside the timeline card.

## Layout

8px grid; content column max 1160px in a 48px-padded area; sections separated
by 24px. Focus ring: 2px `--sea`, offset 2. `prefers-reduced-motion` honored.

## Voice

Bahasa Indonesia everywhere, sentence case, no jargon, no exclamation points.
Verbs specific and consistent: "Simpan kegiatan", "Selesaikan voyage",
"Ekspor CSV". Labels are phrases, not codes ("hari di pelabuhan, semua
voyage").
