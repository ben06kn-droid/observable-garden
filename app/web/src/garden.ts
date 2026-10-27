// The garden: a logged search drawn as trees. A bud is one evaluation, at the height of its
// in-sample Sharpe; a move fans out to every candidate it scored and the kept one grows on; a
// restart starts a new tree. Every stroke is an evaluation that happened.
//
// Drawn as trees: each stem's trunk is its anchor's edge and then every kept edge while the kept
// moves climb, and every branch grows out of the top of that trunk or from a kept node in the crown,
// forking upward and outward. A candidate that scored below its fork still sits at its own height,
// so it arches out of the crown and hangs down; nothing grows from the side of the trunk. The canopy
// outline is drawn around every bud of the tree. A blurred copy of the strokes behind the tree is
// its halo; with `neon`, the halo is narrow and a thin bright core runs along every stroke.
//
// With `crown` (the background trees, which are decoration): each stem is a tall or a short tree, a
// bare trunk and one crown at its own top, like a palm: every branch grows from the top of the trunk
// and drapes down to its bud, the best-scoring buds hanging least far. No branch points up or out.
//
// Each tree (stem) is a focusable button; each branch (move) inside it is clickable too.
import { drawHead, svgSink, type Kind } from "./heads";
import type { SearchTree } from "./types";

const NS = "http://www.w3.org/2000/svg";
export const W = 1080, H = 600;
const GROUND = 560, TOP = 30;
/** Where a one-tree garden's trunk stands (layout's root for one stem in an interactive garden). */
export const SEED: [number, number] = [(60 + W - 30) / 2, GROUND];

type Pt = [number, number];
const TREE = { trunk: [22, 9], flare: 12, spread: 1.0, pad: 20, bump: 30, lean: 0.06 };
let uid = 0;

function el<K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent?: Element): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  if (parent) parent.appendChild(e);
  return e;
}
const jit = (i: number, amp: number) => { const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return (x - Math.floor(x) - 0.5) * 2 * amp; };
const f = (n: number) => n.toFixed(1);

export interface Scale { lo: number; hi: number; y: (s: number) => number }
export function scaleFor(values: number[], bar?: number, tight = false): Scale {
  let lo = tight ? Infinity : -3.2, hi = tight ? -Infinity : 2.3;
  for (const v of values) { lo = Math.min(lo, v - 0.2); hi = Math.max(hi, v + 0.45); }
  if (bar !== undefined) hi = Math.max(hi, bar + 0.45);
  return { lo, hi, y: (s) => GROUND - ((s - lo) / (hi - lo)) * (GROUND - TOP) };
}

// candidates placed by score: the best nearest the fork, the rest alternating outwards
function offsets(sharpes: number[], spread: number): number[] {
  const order = sharpes.map((_, i) => i).sort((a, b) => sharpes[b] - sharpes[a]);
  const unit = spread / Math.max(1, Math.ceil(sharpes.length / 2)), out = new Array<number>(sharpes.length);
  order.forEach((idx, r) => { out[idx] = r === 0 ? 0 : (r % 2 ? -1 : 1) * Math.ceil(r / 2) * unit; });
  return out;
}

// a branch from a fork: up and out first, as an oak's limbs; one that ends below its fork arches
// over and hangs down to its bud
function branch(a: Pt, b: Pt, i: number): string {
  const dx = b[0] - a[0], rise = Math.max(18, Math.abs(dx) * 0.35);
  if (b[1] <= a[1]) {
    const c1: Pt = [a[0] + dx * 0.15 + jit(i, 3), a[1] - rise * 0.6 - (a[1] - b[1]) * 0.35];
    const c2: Pt = [b[0] - dx * 0.25 + jit(i + 1, 5), b[1] + (a[1] - b[1]) * 0.1];
    return `M${f(a[0])} ${f(a[1])} C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(b[0])} ${f(b[1])}`;
  }
  const c1: Pt = [a[0] + dx * 0.3 + jit(i, 3), a[1] - rise];
  const c2: Pt = [b[0] + jit(i + 1, 4), Math.min(a[1], b[1]) - rise * 0.8];
  return `M${f(a[0])} ${f(a[1])} C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(b[0])} ${f(b[1])}`;
}

