# The site's design

Read this before restyling any page. It records the reference the whole site is held to (section 1), the
page order and how one page carries to the next (2), each page's theme (3), the shared grid, type scale and
header (4), where things live in the code (5), and the standing rules (6).

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

## 2. The pages, in order

The site reads as four pages in sequence, each its own HTML document and URL:

**home** (`/`) → **run** (`/run.html`) → **docs** (`/docs.html`) → **Sancho** (`/sancho.html`)

Scrolling past the end of one carries the visitor to the next; scrolling up from the top goes back and lands
at the previous page's end. Outside the chain, reached by links: **demo** (`/demo.html`, from home's call to
action and the run page's "Try it on three bundled searches"), **viewer** (`/viewer.html`, from Sancho),
**result** (a demo verdict on its own page), **share**, **privacy**, **terms**, **404**.

### The carry (src/chain.ts, public/carry.js, src/styles/chain.css)

- Reading scroll is the browser's own on every page. Nothing intercepts the wheel within a page.
- A carry fires only at the very end of a page (or the very top, going back). It arms once the page is there
  **and** the wheel has gone quiet for 220 ms, so the momentum of the scroll that reached the end never counts.
  Then it takes one gesture of 40% of the viewport, or a nudge, a pause (250 ms) and another. Touch: a pull of
  30% of the viewport that starts at the edge, carried on release. Keys at the edge: two presses with a pause.
- Each end carries a cue: "Next", "Continue to docs ↓" at the large step, and a hairline that fills with the
  push. It is a plain link (keyboard, no script). At the top, "↑ Back to run" appears while a pull builds,
  and on focus.
