// The background trees: decoration, drawn from the restart example's logged search (its eight
// restarts are eight trees). Each is a tall or a short tree: a bare trunk and one crown at its own
// top. Page one shows all eight, tall and short alternating, reaching high into the page. Page two
// shows six upright neon trees, three at each edge (the outermost in front of the pylon), the pair
// nearest the centre further away (smaller, dimmer), all smaller than the run's tree, so none can be
// mistaken for it and none crosses the animation spot.
//
// The trees do not respond to clicks. Leaves and petals are released from points spread along every
// frond, weighted toward the outer canopy (branchSources).
import { drawGarden, type GardenHandle } from "./garden";
import type { Source } from "./particles";
import type { SearchTree } from "./types";

const H = 600;
const NS = "http://www.w3.org/2000/svg";

/** The search restricted to some of its stems, renumbered 0..n-1. */
export function subTree(tree: SearchTree, stems: number[]): SearchTree {
  const moves = tree.moves.filter((m) => stems.includes(m.stem)).map((m) => ({ ...m, stem: stems.indexOf(m.stem) }));
  return { ...tree, moves, stems: stems.length, evaluations: moves.reduce((n, m) => n + m.candidates.length, 0) };
}

const aspect = (svg: SVGSVGElement) => { const r = svg.getBoundingClientRect(); return r.width && r.height ? r.width / r.height : 1.6; };

// ---------- the home page's grove ----------
// The restart example's logged search as birches standing on one ground line (src/birch.ts). Every twig
// and leaf was placed at build time (scripts/make_grove.mjs, public/examples/grove.json); here the page
// only scales and positions the finished drawings, one <svg> per tree so a tree's entrance is
// composited. Desktop: every restart in search order, the even ones in front, spaced so no two front
// crowns touch, the odd ones a row behind (smaller, finer, lighter), each midway between its
// neighbours; a 3 px knockout in the paper's colour under every front stroke keeps the front trees
// reading cleanly where a back tree passes behind. Phone: three of the same trees (two in front, one
// behind), laid out the same way in a taller grove that may run past the first screen.
import { renderPrims, type Prims } from "./birch";

export interface GroveTree { stem: number; back: boolean; height: number; l: number; r: number; top: number; trunk: string; bark: string; prims: Prims }
export interface GroveData { restarts: number; evaluations: number; phone_evaluations: number; phone_stems: number[]; desktop: GroveTree[] }
export interface Grove { stems: SVGSVGElement[]; sources: (stem?: number) => Source[]; restarts: number; evaluations: number; shown: number }

const PAD = 4;   // around each tree's drawing, in its own units
const END = 0.36; // the last back tree's trunk, past the last front one, in front spacings

function treeSvg(t: GroveTree, s: number, left: number): SVGSVGElement {
  const svg = document.createElementNS(NS, "svg");
  const vx = t.l - PAD, vw = t.r - t.l + 2 * PAD, vy = t.top - PAD, vh = -t.top + PAD;
  svg.setAttribute("class", "stem" + (t.back ? " back" : ""));
  svg.setAttribute("viewBox", `${vx} ${vy} ${vw} ${vh}`);
  svg.dataset.stem = String(t.stem);
  for (const [k, v] of [["--l", `${left.toFixed(2)}px`], ["--w", `${(vw * s).toFixed(2)}px`], ["--h", `${(vh * s).toFixed(2)}px`], ["--ox", `${((0 - vx) * s).toFixed(2)}px`], ["--i", String(t.stem)]] as const) svg.style.setProperty(k, v);
  const d = renderPrims(t.prims);
  const add = (cls: string, path: string) => { if (!path) return; const e = document.createElementNS(NS, "path"); e.setAttribute("class", cls); e.setAttribute("d", path); e.setAttribute("vector-effect", "non-scaling-stroke"); svg.appendChild(e); };
  // the knockout first (front trees only), then the tree: branches and twigs, the trunk over their
  // feet, its bark, then the leaves
  if (!t.back) for (const path of [d.branches, d.twigs, t.trunk, ...d.leaves]) add("ko", path);
  add("br", d.branches); add("tw", d.twigs); add("tr", t.trunk); add("bk", t.bark);
  d.leaves.forEach((path, k) => add(`lf l${k}`, path));
  return svg;
}