function trunk(x0: number, base: number, x1: number, y1: number, k: number): string {
  const w0 = TREE.trunk[0] * k, w1 = TREE.trunk[1] * k, n = 10, L: Pt[] = [], R: Pt[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, y = base + (y1 - base) * t;
    const x = x0 + (x1 - x0) * t * t + TREE.lean * 40 * Math.sin(Math.PI * t);
    const w = w0 + (w1 - w0) * t + TREE.flare * k * Math.pow(1 - t, 6);
    L.push([x - w / 2 + jit(i + k * 7, 0.8), y]); R.push([x + w / 2 + jit(i + 31 + k * 7, 0.8), y]);
  }
  let d = `M${f(L[0][0])} ${f(L[0][1])}`;
  for (let i = 1; i <= n; i++) d += ` L${f(L[i][0])} ${f(L[i][1])}`;
  d += ` Q${f((L[n][0] + R[n][0]) / 2)} ${f(y1 - w1 * 0.5)} ${f(R[n][0])} ${f(R[n][1])}`;
  for (let i = n - 1; i >= 0; i--) d += ` L${f(R[i][0])} ${f(R[i][1])}`;
  return d;
}
function limb(a: Pt, b: Pt, wa: number, wb: number): string {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, bow = L * 0.06;
  const mx = (a[0] + b[0]) / 2 + nx * bow, my = (a[1] + b[1]) / 2 + ny * bow, m = (wa + wb) / 4;
  return `M${f(a[0] + nx * wa / 2)} ${f(a[1] + ny * wa / 2)} Q${f(mx + nx * m)} ${f(my + ny * m)} ${f(b[0] + nx * wb / 2)} ${f(b[1] + ny * wb / 2)}`
    + ` L${f(b[0] - nx * wb / 2)} ${f(b[1] - ny * wb / 2)} Q${f(mx - nx * m)} ${f(my - ny * m)} ${f(a[0] - nx * wa / 2)} ${f(a[1] - ny * wa / 2)} Z`;
}
function hull(pts: Pt[]): Pt[] {
  pts = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (pts.length < 3) return pts;
  const cross = (o: Pt, a: Pt, b: Pt) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo: Pt[] = [], up: Pt[] = [];
  for (const p of pts) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
  for (const p of pts.slice().reverse()) { while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }
  return lo.slice(0, -1).concat(up.slice(0, -1));
}
function canopy(pts: Pt[], pad: number, bump: number, seed: number): string | null {
  if (!pts.length) return null;
  let h = hull(pts); let cx = 0, cy = 0;
  for (const p of pts) { cx += p[0]; cy += p[1]; } cx /= pts.length; cy /= pts.length;
  if (h.length < 3) { const r = pad + 6; h = []; for (let a = 0; a < 6; a++) h.push([cx + r * Math.cos(a * Math.PI / 3), cy + r * 0.8 * Math.sin(a * Math.PI / 3)]); }
  else h = h.map((p) => { const dx = p[0] - cx, dy = p[1] - cy, n = Math.hypot(dx, dy) || 1; return [p[0] + dx / n * pad, p[1] + dy / n * pad] as Pt; });
  let d = `M${f(h[0][0])} ${f(h[0][1])}`, k = seed;
  for (let i = 0; i < h.length; i++) {
    const p = h[i], q = h[(i + 1) % h.length], len = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1, segs = Math.max(1, Math.round(len / bump));
    let nx = (q[1] - p[1]) / len, ny = -(q[0] - p[0]) / len;
    if (nx * ((p[0] + q[0]) / 2 - cx) + ny * ((p[1] + q[1]) / 2 - cy) < 0) { nx = -nx; ny = -ny; }
    for (let s = 1; s <= segs; s++) {
      const tm = (s - 0.5) / segs, t1 = s / segs, out = (len / segs) * 0.42 + jit(k++, 2);
      d += ` Q${f(p[0] + (q[0] - p[0]) * tm + nx * out)} ${f(p[1] + (q[1] - p[1]) * tm + ny * out)} ${f(p[0] + (q[0] - p[0]) * t1)} ${f(p[1] + (q[1] - p[1]) * t1)}`;
    }
  }
  return d + " Z";
}

