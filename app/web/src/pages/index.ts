// The home page: the overview on paper, the search drawn as a grove standing on one ground line, yellow
// leaves falling onto it. The demo is its own page (demo.html, src/pages/demo.ts); the scroll chain
// (chain.ts) carries the visitor on to the run page from the end of this one.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/home.css";
import "../chain";
import { reduceMotion } from "../common";
import { LEAVES } from "../leaves";
import { Field, startLife } from "../particles";
import { drawGrove, swayTree, type Grove } from "../woods";
import type { SearchTree } from "../types";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const one = $("overview"), groveBox = $("bg-trees"), host = $("grove");
const horizon = one.querySelector<HTMLElement>(".horizon")!;
const phone = () => window.matchMedia("(max-width: 812px)").matches;
const tone = (k: string) => getComputedStyle(document.documentElement).getPropertyValue(k).trim();

// ---- leaves (particles.ts): few and small, three outlines in three ochres, near ones larger and more
// opaque; a slow fall and a calm sway. They land on the ground line and lie along it, one deep.
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
  look: { shapes: LEAVES, tones: [tone("--leaf-1"), tone("--leaf-2"), tone("--leaf-3")], size: [6, 12.5], alpha: [0.55, 1],
          fall: [26, 46], sway: 13, spin: 0.9, wind: 0.45, rest: 0.55 } });
startLife({ fields: [leaves], paused: () => document.hidden, throttled: () => false, reduce: reduceMotion });

// ---- the grove (woods.ts): the restart example's search, from its log, one tree per restart. A click
// (or Enter) sways a tree and sheds a few leaves from its twigs.
let backdrop: SearchTree | null = null, grove: Grove | null = null;
const draw = () => {
  if (!backdrop) return;
  const r = groveBox.getBoundingClientRect(), b = one.getBoundingClientRect();
  const again = host.classList.contains("drawn");
  grove = drawGrove(host, backdrop, { w: Math.floor(r.width), h: Math.floor(r.height) }, { x: r.left - b.left, y: r.top - b.top });
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
  const each = document.createElement("span"); each.className = "each"; each.textContent = ", one stroke each";
  $("grove-count").replaceChildren(`${grove.restarts} restarts · ${grove.evaluations} evaluations`, each);
};
// drawn once the type has settled, so the arrival plays once on the final layout
Promise.all([fetch("/examples/overview-tree.json").then((r) => r.json()), document.fonts.ready])
  .then(([tree]) => { backdrop = tree as SearchTree; avoid = text(); draw(); }).catch(() => {});
// redrawn whenever the grove's box changes size (fonts arriving, a resize), never stretched
let resizeT = 0, size = "";
new ResizeObserver(([e]) => {
  const s = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
  if (s === size) return;
  window.clearTimeout(resizeT);
  resizeT = window.setTimeout(() => { size = s; avoid = text(); draw(); }, size ? 150 : 0);
}).observe(groveBox);
