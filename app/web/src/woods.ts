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
const NS = "http://www.w3.org/2000/svg";

/** The search restricted to some of its stems, renumbered 0..n-1. */
export function subTree(tree: SearchTree, stems: number[]): SearchTree {
  const moves = tree.moves.filter((m) => stems.includes(m.stem)).map((m) => ({ ...m, stem: stems.indexOf(m.stem) }));
  return { ...tree, moves, stems: stems.length, evaluations: moves.reduce((n, m) => n + m.candidates.length, 0) };
}

const aspect = (svg: SVGSVGElement) => { const r = svg.getBoundingClientRect(); return r.width && r.height ? r.width / r.height : 1.6; };

// ---------- the home page's grove ----------
// The restart example's logged search as eight trees standing on one ground line, drawn at 1:1 in CSS
// pixels (one <svg> per tree, so a tree's entrance and sway are composited). Every stroke is one
// evaluation that happened: each move's kept rule is a segment of the tree's axis (the first move's is
// the trunk), and every other rule the move scored is a twig off that segment. A twig's reach and angle
// are its in-sample Sharpe within the tree: the best reach long and nearly upright, the worst are short
// and droop. A tree's height is its best Sharpe (the tallest tree is the best restart). Line weight falls
// with depth in the tree (trunk, limbs, twigs) and with depth in the scene (the back row is smaller,
// finer and a lighter green). Buds are small solid points; a kept rule's point is a little larger.
type P = [number, number];
interface Built { d: string[]; buds: { x: number; y: number; r: number }[]; tips: { x: number; y: number; w: number }[]; l: number; r: number; top: number }

const hash = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const n2 = (v: number) => (Math.round(v * 100) / 100).toString();

// a quadratic from a through c to b, sampled
function quad(a: P, c: P, b: P, n = 10): P[] {
  const out: P[] = [];
  for (let i = 0; i <= n; i++) { const t = i / n, u = 1 - t; out.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]); }
  return out;
}
// a filled stroke along `pts`, its width easing from w0 to w1 (a tapered line); a flat end at the start
function taper(pts: P[], w: (t: number) => number, flat = false): string {
  const L: P[] = [], R: P[] = [], n = pts.length - 1;
  for (let i = 0; i <= n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
    const h = w(i / n) / 2, nx = -dy / len * h, ny = dx / len * h;
    L.push([pts[i][0] + nx, pts[i][1] + ny]); R.push([pts[i][0] - nx, pts[i][1] - ny]);
  }
  if (flat) { const s = L[1][0] > pts[1][0] ? 1 : -1; L[0] = [pts[0][0] + s * w(0) / 2, pts[0][1]]; R[0] = [pts[0][0] - s * w(0) / 2, pts[0][1]]; }   // a level foot, on the ground
  const tip = pts[n];
  return "M" + L.map((p) => `${n2(p[0])} ${n2(p[1])}`).join("L") + `L${n2(tip[0])} ${n2(tip[1])}L` + R.reverse().map((p) => `${n2(p[0])} ${n2(p[1])}`).join("L") + "Z";
}

