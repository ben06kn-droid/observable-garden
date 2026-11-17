// The home page: the overview on paper, the search drawn as a grove of birches standing on one ground
// line, their turned leaves falling onto it. The demo is its own page (demo.html, src/pages/demo.ts); the scroll chain
// (chain.ts) carries the visitor on to the run page from the end of this one.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/home.css";
import "../chain";
import { reduceMotion } from "../common";
import { BIRCH_LEAF_D } from "../birch";
import { Field, startLife } from "../particles";
import { svgPart, WakeLayer } from "../cursorwake";
import { drawGrove, swayTree, type Grove, type GroveData } from "../woods";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const one = $("overview"), groveBox = $("bg-trees"), host = $("grove");
const horizon = one.querySelector<HTMLElement>(".horizon")!;
const phone = () => window.matchMedia("(max-width: 812px)").matches;
const tone = (k: string) => getComputedStyle(document.documentElement).getPropertyValue(k).trim();

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
          fall: [26, 46], sway: 13, spin: 0.9, wind: 0.45, rest: 0.55 } });
startLife({ fields: [leaves], paused: () => document.hidden, throttled: () => false, reduce: reduceMotion });

// ---- the grove (woods.ts): the restart example's search as birches, placed at build time
// (scripts/make_grove.mjs); desktop shows every restart, the phone its own grove of two. A click (or
// Enter) sways a tree and sheds a few leaves from it.
let data: GroveData | null = null, grove: Grove | null = null;
const draw = () => {
  if (!data) return;
  const r = groveBox.getBoundingClientRect(), b = one.getBoundingClientRect();
  const again = host.classList.contains("drawn");
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
// ---- the cursor's wake (cursorwake.ts, the site's signature). Here it moves only the falling leaves: the
// trees and the ground line stay exactly where they are, and the wake passes over them as a trace, white
// with fringes of the grove's green. Never over the text.
const box = (e: Element) => { const r = e.getBoundingClientRect(), b = one.getBoundingClientRect(); return { x: r.left - b.left, y: r.top - b.top, w: r.width, h: r.height }; };
const horizonPart = { paint(c: CanvasRenderingContext2D) {      // the ground line and its ticks (drawn by CSS, so drawn here too)
  const h = box(horizon); c.fillStyle = tone("--paper-tree"); c.fillRect(h.x, h.y, h.w, 1);
  for (const i of horizon.querySelectorAll("i")) { const t = box(i); c.fillRect(t.x, h.y - 4, 1, 9); }
} };
const wake = new WakeLayer({ host: one,
  ground: (c, w, h) => { c.fillStyle = tone("--paper"); c.fillRect(0, 0, w, h); },
  parts: () => [grovePart, horizonPart, $("air-one") as HTMLCanvasElement, $("pile-one") as HTMLCanvasElement],
  // the text's own boxes (the legend's spans, not its padded paragraph, which reaches up to the ground line)
  keep: () => [...one.querySelectorAll(".head h1, .head .lead, .body > *, .legend > span")].map(box),
  moving: () => !!grove?.stems.some((s) => s.getAnimations().length > 0),
  bends: (p) => p instanceof HTMLCanvasElement });           // the leaves, in the air and on the ground
const grovePart = svgPart(one, () => grove?.stems ?? []);
one.addEventListener("animationend", () => wake.invalidate());   // a tree done arriving or swaying

// drawn once the type has settled, so the arrival plays once on the final layout
Promise.all([fetch("/examples/grove.json").then((r) => r.json()), document.fonts.ready])
  .then(([g]) => { data = g as GroveData; avoid = text(); draw(); }).catch(() => {});
// redrawn whenever the grove's box changes size (fonts arriving, a resize), never stretched
let resizeT = 0, size = "";
new ResizeObserver(([e]) => {
  const s = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
  if (s === size) return;
  window.clearTimeout(resizeT);
  resizeT = window.setTimeout(() => { size = s; avoid = text(); draw(); }, size ? 150 : 0);
}).observe(groveBox);
