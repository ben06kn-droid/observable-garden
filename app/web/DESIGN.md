# The site's design

Read this before restyling any page. It records the reference the whole site is held to (section 1), the
page order and how the chain's five sections work as one document behind a loading screen (2), each page's theme (3),
the shared grid, type scale and menu (4), where things live in the code (5), the standing rules (6) and what is
still open (7).

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
- **Page to page** is a curtain, and slow: see "Moving from one part to the next", below.

### Moving from one part to the next, frame by frame (measured 2026-11-17)

Recorded in Chrome 157 at 1440x900, 60 Hz (a screenshot of every compositor frame from the trace, and each
frame's element positions logged in the page), driven by a trackpad-like wheel: events every 16.7 ms, a
quick ramp to a peak, momentum decaying by 0.9 to 0.88 per event. Read alongside his script bundle, which
gives the exact formulas the frames show. Frame sheets: `screenshots/lukres/`.

**Selected Work → Recognition (the "proof" section)**

- **Trigger: none.** This is not a page change: Recognition is the next section of the same document, and
  the move is ordinary (eased) scrolling. No threshold, nothing plays on its own. Stop the wheel halfway and
  everything stops halfway (measured: the ground held at a mid grey, rgb(114,115,119), while the wheel rested).
- **The motion follows the wheel**, 1:1 in distance, through his eased scroll: content lags the wheel by up
  to about 80 px during a swipe and settles about 0.4 s after the last event (`1 − e^(−12·dt)` per frame;
  never overshoots).
- **What moves.** The content scrolls up as one; nothing is masked, scaled or cross-faded at the boundary.
  Three things are tied to the scroll position:
  - the ground sweeps from off-white (rgb(238,241,248)) to black, linearly, while Recognition's top moves
    from 585 px to 248 px below the top of the viewport (337 px of scroll, 0.37 of the viewport's height);
  - a huge "PROOF OF WORK" title (WebGL, behind the content) scrolls up with the section, solid black on
    the light ground and turning to an outline as the ground darkens;
  - nothing else: no parallax on the reading content.
- **Entrances on their own clocks.** Each block's entrance starts when its top reaches the bottom of the
  viewport and plays at real time (1 s per s), and runs backwards if the block goes back below the fold:
  heading characters rise from 100% and turn from 30° to rest over 0.7 s on expo-out, 40 ms apart; the
  section number's digits 50 ms apart; each row's hairline draws (scaleX 0 → 1) over 0.8 s from 0.2 s,
  expo-out; each row's words rise out of masks over 0.8 s, staggered 100 ms by column, 50 ms by line,
  20 ms by word.
- **Header**: fixed, never moves or fades, no background. Its text turns white when the sweep is half done
  (a class toggle, not scrubbed) with `transition: color .25s` (the logo 0.5 s).

**Recognition (Education, the proof's last block) → "What I build with"**

- **Trigger: none**, again one document and ordinary scrolling.
- **The ground** goes from black to blue (rgb(26,46,241)), linearly, from the moment the section's top
  enters at the bottom of the viewport until it has travelled a quarter of (viewport + section height):
  about 1,190 px here, 1.3 viewports (the section is tall; its cards are pinned while they play). The last
  proof block therefore already reads navy (rgb(8,12,60)) as the section enters.
- **The title** "WHAT I / BUILD WITH" plays on a clock that runs only while it is on screen: the first two
  words rise from 100% over 1.0 s on `cubic-bezier(.35, 0, 0, 1)`, 100 ms apart; the last two drop in from
  −100% and then slide sideways into line between 1 and 2 s. The previous section's giant outlined words
  change colour over the first quarter of the sweep.
- **The cards are scrubbed by scroll**: they spread from a stack into a fan (expo-out), flip 180° → 0
  (back-in-out, staggered) and tilt, all mapped to the section's position, with a small wobble on time;
  the pinned card row drifts with a gentle parallax.
- **Header**: unchanged (white, still, no background).

**The end of the page → the projects page (his only real page change)**

- **Trigger: time, not distance.** At the very end (within 5 px), a bar under "NEXT PAGE" fills at 2 per
  second for as long as wheel input keeps arriving (any downward delta counts), holds for 0.3 s after each
  event, drains at 5/s on an upward scroll and 0.2/s when idle. Measured: one swipe filled it in 0.53 s.
  The scroll that arrives at the end is not excluded; it counts as soon as the page is at its end.
- **Then it plays on its own** and is slow: the route changes; the old page holds still for about 0.45 s; a
  black diagonal shutter closes from two corners, turning, in about 0.25 s, into an L-shaped window (his
  logo) that shrinks to nothing; on a first visit a pixel "LOADING" plays until the page's assets arrive
  (2.2 s here); then the L grows and turns to reveal the new page through it in about 0.4 s, while the new
  title's letters rise and tilt in. 3.5 s in all on a cold visit. The header is covered by the curtain.
- **Shared by all three**: transform and opacity only, 60 fps (median frame 16.6 ms; one frame in 230 over
  34 ms, during the first sweep).

**What this means for the chain here.** The two moves that feel effortless on his site are not transitions
at all: the next thing is already on the page, and scrolling simply continues into it while the ground's
colour is scrubbed by the scroll. His one real page change is a curtain with a loading screen, triggered by
half a second of pushing, and it is the slowest thing on his site. Here the four chain pages are therefore one
document (section 2): scrolling simply continues from one into the next while the ground's colour is scrubbed by
the scroll, as on his site. Two deliberate differences: the scroll is the browser's own, not his eased wheel; and
his site does not respond to `prefers-reduced-motion` at all. Ours does, and must.

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

## 2. The pages, in order: one document

The chain's five sections are one document, built once behind a loading screen and kept alive:

**home** (`/`) → **run** (`/run.html`) → **docs** (`/docs.html`) → **Sancho** (`/sancho.html`) → **Eucalyptus**
(`/eucalyptus.html`; a section since 2026-11-18, it had been a page of its own)

Each is a section of that document with its own address. Scrolling simply continues from one into the next. Outside
the chain, separate documents reached by links: **demo** (`/demo.html`, from the run section's "Try it on three bundled searches" only; home does
not link to it), **viewer** (`/viewer.html`, from Sancho), **result** (a demo
verdict on its own page), **share**, **privacy**, **terms**, **404**, and **loader** (`/loader.html`, the loading
screen on its own with a simulated load, for review).

(Until 2026-11-17 the four were separate documents joined by a "carry": a gesture at a page's end and a
cross-document view transition. That work stays on the `site-revamp` branch; it is retired here.)

### How the document is built (vite.config.ts, src/onepage/)

- `index.html`, `run.html`, `docs.html`, `sancho.html` and `eucalyptus.html` are five shells of the same document. Each has its own
  `<title>`, description and `data-start` (the section it opens on), the early script `public/loader-early.js`,
  the loading screen's stylesheet, the one module `src/onepage/main.ts`, and a `<!-- onepage -->` marker.
- The `onepage()` plugin in `vite.config.ts` replaces the marker at build time with, in order: the loading
  screen's markup (`LOADER`, from `src/loader-mark.ts`, so it is on screen from the first frame);
  `src/onepage/header.html` (the skip link and the menu); one backdrop per section (`.backdrops`); and
  `<main>` holding `src/onepage/{home,run,docs,sancho}.html`. `SECTIONS` in the plugin is the order.
- `src/onepage/main.ts` imports `common`, then `boot.ts` (so the loading screen and the work count exist before
  any section registers work), then each section's script in page order (`src/pages/index.ts`, `run.ts`,
  `docs.ts`, `sancho.ts`), then calls `start()`.

### Sections (src/onepage/*.html)

- Each section is `<div class="section" data-section="…" data-theme="…" data-path="…" data-title="…">`, and docs
  and Sancho also carry `data-page` (their shared glass structure, section 3). What was each page's `<main>` is
  a `div` inside it (`run-main`, `docs-main`, `sancho-main`): the document has one `<main>`.
- Each section ends with one small cue, `<a class="cue" href="next">Continue ↓</a>` (mono, micro size,
  uppercase, muted): the way on for the keyboard and a click. There is no other seam: no gap, rule or
  heading between sections. Only Eucalyptus, the last section, has the footer (Sancho's ends with the cue).
- `boot.ts`'s `snap()` starts every section on a whole pixel (it adds under 1 px of `margin-top` where needed,
  again whenever the first section resizes), so each renders exactly as its page did.
- `.section` takes over what `<body>` gave each page (colour, body type) and clips anything reaching past the
  screen's sides (`overflow-x: clip`, not `hidden`, so the docs contents stay sticky). On a phone the docs and
  Sancho sections are positioned, so the clouds and the dusk band are placed from the section, as they were from
  their page (`src/styles/onepage.css`).
- A section's script finds its own elements under `section("name")` (exported by `boot.ts`), never document-wide,
  since every section's markup is in the one document.

### Themes

- A theme applies to whatever carries `data-theme`: a section, its backdrop, the menu's wrapper, or `<html>` on
  the separate pages. Each theme's block in `src/styles/<theme>.css` is written `[data-theme="…"]`, never
  `html[data-theme]`, so it works in all four places. Rules that were `[data-theme="x"] body` on a page are
  matched by `.section` too where the section needs them.
- The menu sits in `<div class="top-theme">`. `boot.ts` gives that wrapper the theme (and `data-page`) of the
  section that leads at the moment, so the menu's type changes with the sections; its colours are mixed separately
  (below). Its ground is `var(--header-bg)`, set per theme, docs and Sancho included.
- The run section's light/dark inversion (`data-hg` on the section, mirrored on the run backdrop) calls
  `refreshThemes()`, so the menu mixes from the inverted colours.

### Backdrops and the scroll crossfade (src/onepage/boot.ts, src/styles/onepage.css)

- One fixed backdrop per section, behind everything (`z-index: -2`), each in its theme's `--ground`; the body
  is transparent. The first is always fully there; each next one fades in on top.
- **The crossfade is tied to scroll position, not time**, as on lukres.dev (section 1): a backdrop's opacity
  goes linearly from 0 to 1 while its section's top rises from 65% to 27.6% of the viewport's height (`BAND`;
  his 585 to 248 px at 900). Scrolling back reverses it exactly. Opacity only.
- **The menu** mixes its colours (`--header-bg`, `--ink`, `--muted`, `--rule`) between the two sections'
  values by the same share, and takes the new section's theme half way through the band. Each section's values are
  read from its backdrop (`refreshThemes()`) when `start()` runs, after every section's script and stylesheet: read
  any earlier (under the dev server a section's styles arrive with its script), they came out transparent and the
  header vanished.
- `scrub()` runs at most once per animation frame, from passive `scroll` and `resize` listeners. It writes only
  opacities and the header's custom properties, and reads only section rectangles.
- Reduced motion: the same position-based crossfade (it moves only as the reader scrolls, so it is not an
  animation); links jump instead of scrolling smoothly.

### Scenes

- Every scene is built once, behind the loading screen, and kept: the home grove and its leaves, the run
  section's glass, hero layer and fan, the docs sky, the Sancho dusk.
- The docs sky (`src/sky.ts`) and the Sancho dusk (`src/dusk.ts`) are canvases inside their section's
  **backdrop**, so they fade in with it. They draw only while that backdrop can be seen (`onBackdrop()` →
  `setActive()`): from when it starts fading in until the next backdrop fully covers it. The sky reads its colours
  from its own canvas (the docs theme), not from `<html>`. On a phone the dusk is instead a band at the top of
  the Sancho section, scrolling with it, as at the top of its page.
- Home's leaves pause while home is off screen (`inView("home")`); the run section's glass pauses through its own
  IntersectionObserver and the fan when its region is off screen; the home grove is drawn finished, with no
  arrival animation (it is already there beneath the loading screen).
- `onView(name, f)` and `inView(name)` in `boot.ts` report whether a section is on screen, for any other scene.

### Addresses and history (src/onepage/boot.ts)

- Each section's address and title are its `data-path` and `data-title`. As the reader scrolls, the address, the
  title and the menu's current item (`aria-current`) follow the section under the middle of the screen, with
  `history.replaceState`: scrolling adds no history.
- A same-origin link to a section's address (the menu's items, a cue, a link in the text) is caught: a smooth
  scroll to the section, one `pushState` entry, and focus moved to the section (`tabindex="-1"`, no ring), so the
  next Tab continues from there. A link with an anchor (`/docs.html#tracing`) pushes the section's address with
  the anchor and scrolls to the heading. While such a scroll is under way the address is left alone (`steering`).
- Back and Forward (`popstate`) jump to the entry's section, and anchor.
- A direct link to any of the five addresses opens on its section (and anchor), behind the loading screen:
  `history.scrollRestoration` is manual, and the jump is made once the layout is final, before the screen goes.
- Links out of the chain (demo, viewer, Eucalyptus, the paper) are plain navigations.

### The loading screen (src/loader.ts, src/loader-mark.ts, src/styles/loader.css, public/loader-early.js)

- White, with a navy-blue mark centred and a box bottom left. The mark: a ring draws itself clockwise from the top
  (0–400 ms), a line cuts across it (400–700 ms), and its two halves each turn a quarter about the ring's
  rightmost point while the line turns upright and grows into the spine, forming a B 224 px tall (700–1500 ms);
  the whole mark slides 78 px left so the B ends centred, and the ink deepens from #1f4fd8 to #0b1f4b. Stroke 16
  throughout; every step on `cubic-bezier(.35, 0, 0, 1)`; SVG and CSS only.
- The box: a rectangular prism (face 56 × 384, depth drawn up and to the right, sharp mitred corners), filling
  with solid black from the bottom in proportion to the work really done. The level only rises and eases toward
  the share done (about 0.3 s to close a gap).
- **The counter** (2026-11-18; `src/loader-mark.ts`, `loader.ts`): to the right of the box, 12 px from its outline,
  the digits' foot level with the box's foot: the percent loaded in block numerals (a 5 x 7 grid of 4 px squares,
  like a pixel display, drawn as one SVG path; 28 px tall, solid black) and a "%" in the same blocks. Three
  fixed-width cells, right aligned, so nothing moves sideways from one digit to three. It is the fill's own eased
  value as a whole number (rounded down): it only rises, the two always agree, and it reads 100 exactly when the
  box is full (checked on `loader.html`: 35 samples through a load). It leaves with the screen, and shows on the
  short version too. The screen is one `progressbar` whose `aria-valuenow` and `aria-valuetext` ("57%") are that
  number. Reduced motion: it updates without smoothing, as the fill does.
- **The work** (`task()` in `boot.ts`): each section's script registers what must be done before it can be
  shown (home: the grove's data and its drawing; run: the glass, hero layer and fan with their first frames;
  docs: the sky; Sancho: the dusk), plus the fonts. The files fetched before any script ran count as already done.
  So the box jumps to most of the way at once and the rest fills as the scenes are built. It is never full while
  work remains.
- **The exit**: once the B has formed (the drawing's own animations played to their end: ring, cut and fold, the
  minimum time; 2026-11-18, a timer from the page's start had cut the fold short by 100-380 ms), then held 0.4 s,
  **and** the box is full, the open section is
  scrolled into place, two frames pass (every scene's first frame is on screen beneath), and the whole screen
  slides up off the page (600 ms, the same curve). A first visit reveals at about 2.1 s when the work is done
  sooner; it never waits on work nobody can see yet (Pyodide, below). Performance marks `qx-work-done` and
  `qx-revealed` time it.
- **Later in the session** (back from the demo, the viewer or Eucalyptus with a rebuild): `sessionStorage`
  `qx-loader-seen` is set when the screen first goes. `public/loader-early.js`, a classic render-blocking script,
  then sets `<html data-loader="formed">` before the first frame: the finished B is drawn at once, there is no
  minimum time, the box does not ease, and the screen goes as soon as the rebuild is done.
- Reduced motion: a still navy B and the box, then a plain cut to the site.
- `loader.html` (`src/pages/loader-preview.ts`) shows the screen alone over a simulated load.

### Pyodide on demand (src/pages/run.ts)

The gate (Pyodide and the package, about 23 MB, in a worker) is never loaded behind the loading screen, and
never for a visitor who only scrolls past the run section. It starts when the run form is on screen and the page
has been still for 0.8 s and then idle, or at once when a field in the form takes focus or Start is pressed. Start pressed
before it has loaded runs as soon as the gate and the bundled inputs are in. Marks: `qx-gate-start:<view|focus|start>`,
`qx-gate-ready`, `qx-gate-inputs`. The two lines the gate fills in when it arrives (the inputs' summary, the
class table's size) have their room from the start, so its arrival never moves the form or rebuilds the glass.

### Checks and measurement

- `scripts/browser_check.mjs` checks the one page in headless Chrome at 1440x900 and 1366x768:
  - a first visit and a later one;
  - each address as a direct link (it opens on its section, with its title and current link);
  - the address following the scroll through all five sections without adding history;
  - header links, Back, the cue by click and by Enter (focus moves to the section);
  - a docs contents link;
  - Pyodide on demand: not loaded for a visitor who scrolls past, loaded when the form is on screen;
  - out to the demo (from run) and Back: the page kept, on its section (`out_and_back`); home's Eucalyptus line
    scrolls to the last section, which holds its two lines and the footer, in its theme, with no canvas
    (`eucalyptus_section`).

  `--run-page` runs the run form against the mock providers.
- `scripts/reference.mjs` takes reference shots of each section (top, middle, end; 1440x900 and 390x844) and
  compares two sets, allowing for anti-aliasing. `--at DIR` shoots at another set's offsets, so a section whose
  length changed is still compared content for content.
- `scripts/onepage_measure.mjs` measures with real trackpad input (`scripts/carry/swipe.swift`) in Chrome or
  Safari, with nothing attached to the browser: time behind the loading screen, frame times across each boundary,
  and memory (with `--baseline DIST`, against a multi-page build). `scripts/freeze_trace.mjs` catches long frames
  across the run/docs boundary with a Chrome trace of each.

## 3. One look per page

Every page has a theme: the chain's sections set it on themselves (`data-theme` on the section, section 2), every
other page on `<html data-theme="…">`. Each imports one token block from `src/styles/<theme>.css`. Shared
components read only semantic tokens (`--ground`, `--ink`, `--muted`, `--faint`, `--rule`, `--header-bg`,
`--accent`, `--focus`, `--field`, `--field-line`, `--problem`, `--tree`, `--tree-path`, `--tree-bar`). Each page's
session restyles its own theme; the run, docs, Sancho and viewer tokens set here are interim.

- **home**: paper and dark green; the search drawn as a grove of birches beside the overview, their turned
  leaves falling. The headline and the brand mark are Bricolage Grotesque at its heavy weight, and nothing
  else is. One complete screen at every size: the copy in columns 1–6, read as one block from the top (the
  open paper under it is where the leaves land); the grove in 7–12; a hairline ground across the grid with
  ticks on the edges and the centre line. The copy (2026-11-18): under the title, "Did the
  agent find an edge, or just search long enough?"; one paragraph (what a search's best backtest is and what
  Quixote does); one line of links ("Run it on your own search, read the docs, or read the paper."); then one larger
  line in the body face at 1.5 times the body size, "**Eucalyptus**, coming soon: the same test for agents that
  search raw data freely.", the whole line a link to `eucalyptus.html` (2.25 body-em below the copy; 1.4 on a
  phone). Nothing is written under the ground line. The paragraph and the links line are in `--paper-text`
  (#2d2e24, 11.1:1), darker than the muted tone, under the headline's ink. Home has no link to the demo. All the copy has arrived within a second;
  the cue to the run page starts at the fold. Below 813 px the same parts stack: headline, reading, grove,
  ground (on the phone the grove runs past the first screen). No tree is drawn behind text; every tree is
  inside its box with its foot on the ground line.
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
    three of the same trees at the same proportions (the restarts with the best Sharpe: two in front, one
    behind), laid out the same way in a taller grove; the headline, the copy and the tree tops are on the
    first screen and the ground line may fall below the fold; nothing is written under it.
  - **The trees do not respond to clicks** (2026-11-18), here or on the demo: no sway, not buttons, no pointer
    cursor. On the demo the run's tree alone is clickable, to open the run, and it does not shake.
  - **Colour**: leaves on the trees are three greens (lighter in the back row); the falling and fallen leaves
    are the same birch leaf in three ochres, the page's only warm accent. Few and small, depth from size and
    opacity, a slow fall, a light cursor wind; they leave from the trees' leaves, lie along the ground line
    one deep and fade where they fall past its ends.
- **run**: lukres.dev's near-black (#121416) and off-white (#f0f1fa), hairline rules, and one warm sand
  (#d6b27b) for the glass's sand, the gold paths and the one accent (Start, the submitted branch, focus).
  No glows, halos or gradients. Three things are on the page: the glass, the fan of paths and the form.
  - **Desktop**: on the 12-column grid. The hero, the form, the result's scale and the moves sit in columns 1–8;
    each form section (01 Data, 02 Model, 03 Key, 04 Budget) has its name in 1–2 and its fields in 3–8.
  - **The glass** (src/glass.ts): a still hourglass drawn as its two outline curves, no frame. Each wall
    widens from a round neck all the way to its rim (the half width never decreases away from the neck),
    so each bulb is widest at its open rim. It stands in columns 9–12 from the opening screen to the rule
    above 03 Key and scrolls with the page; its bulbs clear the form's columns and may be cropped by the
    page's right edge. Through it pours an abstract flow: fine strokes of varying length and a few small
    shapes, entering across the top rim, drawn together through the neck along streamlines (each a fixed
    fraction of the half width, so nothing crosses a wall) and spreading out to leave at the bottom rim.
    Nothing collects; it runs at one steady rate from the first frame, quicker where the glass is narrow,
    and nothing about it changes with the scroll. White with about one gold stroke in eight; where the
    strokes crowd into the neck each is drawn fainter, so it stays a bundle of lines. The headline's last
    letters pass through the upper bulb (drawn by the hero layer, below).
  - **The cursor in the glass** (src/glass.ts, 2026-11-18): a smooth, round obstacle in the stream. Every stroke
    within 140px is moved straight away from the cursor by an amount set only by its distance (22px at the
    cursor, `22·(1 − (d/140)²)²`, nothing at 140px). The push is an offset added when a stroke is drawn, kept at
    five points along it: it never changes where a stroke is on its streamline or how fast it goes, and never
    accumulates. Each offset eases in quickly (60 ms) and back to zero with a 120 ms time constant (about 500 ms,
    no overshoot); under a hundredth of a pixel it is exactly zero (checked: two seconds after the cursor
    leaves, the largest offset is 0). Pushed strokes and shapes are held inside the outline. A pushed stroke
    turns the wake's silver-white tone and takes fine red fringes, in proportion to how far it actually moves
    (one pressed against a wall barely moves and barely changes). Only cursor movement, a fine pointer and
    motion allowed. Cost: about 0.1 ms a frame in Chrome while the cursor is near; in Safari at 1440x900 frame
    times with the cursor sweeping the glass matched those before (median 54–55 ms against 53 ms, p95 58–59 ms
    against 57–77 ms; this machine's Safari ran the run section at about 18 fps either way).
  - **The hero layer** (src/hero.ts): on a desktop with motion, the opening text (down to 01 Data) and the
    glass are drawn in one WebGL canvas that scrolls with the page; the page's own text stays, transparent,
    for selection, search and screen readers. Through the glass the headline is seen gently magnified
    toward the middle and compressed toward the walls, with no change of height (the letters stay on their
    line), each colour channel bent a little differently; the glass's flow fades across the letters. The
    cursor's wake never moves the letters or the glass's outline: in the blank space around them it shows
    as a glossy trace (a soft highlight toward an upper-left light, a faint shade, a hairline red rim;
    drawn by the fan's pass so it runs the whole page, never under a field). It follows the cursor 70 ms
    behind on purpose, and its strength rises steeply with the cursor's speed (a slow drift barely stirs it).
    Inside the glass the cursor pushes the strokes aside instead (above); the hero layer runs no fluid of its
    own. Phones and reduced motion keep the plain page text and a glass without the lens.
  - **The other mode, and the switch** (2026-11-18): inside its outline the glass is the page's other colour mode:
    on the dark page a light ground (`--hg-inside` #dcdee5, the light ground pushed a little toward grey) with the
    flow in the light palette's line, tone and fringe colours; on the light page the dark ground and the dark
    palette's. Gold strokes stay the page's gold; the outline stays the page's line colour. The headline where it
    passes through the upper bulb takes the inside's ink, so it changes as it enters (13.7:1 inside on the dark page,
    16.4:1 on the light; 16.4:1 outside). The colours are read from a hidden element carrying the other mode, so they
    are the stylesheet's own.
    - The switch: a 28 px line icon at the neck, a sun while the page is dark and a moon while it is light, on a
      40 px disc of the page's ground (16.4:1), a real button (Tab, Enter, Space; "Switch to light mode" / "Switch
      to dark mode"; 44 px on a phone). Clicking it switches the page: the new palette spreads from the neck as a
      growing circle (1 s), after which the glass holds the mode just left; the mark changes at the midpoint (its own
      view-transition group). Clicking elsewhere on the glass does nothing. Reduced motion: an instant change.
    - The preview: while the cursor is over the glass or the mark, the inside's ground leaks about 40 px out from
      the neck with a soft edge, under any text (none is near), and draws back within 300 ms (the hero layer;
      none on a phone or under reduced motion).
    - The mode lasts for the visit (sessionStorage `qx-hg-mode`): scrolling away and back, or returning from the
      demo, keeps it. Frame rate: Chrome 60 fps with the cursor in the glass, as before; Safari 53-56 ms against
      52-53 ms before (two clean pairs; within this machine's run-to-run spread).
  - **The fan** (src/fan.ts): random-walk hairlines down the whole left of the page, from the top to above
    "Continue to docs", behind everything. They run right until the glass (beside it) or the page's right
    edge (below it), fading before it. The fan's canvas sits in the page (the viewport and a margin above and
    below, re-anchored to the scroll as it draws), so it scrolls with the text and never drifts from it. Most are faint off-white; about one in six is gold. They draw left
    to right at a pace that follows the scroll and eases to an idle; at the foot they slow and rest. Behind
    text they dim to 6% (7:1 holds for every text tone over a gold path, both palettes); under
    inputs, selects, text areas and buttons they are removed.
  - **Phone**: composed for itself. Headline, lead, a smaller glass, then the sections stacked; the fan is
    a band between the form and the tree.
  - **Form**: a short lead, with the long paragraph word for word in a details disclosure. File pickers keep
    the native input (unseen, focusable) under a label showing the loaded file's name. Errors appear inline
    above Start. The disclaimers are one row of four notes at the end.
  - **Reduced motion**: one still frame of the glass's flow (the headline wraps clear of the glass); the
    fan still.
  - **Reading face**: body, label and small text in Inter (variable, 450), self-hosted, latin subset; IBM
    Plex Sans stays for the headline and the large words, IBM Plex Mono for labels in capitals. Muted and faint text were brightened so
    every text tone keeps 7.8:1 or more where a path passes behind it (the fan dims to 6% behind text).
  - **Scrolling**: native only. Every scroll, wheel and touch listener is passive. Animation runs from
    animation frames; the glass pauses off screen; nothing forces layout in a scroll. The gate loads on demand
    (section 2, "Pyodide on demand").
  - **No tree on this page**: the run's tree is drawn on the home and demo pages only. Before a run nothing
    sits between Start and the moves; during a run a counter above the moves says how far the search has
    come ("move 5 of 12", then the replay's count); after it, the result area shows the gate's numbers on
    a scale (src/runscale.ts), drawn large across columns 1–8: the bar (dotted), the submitted level, the
    p-value line, and the verdict word large at its top. The scale runs from zero (or the lowest value
    shown) to just above the highest, as before; no number or verdict text changed.
  - **Verdict and moves**: the verdict line is large. The reasons are reading text in a disclosure, open on
    a desktop and closed on a phone. Each move is a block; a refused one has a red rule and a "refused" tag.
- **docs**: ink on a cool light ground, one ink-blue accent: a page for reading. Privacy, terms, 404 and a
  shared verdict use it too.
- **Sancho** (approved 2026-11-17): the docs page's pattern at dusk. A plain, rich backdrop fixed to the viewport,
  one object in the margin, the shared cursor tail, and clean content on a sheet. `docs.css` supplies the
  structure (the grid, the title on the backdrop, the sheet, the panels, the tables, the copy button);
  `sancho.css` holds only warm values.
  - **The backdrop** (src/dusk.ts, one canvas): a deep red sunset as one vertical gradient (#1E0708 at 0%,
    #4A1012 at 30%, #7E1D16 at 55%, #B23A1C at the horizon, 72%; #3A0F0E directly below it at 73% to #1C0606),
    one soft glow where the sun has just set (#E8782E at 30%, about 60vh across, centred on the horizon at 70%
    across; a third as strong below the horizon) and a hairline along the horizon (#E8782E at 35%). No other
    shapes, no grain.
  - **The windmill**, the page's one object: a loose ink drawing of a traditional four-sail mill, eleven brush
    strokes (leaning strokes for the body, a cap, the ground, a door; four crossed strokes for the sails; the
    hub), each thick to thin with dry-brush gaps and uneven ends, in #14070A, a silhouette against the glow.
    About 16% of the viewport high, standing on the horizon in the right margin (84% across), clear of the
    sheet. The sails turn as one: a turn in 14 s; in 3 s while the tail passes within 200px of the hub,
    easing back over about 4 s.
  - **Heat**, subtle: the horizon, the glow and the windmill's lower half waver by 1.5px sideways, rising
    slowly (and 0.6px up and down, without which a level line cannot be seen to waver). Nothing is drawn to
    show it.
  - **Light and scroll**: the glow sinks 6vh over the page and the whole backdrop darkens by 15%. Nothing else
    changes.
  - **Content**: the label and title on the backdrop in #F4E8CF; from the first section down everything is on
    one reading sheet (rgba(250,238,220,0.90), radius 16px, a 1px rgba(255,240,220,0.5) border), body text
    #2A1A12, links #6E200F. The contents of the page, the results table, the command (with a copy button)
    and the buttons on flat panels (rgba(120,40,20,0.06), border rgba(120,40,20,0.18)). The header and the
    footer in the sheet's fill. Certified and refused are told apart by a word and a mark (✓ Certified,
    ✕ Refused), never by colour. Long paragraphs are a short lead with the rest, word for word, in a
    disclosure. Measured from screenshots at five scroll positions, 1440x900 and 390x844: body 7.29:1 at worst
    (a link in the results panel), code 10.9:1, header and footer 12.1:1, the title 12.5:1.
  - **Phone**: the backdrop as a band at the top (the gradient, the glow, a small windmill), then the sheet; no
    tail. **Reduced motion**: drawn once, still. 60 fps while scrolling with the tail active (worst frame
    16.8 ms); paused while hidden or off screen.
- **demo**: the city garden at night in neon tubing (also the result page, which replays a demo verdict). The
  only page with neon, glow or the night palette; `demo.css` is loaded by no other page.
- **Eucalyptus** (`src/onepage/eucalyptus.html`, `src/pages/eucalyptus.ts`, `src/styles/eucalyptus.css`;
  2026-11-18): the one page's last section, at `/eucalyptus.html`. Its own theme, a lime ground (#C4F042) with ink
  #14210A. The words "Coming soon" large in the title face (Bricolage 800 at `--t-hero`) on the grid's left edge, a
  small mono caps label "Eucalyptus" above; the menu (the pill in the ground) and the site's footer in the same
  colours; one full screen. Home's last line and the menu scroll to it in place. Sancho's cursor tail, one to one
  (`src/trace.ts`: the same fluid, the same glossy trace and Sancho's own colours, #f2d7a6 / #14070a / #b5391c),
  drawn in its backdrop over the lime, fading out before the title and the footer; on the lime its pale highlight
  is close to the ground, so it reads mostly by its shade and rim. No tail on a phone or under reduced motion.
- **viewer**: a light counterpart to the run page: cool off-white, graphite type, hairlines, one muted
  oxidized-copper green. No illustration, no glow. Reached from Sancho; outside the chain.

### The cursor's wake (src/cursorwake.ts)

The site's signature: the cursor stirs a small fluid, after lukres.dev's cursor effect. One module serves
every page; a page gives it the drawn layer it acts on and its colours from its theme tokens.

- **On the clock** (2026-11-18): the fluid advances by real elapsed time in fixed steps (`step`, 1/60 s by
  default), the cursor's path sampled at each step's own time (one push per step, however many events the browser
  delivers), and each frame draws the state between the last two steps; so the wake is the same at 30, 60 or 120
  frames a second, and a browser keeps drawing at its own rate. It had advanced once per frame by the frame's
  time measured from the end of the last frame's work, capped at 50 ms: slow frames (Safari's: about 36 a second
  on home while the tail ran, about 20 on run) under-counted time, so the tail lived longer there. Calibrated to
  Safari's look as it was: home steps 1/36 s with the fluid at 0.42 of real time (`rate`); run's fan steps 1/20 s.
  Measured with one recorded stroke (area and width of the tail, and the share left at 900 ms): home, Safari before
  56-63k px, 105-138 px, 68-83%; now Chrome 50-52k, 88-98 px, 75-80%, Safari 49k, 99 px, 85%. Docs, Sancho and the
  demo keep 1/60 s and their look (Chrome, before and after, within the measurement's noise).
- **Rules everywhere**: only cursor movement drives it; pressing and dragging do nothing; no response to
  touch; nothing on a phone or under reduced motion; asleep when its layer is off screen or the fluid is
  still; never on text, controls or the header. Its push trails the cursor by 70 ms on purpose, and its
  strength rises steeply with the cursor's speed (a slow drift barely stirs it): the same on every page.
- **Tokens**: `--wake-tone` and `--wake-fringe` (the two colours every page sets), and as a page needs them
  `--wake-hi`, `--wake-shade` (highlight and shade), `--wake-tone-mix`, `--wake-fringe-alpha`, `--wake-gloss`,
  and for a trail `--wake-trail`, `--wake-tint`, `--wake-refract`, `--wake-warp`, `--wake-edge-out`,
  `--wake-edge-in`.
- **Two ways a page draws it**:
  - *Bending* (the run page): a layer that composites its own pixels in WebGL runs the fluid in its own
    context and bends its strokes along the flow, turning them the tone with fine fringes.
  - *A trail* (home, demo): a `WakeLayer` overlay draws a dye laid thinly along the cursor's path and
    carried by the fluid, kept in the page's coordinates (scrolling leaves it in place). It is contoured
    from the moment it is drawn (a slow noise warps its edges before the fluid's curls form), drifts
    slowly and is gone in about a second. It is read as a glossy liquid: what lies under it is seen
    refracted along its slope, tinted, with a highlight toward an upper-left light, a soft shade and
    hairline ripples where it thins; as it ages (0.2–0.5 s) a fine chromatic split comes in at its outer
    edge. Its shape is halfway between the narrow line it first was and the docs tail (2026-11-18): the fluid's
    settings are the midpoints of the two (cell 6.5, flow 0.356, curl 41.6, force 0.8, fade 0.495 s); the dye,
    which docs lacks, is as wide as the midpoint of the line and the docs push (17 + 24·√dose px), carried at
    0.266 of the flow, and fades in 0.42 s, set so its visible area 0.9 s after a stroke is halfway between them.
    Then its life was cut to 65% (2026-11-18): the fluid's fade 0.322 s, the dye's 0.273 s.
    Measured with one stroke at 1440x900 (median thickness across the path at 150 ms: line 7 px, docs 110 px,
    now 58 px). Its colours are unchanged; its opaque body reads heavier than the docs tail's translucent one. It bends nothing on the page: loose things (leaves, petals) feel it as wind instead, at the
    moment the fluid takes each stretch of the cursor's path in, and are lifted off the ground. The
    overlay repaints a picture of the layer from its SVG (replayed into a canvas) and its canvases.
- **Per page**:
  - run: bending, on the fan's white paths: on the dark ground they take a clear red tint (35% of the way from
    their off-white to #FF3B30, `--wake-tone` #f5b1b3) with vivid #FF3B30 fringes at about 95%, 1.5 to 2 px off the
    line (`--wake-fringe-mix`, `--wake-fringe-off`; measured 4.8-5.0:1 on the ground, 2026-11-18); on the light
    ground silver-grey with fine red fringes, as before; the gold paths bend with it but keep
    their own gold throughout, with no tone and no fringe, in both palettes (2026-11-18: the shader tones and fringes
    the white channel only and lays the gold over it by its own coverage, so the rule follows a path's colour as it
    fades; the same in the glass, where a pushed gold stroke stays gold, unfringed). Inside the glass the strokes are pushed aside by
    the cursor as by a round obstacle, not bent by the fluid (section 3, run, "The cursor in the glass").
  - home: a trail, the grove's green with a pale green highlight, over the grove, the ground line and the
    open paper, and behind the text (the overlay lies under it). The leaves are its wind.
  - demo: a trail in neon blue with pink edges, a little more vivid; over the scenery and the run's tree,
    under the verdict, the stage notes, the bed and the panels (its canvas sits in `#spot` after the
    tree). The petals are its wind. Paused inside a run. While the tree grows its picture is refreshed at
    most four times a second; if a refresh costs more than 4 ms the trail keeps clear of the tree until
    it has grown.
  - Sancho: the run page's form over the docs page's toned-down fluid (force 60%, swirl 60%, its own motion
    75%, life +20%): only the glossy trace (`wakeTrace`: a #F2D7A6 highlight, a #14070A shade, a #B5391C
    hairline rim), laid over the backdrop, the horizon and the windmill alike. It distorts nothing: the
    horizon and the windmill never bend or change colour under it. It fades out before the sheet's text. The
    windmill's sails are its wind.
  - **docs and the viewer: not yet.** Each gets the wake in its own session, with its colours
    chosen then. Docs will be blue, white and green, in a soft, bubble-like form.

The viewer draws a run's tree without the demo's decoration (the run page draws only the scale, src/runscale.ts): `makeScene()` without `decor`
draws the tree, its bar and the verdict written on it, flat, in `--tree`, `--tree-path` and `--tree-bar`.

## 4. The grid, the type scale, the menu

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

No bold except the home headline, the brand mark and the word "Eucalyptus" in home's last line (IBM Plex Sans 700,
loaded by `home.css` alone); emphasis is weight 500.

**Motion tokens**: `--ease-travel` = `cubic-bezier(.35, 0, 0, 1)`, `--ease-ui` = `cubic-bezier(.4, 0, .1, 1)`,
`--dur-page` 1000 ms, `--dur-enter` 700 ms, `--dur-ui` 350 ms, `--dur-colour` 450 ms.

**The menu** (2026-11-18; `src/menu.html`, `src/menu.ts`, `base.css`): there is no header bar. One control is fixed
at the top left of the window: the wordmark "Garden" (the display face) with a small "Menu" label (mono caps) on a
pill in the section's `--header-bg` (the ground itself on home, run, the demo, the viewer and Eucalyptus; on docs
and Sancho the light glass and sheet their dark ink reads on, with what lies beneath blurred). The wordmark hangs on
the grid's left edge; the control lies in the band `--head` reserves (76 px, 60 on a phone), which every section,
the docs contents (sticky at `--head` + `--pad-y`) and every anchor (`scroll-margin-top`) already clear (checked:
the pill ends at 58 px, the contents stick at 126 px, a docs heading lands at 100 px in its own column); the docs bubbles' lane, which had started under the bar, now runs from the top of the screen).
- A click opens a panel directly beneath, in the same colours with a hairline border: Quixote (the home section),
  Run, Docs, Sancho (scrolled to, as the header's links were), Eucalyptus (its page, under Sancho), Paper (the
  paper, a new tab). No demo. The section on screen (on a separate page, that page) is marked with a dot (`aria-current`).
- It closes on choosing an item, on Escape (focus back on the button) and on a click outside, and when focus
  leaves it. A disclosure: a button with `aria-expanded` and `aria-controls`, the panel a labelled `nav` of plain
  links. Enter or Space opens it with focus on the current item; Down and Up open it at the first or last;
  inside, Up, Down, Home and End move between items.
- On the one page its colours mix between sections with the scroll as the header's did (`boot.ts`). On a phone
  the same control and panel, sized for touch (a 44 px control and 44 px items).
- It is written into every page with a menu by the build, at a `<!-- menu -->` marker (`vite.config.ts`): the one
  page, the demo, the viewer, Eucalyptus, and the legal, shared-verdict, result and 404 pages (their bar's styles
  are gone).
- The author's name, Contact (a mailto link; the address is never printed) and LinkedIn are in the footer only.

## 5. Where things live

| file | what |
|---|---|
| `src/styles/base.css` | fonts, grid, type and motion tokens, header, footer, shared components, the flat tree |
| `src/styles/<theme>.css` | one token block per page, and that page's own rules |
| `index.html`, `run.html`, `docs.html`, `sancho.html`, `eucalyptus.html` | the five shells of the one document (title, description, `data-start`) |
| `vite.config.ts` (`onepage()`, `SECTIONS`) | writes the loading screen, header, backdrops and sections into the shells |
| `src/onepage/*.html` | the header and each section's markup |
| `src/menu.html`, `src/menu.ts` | the menu: its markup (written into every page at `<!-- menu -->`) and its behaviour |
| `src/onepage/main.ts` | the one module: boot, then each section's script, then `start()` |
| `src/onepage/boot.ts` | the work count, the reveal, addresses and history, the scroll crossfade, section visibility, whole-pixel sections |
| `src/styles/onepage.css` | backdrops, `.section`, the cue, the header's mixed ground |
| `src/loader.ts`, `src/loader-mark.ts`, `src/styles/loader.css`, `public/loader-early.js` | the loading screen |
| `loader.html`, `src/pages/loader-preview.ts` | the loading screen alone, for review |
| `src/scene.ts` | a run's tree in a section; the demo's decoration only with `decor` |
| `src/cursorwake.ts` | the cursor's wake: the fluid, the shared shader, the pointer rules, the theme's colours, the trail overlay (`WakeLayer`) and its SVG painter |
| `src/pages/<page>.ts` | each page's script; it imports `../common` first, then its theme. The chain's four (`index`, `run`, `docs`, `sancho`) are imported by `src/onepage/main.ts`, register their work with `task()` and keep to their own section |

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

- **One cross-browser pass, Firefox included.** Scroll through the one page both ways in Firefox at 1440x900 and
  390x844, with every section's shots, and again in Safari and Chrome. Firefox is not yet installed on the development machine; drive it with geckodriver.
- **Safari at the run section.** Measured 2026-11-17, before Pyodide loaded on demand: the median frame crossing
  into run was 40 ms and into docs 37 ms (Chrome: 16.7 ms). The old run page alone was already about 30 fps in
  Safari. Target: 60 fps with a 95th-percentile frame under 20 ms through run and across both its boundaries. Not
  yet profiled (suspects: the fan's 2D canvas uploaded as a texture each frame, two separate WebGL scenes, full
  Retina resolution); the author judged the scrolling good by eye on 2026-11-18.
- **Rare long frames in Chrome.** Up to 1.25 s, in 2 of 6 runs of the build before Pyodide loaded on demand. They
  were in Chrome's GPU process, compiling shader pipelines for the first raster of something (the docs sheet's
  rim light was one), while Pyodide was compiling its WebAssembly on the other cores. With Pyodide on demand, none
  appeared in 4 runs, including Pyodide loading during the scroll. Too few runs to call it gone.
- **Memory** after Pyodide on demand is not yet measured. Before it, the one page was 333 MB in its renderer plus
  1.4 GB in Chrome's GPU process, and 1.39 GB in Safari's page process, Pyodide included.
- **The one-page browser check and the reference comparison** were last run before the loader timing and Pyodide
  on demand changed (2026-11-18). Run both again.
- **The viewer check** (`browser_check.mjs --pages --fixtures DIR`) needs fixtures from a Sancho fit, too heavy for
  the development laptop.
- **Run the equivalence script**, `node scripts/equivalence.mjs --python python3`: the gate, worker, wheel and
  examples were not touched by the revamp, and this confirms it.
- The empty tree area on the viewer before a run is loaded: settled in its session. (The run page has no tree area: its result is the scale alone.)
- The docs and viewer colours are interim until each page's session (Sancho's are settled).
- The cursor's wake on docs (blue, white and green, soft and bubble-like) and the viewer: each in its own
  session (Sancho's is settled).