- With cross-document view transitions (Chrome, Edge, Safari 18.2+): a navigation that opts in. The old page
  rises off and the new rises in as one scroll, 1.0 s on `cubic-bezier(.35, 0, 0, 1)`, transform only, on the
  compositor. The header holds still and cross-fades its colours. `carry.js` (classic, render-blocking in each
  chain page's `<head>`) reads the direction before the first frame. A `<link rel="expect" href="#chain-end"
  blocking="render">` holds that frame until the page is parsed, so a carry upward can land at the end.
- Without them (the fallback, in any browser that lacks them): a cover in the next page's ground slides over this page (0.6 s,
  same curve), the browser navigates, and the next page starts under its own ground and fades it off. No white
  flash. `?carry=fallback` on any chain page forces this path for testing.
- Reduced motion: the same gesture, then an immediate navigation. Header links and Back are plain navigations
  with no transition.
- The rest of the gesture that made a carry (a trackpad's momentum) must not scroll the page it lands on:
  `carry.js` swallows wheel events while they keep coming, for at most 1.2 s; the first 220 ms pause ends it.
- `CHAIN` in `src/chain.ts` lists the pages in order with each one's ground colour, which must equal that
  theme's `--ground` (the browser check holds them equal).

## 3. One look per page

Every page sets `<html data-theme="…">` and imports one token block from `src/styles/<theme>.css`. Shared
components read only semantic tokens (`--ground`, `--ink`, `--muted`, `--faint`, `--rule`, `--header-bg`,
`--accent`, `--focus`, `--field`, `--field-line`, `--problem`, `--tree`, `--tree-path`, `--tree-bar`). Each page's
session restyles its own theme; the run, docs, Sancho and viewer tokens set here are interim.

- **home**: paper and dark green; the search drawn as a grove of birches beside the overview, their turned
  leaves falling. The headline and the brand mark are Bricolage Grotesque at its heavy weight, and nothing
  else is. One complete screen at every size: the copy in columns 1–6, read as one block from the top (the
  open paper under it is where the leaves land); the grove in 7–12; a hairline ground across the grid with
  ticks on the edges and the centre line; a mono legend under it. All the copy has arrived within a second;
  the cue to the run page starts at the fold. Below 813 px the same parts stack: headline, reading, grove,
  ground. No tree is drawn behind text; every tree is inside its box with its foot on the ground line.
  - **The birches** (`src/birch.ts`): one per restart, its height its best in-sample Sharpe; one branch per
    move and feature family, in search order from the crown's top, spaced by the twigs they carry; one twig
    per evaluation; 1 to 3 leaves on a twig by its rule's Sharpe. A pale trunk with dark bark marks,
    narrowing into the leader, which ends inside a narrow oval crown; steep branches whose tips turn out;
    short sprigs that droop at the tip. Weight falls from trunk to branch to twig to leaf. No stroke crosses
    another within a tree. Bark, jitter and leaf placement are decoration and claim nothing.
  - **Placed at build time**: `scripts/make_grove.mjs` runs the placement search and writes
    `public/examples/grove.json` (checked in the build with `--check`); the page only scales and positions
    the drawings (`drawGrove` in `src/woods.ts`). Nothing searches in the visitor's browser.
  - **Desktop grove**: every restart, in search order; the even ones in front, spaced so no two front crowns
    meet; the odd ones a row behind, smaller, finer and lighter, standing between the front trunks; a 3 px
    knockout in the paper's colour under every front stroke keeps the front trees clean. **Phone grove**:
    its own two trees (the best restarts), larger and wider-crowned; the legend says "2 of 8 restarts".
  - **Colour**: leaves on the trees are three greens (lighter in the back row); the falling and fallen leaves
    are the same birch leaf in three ochres, the page's only warm accent. Few and small, depth from size and
    opacity, a slow fall, a light cursor wind; they leave from the trees' leaves, lie along the ground line
    one deep and fade where they fall past its ends.
- **run**: a dark graphite working surface (not night, not neon), pale steel accent. The run's tree drawn flat
  in the page's tokens.
- **docs**: ink on a cool light ground, one ink-blue accent: a page for reading. Privacy, terms, 404 and a
  shared verdict use it too.
- **Sancho**: sand, umber type, a terracotta accent; the desert is its motif. Its session may propose a
  storybook serif for its headings.
- **demo**: the city garden at night in neon tubing (also the result page, which replays a demo verdict). The
  only page with neon, glow or the night palette; `demo.css` is loaded by no other page.
- **viewer**: a light counterpart to the run page: cool off-white, graphite type, hairlines, one muted
  oxidized-copper green. No illustration, no glow. Reached from Sancho; outside the chain.

The run page and the viewer draw a run's tree without the demo's decoration: `makeScene()` without `decor`
draws the tree, its bar and the verdict written on it, flat, in `--tree`, `--tree-path` and `--tree-bar`.

## 4. The grid, the type scale, the header

**Grid** (`src/styles/base.css`, `:root`): side padding `--pad-x` = `max(5vw, 40px)` (72 px at 1440), 25 px up to
812 px wide, 15 px up to 400 px; vertical padding `--pad-y` = `clamp(30px, 4vw, 50px)`; 12 columns with gap
`--gap` = 2vw (4vw up to 812 px). Everything hangs off the same left edge as the brand mark: the header, every
page's label and headline, the cue, the footer. The reading measure is `--measure` = 44rem.

**Type scale** (tokens; IBM Plex Sans 400/500 for headings and text, IBM Plex Mono for labels, figures and code):

| token | value | use |
|---|---|---|
| `--t-hero` | `clamp(3.25rem, 10vw, 10rem)` | one word or name per screen |
| `--t-section` | `clamp(2.6rem, 8vw, 8rem)` | a section's name |
| `--t-large` | `clamp(2rem, 4vw, 4.5rem)` | a page's headline; the cue; a big number |
| `--t-medium` | `clamp(1.6rem, 3vw, 3.25rem)` | the verdict word on a drawing |
| `--t-small` | `clamp(1.3rem, 2vw, 2.25rem)` | a section heading in a long page |
| `--t-lead` | `clamp(1.125rem, 1.5vw, 1.6rem)` | the one paragraph that leads |
| `--t-body` | `clamp(1rem, 1.2vw, 1.125rem)` | reading text, line-height 1.5 |
| `--t-label` | `clamp(0.75rem, 0.9vw, 0.875rem)` | header links, captions, uppercase |
| `--t-micro` | `0.6875rem` | mono labels, uppercase, tracked 0.14em |

No bold except the home headline and the brand mark; emphasis is weight 500.

**Motion tokens**: `--ease-travel` = `cubic-bezier(.35, 0, 0, 1)`, `--ease-ui` = `cubic-bezier(.4, 0, .1, 1)`,
`--dur-page` 1000 ms, `--dur-enter` 700 ms, `--dur-ui` 350 ms, `--dur-colour` 450 ms.

**Header**: the same markup on every page, coloured only by tokens. The brand on the grid's left edge (columns
1–3), Run · Docs · Sancho · Paper starting on column 7 (the grid's centre line, where the home page's grove
starts), the author, Contact (a mailto link; the address is never
printed) and LinkedIn on the right edge (columns 9–12). Links roll on hover (the label out of its mask, a copy
in after it: `--dur-ui`, `--ease-ui`); the current page is underlined. Below 1241 px the name leaves the header,
below 901 px LinkedIn too, so the links never crowd (checked from 813 to 1920 px); below 812 px Paper also
moves to the footer (which carries the author's line on every page); Contact stays in the header at every width.

## 5. Where things live

| file | what |
|---|---|
| `src/styles/base.css` | fonts, grid, type and motion tokens, header, footer, shared components, the flat tree |
| `src/styles/<theme>.css` | one token block per page, and that page's own rules |
| `src/styles/chain.css` | the carry's transitions, cue and fallback cover (chain pages only) |
| `src/chain.ts`, `public/carry.js` | the leaving and arriving halves of a carry |
| `src/scene.ts` | a run's tree in a section; the demo's decoration only with `decor` |
| `src/pages/<page>.ts` | each page's script; it imports `../common` first, then its theme |

## 6. Standing rules

- The CSP stays as strict as it is: no inline styles or scripts. Positions and per-element values go through
  CSSOM custom properties (`el.style.setProperty`), as now. `scripts/check_dist.mjs` enforces it.
- No new runtime dependency without asking; any package pinned to a version at least two weeks old.
- Everything decorative is drawn in code and reads no number from the gate; anything that shows a number shows
  the real one.
- Reduced motion gets a still, complete page.
- Don't touch the gate, the worker, the Python wheel, the examples or any verdict text.
- Keyboard access and focus states survive every change.
- Nothing neon outside the demo.
- Every page meets the standard in section 1: few elements, generous space, one idea per screen, transform and
  opacity only, 60 fps, and any animation not as good as lukres.dev's is cut.

## 7. Open items for the last session (before merge)

- **One cross-browser pass, Firefox included.** Walk the chain both ways in Firefox (the fallback path: cover,
  navigation, uncover) at 1440x900 and 390x844, with every page's shots, and again in Safari and Chrome.
  Firefox is not yet installed on the development machine; drive it with geckodriver.
- **Run the equivalence script**, `node scripts/equivalence.mjs --python python3`: the gate, worker, wheel and
  examples were not touched by the revamp, and this confirms it.
- The empty tree area on the run page and the viewer before a run is loaded: settled in those pages' sessions.
- The run, docs, Sancho and viewer colours are interim until each page's session.
