// The home section of the one-page site (src/onepage/): the overview on paper, the search drawn as a grove of birches
// standing on one ground line, their turned leaves falling onto it. The demo is its own page (demo.html,
// src/pages/demo.ts). Built behind the loading screen (its work registered with boot.ts's task()).
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/home.css";
import { inView, section, task } from "../onepage/boot";
import { reduceMotion } from "../common";
import { BIRCH_LEAF_D } from "../birch";
import { Field, startLife } from "../particles";
import { svgPart, WakeLayer } from "../cursorwake";
import { drawGrove, swayTree, type Grove, type GroveData } from "../woods";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const one = $("overview"), groveBox = $("bg-trees"), host = $("grove");
const horizon = one.querySelector<HTMLElement>(".horizon")!;
const phone = () => window.matchMedia("(max-width: 812px)").matches;
const home = section("home");
const tone = (k: string) => getComputedStyle(home).getPropertyValue(k).trim();   // the theme is the section's

// ---- leaves (particles.ts): the birches' own leaf, turned ochre (the page's one warm accent; on the trees
// they are green), few and small, near ones larger and more opaque; a slow fall and a calm sway. They
// leave from the trees' leaves, land on the ground line and lie along it, one deep.
const groundY = () => horizon.offsetTop;   // the ground line's top, in the section's pixels
const text = () => [...one.querySelectorAll<HTMLElement>(".head h1, .head .lead, .body > *")].map((e) => {
  const r = e.getBoundingClientRect(), b = one.getBoundingClientRect();
  return { x: r.left - b.left, y: r.top - b.top, w: r.width, h: r.height };
});
let avoid = text();
const leaves = new Field({ box: one, air: $("air-one") as HTMLCanvasElement, pile: $("pile-one") as HTMLCanvasElement, kind: "leaf",
  count: phone() ? 6 : 14, start: phone() ? 8 : 18,
  // a leaf lies on the line or not at all: past the line's ends it fades where it falls
  ground: () => groundY(), cap: (x) => (x >= horizon.offsetLeft + 4 && x <= horizon.offsetLeft + horizon.offsetWidth - 4 ? 2.4 : 0), avoid: () => avoid,
  look: { shapes: [BIRCH_LEAF_D], tones: [tone("--leaf-1"), tone("--leaf-2"), tone("--leaf-3")], size: [6, 12.5], alpha: [0.55, 1],
          fall: [26, 46], sway: 13, spin: 0.9, wind: 0.45, rest: 0.55, kick: 1.3, lift: 240 } });
// the cursor's wind on the leaves comes from the wake (below), not straight from the pointer
// paused while the page is hidden or the home section is off screen
const life = startLife({ fields: [leaves], paused: () => document.hidden || !inView("home"), throttled: () => false, reduce: reduceMotion, cursor: false });