interface Laid { stem: number; move: number; step: number; tip: Pt; from: Pt | null; kept: boolean; sharpe: number; rule: string; trunk: string | null; twig?: boolean }

// The run's tree (`twigs`): the kept rules make the branches, each tip at its rule's in-sample Sharpe,
// so the tree's height is the submitted Sharpe; every other rule a move scored is a short twig off
// that move's branch (or, for a move that kept nothing, off the node it started from), longer the
// better it scored. Every twig is an evaluation that happened.
function layoutTwigs(tree: SearchTree, y: (s: number) => number, x0: number, x1: number) {
  const per = (x1 - x0) / tree.stems, k = Math.min(1.3, per / 150);
  const stems = new Map<number, StemState & { side: number }>(); const laid: Laid[] = []; let step = 0;
  tree.moves.forEach((m, mi) => {
    let st = stems.get(m.stem);
    if (!st) { st = { root: x0 + per * (m.stem + 0.5), node: null, fork: null, buds: [], chainLen: 0, climbing: true, last: 0, k, side: 1 }; stems.set(m.stem, st); }
    const order = m.candidates.map((_, i) => i).sort((a, b) => m.candidates[b].sharpe - m.candidates[a].sharpe);
    const rank = new Map(order.map((ci, r) => [ci, m.candidates.length > 1 ? r / (m.candidates.length - 1) : 0]));
    const chosen = m.candidates[m.chosen];
    let a: Pt, b: Pt, seg: string | null = null;
    if (m.from_ground || !st.node) {
      a = [st.root, GROUND]; b = [st.root + jit(mi, 4), y(chosen.sharpe)];
      seg = trunk(st.root, GROUND, b[0], b[1], k * 0.45);   // weight at the base, a few pixels, tapering
    } else if (m.kept) {
      a = st.node; b = [a[0] + st.side * (26 + 24 * k), y(chosen.sharpe)]; st.side *= -1;
      const w = Math.max(1.4, TREE.trunk[1] * k * 0.45 * Math.pow(0.78, st.chainLen));
      seg = limb(a, b, w * 1.2, w * 0.55); st.chainLen++;
    } else { a = st.node; b = st.node; }
    const first = step + 1;
    const others = m.candidates.map((_, i) => i).filter((i) => !(seg && i === m.chosen));
    m.candidates.forEach((c, ci) => {
      step++;
      if (seg && ci === m.chosen) return;                     // the branch itself, below
      const j = others.indexOf(ci), t = seg ? 0.3 + (0.68 * (j + 1)) / (others.length + 1) : 1;
      const at: Pt = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
      const r = rank.get(ci) ?? 1, side = j % 2 ? 1 : -1, L = (12 + 30 * (1 - r)) * k, ang = ((35 + 30 * r + jit(step, 6)) * Math.PI) / 180;
      const tip: Pt = [at[0] + side * L * Math.sin(ang), at[1] - L * Math.cos(ang)];
      laid.push({ stem: m.stem, move: mi, step, tip, from: at, kept: false, sharpe: c.sharpe, rule: c.rule, trunk: null, twig: true });
      st!.buds.push(tip); st!.last = step;
    });
    if (seg) {   // the branch grows in with the move's first evaluation, its bud the kept rule
      laid.push({ stem: m.stem, move: mi, step: first, tip: b, from: null, kept: m.kept || !!m.from_ground, sharpe: chosen.sharpe, rule: chosen.rule, trunk: seg });
      st.node = b;
    }
  });
  laid.sort((p, q) => p.step - q.step);
  return { laid, stems, steps: step };
}
// Upright neon trees (page two's background, `crown.upright`): decoration from the logged search. A
// filled trunk tapering up to the crown's base; the first move of each tree a leader straight up to its
// top, every later move a filled limb branching up and outward from the leader, tapering to its tip;
// every second rule a move scored a hairline twig off that limb, up and outward, longer the better it
// scored, ending in a solid point of light.
function layoutUpright(tree: SearchTree, x0: number, x1: number, c: Crown) {
  const stems = new Map<number, StemState & { a: Pt; top: number; base: number; ht: number; j: number; n: number }>(); const laid: Laid[] = []; let step = 0;
  const count = new Map<number, number>(); tree.moves.forEach((m) => count.set(m.stem, (count.get(m.stem) ?? 0) + 1));
  tree.moves.forEach((m, mi) => {
    let st = stems.get(m.stem);
    const first = step + 1;
    if (!st) {
      const hs = c.heights[m.stem % c.heights.length], ht = hs * (GROUND - TOP), root = x0 + (c.xs ? c.xs[m.stem] : (m.stem + 0.5) / tree.stems) * (x1 - x0);
      st = { root, node: null, fork: null, buds: [], chainLen: 0, climbing: true, last: 0, k: Math.sqrt(hs) * 1.1, a: [root, GROUND - 0.42 * ht], top: GROUND - ht, base: GROUND - 0.42 * ht, ht, j: 0, n: count.get(m.stem) ?? 1 };
      stems.set(m.stem, st);
      laid.push({ stem: m.stem, move: mi, step: first, tip: [root, st.base], from: null, kept: false, sharpe: 0, rule: "", trunk: trunk(root, GROUND, root, st.base, st.k * 0.55) });
    }
    const j = st.j++, frac = st.n > 1 ? j / (st.n - 1) : 0, side = j % 2 ? 1 : -1;
    const a: Pt = j === 0 ? [st.root, st.base] : [st.root, st.base - (st.base - st.top) * (0.18 + 0.45 * frac)];
    const b: Pt = j === 0 ? [st.root + jit(mi, 3), st.top] : [st.root + side * st.ht * (0.2 - 0.06 * frac), a[1] - st.ht * (0.2 + 0.12 * (1 - frac))];
    const wa = (j === 0 ? 5.5 : 4) * st.k * (1 - 0.3 * frac), wb = 1.1 * st.k;
    laid.push({ stem: m.stem, move: mi, step: first, tip: b, from: null, kept: false, sharpe: 0, rule: "", trunk: limb(a, b, wa, wb) });
    const order = m.candidates.map((_, i) => i).sort((p, q) => m.candidates[q].sharpe - m.candidates[p].sharpe);
    const rank = new Map(order.map((ci, r) => [ci, m.candidates.length > 1 ? r / (m.candidates.length - 1) : 0]));
    const dx = b[0] - a[0], dy = b[1] - a[1], L0 = Math.hypot(dx, dy) || 1, ux = dx / L0, uy = dy / L0;
    m.candidates.forEach((cd, ci) => {
      step++;
      if (ci % 2) return;                                   // sparse: every second rule
      const t = 0.3 + 0.68 * ((ci + 1) / (m.candidates.length + 1)), at: Pt = [a[0] + dx * t, a[1] + dy * t];
      const r = rank.get(ci) ?? 1, s = (ci / 2) % 2 ? 1 : -1, ang = (s * (28 + 18 * r) * Math.PI) / 180;
      const vx = ux * Math.cos(ang) - uy * Math.sin(ang), vy = ux * Math.sin(ang) + uy * Math.cos(ang), L = st!.ht * (0.05 + 0.08 * (1 - r));
      const tip: Pt = [at[0] + vx * L, Math.min(at[1] + vy * L, at[1] - 2)];
      laid.push({ stem: m.stem, move: mi, step, tip, from: at, kept: false, sharpe: cd.sharpe, rule: cd.rule, trunk: null, twig: true });
      st!.buds.push(tip); st!.last = step;
    });
  });
  laid.sort((p, q) => p.step - q.step);
  return { laid, stems, steps: step };
}
function twigPath(a: Pt, b: Pt, i: number): string {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1], bow = 0.18 + jit(i, 0.06);
  return `M${f(a[0])} ${f(a[1])} Q${f(mx - dy * bow)} ${f(my + dx * bow)} ${f(b[0])} ${f(b[1])}`;
}
interface StemState { root: number; node: Pt | null; fork: Pt | null; buds: Pt[]; chainLen: number; climbing: boolean; last: number; k: number }