/** One restart drawn as a tree, its foot at (0, 0) and growing up (negative y), `ht` px tall. */
function buildTree(moves: SearchTree["moves"], ht: number, back: boolean, seed: number): Built {
  const all = moves.flatMap((m) => m.candidates.map((c) => c.sharpe)), lo = Math.min(...all), hi = Math.max(...all);
  const s01 = (s: number) => (s - lo) / Math.max(1e-9, hi - lo);
  const k = back ? 0.8 : 1;
  const wBase = Math.max(2.2, Math.min(7, ht * 0.0105)) * k, wTwig = Math.max(0.55, Math.min(1.1, ht * 0.0017)) * k, rBud = Math.max(0.85, Math.min(1.6, ht * 0.0023)) * k;
  const out: Built = { d: [], buds: [], tips: [], l: 0, r: 0, top: 0 };
  const keptMoves = moves.filter((m) => !m.from_ground && m.kept).length;
  const crownBase = 0.4 * ht, crownLen = ht - crownBase;
  let node: P = [0, 0], width = wBase, kept = 0, sid = seed * 1000;
  const grow = (p: P) => { out.l = Math.min(out.l, p[0]); out.r = Math.max(out.r, p[0]); out.top = Math.min(out.top, p[1]); };
  for (const m of moves) {
    // the move's own segment of the axis: the trunk for the first, a limb for each kept rule after it
    let a = node, b = node, seg: P[] | null = null;
    if (m.from_ground) {
      b = [(hash(sid++) - 0.5) * ht * 0.02, -crownBase];
      seg = quad(a, [(hash(sid++) - 0.5) * ht * 0.03, -crownBase * 0.5], b, 14);
      const w0 = width, w1 = width * 0.5;
      out.d.push(taper(seg, (t) => (w0 + (w1 - w0) * t) * (1 + 0.55 * Math.pow(1 - t, 10)), true));   // a slight flare at the foot
      width = w1;
    } else if (m.kept) {
      const share = keptMoves > 1 ? [0.46, 0.34, 0.2, 0.12][Math.min(3, kept)] : 1, len = crownLen * share;
      const lean = ((kept % 2 ? 1 : -1) * (seed % 2 ? 1 : -1)) * (4 + hash(sid++) * 6) * Math.PI / 180;
      b = [a[0] + Math.sin(lean) * len, a[1] - Math.cos(lean) * len];
      seg = quad(a, [(a[0] + b[0]) / 2 + Math.cos(lean) * len * 0.05, (a[1] + b[1]) / 2], b, 10);
      const w0 = width, w1 = Math.max(0.7 * k, width * 0.55);
      out.d.push(taper(seg, (t) => w0 + (w1 - w0) * t));
      width = w1; kept++;
    }
    for (const p of seg ?? []) grow(p);
    // every other rule the move scored: a twig off the segment (or off the node, for a move that kept nothing)
    const others = m.candidates.map((_, i) => i).filter((i) => !(seg && i === m.chosen));
    const t0 = m.from_ground ? 0.74 : 0.18;
    others.forEach((ci, j) => {
      const v = s01(m.candidates[ci].sharpe), t = seg ? Math.min(1, t0 + (1 - t0) * ((j + 1) / (others.length + 1) + (hash(sid++) - 0.5) * 0.05)) : 1;
      const at: P = seg ? seg[Math.round(t * (seg.length - 1))] : node;
      const side = (j + seed) % 2 ? 1 : -1;
      const ang = (16 + (1 - v) * 84 + (hash(sid++) - 0.5) * 10) * Math.PI / 180;
      const L = ht * (0.045 + 0.13 * v) * (0.88 + hash(sid++) * 0.24);
      const tip: P = [at[0] + side * Math.sin(ang) * L, at[1] - Math.cos(ang) * L];
      const pts = quad(at, [(at[0] + tip[0]) / 2, (at[1] + tip[1]) / 2 - L * 0.16], tip, 8);
      out.d.push(taper(pts, (u) => wTwig * (1 - 0.65 * u)));
      out.buds.push({ x: tip[0], y: tip[1], r: rBud });
      out.tips.push({ x: tip[0], y: tip[1], w: 0.4 + v });
      grow([tip[0] - rBud, tip[1] - rBud]); grow([tip[0] + rBud, tip[1] + rBud]);
    });
    if (seg) { out.buds.push({ x: b[0], y: b[1], r: rBud * (m.from_ground ? 1.2 : 1.45) }); node = b; }
  }
  return out;
}

export interface Grove { stems: SVGSVGElement[]; sources: (stem?: number) => Source[]; evaluations: number; restarts: number }

