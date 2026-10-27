// The garden: a logged search drawn as trees. A bud is one evaluation, at the height of its
// in-sample Sharpe; a move fans out to every candidate it scored and the kept one grows on; a
// restart starts a new tree. Every stroke is an evaluation that happened.
//
// Drawn as trees: each stem's trunk is its anchor's edge and then every kept edge while the kept
// moves climb, and every branch grows out of the top of that trunk or from a kept node in the crown,
// forking upward and outward. A candidate that scored below its fork still sits at its own height,
// so it arches out of the crown and hangs down; nothing grows from the side of the trunk. The canopy
// outline is drawn around every bud of the tree. A blurred copy of the strokes behind the tree is
// its halo.
//
// Each tree (stem) is a focusable button; each branch (move) inside it is clickable too.
import type { SearchTree } from "./types";

const NS = "http://www.w3.org/2000/svg";
export const W = 1080, H = 600;
const GROUND = 560, TOP = 30;

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
export function scaleFor(values: number[], bar?: number): Scale {
  let lo = -3.2, hi = 2.3;
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

interface Laid { stem: number; move: number; step: number; tip: Pt; from: Pt | null; kept: boolean; sharpe: number; rule: string; trunk: string | null }
interface StemState { root: number; node: Pt | null; fork: Pt | null; buds: Pt[]; chainLen: number; climbing: boolean; last: number; k: number }

function layout(tree: SearchTree, y: (s: number) => number, x0: number, x1: number) {
  const stems = new Map<number, StemState>(); const laid: Laid[] = []; let step = 0;
  // a crown spreads about as wide as the space its tree has, overlapping its neighbours a little
  const per = (x1 - x0) / tree.stems, k = Math.min(1.3, per / 150), fan = Math.min(per * 0.9, 300) * TREE.spread;
  tree.moves.forEach((m, mi) => {
    let st = stems.get(m.stem);
    if (!st) { st = { root: x0 + per * (m.stem + 0.5), node: null, fork: null, buds: [], chainLen: 0, climbing: true, last: 0, k }; stems.set(m.stem, st); }
    const off = offsets(m.candidates.map((c) => c.sharpe), m.from_ground ? fan : fan * 0.8);
    // the fork every branch of this move grows from: the top of the trunk for a move from the
    // ground (its anchor), the kept node otherwise
    const anchorX = st.root;
    const tips: Pt[] = m.candidates.map((c, ci) => [(m.from_ground ? anchorX : st!.node![0]) + off[ci], y(c.sharpe)]);
    let fork: Pt;
    let trunkD: string | null = null;
    if (m.from_ground) {
      fork = [anchorX + off[m.chosen] * 0.15, tips[m.chosen][1]];
      tips[m.chosen] = fork;
      trunkD = trunk(st.root, GROUND, fork[0], fork[1], k);
      st.fork = fork; st.chainLen = 1; st.climbing = true;
    } else fork = st.node!;
    const extend = !m.from_ground && m.kept && st.climbing && tips[m.chosen][1] < st.node![1] - 2;
    if (!m.from_ground && m.kept && !extend) st.climbing = false;
    m.candidates.forEach((c, ci) => {
      step++;
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
  onPick(cb: (stem: number, move: number | null) => void): void;
}

export interface DrawOptions {
  submitted?: { rule: string; sharpe: number };
  bar?: number;
  interactive?: boolean;
  quiet?: boolean;     // no axis, no bar, no ground line
  fill?: boolean;      // cover the whole box, edge to edge (cropping if needed)
  halo?: boolean;      // the blurred halo behind the strokes (default on)
}

export function drawGarden(svg: SVGSVGElement, tree: SearchTree, opts: DrawOptions = {}): GardenHandle {
  const id = `g${++uid}`;
  const values = tree.moves.flatMap((m) => m.candidates.map((c) => c.sharpe));
  const sc = scaleFor(values, opts.bar);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", opts.fill ? "xMidYMax slice" : "xMidYMax meet");
  svg.classList.add("garden");
  svg.classList.remove("growing");
  svg.replaceChildren();
  const defs = el("defs", {}, svg);
  const filter = el("filter", { id: `${id}-halo`, x: "-30%", y: "-30%", width: "160%", height: "160%" }, defs);
  el("feGaussianBlur", { stdDeviation: "14" }, filter);
  if (!opts.quiet) {
    const ax = el("g", { class: "axis", "aria-hidden": "true" }, svg);
    for (let s = Math.ceil(sc.lo); s <= Math.floor(sc.hi); s++) {
      el("line", { x1: 34, x2: 40, y1: f(sc.y(s)), y2: f(sc.y(s)) }, ax);
      el("text", { x: 28, y: f(sc.y(s) + 4), "text-anchor": "end" }, ax).textContent = String(s);
    }
    if (opts.bar !== undefined) {
      const bar = el("g", { class: "bar", "aria-hidden": "true" }, svg);
      el("line", { x1: 40, x2: W - 10, y1: f(sc.y(opts.bar)), y2: f(sc.y(opts.bar)) }, bar);
      el("text", { x: 48, y: f(sc.y(opts.bar) - 8) }, bar).textContent = `BAR ${opts.bar.toFixed(3)}`;
    }
    el("path", { d: `M40 ${GROUND} L${W - 10} ${GROUND}`, class: "ground", "aria-hidden": "true" }, svg);
  }
  const haloLayer = el("g", { class: "halo", "aria-hidden": "true", filter: `url(#${id}-halo)` }, svg);
  const real = el("g", { class: "real" }, svg);
  const res = layout(tree, sc.y, opts.quiet ? 30 : 60, W - 30);

  // the submitted bud: the first kept evaluation of the submitted rule at its score
  const key = (r: string) => r.split(" ").sort().join(" ");
  let sub: Laid | null = null; const onPath = new Set<number>();
  if (opts.submitted) {
    for (const b of res.laid) if (!sub && b.kept && Math.abs(b.sharpe - opts.submitted.sharpe) < 1e-12 && key(b.rule) === key(opts.submitted.rule)) sub = b;
    if (sub) for (const b of res.laid) if (b.stem === sub.stem && b.kept && b.step <= sub.step) onPath.add(b.step);
  }

  const stemEls = new Map<number, SVGGElement>(), moveEls = new Map<number, SVGGElement>();
  for (const [s, st] of res.stems) {
    const g = el("g", { class: "stem", "data-stem": s }, real);
    if (opts.interactive) {
      const moves = tree.moves.filter((m) => m.stem === s);
      const best = Math.max(...moves.flatMap((m) => m.candidates.map((c) => c.sharpe)));
      g.setAttribute("tabindex", "0"); g.setAttribute("role", "button");
      g.setAttribute("aria-label", `Tree ${s + 1}: ${moves.length} moves, ${moves.reduce((n, m) => n + m.candidates.length, 0)} evaluations, best ${best.toFixed(3)}. Enter to go inside.`);
    }
    stemEls.set(s, g);
    const d = canopy(st.buds, TREE.pad * Math.max(0.6, st.k), TREE.bump * Math.max(0.6, st.k), s * 97);
    if (d) { const c = el("path", { d, class: "canopy" }, g); c.dataset.step = String(st.last); }
  }
  for (const b of res.laid) {
    const stem = stemEls.get(b.stem)!;
    let mg = moveEls.get(b.move);
    if (!mg) { mg = el("g", { class: "move", "data-move": b.move }, stem); moveEls.set(b.move, mg); }
    const cls = onPath.has(b.step) ? " path" : "";
    const e = b.trunk
      ? el("path", { d: b.trunk, class: "trunk" + cls }, mg)
      : el("path", { d: branch(b.from!, b.tip, b.step), class: "twig" + cls + (b.tip[1] > b.from![1] + 4 ? " down" : ""), pathLength: 1 }, mg);
    e.dataset.step = String(b.step);
    const r = b.kept ? 1.4 : 1;
    const bud = el("ellipse", { cx: f(b.tip[0]), cy: f(b.tip[1]), rx: f(2.6 * r), ry: f(3.6 * r), class: "bud" + cls + (b.kept ? " kept" : "") }, mg);
    bud.dataset.step = String(b.step);
  }
  if (opts.halo !== false) {
    const copy = real.cloneNode(true) as SVGGElement;
    copy.querySelectorAll("[tabindex]").forEach((e) => { e.removeAttribute("tabindex"); e.removeAttribute("role"); e.removeAttribute("aria-label"); });
    haloLayer.append(...Array.from(copy.childNodes));
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
    onPick: (cb) => { pick = cb; },
  };
}