export interface Crown { heights: number[]; xs?: number[]; fan?: number; upright?: boolean; far?: number[] }   // per stem: height as a fraction of the box; x as a fraction of the width

function layout(tree: SearchTree, y: (s: number, stem: number) => number, x0: number, x1: number, crown?: Crown & { base: (stem: number) => number }) {
  const stems = new Map<number, StemState>(); const laid: Laid[] = []; let step = 0;
  // a crown spreads about as wide as the space its tree has, overlapping its neighbours a little
  const per = (x1 - x0) / tree.stems, k0 = Math.min(1.3, per / 150), fan0 = crown?.fan ?? Math.min(per * 0.9, 300) * TREE.spread;
  tree.moves.forEach((m, mi) => {
    let st = stems.get(m.stem);
    const hs = crown ? crown.heights[m.stem % crown.heights.length] : 1;
    if (!st) {
      const root = crown?.xs ? x0 + crown.xs[m.stem] * (x1 - x0) : x0 + per * (m.stem + 0.5);
      st = { root, node: null, fork: null, buds: [], chainLen: 0, climbing: true, last: 0, k: k0 * Math.sqrt(hs) }; stems.set(m.stem, st);
    }
    const k = st.k, fan = fan0 * (crown ? 0.55 + 0.45 * hs : 1);
    const off = offsets(m.candidates.map((c) => c.sharpe), m.from_ground ? fan : fan * 0.8);
    // the fork every branch of this move grows from: the top of the trunk for a move from the
    // ground (its anchor), the kept node otherwise
    const anchorX = st.root;
    const tips: Pt[] = m.candidates.map((c, ci) => [(m.from_ground || crown ? anchorX : st!.node![0]) + off[ci], y(c.sharpe, m.stem)]);
    if (crown) {   // fronds of uneven length: each tip moved by a fixed jitter, never above a third of the way down
      const top = crown.base(m.stem), d = (GROUND - top) * 0.36;
      tips.forEach((t, ci) => { const j = mi * 31 + ci; t[0] += jit(j, fan * 0.18); t[1] = Math.max(top + d * 0.3, t[1] + jit(j + 7, d * 0.3)); });
    }
    let fork: Pt;
    let trunkD: string | null = null;
    if (m.from_ground) {
      fork = [anchorX + off[m.chosen] * 0.15, crown ? crown.base(m.stem) : tips[m.chosen][1]];
      tips[m.chosen] = fork;
      trunkD = trunk(st.root, GROUND, fork[0], fork[1], k);
      st.fork = fork; st.chainLen = 1; st.climbing = true;
    } else fork = crown ? st.fork! : st.node!;
    const extend = !crown && !m.from_ground && m.kept && st.climbing && tips[m.chosen][1] < st.node![1] - 2;
    if (!m.from_ground && m.kept && !extend) st.climbing = false;
    m.candidates.forEach((c, ci) => {
      step++;
      if (crown && ci !== m.chosen && ci % 3 !== 1) return;   // the background trees are sparser: one frond in three
      const tip = tips[ci], chosen = ci === m.chosen;
      let from: Pt | null = fork, seg: string | null = null;
      if (m.from_ground && chosen) { from = null; seg = trunkD; }
      else if (chosen && extend) {
        const w = Math.max(3, TREE.trunk[1] * k * Math.pow(0.78, st!.chainLen));
        seg = limb(fork, tip, w * 1.25, w); from = null;
      }
      laid.push({ stem: m.stem, move: mi, step, tip, from, kept: chosen && m.kept, sharpe: c.sharpe, rule: c.rule, trunk: seg });
      st!.buds.push(tip); st!.last = step;
    });
    if (extend) st.chainLen++;
    if (m.kept) st.node = tips[m.chosen];
  });
  return { laid, stems, steps: step };
}

