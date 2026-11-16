# The site's design

Read this before restyling any page. It records the reference the whole site is held to, then (once the
structure lands) the page order, each page's theme, the shared grid and type scale, and the standing rules.

## 1. The reference: lukres.dev, measured

lukres.dev is a heavy influence on the whole site, not a loose reference: for craft, never for palette.
Measured 2026-11-16 from the live site: its stylesheet (`/_astro/about.*.css`), its script bundle
(`/_astro/hoisted.*.js`, readable, with the author's comments), and the rendered page at 1440x900 and
390x844 (text boxes measured in the browser on each screen as the page was scrolled).

### Easing and duration

| use | curve | duration |
|---|---|---|
| his signature: page show and hide, text entrances, anything that travels | `cubic-bezier(.35, 0, 0, 1)` (named `lusion` in his code: a quick start, a very long soft settle) | 1.0 s for a page; 0.6–0.7 s for an entrance |
| UI: hover rolls, menu items, buttons | `cubic-bezier(.4, 0, .1, 1)` | 0.3–0.4 s; menu groups 0.5 s with staggered delays |
| rare: a snap that overshoots nothing | `cubic-bezier(.16, 1, .3, 1)` | 0.3 s |
| colour (hover, theme change) | linear or default | 0.4–0.5 s |

The two curves account for 64 of the 72 easing declarations in his CSS. Nothing bounces, nothing is
linear except colour.

### How elements enter and leave

- **Headline words rise out of a mask.** Each line is its own `overflow: hidden` box; each word starts
  1.7em below, tilted 15°, and settles to place over 1.0 s (the tilt over the first 0.7 s), on the
  signature curve, 50 ms after the word before it. Nothing moves in the first second after a page shows.
- **Small marks follow.** Corner crosses scale 0 → 1 and turn 180° over 0.6 s, 100 ms apart; secondary words
  scale 0.8 → 1 and fade in over 0.6 s, 100 ms apart.
- **Reveals are reversible.** A section title's reveal is a clock that runs forward while the section is in view
  and backward when it leaves (clamped 0–2 s), so leaving plays the entrance in reverse instead of popping.
- **Hover is a roll, not a fade.** A label slides up out of its mask (`translateY(-100%)`) while a copy rises from
  below (`100%` → `0`), 0.3–0.4 s, UI curve; an arrow slides in from the left the same way.
- **The menu** opens with each group rising 5.5em and turning 3.5° back to level, with opacity, 0.5 s, staggered.
- **Everything animated is transform or opacity.** Positions are written as `translate3d`; colour changes are the
  only exception and are slow (0.4–0.5 s).

### How scroll drives motion

- **Eased wheel.** His `ScrollPane` keeps a target offset; each frame the page moves
  `remaining × (1 − e^(−12·dt))` toward it (`wheelEaseCoeff = 12`, frame-rate independent, about 0.38 s to
  settle, never overshooting). Drag has a fling with friction easing from 2.1 to 1.9. The document itself never
  scrolls (`overflow: hidden` on html and body); the content is translated.
- **Scroll is a timeline.** Sections map the scroll position to 0–1 ranges (`math.fit(range.ratio, a, b, 0, 1, ease)`)
  and drive their drawing from that: scroll scrubs motion, it does not trigger it.
- **Page to page** is 1.0 s each way (1.5 s when a project card morphs into its page), behind a full-screen curtain.

`src/scroll.ts` already models the eased wheel and his page carry. Note one deliberate difference: his site does
not respond to `prefers-reduced-motion` at all. Ours does, and must.

### Type scale

Two families (DM Sans 400 and 500; IBM Plex Mono 400 and 500 for labels and figures). **No bold anywhere.**
Display sizes are set in viewport width, so the page scales as one picture:

| step | size at 1440 | as set | where |
|---|---|---|---|
| hero | 144–173 px | 10–12vw (`clamp(7em, 8vw, 20em)` elsewhere) | one name or one word per screen |
| section | 115 px | 8vw | "Selected Work" |
| large | 58 px | 4vw | a subhead or a big number |
| medium | 43 px | 3vw | a project name |
| small display | 29 px | 2vw | a list in the mono face, figures |
| lead | 22 px | 1.5vw | the one paragraph beside a headline |
| body | 17–18 px | `clamp(1rem, 1vw, 1.75rem)` region | reading text, line-height 1.4 |
| label | 13–14 px | `clamp(.875rem, 1vw, 2rem)`, uppercase | header, captions |
| micro | 10 px | mono, uppercase, tracked | table labels ("LOCATION") |

Display lines are set at line-height 0.9–1.0 with −0.02em tracking; body at 1.4. At 390 the hero drops to
23 px for the intro line (measured) and the name to about 60 px (read off the screenshot); the side padding drops to 15 px.

### Spacing rhythm and grid

- **Side padding**: `max(5vw, 40px)` (72 px at 1440); 25 px up to 812 px wide; 15 px up to 400 px.
- **Vertical padding**: `clamp(30px, 4vw, 50px)`; the header sits inside it.
- **Grid**: 12 columns, gap 2vw (4vw up to 812 px).
- **Gaps between ideas are in em of the local type**: 1em, 2em, 3em, 4em steps. Between sections, close to a full
  viewport of space.
- Everything on a screen hangs off the same left edge (72 px at 1440): the logo, the headline, the paragraph's
  column, the card edges.

### How few elements each screen holds, and how much is empty

At 1440x900, over twelve screens of his home page, text covers **4–27% of each screen, median 11%**; the rest
is space or one image. A typical screen is **one headline, one paragraph, and at most one small table or one
pair of cards**. At 390 each screen holds one of those things, never two. One idea per screen.

### What this asks of every page here

- Few elements, generous space, one idea per screen.
- Motion only where it carries meaning (arrival, a change of state, a page ending), on the two curves above, at
  the durations above. Transform and opacity only. Hold 60 fps. An animation that is not as good as his is cut,
  not kept.
- Each page keeps its own palette and motif; the restraint and the motion quality are shared.