/** Draw the grove into `host`, a box whose bottom edge is the ground; `offset` is the box in the section. */
export function drawGrove(host: HTMLElement, data: GroveData, box: { w: number; h: number }, offset: { x: number; y: number }, phone: boolean): Grove {
  host.replaceChildren();
  // the phone shows some of the same trees, laid out the same way in its own (taller) box
  const trees = phone ? data.desktop.filter((t) => data.phone_stems.includes(t.stem)) : data.desktop;
  const tall = Math.max(...trees.map((t) => -t.top + PAD));
  const wid = (t: GroveTree) => [(t.l - PAD), (t.r + PAD)] as const;
  let s = (box.h - 1) / tall, xs: number[] = [];
  {
    // front trunks at x0 + i·d, every back trunk half a spacing after a front one (the last a third of a
    // spacing past the last front tree, never beside its trunk); the largest scale at which no two front crowns come within
    // `gap` of each other and every tree ends inside the box. A back crown may lie behind a front one (the
    // knockout keeps the front tree clean); no two front crowns ever meet.
    const F = trees.filter((t) => !t.back), lastBack = trees[trees.length - 1].back, gap = 18;
    const lay = (sc: number) => {
      let d = 0;
      for (let k = 0; k + 1 < F.length; k++) d = Math.max(d, (wid(F[k])[1] - wid(F[k + 1])[0]) * sc + gap);
      const x0 = -wid(F[0])[0] * sc, end = trees[trees.length - 1];
      const right = lastBack ? x0 + (F.length - 1 + END) * d + wid(end)[1] * sc : x0 + (F.length - 1) * d + wid(end)[1] * sc;
      return { d, x0, right };
    };
    let lo = 0, hi = s;
    for (let it = 0; it < 32; it++) { const mid = (lo + hi) / 2; if (lay(mid).right <= box.w) lo = mid; else hi = mid; }
    s = lo;
    const L0 = lay(s), slack = box.w - L0.right, d = L0.d + slack / (F.length - 1 + (lastBack ? END : 0));
    xs = trees.map((t, i) => L0.x0 + (i === trees.length - 1 && t.back ? (F.length - 1 + END) : i / 2) * d);
  }
  const svgs: SVGSVGElement[] = [];
  // back trees first, so the front ones (and their knockouts) lie over them
  const order = trees.map((_, i) => i).sort((a, b) => Number(trees[b].back) - Number(trees[a].back) || a - b);
  for (const i of order) { const t = trees[i], svg = treeSvg(t, s, xs[i] + (t.l - PAD) * s); svgs[i] = svg; host.appendChild(svg); }
  const sources = (stem?: number): Source[] => {
    const out: Source[] = [];
    trees.forEach((t, i) => {
      if (stem !== undefined && t.stem !== stem) return;
      for (const [x, y, a, sz] of t.prims.leaves) {
        const lx = x + Math.cos(a) * sz * 0.5, ly = y + Math.sin(a) * sz * 0.5;
        out.push({ x: offset.x + xs[i] + lx * s, y: offset.y + box.h + ly * s, vx: (lx >= 0 ? 1 : -1) * (2 + Math.abs(Math.sin(lx * 7 + ly)) * 4), w: 0.5 + Math.min(1, -ly / Math.max(1, -t.top)) });
      }
    });
    return out;
  };
  return { stems: svgs, sources, restarts: data.restarts, evaluations: phone ? data.phone_evaluations : data.evaluations, shown: trees.length };
}

export function woodTwo(svg: SVGSVGElement, tree: SearchTree): GardenHandle {
  const width = H * aspect(svg);
  const t = subTree(tree, [0, 1, 3, 5, 7, 6]);
  // two depths: the pair nearest the centre is the far pair, smaller and dimmer (css .far)
  return drawGarden(svg, t, { quiet: true, halo: true, neon: true, canopy: false, width,
    crown: { upright: true, heights: [0.46, 0.5, 0.27, 0.29, 0.52, 0.44], xs: [0.022, 0.1, 0.19, 0.81, 0.9, 0.978], far: [2, 3] } });
}

/** Points along every frond of the drawn trees (or one tree), in `box`'s pixels: the tips and three
 *  points along each limb, weighted toward the tips and away from the trunk, each with its branch's
 *  sideways drift. */
export function branchSources(svg: SVGSVGElement, box: HTMLElement, stem?: number): Source[] {
  const m = svg.getScreenCTM(), b = box.getBoundingClientRect(), out: Source[] = [];
  if (!m) return out;
  const pt = svg.createSVGPoint();
  const sel = stem === undefined ? ".real .stem" : `.real .stem[data-stem="${stem}"]`;
  for (const g of svg.querySelectorAll<SVGGElement>(sel)) {
    const tr = g.querySelector<SVGGraphicsElement>(".trunk"), bb = tr?.getBBox(), ax = bb ? bb.x + bb.width / 2 : null;
    for (const tw of g.querySelectorAll<SVGPathElement>(".twig")) {
      const L = tw.getTotalLength();
      for (const t of [0.3, 0.55, 0.8, 1]) {
        const q = tw.getPointAtLength(L * t); pt.x = q.x; pt.y = q.y;
        const sp = pt.matrixTransform(m), x = sp.x - b.left, y = sp.y - b.top;
        if (x < 0 || x > b.width || y < 0 || y > b.height) continue;
        const off = ax === null ? 0 : q.x - ax;
        out.push({ x, y, vx: (off >= 0 ? 1 : -1) * (5 + Math.random() * 9), w: (0.25 + Math.min(1.2, Math.abs(off) / 60)) * (0.5 + t) });
      }
    }
  }
  return out;
}