/** Draw the search into `host` (a box whose bottom edge is the ground), each tree inside the box. */
export function drawGrove(host: HTMLElement, tree: SearchTree, box: { w: number; h: number }, offset: { x: number; y: number }): Grove {
  host.replaceChildren();
  const byStem = new Map<number, SearchTree["moves"]>();
  for (const m of tree.moves) { if (!byStem.has(m.stem)) byStem.set(m.stem, []); byStem.get(m.stem)!.push(m); }
  const stems = [...byStem.keys()].sort((a, b) => a - b);
  const best = new Map(stems.map((s) => [s, Math.max(...byStem.get(s)!.flatMap((m) => m.candidates.map((c) => c.sharpe)))]));
  const top = Math.max(...best.values());
  // heights in proportion to each restart's best Sharpe; the back row (every second restart) smaller
  const want = (s: number, i: number) => (best.get(s)! / top) * (i % 2 ? 0.74 : 1);
  let scale = box.h;
  let built = stems.map((s, i) => buildTree(byStem.get(s)!, scale * want(s, i), i % 2 === 1, s + 1));
  // fit: the tallest drawing (twigs included) exactly the box's height, and the row exactly its width
  for (let pass = 0; pass < 3; pass++) {
    const tall = Math.max(...built.map((b) => -b.top)), first = built[0], last = built[built.length - 1];
    const span = (-first.l) + last.r, room = box.w - span, gap = room / Math.max(1, stems.length - 1);
    const shrinkH = (box.h - 1) / tall, minGap = box.w * 0.06;
    const shrinkW = gap < minGap ? (box.w - minGap * (stems.length - 1)) / span : 1;
    const f = Math.min(shrinkH, shrinkW);
    if (Math.abs(f - 1) < 0.002) break;
    scale *= f;
    built = stems.map((s, i) => buildTree(byStem.get(s)!, scale * want(s, i), i % 2 === 1, s + 1));
  }
  const first = built[0], last = built[built.length - 1];
  const x0 = Math.ceil(-first.l + 0.5), x1 = Math.floor(box.w - last.r - 0.5), pad = 3;
  const svgs: SVGSVGElement[] = [];
  const xs = stems.map((_, i) => Math.round(x0 + (x1 - x0) * (stems.length > 1 ? i / (stems.length - 1) : 0.5)));   // whole pixels, inside the box
  // the back row first, so the front row's trees overlap it
  const order = stems.map((_, i) => i).sort((a, b) => (b % 2) - (a % 2) || a - b);
  for (const i of order) {
    const b = built[i], x = xs[i];
    const left = Math.floor(x + b.l - pad), right = Math.ceil(x + b.r + pad), up = Math.ceil(-b.top + pad);
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "stem" + (i % 2 ? " back" : ""));
    svg.setAttribute("viewBox", `${left - x} ${-up} ${right - left} ${up}`);
    svg.setAttribute("width", String(right - left)); svg.setAttribute("height", String(up));
    svg.dataset.stem = String(stems[i]);
    for (const [k, v] of [["--l", left], ["--w", right - left], ["--h", up], ["--ox", x - left], ["--i", stems[i]]] as const) svg.style.setProperty(k, `${v}${k === "--i" ? "" : "px"}`);
    const g = document.createElementNS(NS, "path");
    g.setAttribute("d", b.d.join("") + b.buds.map((p) => `M${n2(p.x - p.r)} ${n2(p.y)}a${n2(p.r)} ${n2(p.r)} 0 1 0 ${n2(2 * p.r)} 0a${n2(p.r)} ${n2(p.r)} 0 1 0 ${n2(-2 * p.r)} 0Z`).join(""));
    svg.appendChild(g);
    svgs[i] = svg;
    host.appendChild(svg);
  }
  const sources = (stem?: number): Source[] => {
    const out: Source[] = [];
    built.forEach((b, i) => {
      if (stem !== undefined && stems[i] !== stem) return;
      for (const t of b.tips) out.push({ x: offset.x + xs[i] + t.x, y: offset.y + box.h + t.y, vx: (t.x >= 0 ? 1 : -1) * (2 + hash(t.x * 7 + t.y) * 4), w: t.w * (0.4 + (-t.y / Math.max(1, -b.top))) });
    });
    return out;
  };
  return { stems: svgs, sources, evaluations: tree.moves.reduce((n, m) => n + m.candidates.length, 0), restarts: stems.length };
}

/** A tree's short damped sway about its foot, on the compositor; no sway under reduced motion. */
export function swayTree(svg: SVGSVGElement) {
  const k = [0, 1.1, -0.8, 0.5, -0.28, 0.12, 0];
  svg.getAnimations().forEach((a) => a.cancel());
  svg.animate(k.map((d) => ({ transform: `rotate(${d}deg)` })), { duration: 1800, easing: "cubic-bezier(.35, 0, 0, 1)" });
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
