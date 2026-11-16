// A birch drawn from one restart of a logged search: pure geometry, no DOM, so the same code draws the
// home page's grove and can be checked on its own (no stroke crosses another within a tree).
//
// What the log sets, and what it does not:
//  - one tree per restart; its height is the restart's best in-sample Sharpe (set by the caller);
//  - one main branch per (move, feature family): the rules a move tried, grouped by the family of the
//    feature each one added (mom60, rev5, vol20, noise), in search order up the trunk;
//  - one twig per evaluation, on its group's branch;
//  - the leaves on a twig (1, 2 or 3) are that rule's in-sample Sharpe within the tree, in three even
//    steps from the tree's worst rule to its best.
// The search reads from the crown's top down: the first move's groups nearest the leader, the last
// move's (which tried the most rules) lowest, on the longest branches.
// Branch lengths follow the crown's outline (a narrow oval), not the data, so the crown stays ordered.
// The bark marks, the leaves' shapes, tones and placement are decoration and claim nothing.
import type { TreeMove } from "./types";

export type P = [number, number];
export interface Twig { leaves: number }
export interface Group { twigs: Twig[] }
export interface Leaf { d: string; tone: number; x: number; y: number }
export interface Birch {
  trunk: string; bark: string; branches: string; twigs: string; leaves: Leaf[];
  l: number; r: number; top: number;
  /** twigs that found no clear place (branch index for each); drawn at their planned place */
  forced: number[];
  /** the placed geometry, compact: what the page draws from (renderPrims), with no search */
  prims: Prims;
  /** centre lines of every stroke, for the crossing check */
  lines: { kind: "trunk" | "branch" | "twig" | "leaf"; pts: P[]; parent: number; id?: number }[];
}

const FAMILIES = ["mom60", "rev5", "vol20", "noise"];
const hash = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const n2 = (v: number) => (Math.round(v * 100) / 100).toString();
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const rot = (v: P, a: number): P => [v[0] * Math.cos(a) - v[1] * Math.sin(a), v[0] * Math.sin(a) + v[1] * Math.cos(a)];
const norm = (v: P): P => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };

/** A restart's moves as branch groups: per move, its rules grouped by the family of the feature each added. */
export function birchGroups(moves: TreeMove[]): Group[] {
  const all = moves.flatMap((m) => m.candidates.map((c) => c.sharpe)), lo = Math.min(...all), hi = Math.max(...all);
  const leaves = (s: number) => 1 + Math.round(2 * (s - lo) / Math.max(1e-9, hi - lo));   // 1, 2 or 3
  const family = (tok: string) => tok.replace(/^[+-]/, "").split("_")[0];
  const out: Group[] = [];
  let parent = new Set<string>();
  for (const m of moves) {
    const by = new Map<string, Twig[]>();
    for (const c of m.candidates) {
      const added = c.rule.split(" ").filter((t) => !parent.has(t));
      const f = added.length ? family(added[added.length - 1]) : "same";
      if (!by.has(f)) by.set(f, []);
      by.get(f)!.push({ leaves: leaves(c.sharpe) });
    }
    const order = [...by.keys()].sort((a, b) => (FAMILIES.indexOf(a) + 99) % 99 - (FAMILIES.indexOf(b) + 99) % 99);
    for (const f of order) out.push({ twigs: by.get(f)! });
    if (m.kept) parent = new Set(m.candidates[m.chosen].rule.split(" "));
  }
  return out;
}