// ---- the grove (woods.ts): the restart example's search as birches, placed at build time
// (scripts/make_grove.mjs); desktop shows every restart, the phone its own grove of two. A click (or
// Enter) sways a tree and sheds a few leaves from it.
let data: GroveData | null = null, grove: Grove | null = null;
const draw = () => {
  if (!data) return;
  const r = groveBox.getBoundingClientRect(), b = one.getBoundingClientRect();
  // drawn finished, with no arrival: it is built behind the loading screen, where an arrival could not be seen (and
  // its end would repaint the trail's picture after the work had been counted done)
  const again = true;
  grove = drawGrove(host, data, { w: Math.floor(r.width), h: Math.floor(r.height) }, { x: r.left - b.left, y: r.top - b.top }, phone());
  host.classList.toggle("still", again);
  for (const svg of grove.stems) {
    const stem = Number(svg.dataset.stem);
    svg.setAttribute("tabindex", "0"); svg.setAttribute("role", "button");
    svg.setAttribute("aria-label", `Restart ${stem + 1}: sway it`);
    const go = () => { if (!reduceMotion) swayTree(svg); leaves.burst(grove!.sources(stem), 4); };
    svg.addEventListener("click", go);
    svg.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  }
  leaves.setSources(grove.sources());
  if (reduceMotion) leaves.draw();         // no loop under reduced motion: the still frame, drawn once
  host.classList.add("drawn");             // a redraw (a resize) does not play the arrival again
  wake.invalidate(); wake.keepMask();
  // the legend counts what is drawn: every restart on a desktop, two of them on a phone
  const each = document.createElement("span"); each.className = "each"; each.textContent = ", a twig each";
  const shown = grove.shown < grove.restarts ? `${grove.shown} of ${grove.restarts} restarts` : `${grove.restarts} restarts`;
  $("grove-count").replaceChildren(`${shown} · ${grove.evaluations} evaluations`, each);
};
// ---- the cursor's wake (cursorwake.ts, the site's signature). Here it moves nothing and bends nothing: it
// is drawn as a trail, a thin glossy green line that follows the cursor with small wisps curling off its
// sides, over the grove and the paper, never over the text. The leaves feel it as wind: the fluid hands
// each stretch of the cursor's path to the leaves as it takes it in (the same beat and the same response
// to speed), so the trail and the kick arrive together and leaves on the ground are sent back up.
const box = (e: Element) => { const r = e.getBoundingClientRect(), b = one.getBoundingClientRect(); return { x: r.left - b.left, y: r.top - b.top, w: r.width, h: r.height }; };
const horizonPart = { paint(c: CanvasRenderingContext2D) {      // the ground line and its ticks (drawn by CSS, so drawn here too)
  const h = box(horizon); c.fillStyle = tone("--paper-tree"); c.fillRect(h.x, h.y, h.w, 1);
  for (const i of horizon.querySelectorAll("i")) { const t = box(i); c.fillRect(t.x, h.y - 4, 1, 9); }
} };
const grovePart = svgPart(one, () => grove?.stems ?? []);
const wake = new WakeLayer({ host: one,
  ground: (c, w, h) => { c.fillStyle = tone("--paper"); c.fillRect(0, 0, w, h); },
  // what the trail refracts: the grove, the ground line and the leaves (none of them is bent)
  parts: () => [grovePart, horizonPart, $("air-one") as HTMLCanvasElement, $("pile-one") as HTMLCanvasElement],
  bends: () => false,
  // a tree swaying or arriving now (finished animations that hold their last frame do not count)
  moving: () => !!grove?.stems.some((s) => s.getAnimations().some((a) => a.playState === "running")),
  keep: () => [...one.querySelectorAll(".head h1, .head .lead, .body > *, .legend > span")].map(box),
  // halfway between the narrow line it was and the docs tail (src/sky.ts; 2026-11-18). The fluid's settings, shared
  // with docs, are the midpoints: cell 5 | 8, flow 0.3 | 0.4125, curl 70 | 13.2, force 1 | 0.6, fade 0.45 | 0.54. The
  // dye has no docs counterpart (docs draws the fluid itself): its width is the midpoint of the line's (2.4px) and
  // the docs push's (32 + 48·√dose px), its carry the midpoint of 0.12 and the docs flow; its fade, 0.42 s, was set
  // by measurement so the tail's visible area 0.9 s after a stroke is halfway between the two (about 8k px)
  scale: { cell: 6.5, flow: 0.35625, curl: 41.6, force: 0.8, fade: 0.495,
           dye: 1.5, dyeWidth: 17.2 / 1.5, dyeGrow: 24 / 1.5, dyeFlow: 0.26625, dyeFade: 0.42 },
  onPush: (x, y, vx, vy, dose) => { const k = 0.5 + 0.9 * Math.sqrt(dose); life.wind.add(x, y, vx * k, vy * k); } });

one.addEventListener("animationend", () => wake.invalidate());   // a tree done arriving or swaying

// drawn once the type has settled, behind the loading screen: the grove's data fetched, then the grove drawn
const fetched = task("home: grove data"), drawn = task("home: grove drawn");
Promise.all([fetch("/examples/grove.json").then((r) => r.json()).finally(fetched), document.fonts.ready])
  .then(([g]) => { data = g as GroveData; avoid = text(); draw(); requestAnimationFrame(() => requestAnimationFrame(() => drawn())); }).catch(() => drawn());
// redrawn whenever the grove's box changes size (fonts arriving, a resize), never stretched
let resizeT = 0, size = "";
new ResizeObserver(([e]) => {
  const s = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
  if (s === size) return;
  window.clearTimeout(resizeT);
  resizeT = window.setTimeout(() => { size = s; avoid = text(); draw(); }, size ? 150 : 0);
}).observe(groveBox);