export interface GardenHandle {
  total: number;
  grow(): void;
  setStep(n: number): void;
  verdict(status: string): void;
  select(stem: number | null): void;
  rectOf(stem: number): DOMRect | null;
  treeRect(): DOMRect;
  /** a point of the drawing (its own units) on screen */
  toScreen(x: number, y: number): DOMPoint;
  /** the drawing's height for a Sharpe ratio, and the bar's ends (its own units) */
  ySharpe(s: number): number;
  ends: [number, number];
  /** the highest kept branch tip grown by `step` (all steps when omitted) */
  best(step?: number): { x: number; y: number; sharpe: number } | null;
  /** open every blossom, staggered, each on its own eased curve, over about `ms` */
  bloomAll(ms: number): void;
  bloom(fraction: number): void;
  onPick(cb: (stem: number, move: number | null) => void): void;
}

export interface DrawOptions {
  submitted?: { rule: string; sharpe: number };
  bar?: number;
  interactive?: boolean;
  quiet?: boolean;     // no axis, no bar, no ground line
  fill?: boolean;      // cover the whole box, edge to edge (cropping if needed)
  halo?: boolean;      // the blurred halo behind the strokes (default on)
  canopy?: boolean;    // the outline around each tree's buds (default on)
  tight?: boolean;     // fit the Sharpe scale to the buds, so the trees reach the top of the box
  blossom?: { kind: Kind; colour: number };   // flower heads on the branches, opened by bloom()
  neon?: boolean;      // neon tubing: a narrow halo and a thin bright core on every stroke
  crown?: Crown;       // decoration: tall and short trees, a bare trunk and one crown at the top
  width?: number;      // the viewBox width (default W), to match the box's aspect so nothing is cropped
  twigs?: boolean;     // the run's tree: branches of kept rules, a twig for every other evaluation
}