// ---- geometry helpers
function quad(a: P, c: P, b: P, n: number): P[] {
  const out: P[] = [];
  for (let i = 0; i <= n; i++) { const t = i / n, u = 1 - t; out.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]); }
  return out;
}
/** a filled stroke along `pts`, its width w(t); a level end at the start when `flat` */
function taper(pts: P[], w: (t: number) => number, flat = false): string {
  const L: P[] = [], R: P[] = [], n = pts.length - 1;
  for (let i = 0; i <= n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n, i + 1)], d = norm([b[0] - a[0], b[1] - a[1]]), h = w(i / n) / 2;
    L.push([pts[i][0] - d[1] * h, pts[i][1] + d[0] * h]); R.push([pts[i][0] + d[1] * h, pts[i][1] - d[0] * h]);
  }
  if (flat) { const s = L[1][0] < pts[1][0] ? -1 : 1; L[0] = [pts[0][0] + s * w(0) / 2, pts[0][1]]; R[0] = [pts[0][0] - s * w(0) / 2, pts[0][1]]; }
  const tip = pts[n];
  return "M" + L.map((p) => `${n2(p[0])} ${n2(p[1])}`).join("L") + `L${n2(tip[0])} ${n2(tip[1])}L` + R.reverse().map((p) => `${n2(p[0])} ${n2(p[1])}`).join("L") + "Z";
}
function segX(a: P, b: P, c: P, d: P): boolean {
  const o = (p: P, q: P, r: P) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const d1 = o(c, d, a), d2 = o(c, d, b), d3 = o(a, b, c), d4 = o(a, b, d);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}
/** whether two polylines cross (or come within `gap` px of each other), ignoring the first `skip` px of `a` */
function near(a: P[], b: P[], gap: number, skip = 0): boolean {
  if (skip === 0) {   // far apart: no segment can come within `gap`
    let ax0 = Infinity, ax1 = -Infinity, ay0 = Infinity, ay1 = -Infinity, bx0 = Infinity, bx1 = -Infinity, by0 = Infinity, by1 = -Infinity;
    for (const p of a) { if (p[0] < ax0) ax0 = p[0]; if (p[0] > ax1) ax1 = p[0]; if (p[1] < ay0) ay0 = p[1]; if (p[1] > ay1) ay1 = p[1]; }
    for (const p of b) { if (p[0] < bx0) bx0 = p[0]; if (p[0] > bx1) bx1 = p[0]; if (p[1] < by0) by0 = p[1]; if (p[1] > by1) by1 = p[1]; }
    if (ax0 > bx1 + gap || bx0 > ax1 + gap || ay0 > by1 + gap || by0 > ay1 + gap) return false;
  }
  let run = 0;
  for (let i = 1; i < a.length; i++) {
    run += Math.hypot(a[i][0] - a[i - 1][0], a[i][1] - a[i - 1][1]);
    if (run < skip) continue;
    for (let j = 1; j < b.length; j++) {
      if (segX(a[i - 1], a[i], b[j - 1], b[j])) return true;
      if (gap > 0 && segDist(a[i], b[j - 1], b[j]) < gap) return true;
    }
  }
  return false;
}
function segDist(p: P, a: P, b: P): number {
  const dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}

// a birch leaf: ovate with a drawn-out point, a short stalk; the tip at y = -10, the stalk's end at y = +10
export const BIRCH_LEAF: number[][] = [
  [0, 10], [0.25, 7.6, 0.3, 6.2, 0.35, 5.2],                   // the stalk
  [3.6, 4.8, 6.4, 1.8, 6, -1.2], [5.6, -4.2, 2.4, -6.8, 0, -10],  // the right edge to the point
  [-2.4, -6.8, -5.6, -4.2, -6, -1.2], [-6.4, 1.8, -3.6, 4.8, -0.35, 5.2],
  [-0.3, 6.2, -0.25, 7.6, 0, 10],
];
export const BIRCH_LEAF_D = (() => { const [m, ...cs] = BIRCH_LEAF; return `M${m[0]} ${m[1]}` + cs.map((c) => "C" + c.join(" ")).join("") + "Z"; })();
/** the leaf placed: its stalk's end at `at`, pointing along `dir`, `s` px long */
function leafPath(at: P, dir: P, s: number): string {
  const k = s / 20, d = norm(dir), nx = -d[1], ny = d[0];
  // local (x, y) → world: y runs from the tip (-10) to the stalk (+10), so -y is along `dir`
  const tf = (x: number, y: number): string => { const u = (10 - y) * k, v = x * k; return `${n2(at[0] + d[0] * u + nx * v)} ${n2(at[1] + d[1] * u + ny * v)}`; };
  const [m, ...cs] = BIRCH_LEAF;
  return `M${tf(m[0], m[1])}` + cs.map((c) => `C${tf(c[0], c[1])} ${tf(c[2], c[3])} ${tf(c[4], c[5])}`).join("") + "Z";
}

