# Pre-merge check: site-onepage into main (2026-11-18)

The redesign (branch `site-onepage`) checked before merging into `main`. No design change was made in this pass.
Base: `origin/main` at `e5fa81e444f9891afe60050658d7debff85fffb3`. The design itself is described in `DESIGN.md`.

## What changed, in short

- **For visitors:** a complete redesign. Home, Run, Docs, Sancho and Eucalyptus are one continuous page behind a
  loading screen, each with its own address. The viewer is a layer opened from Sancho. There are new Demo and Contact
  pages, and the header bar is replaced by a single menu control. The gate, its verdicts and the examples are unchanged.
- **In structure:** five shells of one document built by the `onepage()` plugin in `vite.config.ts`; the sections'
  markup is in `src/onepage/`; `src/onepage/boot.ts` handles the reveal, addresses and the scroll crossfade; the menu is
  written into every page at its marker; one theme stylesheet per page.
- **Removed in this pass** (commit `b54f962`), all unreachable from any page:
  - the loader preview page, out of the production build (`loader.html` and `src/pages/loader-preview.ts` stay for
    the dev server only);
  - `src/runView.ts` (the old demo's run view), `src/verdict.ts` (the old verdict card), `src/searchtree.ts` and
    `src/dev/` (the first-round demo tree and its dev preview);
  - `common.ts`'s `headerOverPaper` (the old header bar) and `lowerBound`, and `process.ts`'s `processOfRun`, which
    only those used;
  - dead CSS: the run view's tide, zoom and panel, chips, the choice note, the full-gate note, bar petals, the sprout
    and `.demo-main` (`demo.css`); `.run-new` (`base.css`); `.carry-prev`, the old cross-page carry (`docs.css`,
    `sancho.css`); `canvas.dusk-standin` (`sancho.css`); comments that named `runView.ts`;
  - 59 screenshots of the pre-redesign site (2026-10-27), referenced nowhere. `screenshots/lukres/` (cited in
    DESIGN.md) and `screenshots/loader/` stay.
  - Kept on purpose: `scripts/carry/` (`onepage_measure.mjs` still uses it), `runtree.ts`'s `runCrossings` (the
    demo tree's crossing test), `levers.ts`'s `RATE_GRIDS` and `RIDGE_OFF` (they mirror Sancho's registered values).
- **Fixed in this pass:** `scripts/browser_check.mjs`'s contrast measurement. It hid only the measured element's own
  text, so the demo intro's first sentence (a span in its own colour) was counted as background (it read 1:1). It also
  shot after 60 ms while the Start button's border was still fading over 450 ms (it read 1.67:1). It now hides
  descendants too and turns transitions off while it shoots. Re-measured: the demo text is 9.5:1 or more.
- **Deferred:** see DESIGN.md §7. Firefox is untested; Safari's speed in the run section is not yet profiled; long
  frames and memory were not re-measured.

## Results (Chrome 157, headless, macOS; each run alone)

| check | result |
|---|---|
| `npm run build` | passes: typecheck; Pyodide 314.0.7 files match the manifest; 8 example copies equal their sources; the wheel matches its manifest; grove.json current, no crossings; `check_dist`: 79 files, no inline script or style, no other origin, 36 pinned files match the lock. One Vite notice: `vite.config.ts` imports `./src/loader-mark` without an extension, which a future Vite will require (not a failure) |
| `browser_check.mjs` (full) | exit 0. 0 CSP violations, nothing missing, no page errors (the only console lines are `/_vercel/insights/script.js` 404s, which exist only on Vercel). Every item matches DESIGN.md: loader, direct links, addresses following the scroll without adding history, cue and header links, Back, the menu by keys and pointer, the mode switch, out to the demo and to Contact and back, the Eucalyptus section, the demo's run and inside view, the menu pill on every page, the footers, the paper linked from home and docs only, the viewer layer, no sideways scroll on a phone, reduced motion still |
| `browser_check.mjs --run-page` | exit 0. Anthropic, OpenAI, OpenRouter and Local runs against the mock providers; the key, rate-limit, credit, version and cancel errors; the key in no text, HTML, URL or storage; only the expected hosts contacted; the share link |
| `browser_check.mjs --pages --fixtures scripts/fixtures/viewer` | exit 0. The viewer on a search's files and on `sancho.json`; Sancho's lever editor (registered and tailored hashes, bad input refused, reset, the downloaded config's hash matches); 8 pages on a phone with no sideways scroll, 44 px menu control and items |
| `reference.mjs`, before (`6daee14`) vs after this pass | run, docs, Sancho and Eucalyptus: 0 pixels differ in every shot (top, middle, end; 1440x900 and 390x844). Home: 545–1,880 pixels differ in five of its six shots (up to 0.14%), shifted by 1 px; the build before this pass differs from itself by the same amount between two shoots (731 / 1,510 px), so this is noise between shoots, not a change |
| `equivalence.mjs` | exit 0. nothing (FAIL), planted (CERTIFIED), restart (FAIL); the full run through the Anthropic, OpenAI, OpenRouter and Local mock providers; Sancho's config hash. Verdicts and exit codes identical; largest difference 2.2e-16 (tolerance 1e-9) |
| Direct visits | `/`, `/run.html`, `/docs.html`, `/sancho.html`, `/eucalyptus.html`: 200, each opens on its own section with its title and current menu item. `/viewer.html`: 200, the viewer open over Sancho. `/demo.html`, `/contact.html`: 200, their own pages. `/no-such-page`, `/garden/missing.html`: 404 and the not-found page |
| Phone, 390x844 with touch | the one page (all five sections), the menu open, the viewer (empty, with `sancho.json`, with `result.json`), the demo (idle, after a run, with the run opened by a real tap), Contact, privacy, terms, share, the three result pages, 404. No page scrolls sideways. No text is cut off: the only text past the window is inside the three command blocks in Docs and Sancho, which scroll inside themselves (`overflow-x: auto`) and each have a Copy button. Every control is hit where a finger lands. Targets under 24 px are inline links in text (exempt) or pass WCAG 2.5.8 by spacing: the Continue cues (14 px tall), the disclosures (15–18 px), the footer links (20 px), the lever checkboxes, whose labels are the target (19 px) |
| Reduced motion | every section (top and middle) and every page: no animation running, 0 pixels change over 1.5 s; the menu opens with no animation. One pass saw 21,676 px change in the run section's middle with no animation running; it did not recur when repeated, during and after the gate's load (0 px over 3 s). Most likely the gate's two status lines being filled in when it arrived, which is content, not motion |
| Keyboard only | Menu: Tab reaches it second (after the skip link); Enter and Space open it on the current item; Down, Up, Home and End move; Escape closes it with focus back on the button; Enter on an item scrolls there and moves focus to the section. Run form: every field and button reached in order; a focus mark on each (2 px outline on links and buttons; the border turns the accent on inputs and selects; an outline on the file pickers' labels); a select changes by typing; Enter on Start without a key shows "Enter your API key to start." and moves focus to the key field. Mode switch: reached by Tab, Enter switches to light, Space back to dark, its label follows. Viewer: Enter on "Open the viewer" opens it; Tab stays inside (Close, each panel, the file input); after a file, the arrows, End and Home move between the six panels; Escape closes it with focus back on the control. Contact: Tab reaches the email, LinkedIn, Résumé, Open in browser and the footer links, each with a 2 px white outline; Enter follows them |
| Links | 62 distinct links over every page. Internal: all 200; every anchor exists. Résumé: `/Benjamin-Knaster-Resume.pdf`, 200, a PDF (43,585 bytes), the `download` attribute; "Open in browser": the same file in a new tab. The demo's "Open this verdict on its own page" is hidden until a run ends, then points to `/result.html?ex=…`; each of the three result pages recomputes its verdict (FAIL p 0.9630, PASS p 0.0005, FAIL p 0.9760, as the equivalence run). External: 9 of 11 answer 200 (GitHub source, issues, gate.worker.ts, NOTE_MAP.md, the four read/grading files; the DOI resolves to the Zenodo record). **Not verified:** SSRN (403) and LinkedIn (999) refuse automated requests; check them by hand. Every new-tab link has `rel="noopener noreferrer"` |
| Contrast (measured by browser_check) | the demo 9.5:1 or more; Contact's lines 5.43:1 or more at rest and under the tail; Contact's footer line 4.57:1 at rest (above 4.5:1, below the 5.4:1 measured on `79d926f`; noted in DESIGN.md, not changed) |

**Not run:** Firefox (not installed); Safari; a real phone (touch was emulated in Chrome); long-frame and memory
measurements.

## Rolling back

- **The site:** Vercel deploys production from `main`. To undo at once, promote the previous production deployment in
  Vercel (Instant Rollback); nothing else is needed.
- **The code:** revert the merge commit on `main` (`git revert -m 1 <merge commit>`), push, and Vercel redeploys the
  old site. `e5fa81e` is the last `main` commit before the redesign.
- **This pass only:** revert `b54f962` (the removals) and the commit that adds this file.