export function drawGarden(svg: SVGSVGElement, tree: SearchTree, opts: DrawOptions = {}): GardenHandle {
  const id = `g${++uid}`;
  const values = tree.moves.flatMap((m) => m.candidates.map((c) => c.sharpe));
  const sc = scaleFor(values, opts.bar, opts.tight);
  const Wd = opts.width ?? W;
  svg.setAttribute("viewBox", `0 0 ${f(Wd)} ${H}`);
  svg.setAttribute("preserveAspectRatio", opts.fill && !opts.width ? "xMidYMax slice" : "xMidYMax meet");
  svg.classList.add("garden");
  svg.classList.toggle("neon", !!opts.neon);
  svg.classList.remove("growing");
  svg.replaceChildren();
  const defs = el("defs", {}, svg);
  const filter = el("filter", { id: `${id}-halo`, x: "-30%", y: "-30%", width: "160%", height: "160%" }, defs);
  el("feGaussianBlur", { stdDeviation: opts.neon ? "2.6" : "14" }, filter);
  if (!opts.quiet) {
    const ax = el("g", { class: "axis", "aria-hidden": "true" }, svg);
    for (let s = Math.ceil(sc.lo); s <= Math.floor(sc.hi); s++) {
      el("line", { x1: 34, x2: 40, y1: f(sc.y(s)), y2: f(sc.y(s)) }, ax);
      el("text", { x: 28, y: f(sc.y(s) + 4), "text-anchor": "end" }, ax).textContent = String(s);
    }
    if (opts.bar !== undefined) {
      const bar = el("g", { class: "bar", "aria-hidden": "true" }, svg);
      const by = f(sc.y(opts.bar)), n = 12;   // in segments, so colour can travel along it (runView.ts)
      for (let j = 0; j < n; j++) {   // each a faint wide glow under a lit line (no filter)
        const g = el("g", { "data-tide": "" }, bar), a = { x1: f(40 + ((Wd - 50) * j) / n), x2: f(40 + ((Wd - 50) * (j + 1)) / n), y1: by, y2: by };
        el("line", { ...a, class: "glow" }, g); el("line", { ...a, class: "lit" }, g);
      }
      for (const x of [40, Wd - 10]) el("circle", { cx: x, cy: by, r: 2.4, class: "cap", "data-tide": "" }, bar);   // the tube's end caps
    }
    el("path", { d: `M40 ${GROUND} L${Wd - 10} ${GROUND}`, class: "ground", "aria-hidden": "true" }, svg);
  }
  const haloLayer = el("g", { class: "halo", "aria-hidden": "true", filter: `url(#${id}-halo)` }, svg);
  const real = el("g", { class: "real" }, svg);
  // crown mode: each stem's buds pressed, in Sharpe order, into a crown at the top of its own height
  let yOf = (v: number, _stem: number) => sc.y(v), crownOpt: (Crown & { base: (stem: number) => number }) | undefined;
  if (opts.crown) {
    const c = opts.crown, span = GROUND - TOP, range = new Map<number, [number, number]>();
    for (const m of tree.moves) for (const cd of m.candidates) { const r = range.get(m.stem) ?? [Infinity, -Infinity]; range.set(m.stem, [Math.min(r[0], cd.sharpe), Math.max(r[1], cd.sharpe)]); }
    const top = (st: number) => GROUND - c.heights[st % c.heights.length] * span;
    const depth = (st: number) => (GROUND - top(st)) * 0.36;
    // every bud hangs at least a third of the crown's depth below the top, so no branch runs flat
    yOf = (v, st) => { const [lo, hi] = range.get(st)!; return top(st) + depth(st) * (0.35 + 0.65 * (1 - (v - lo) / Math.max(1e-9, hi - lo))); };
    crownOpt = { ...c, base: top };
  }
  const res = opts.twigs ? layoutTwigs(tree, sc.y, 60, Wd - 30)
    : opts.crown?.upright ? layoutUpright(tree, 30, Wd - 30, opts.crown)
    : layout(tree, yOf, opts.quiet ? 30 : 60, Wd - 30, crownOpt);

  // the submitted bud: the first kept evaluation of the submitted rule at its score
  const key = (r: string) => r.split(" ").sort().join(" ");
  let sub: Laid | null = null; const onPath = new Set<number>();
  if (opts.submitted) {
    for (const b of res.laid) if (!sub && b.kept && Math.abs(b.sharpe - opts.submitted.sharpe) < 1e-12 && key(b.rule) === key(opts.submitted.rule)) sub = b;
    if (sub) for (const b of res.laid) if (b.stem === sub.stem && b.kept && b.step <= sub.step) onPath.add(b.step);
  }

  const stemEls = new Map<number, SVGGElement>(), moveEls = new Map<number, SVGGElement>();
  for (const [s, st] of res.stems) {
    const g = el("g", { class: `stem c${s % 3}${opts.crown?.far?.includes(s) ? " far" : ""}`, "data-stem": s, "data-tide": "" }, real);
    if (opts.interactive) {
      const moves = tree.moves.filter((m) => m.stem === s);
      const best = Math.max(...moves.flatMap((m) => m.candidates.map((c) => c.sharpe)));
      g.setAttribute("tabindex", "0"); g.setAttribute("role", "button");
      g.setAttribute("aria-label", `Tree ${s + 1}: ${moves.length} moves, ${moves.reduce((n, m) => n + m.candidates.length, 0)} evaluations, best ${best.toFixed(3)}. Enter to go inside.`);
    }
    stemEls.set(s, g);
    const d = opts.canopy === false ? null : canopy(st.buds, TREE.pad * Math.max(0.6, st.k), TREE.bump * Math.max(0.6, st.k), s * 97);
    if (d) { const c = el("path", { d, class: "canopy" }, g); c.dataset.step = String(st.last); }
  }
  for (const b of res.laid) {
    const stem = stemEls.get(b.stem)!;
    let mg = moveEls.get(b.move);
    if (!mg) { mg = el("g", { class: "move", "data-move": b.move, "data-tide": "" }, stem); moveEls.set(b.move, mg); }
    const cls = onPath.has(b.step) ? " path" : "";
    const e = b.trunk
      ? el("path", { d: b.trunk, class: "trunk" + cls }, mg)
      : el("path", { d: b.twig ? twigPath(b.from!, b.tip, b.step) : branch(b.from!, b.tip, b.step), class: "twig" + cls + (b.tip[1] > b.from![1] + 4 ? " down" : ""), pathLength: 1 }, mg);
    e.dataset.step = String(b.step);
    const r = b.kept ? 1.4 : 1, pt = opts.crown?.upright || opts.twigs;   // points of light, or the round buds
    const bud = el("ellipse", { cx: f(b.tip[0]), cy: f(b.tip[1]), rx: f((pt ? 1.6 : 2.6) * r), ry: f((pt ? 1.6 : 3.6) * r), class: "bud" + cls + (b.kept ? " kept" : "") }, mg);
    bud.dataset.step = String(b.step);
  }
  if (opts.halo !== false) {
    const copy = real.cloneNode(true) as SVGGElement;
    copy.querySelectorAll("[tabindex]").forEach((e) => { e.removeAttribute("tabindex"); e.removeAttribute("role"); e.removeAttribute("aria-label"); });
    haloLayer.append(...Array.from(copy.childNodes));
  }
  if (opts.neon) {   // the tube's bright core: a thin copy of every stroke over it, not interactive
    const core = real.cloneNode(true) as SVGGElement;
    core.setAttribute("class", "core"); core.setAttribute("aria-hidden", "true");
    core.querySelectorAll("[tabindex]").forEach((e) => { e.removeAttribute("tabindex"); e.removeAttribute("role"); e.removeAttribute("aria-label"); });
    svg.insertBefore(core, real.nextSibling);
  }

  // blossoms: a head on each of the top third (by in-sample Sharpe) of every move's candidates, so
  // each head sits on an evaluation; they open in search order as bloom(fraction) rises, the fraction
  // being the replay's done / total. The submitted rule's head is a deeper tone.
  const heads: SVGGElement[] = [];
  if (opts.blossom) {
    const layer = el("g", { class: "blossoms" }, svg);
    const byMove = new Map<number, Laid[]>();
    for (const b of res.laid) { if (!byMove.has(b.move)) byMove.set(b.move, []); byMove.get(b.move)!.push(b); }
    const chosenSteps = new Set<number>();
    for (const list of byMove.values()) list.slice().sort((a, b) => b.sharpe - a.sharpe).slice(0, Math.ceil(list.length / 3)).forEach((b) => chosenSteps.add(b.step));
    for (const b of res.laid) {
      if (!chosenSteps.has(b.step)) continue;
      const hd = el("g", { class: "blossom" }, layer);       // the head's place baked into its paths (heads.ts svgSink)
      drawHead(svgSink(hd, new DOMMatrix().translate(b.tip[0], b.tip[1])), opts.blossom.kind, opts.blossom.colour, b === sub ? 8 : 6, 1, b === sub);
      heads.push(hd);
    }
  }

  const growable = svg.querySelectorAll<SVGElement>("[data-step]");
  let pick: ((stem: number, move: number | null) => void) | null = null;
  if (opts.interactive) {
    const fire = (target: EventTarget | null) => {
      const t = target as Element | null;
      const stem = t?.closest(".real .stem") as SVGGElement | null;
      if (!stem || !pick) return;
      const move = t?.closest(".move") as SVGGElement | null;
      pick(Number(stem.dataset.stem), move ? Number(move.dataset.move) : null);
    };
    real.addEventListener("click", (e) => fire(e.target));
    real.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fire(e.target); } });
  }
  return {
    total: res.steps,
    grow: () => svg.classList.add("growing"),
    setStep: (n) => growable.forEach((e) => e.classList.toggle("on", Number(e.dataset.step) <= n)),
    verdict: (status) => { svg.dataset.verdict = status; },
    select: (stem) => svg.querySelectorAll<SVGGElement>(".stem").forEach((g) => g.classList.toggle("selected", Number(g.dataset.stem) === stem)),
    rectOf: (stem) => stemEls.get(stem)?.getBoundingClientRect() ?? null,
    treeRect: () => real.getBoundingClientRect(),
    toScreen: (x, y) => { const p = svg.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(svg.getScreenCTM() ?? new DOMMatrix()); },
    ySharpe: (s) => sc.y(s),
    ends: [40, Wd - 10],
    best: (n) => {
      let top: Laid | null = null;
      for (const b of res.laid) if (b.kept && (n === undefined || b.step <= n) && (!top || b.sharpe > top.sharpe)) top = b;
      return top ? { x: top.tip[0], y: top.tip[1], sharpe: top.sharpe } : null;
    },
    bloomAll: (ms) => heads.forEach((hd, i) => { hd.style.setProperty("--bd", `${((i / Math.max(1, heads.length)) * ms * 0.7).toFixed(0)}ms`); hd.classList.add("open"); }),
    bloom: (fraction) => { const k = Math.round(Math.max(0, Math.min(1, fraction)) * heads.length); heads.forEach((hd, i) => hd.classList.toggle("open", i < k)); },
    onPick: (cb) => { pick = cb; },
  };
}