/** The placed geometry of one tree, compact. Branches: centre line (x, y, x, y, …) and end widths;
 *  twigs: a quadratic's three points; leaves: stalk point, angle (radians), length, tone. */
export interface Prims { k: number; branches: { p: number[]; a: number; e: number }[]; twigs: number[][]; leaves: number[][] }
const twigD = (o: P, c: P, e: P, k: number) => taper(quad(o, c, e, 16), (t) => lerp(0.7 * k, 0.32 * k, t));
const branchD = (pts: P[], a: number, e: number) => taper(pts, (t) => lerp(a, e, Math.pow(t, 0.8)));
/** Draw a tree's placed geometry: the branch, twig and leaf paths (the leaves by tone). */
export function renderPrims(p: Prims): { branches: string; twigs: string; leaves: string[] } {
  const pairs = (f: number[]) => { const out: P[] = []; for (let i = 0; i + 1 < f.length; i += 2) out.push([f[i], f[i + 1]]); return out; };
  const leaves = ["", "", ""];
  for (const [x, y, a, s, t] of p.leaves) leaves[t] += leafPath([x, y], [Math.cos(a), Math.sin(a)], s);
  return {
    branches: p.branches.map((b) => branchD(pairs(b.p), b.a, b.e)).join(""),
    twigs: p.twigs.map((t) => twigD([t[0], t[1]], [t[2], t[3]], [t[4], t[5]], p.k)).join(""),
    leaves,
  };
}

export interface BirchOptions { height: number; groups: Group[]; seed: number; back?: boolean; crown?: number /* the crown's width, × the default */; attempts?: number }

/** One birch, its foot at (0, 0), growing up (negative y), with no stroke crossing another: built with
 *  the seed's own jitter, and rebuilt with other jitter (bark, spacing, twig lengths and angles; never
 *  anything the log sets) until it is clean, at most `attempts` times (6); the cleanest is kept. */
export function buildBirch(o: BirchOptions): Birch {
  let best: Birch | null = null, bestN = Infinity;
  for (let attempt = 0; attempt < (o.attempts ?? 6); attempt++) {
    const b = buildOnce(o, attempt), c = crossings(b).total;
    if (c < bestN) { best = b; bestN = c; }
    if (c === 0) break;
  }
  return best!;
}

