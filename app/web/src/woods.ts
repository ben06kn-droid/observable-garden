// The background trees: decoration, drawn from the restart example's logged search (its eight
// restarts are eight trees). Each is a tall or a short tree: a bare trunk and one crown at its own
// top. Page one shows all eight, tall and short alternating, reaching high into the page. Page two
// shows six upright neon trees, three at each edge (the outermost in front of the pylon), the pair
// nearest the centre further away (smaller, dimmer), all smaller than the run's tree, so none can be
// mistaken for it and none crosses the animation spot.
//
// Every tree can be shaken: a click (or Enter, the trees are focusable) gives its crown a short damped
// sway and sheds a burst of leaves or petals from its branches. Leaves and petals are released from
// points spread along every frond, weighted toward the outer canopy (branchSources).
import { drawGarden, type GardenHandle } from "./garden";
import type { Source } from "./particles";
import type { SearchTree } from "./types";

const H = 600;

/** The search restricted to some of its stems, renumbered 0..n-1. */
export function subTree(tree: SearchTree, stems: number[]): SearchTree {
  const moves = tree.moves.filter((m) => stems.includes(m.stem)).map((m) => ({ ...m, stem: stems.indexOf(m.stem) }));
  return { ...tree, moves, stems: stems.length, evaluations: moves.reduce((n, m) => n + m.candidates.length, 0) };
}

const aspect = (svg: SVGSVGElement) => { const r = svg.getBoundingClientRect(); return r.width && r.height ? r.width / r.height : 1.6; };

export function woodOne(svg: SVGSVGElement, tree: SearchTree): GardenHandle {
  return drawGarden(svg, tree, { quiet: true, fill: true, halo: false, canopy: false, crown: { heights: [0.96, 0.5, 0.9, 0.46, 0.98, 0.52, 0.92, 0.48], fan: 115 } });
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

/** A short damped sway of one tree's crown (every copy of it: the strokes, the halo, the core). */
export function shakeTree(svg: SVGSVGElement, stem: number) {
  const k = [0, 2.6, -2.0, 1.3, -0.75, 0.35, -0.12, 0];
  for (const g of svg.querySelectorAll<SVGGElement>(`[data-stem="${stem}"]`)) {
    g.getAnimations().forEach((a) => a.cancel());
    g.animate(k.map((d) => ({ transform: `skewX(${d}deg)` })), { duration: 1150, easing: "linear" });
  }
}

/** Make each background tree a focusable button that shakes: a transparent hit area over the tree,
 *  click or Enter. `onShake` sheds the burst. */
export function shakeable(svg: SVGSVGElement, name: string, onShake: (stem: number) => void) {
  for (const g of svg.querySelectorAll<SVGGElement>(".real .stem")) {
    const stem = Number(g.dataset.stem), bb = g.getBBox();
    const hit = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    hit.setAttribute("class", "hit");
    for (const [k, v] of [["x", bb.x], ["y", bb.y], ["width", bb.width], ["height", bb.height]] as const) hit.setAttribute(k, v.toFixed(1));
    g.insertBefore(hit, g.firstChild);
    g.setAttribute("tabindex", "0"); g.setAttribute("role", "button");
    g.setAttribute("aria-label", `${name} ${stem + 1}: shake it`);
    const go = () => { shakeTree(svg, stem); onShake(stem); };
    g.addEventListener("click", go);
    g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  }
}
