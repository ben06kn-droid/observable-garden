// The home page: the overview on paper, the search drawn behind it in dark green, yellow leaves falling.
// The demo is its own page (demo.html, src/pages/demo.ts); the scroll chain (chain.ts) carries the
// visitor on to the run page from the end of this one.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/home.css";
import { reduceMotion } from "../common";
import { Field, startLife } from "../particles";
import { branchSources, shakeable, woodOne } from "../woods";
import type { SearchTree } from "../types";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const one = $("overview");

// ---- leaves (particles.ts): the ground is the page's foot; the pile stays below the text
const textBox = () => { const t = document.querySelector(".one .copy")?.getBoundingClientRect(), b = one.getBoundingClientRect(); return t ? { l: t.left - b.left, r: t.right - b.left, below: one.clientHeight - (t.bottom - b.top) - 10 } : null; };
let text = textBox();
const leaves = new Field({ box: one, air: $("air-one") as HTMLCanvasElement, pile: $("pile-one") as HTMLCanvasElement, kind: "leaf", count: 90, start: 46,
  ground: () => one.clientHeight - 4,
  cap: (x) => (text && x > text.l - 20 && x < text.r + 20 ? Math.max(0, Math.min(26, text.below)) : 26) });
startLife({ fields: [leaves], paused: () => document.hidden, throttled: () => false, reduce: reduceMotion });

// ---- the background trees (woods.ts): the restart example's search, from its log; eight tall and short
// trees in dark green. A click (or Enter) shakes one and sheds a burst from its branches.
const bgOne = $("bg-trees") as unknown as SVGSVGElement;
let backdrop: SearchTree | null = null;
const woods = () => {
  if (!backdrop) return;
  woodOne(bgOne, backdrop);
  shakeable(bgOne, "Tree", (s) => leaves.burst(branchSources(bgOne, one, s), 16));
  leaves.setSources(branchSources(bgOne, one));
};
fetch("/examples/overview-tree.json").then((r) => r.json()).then((tree: SearchTree) => { backdrop = tree; woods(); }).catch(() => {});
let resizeT = 0;
window.addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => { text = textBox(); woods(); }, 200); });