function buildOnce(o: BirchOptions, attempt: number): Birch {
  const H = o.height, seed = o.seed, n = o.groups.length;
  let sid = seed * 7919 + attempt * 104729;
  const rnd = () => hash(sid++);
  const k = o.back ? 0.82 : 1;                          // the back row: finer throughout
  const lines: Birch["lines"] = [];
  // leaves large enough to read as leaves at 1x: at least 7.5 px, 1.35% of the tree's height
  const leafS = Math.max(7.5, Math.min(12, H * 0.0135) * k);   // the floor holds in the back row too
  // ---- the trunk: slender, gently tapering, with a very slight lean and curve, running on as a fine
  // leader that ends inside the crown (the top twigs reach a little above it)
  const wb = Math.max(3.2, H * 0.021) * k, tLead = 0.95;
  const lean = (seed % 2 ? 1 : -1) * H * (0.012 + rnd() * 0.01), ph = rnd() * 6;
  const cx = (t: number) => lean * Math.pow(t, 1.6) + H * 0.005 * (Math.sin(ph + 3.1 * t) - Math.sin(ph));
  // the pale bark carries well up into the crown, narrowing gradually into the leader
  const w = (t: number) => Math.max(0.6 * k, wb * Math.pow(Math.max(0, 1 - t / tLead), 0.55) * (1 + 0.18 * Math.pow(1 - t, 14)));
  const axis: P[] = []; for (let i = 0; i <= 48; i++) { const t = (i / 48) * tLead; axis.push([cx(t), -t * H]); }
  const trunk = taper(axis, w, true);
  lines.push({ kind: "trunk", pts: axis, parent: -1 });

  // ---- bark: short dark marks across the trunk from one edge, denser and heavier toward the foot
  let bark = "";
  const marks: { t: number; side: number; th: number }[] = [];
  const tMax = 0.78, M = Math.round(H * 0.055);
  for (let i = 0; i < M * 3 && marks.length < M; i++) {
    const u = rnd(), t = 0.015 + (1 - Math.pow(1 - u * (1 - Math.pow(1 - tMax, 2.4)), 1 / 2.4));
    if (t > tMax) continue;
    const y = t * H, ww = w(t), side = rnd() < 0.5 ? -1 : 1;
    const th = Math.max(0.8, ww * (0.09 + rnd() * 0.2) * (1.3 - 0.6 * t / tMax));
    if (marks.some((m) => m.side === side && Math.abs(m.t * H - y) < m.th + th + 2.2)) continue;
    if (marks.some((m) => Math.abs(m.t * H - y) < Math.max(m.th, th) * 0.7)) continue;
    marks.push({ t, side, th });
    const len = ww * (0.3 + rnd() * 0.45), x0 = cx(t) + side * (ww / 2 + 0.6), tilt = (rnd() - 0.5) * 0.16 * len;
    // a wedge: its full thickness at the trunk's edge, thinning to a point inside it, its inner edge
    // slightly bowed; one in four a pair, a thin second mark just above the first
    const mx = x0 - side * len * 0.55;
    bark += `M${n2(x0)} ${n2(-y - th / 2)}Q${n2(mx)} ${n2(-y - th * 0.45 + tilt * 0.5)} ${n2(x0 - side * len)} ${n2(-y + tilt)}Q${n2(mx)} ${n2(-y + th * 0.4 + tilt * 0.5)} ${n2(x0)} ${n2(-y + th / 2)}Z`;
    if (rnd() < 0.25) { const y2 = y + th / 2 + 1.6, l2 = len * 0.5; bark += `M${n2(x0)} ${n2(-y2 - 0.45)}L${n2(x0 - side * l2)} ${n2(-y2)}L${n2(x0)} ${n2(-y2 + 0.45)}Z`; }
  }

  // the foot: darker, fissured, a few broad marks on both sides
  for (let q = 0; q < 7; q++) {
    const side = rnd() < 0.5 ? -1 : 1, t = 0.003 + rnd() * 0.045, y = t * H, ww = w(t);
    {
      const len = ww * (0.2 + rnd() * 0.35), th = ww * (0.08 + rnd() * 0.14), x0 = cx(t) + side * (ww / 2 + 0.6);
      bark += `M${n2(x0)} ${n2(-y - th)}L${n2(x0 - side * len)} ${n2(-y)}L${n2(x0)} ${n2(-y + th * 0.6)}Z`;
    }
  }

  // ---- the crown: a narrow oval, widest near its middle. Main branches alternate up the trunk at
  // irregular heights (never mirrored), climb steeply, and only their last fifth turns outward and
  // down; their reach follows the oval with some irregularity, and each is long enough to carry its
  // own twigs (a long branch for a small reach climbs more steeply)
  const cb = 0.25, top = tLead + 0.035, Wmax = H * 0.095 * k * (o.crown ?? 1);
  const env = (t: number) => { const u = Math.max(0, Math.min(1, (t - cb) / (top - cb))); return Wmax * Math.max(0.3, Math.pow(Math.sin(Math.PI * u), 0.75)); };
  let branches = "";
  // a branch and the twigs it carries
  const brs: { pts: P[]; side: number; tAt: number; wa: number; we: number; twigs: Twig[]; id: number }[] = [];
  const side0 = seed % 2 ? 1 : -1;
  // attachment heights: the space between two branches in proportion to the twigs they carry, so a
  // large group has the room it needs (irregular spacing that comes from the data), each moved a little
  const lo = cb + 0.01, hi = tLead - 0.05;
  const need = o.groups.map((g) => Math.sqrt(g.twigs.length));
  const steps = need.slice(1).map((v, i) => (v + need[i]) / 2), total = steps.reduce((a, v) => a + v, 0) || 1;
  const heights: number[] = [hi];
  steps.forEach((v, i) => heights.push(heights[i] - (hi - lo) * v / total));
  for (let i = 1; i < n - 1; i++) heights[i] += (rnd() - 0.5) * 0.5 * (hi - lo) * Math.min(steps[i - 1], steps[i]) / total;
  for (let i = 0; i < n; i++) {
    const f = n > 1 ? 1 - i / (n - 1) : 0.5;              // i = 0 (the first group) nearest the top
    const tAt = heights[i];
    const side = i % 2 ? -side0 : side0;
    const m = o.groups[i].twigs.length;
    const X = Math.max(H * 0.02, env(tAt + 0.08) * (0.72 + rnd() * 0.28));
    const L = Math.max(X / (Math.sin(lerp(30, 18, f) * Math.PI / 180) * 0.8 + 0.2), m * leafS * (m > 5 ? 1.4 : 1.15));
    const theta = Math.asin(Math.max(Math.sin(8 * Math.PI / 180), Math.min(Math.sin(40 * Math.PI / 180), (X / L - 0.2) / 0.8))) + (rnd() - 0.5) * 0.06;
    const A: P = [cx(tAt) + side * w(tAt) * 0.25, -tAt * H];
    const dU: P = [side * Math.sin(theta), -Math.cos(theta)];
    // climbing steeply, then the last fifth turns gently outward, its fine tip just level
    const T: P = [A[0] + dU[0] * L * 0.82 + side * L * 0.17, A[1] + dU[1] * L * 0.82 + L * 0.01];
    const C1: P = [A[0] + dU[0] * L * 0.45, A[1] + dU[1] * L * 0.45], C2: P = [A[0] + dU[0] * L * 0.78, A[1] + dU[1] * L * 0.78];
    const pts: P[] = [];
    for (let q = 0; q <= 20; q++) { const t = q / 20, u = 1 - t; pts.push([u * u * u * A[0] + 3 * u * u * t * C1[0] + 3 * u * t * t * C2[0] + t * t * t * T[0], u * u * u * A[1] + 3 * u * u * t * C1[1] + 3 * u * t * t * C2[1] + t * t * t * T[1]]); }
    const wa = Math.max(0.9, Math.min(2.6, w(tAt) * 0.45)) * k, we = 0.45 * k;
    brs.push({ pts, side, tAt, wa, we, twigs: o.groups[i].twigs, id: i });
    lines.push({ kind: "branch", pts, parent: -1, id: i });
  }

  // ---- twigs: one per evaluation, hanging from their branch: a small outward kick, then an arc that
  // hangs a little off the vertical; three lengths in turn so neighbouring tassels sit at different
  // heights. The leaves alternate down the twig's lower part, hanging close to it. A twig (with its
  // leaves) that would touch any other stroke moves along its branch, then shortens, until it is clear.
  let twigs = "";
  const leaves: Leaf[] = [];
  const prims: Prims = { k, branches: [], twigs: [], leaves: [] };
  const placed: { pts: P[]; leaf: boolean }[] = [];      // every twig and leaf so far
  const forced: number[] = [];
  for (let i = 0; i < brs.length; i++) {
    const b = brs[i], g = { twigs: b.twigs }, m = g.twigs.length;
    // the branch may run on a little past its planned tip, along its own curve, when its last twigs
    // need the room; it is drawn to the furthest twig it carries
    const B0 = b.pts, nB = B0.length - 1, ext: P[] = [...B0];
    { const a = B0[nB - 1], z = B0[nB]; for (let e = 1; e <= 7; e++) { const d = norm([z[0] - a[0], z[1] - a[1]]), st = Math.hypot(z[0] - a[0], z[1] - a[1]), prev = ext[ext.length - 1], dd = rot(d, b.side * 0.03 * e); ext.push([prev[0] + dd[0] * st, prev[1] + dd[1] * st]); } }
    let used = nB;
    const hard = [...brs.filter((_, q) => q !== i).map((x) => x.pts), axis];
    for (let j = 0; j < m; j++) {
      // alternately on the branch's outer and inner side, each its own length and angle
      const nl = g.twigs[j].leaves, outer0 = (j + i) % 2 === 0, lenF = rnd(), tilt = (50 + rnd() * 18) * Math.PI / 180, droop = 0.28 + rnd() * 0.2;
      let best: { tw: P[]; q: P[]; lv: { at: P; dir: P }[]; ls: number; idx: number } | null = null, okAny = false;
      // leaf size is decoration: a twig that cannot be placed clear with full-size leaves tries smaller ones
      // full size on its own side, then the other side, then smaller leaves; last, half the clearance
      // (strokes may come close, never cross)
      for (const [ls, outer, cf] of [[leafS, outer0, 1], [leafS, !outer0, 1], [leafS * 0.85, outer0, 1], [leafS * 0.85, !outer0, 1], [leafS * 0.75, outer0, 1], [leafS * 0.75, !outer0, 1], [leafS * 0.75, outer0, 0.45], [leafS * 0.75, !outer0, 0.45], [leafS * 0.65, outer0, 0.35], [leafS * 0.65, !outer0, 0.35]] as [number, boolean, number][]) {
        const u0 = m === 1 ? 0.8 : 0.22 + 0.76 * ((j + (rnd() - 0.5) * 0.6) / (m - 1));
        // the planned place first, then outward along the whole branch in both directions
        const tries: number[] = [u0];
        for (let e = 1; e <= 34; e++) { const v = u0 + Math.ceil(e / 2) * 0.035 * (e % 2 ? 1 : -1); if (v >= 0.15 && v <= 1.32) tries.push(v); }
        for (const u of tries) {
          const idx = Math.min(ext.length - 2, Math.round(u * nB)), O = ext[idx], B = ext.slice(0, Math.max(nB, idx + 1) + 1);
          const d = norm([ext[idx + 1][0] - O[0], ext[idx + 1][1] - O[1]]);
          // the normal on this twig's side of the branch: the outer side faces away from the trunk
          const nA: P = [-d[1], d[0]], nOut = Math.sign(nA[0]) === b.side ? nA : [d[1], -d[0]] as P, nrm = outer ? nOut : [-nOut[0], -nOut[1]] as P;
          // a short sprig: out from the branch, leaning along it, its tip hanging a little
          const dir = norm([nrm[0] * Math.cos(tilt) + d[0] * Math.sin(tilt), nrm[1] * Math.cos(tilt) + d[1] * Math.sin(tilt)]);
          let L = ls * (1.6 + 2.2 * lenF) * (0.75 + 0.25 * Math.min(1, u));
          const minL = ls * (0.7 + 0.42 * nl);
          L = Math.max(L, minL) * (cf < 1 ? 1.6 : 1);           // the last resort may also reach further
          for (; L >= minL * 0.999; L *= 0.9) {
            const C: P = [O[0] + dir[0] * L * 0.6, O[1] + dir[1] * L * 0.6], E: P = [O[0] + dir[0] * L, O[1] + dir[1] * L + droop * L];
            const tw = quad(O, C, E, 16);
            // leaves along the hanging end: one at the tip, the rest back along the twig, alternating
            // sides, each leaning toward the ground
            const lv: { at: P; dir: P }[] = [];
            const tipDir = norm([E[0] - tw[15][0], E[1] - tw[15][1] + 0.3]);
            lv.push({ at: E, dir: tipDir });
            for (let q = 1; q < nl; q++) {
              const pi = Math.max(3, Math.round(16 - q * ls * 0.6 / L * 16)), at = tw[pi];
              const tan = norm([tw[Math.min(16, pi + 1)][0] - tw[pi - 1][0], tw[Math.min(16, pi + 1)][1] - tw[pi - 1][1]]);
              lv.push({ at, dir: norm([...rot(tan, (q % 2 ? 1 : -1) * 50 * Math.PI / 180)].map((v, c) => v + (c === 1 ? 0.45 : 0)) as P) });
            }
            const axes = lv.map((l) => [l.at, [l.at[0] + l.dir[0] * ls, l.at[1] + l.dir[1] * ls]] as P[]);
            // the branch's run-on to reach this twig, if any, must clear everything already drawn too
            const run = idx + 1 > used ? ext.slice(used, idx + 2) : null;
            const ownLeaves = axes.some((x, a) => axes.some((y, c) => c > a && (x[0][0] !== y[0][0] || x[0][1] !== y[0][1]) && near(x, y, cf * ls * 0.45)));
            const clash = near(tw, B, 0, 2) || near(tw, axis, 1) || ownLeaves
              || (run !== null && (placed.some((q) => near(run, q.pts, q.leaf ? cf * (ls * 0.32 + 1) : cf * 1.5)) || hard.some((q) => near(run, q, cf * 1.5))))
              || hard.some((q) => near(tw, q, cf * 1.5) || axes.some((x) => near(x, q, cf * (ls * 0.32 + 1))))
              || placed.some((q) => near(tw, q.pts, q.leaf ? cf * (ls * 0.32 + 1) : cf * 1.5) || axes.some((x) => near(x, q.pts, q.leaf ? cf * ls * 0.6 : cf * (ls * 0.32 + 1))))
              || axes.some((x) => near(x, B, cf * (ls * 0.32 + 1)));
            if (!best) best = { tw, q: [O, C, E], lv, ls, idx };
            if (!clash) { best = { tw, q: [O, C, E], lv, ls, idx }; okAny = true; break; }
          }
          if (okAny) break;
        }
        if (okAny) break;
      }
      if (!okAny) forced.push(i);
      const { tw, q, lv, ls, idx } = best!;
      prims.twigs.push([q[0][0], q[0][1], q[1][0], q[1][1], q[2][0], q[2][1]]);
      used = Math.max(used, idx + 1);
      twigs += twigD(q[0], q[1], q[2], k);
      placed.push({ pts: tw, leaf: false });
      const twigId = lines.length;
      lines.push({ kind: "twig", pts: tw, parent: b.id, id: twigId });
      for (const l of lv) {
        const size = ls * (0.9 + rnd() * 0.2), tone = Math.floor(rnd() * 3);
        leaves.push({ d: leafPath(l.at, l.dir, size), tone, x: l.at[0] + l.dir[0] * ls * 0.5, y: l.at[1] + l.dir[1] * ls * 0.5 });
        prims.leaves.push([l.at[0], l.at[1], Math.atan2(l.dir[1], l.dir[0]), size, tone]);
        const ax: P[] = [l.at, [l.at[0] + l.dir[0] * ls, l.at[1] + l.dir[1] * ls]];
        placed.push({ pts: ax, leaf: true });
        lines.push({ kind: "leaf", pts: ax, parent: twigId });
      }
    }
    const fin = ext.slice(0, used + 1);
    branches += branchD(fin, b.wa, b.we);
    prims.branches.push({ p: fin.flat(), a: b.wa, e: b.we });
    b.pts = fin;
    const ln = lines.find((x) => x.kind === "branch" && x.id === b.id); if (ln) ln.pts = fin;
  }
  // extent
  let l = 0, r = 0, tp = 0;
  for (const ln of lines) for (const p of ln.pts) { l = Math.min(l, p[0]); r = Math.max(r, p[0]); tp = Math.min(tp, p[1]); }
  const pad = leafS * 0.5;
  return { trunk, bark, branches, twigs, leaves, l: l - pad, r: r + pad, top: tp - pad, lines, forced, prims };
}

/** Crossings within one tree: pairs of strokes that cross, other than a stroke where it leaves its
 *  parent (a branch on the trunk, a twig on its branch, a leaf's stalk on its twig). */
export function crossings(b: Birch): { total: number; kinds: Record<string, number> } {
  const L = b.lines, kinds: Record<string, number> = {};
  const parentOf = (x: Birch["lines"][number]) => x.kind === "branch" ? (x.parent >= 0 ? L.find((y) => y.kind === "branch" && y.id === x.parent) : L[0]) : x.kind === "twig" ? L.find((y) => y.kind === "branch" && y.id === x.parent) : x.kind === "leaf" ? L[x.parent] : undefined;
  for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) {
    const a = L[i], q = L[j];
    if (parentOf(a) === q || parentOf(q) === a) continue;
    // two leaves on one twig share its stalk point only if both sit at one place: they do not
    if (near(a.pts, q.pts, 0, 0)) { const k = `${a.kind}-${q.kind}`; kinds[k] = (kinds[k] ?? 0) + 1; }
  }
  return { total: Object.values(kinds).reduce((s, v) => s + v, 0), kinds };
}

