// A birch drawn from one restart of a logged search: pure geometry, no DOM, so the same code draws the
// home page's grove and can be checked on its own (no stroke crosses another within a tree).
//
// What the log sets, and what it does not:
//  - one tree per restart; its height is the restart's best in-sample Sharpe (set by the caller);
//  - one main branch per (move, feature family): the rules a move tried, grouped by the family of the
//    feature each one added (mom60, rev5, vol20, noise), in search order up the trunk;
//  - one twig per evaluation, on its group's branch;
//  - the leaves on a twig (2 to 5) are that rule's in-sample Sharpe within the tree, in four even steps
//    from the tree's worst rule to its best.
// The search reads from the crown's top down: the first move's groups nearest the leader, the last
// move's (which tried the most rules) lowest, on the longest branches.
// Branch lengths follow the crown's outline (a narrow oval), not the data, so the crown stays ordered.
// The bark marks, the leaves' shapes, tones and placement are decoration and claim nothing.
import type { TreeMove } from "./types";

export type P = [number, number];
export interface Twig { leaves: number }
export interface Group { twigs: Twig[] }
export interface Leaf { d: string; tone: number }
export interface Birch {
  trunk: string; bark: string; branches: string; twigs: string; leaves: Leaf[];
  l: number; r: number; top: number;
  /** twigs that found no clear place (branch index for each); drawn at their planned place */
  forced: number[];
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
  const leaves = (s: number) => 2 + Math.round(3 * (s - lo) / Math.max(1e-9, hi - lo));   // 2 to 5
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

export interface BirchOptions { height: number; groups: Group[]; seed: number; back?: boolean }

/** One birch, its foot at (0, 0), growing up (negative y). */
export function buildBirch(o: BirchOptions): Birch {
  const H = o.height, seed = o.seed, n = o.groups.length;
  let sid = seed * 7919;
  const rnd = () => hash(sid++);
  const k = o.back ? 0.82 : 1;                          // the back row: finer throughout
  const lines: Birch["lines"] = [];
  const leafS = Math.max(3.2, Math.min(9, H * 0.0105)) * k;
  // ---- the trunk: slender, gently tapering, running on as a fine leader to the top
  const wb = Math.max(3.2, H * 0.021) * k;
  const lean = (rnd() - 0.5) * H * 0.012, ph = rnd() * 6;
  const cx = (t: number) => lean * t * t + H * 0.004 * (Math.sin(ph + 2.4 * t) - Math.sin(ph));
  const w = (t: number) => Math.max(0.7 * k, wb * Math.pow(1 - t, 0.85) * (1 + 0.18 * Math.pow(1 - t, 14)));
  const axis: P[] = []; for (let i = 0; i <= 48; i++) { const t = i / 48; axis.push([cx(t), -t * H]); }
  const trunk = taper(axis, w, true);
  lines.push({ kind: "trunk", pts: axis, parent: -1 });

  // ---- bark: short dark marks across the trunk from one edge, denser and heavier toward the foot
  let bark = "";
  const marks: { t: number; side: number; th: number }[] = [];
  const tMax = 0.62, M = Math.round(H * 0.05);
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

  // ---- the crown: a narrow oval; main branches alternate up the trunk at steep angles, shorter
  // toward the top, arching out at their ends
  const cb = 0.27, top = 1.0, Wmax = H * 0.115 * k;
  // a narrow egg: widest a fifth of the way up the crown, rounding off at its base, full through the
  // middle and closing in a round shoulder to the leader
  const env = (t: number) => { const u = Math.max(0, Math.min(1, (t - cb) / (top - cb))); return Wmax * (u < 0.2 ? Math.sqrt(Math.max(0, 1 - Math.pow((0.2 - u) / 0.42, 2))) : Math.pow(Math.max(0, 1 - Math.pow((u - 0.2) / 0.84, 1.8)), 0.6)); };
  let branches = "";
  const brs: { pts: P[]; side: number; tAt: number; wa: number; we: number }[] = [];
  const side0 = seed % 2 ? 1 : -1;
  for (let i = 0; i < n; i++) {
    const f = n > 1 ? 1 - i / (n - 1) : 0.5;              // i = 0 (the first group) nearest the top
    const tAt = cb + (0.9 - cb) * Math.pow(f, 0.95);
    const side = i % 2 ? -side0 : side0;
    const theta = lerp(46, 20, f) * Math.PI / 180, chord = theta + lerp(18, 10, f) * Math.PI / 180;
    const A: P = [cx(tAt) + side * w(tAt) * 0.25, -tAt * H];
    let tipT = tAt + 0.06, L = 0, T: P = A;
    for (let it = 0; it < 4; it++) {
      // long enough to space its own twigs, else the crown's outline decides
      const X = Math.max(H * 0.018, env(tipT) * 0.8, o.groups[i].twigs.length * leafS * (o.groups[i].twigs.length > 5 ? 1.65 : 1.3));
      L = X / Math.sin(chord);
      // no branch reaches above the leader's last few per cent
      L = Math.min(L, Math.max(H * 0.02, (0.965 * H + A[1]) / Math.cos(chord)));
      T = [A[0] + side * Math.sin(chord) * L, A[1] - Math.cos(chord) * L];
      tipT = -T[1] / H;
    }
    const C: P = [A[0] + side * Math.sin(theta) * L * 0.66, A[1] - Math.cos(theta) * L * 0.66];   // steep out of the trunk, arching at the end
    const pts = quad(A, C, T, 16);
    const wa = Math.max(1.0, Math.min(3.0, w(tAt) * 0.5)) * k, we = 0.55 * k;
    brs.push({ pts, side, tAt, wa, we });
    lines.push({ kind: "branch", pts, parent: -1, id: i });
  }

  // ---- twigs: one per evaluation, hanging from their branch: a small outward kick, then an arc that
  // hangs a little off the vertical; three lengths in turn so neighbouring tassels sit at different
  // heights. The leaves alternate down the twig's lower part, hanging close to it. A twig (with its
  // leaves) that would touch any other stroke moves along its branch, then shortens, until it is clear.
  let twigs = "";
  const leaves: Leaf[] = [];
  const placed: { pts: P[]; leaf: boolean }[] = [];      // every twig and leaf so far
  const forced: number[] = [];
  for (let i = 0; i < n; i++) {
    const b = brs[i], g = o.groups[i], m = g.twigs.length;
    // the branch may run on a little past its planned tip, along its own curve, when its last twigs
    // need the room; it is drawn to the furthest twig it carries
    const B0 = b.pts, nB = B0.length - 1, ext: P[] = [...B0];
    { const a = B0[nB - 1], z = B0[nB]; for (let e = 1; e <= 3; e++) { const d = norm([z[0] - a[0], z[1] - a[1]]), st = Math.hypot(z[0] - a[0], z[1] - a[1]), prev = ext[ext.length - 1], dd = rot(d, b.side * 0.05 * e); ext.push([prev[0] + dd[0] * st, prev[1] + dd[1] * st]); } }
    let used = nB;
    const hard = [...brs.filter((_, q) => q !== i).map((x) => x.pts), axis];
    for (let j = 0; j < m; j++) {
      const nl = g.twigs[j].leaves, lean = (0.24 + (rnd() - 0.5) * 0.08) * b.side;
      let best: { tw: P[]; lv: { at: P; dir: P }[]; ls: number; idx: number } | null = null, okAny = false;
      // leaf size is decoration: a twig that cannot be placed clear with full-size leaves tries smaller ones
      for (const ls of [leafS, leafS * 0.85, leafS * 0.7]) {
        const u0 = m === 1 ? 0.75 : 0.2 + 0.76 * (j / (m - 1));
        for (const du of [0, 0.03, -0.03, 0.06, -0.06, 0.09, -0.09, 0.13, -0.13, 0.18, 0.24]) {
          const u = Math.min(1.18, Math.max(0.14, u0 + du));
          const idx = Math.min(ext.length - 2, Math.round(u * nB)), O = ext[idx], B = ext.slice(0, Math.max(nB, idx + 1) + 1);
          // longer toward the branch's end (the inner twigs short, so none hangs across the gap by the
          // trunk), in three lengths in turn
          let L = H * 0.08 * [1, 0.6, 0.8][j % 3] * (0.45 + 0.55 * u) * (0.95 + rnd() * 0.1) * k;
          const minL = ls * (1 + 0.55 * nl);
          L = Math.max(L, minL);
          for (; L >= minL * 0.999; L *= 0.88) {
            const C: P = [O[0] + b.side * ls * 0.3, O[1] + L * 0.2], E: P = [O[0] + b.side * ls * 0.3 + lean * L * 0.8, O[1] + L];
            const tw = quad(O, C, E, 16);
            const lv: { at: P; dir: P }[] = [];
            const tipDir = norm([E[0] - tw[15][0], E[1] - tw[15][1]]);
            lv.push({ at: E, dir: tipDir });
            for (let q = 1; q < nl; q++) {
              const pi = Math.max(3, Math.round(16 - q * ls * 0.62 / L * 16)), at = tw[pi];
              const tan = norm([tw[Math.min(16, pi + 1)][0] - tw[pi - 1][0], tw[Math.min(16, pi + 1)][1] - tw[pi - 1][1]]);
              lv.push({ at, dir: rot(tan, (q % 2 ? 1 : -1) * 32 * Math.PI / 180) });
            }
            const axes = lv.map((l) => [l.at, [l.at[0] + l.dir[0] * ls, l.at[1] + l.dir[1] * ls]] as P[]);
            const clash = near(tw, B, 0, 2)
              || hard.some((q) => near(tw, q, 1.5) || axes.some((x) => near(x, q, ls * 0.32 + 1)))
              || placed.some((q) => near(tw, q.pts, q.leaf ? ls * 0.32 + 1 : 1.5) || axes.some((x) => near(x, q.pts, q.leaf ? ls * 0.6 : ls * 0.32 + 1)))
              || axes.some((x) => near(x, B, ls * 0.32 + 1));
            if (!best) best = { tw, lv, ls, idx };
            if (!clash) { best = { tw, lv, ls, idx }; okAny = true; break; }
          }
          if (okAny) break;
        }
        if (okAny) break;
      }
      if (!okAny) forced.push(i);
      const { tw, lv, ls, idx } = best!;
      used = Math.max(used, idx + 1);
      twigs += taper(tw, (t) => lerp(0.7 * k, 0.32 * k, t));
      placed.push({ pts: tw, leaf: false });
      const twigId = lines.length;
      lines.push({ kind: "twig", pts: tw, parent: i, id: twigId });
      for (const l of lv) {
        leaves.push({ d: leafPath(l.at, l.dir, ls * (0.9 + rnd() * 0.2)), tone: Math.floor(rnd() * 3) });
        const ax: P[] = [l.at, [l.at[0] + l.dir[0] * ls, l.at[1] + l.dir[1] * ls]];
        placed.push({ pts: ax, leaf: true });
        lines.push({ kind: "leaf", pts: ax, parent: twigId });
      }
    }
    const fin = ext.slice(0, used + 1);
    branches += taper(fin, (t) => lerp(b.wa, b.we, Math.pow(t, 0.8)));
    b.pts = fin;
    const ln = lines.find((x) => x.kind === "branch" && x.id === i); if (ln) ln.pts = fin;
  }
  // extent
  let l = 0, r = 0, tp = 0;
  for (const ln of lines) for (const p of ln.pts) { l = Math.min(l, p[0]); r = Math.max(r, p[0]); tp = Math.min(tp, p[1]); }
  const pad = leafS * 0.5;
  return { trunk, bark, branches, twigs, leaves, l: l - pad, r: r + pad, top: tp - pad, lines, forced };
}

/** Crossings within one tree: pairs of strokes that cross, other than a stroke where it leaves its
 *  parent (a branch on the trunk, a twig on its branch, a leaf's stalk on its twig). */
export function crossings(b: Birch): { total: number; kinds: Record<string, number> } {
  const L = b.lines, kinds: Record<string, number> = {};
  const parentOf = (x: Birch["lines"][number]) => x.kind === "branch" ? L[0] : x.kind === "twig" ? L.find((y) => y.kind === "branch" && y.id === x.parent) : x.kind === "leaf" ? L[x.parent] : undefined;
  for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) {
    const a = L[i], q = L[j];
    if (parentOf(a) === q || parentOf(q) === a) continue;
    // two leaves on one twig share its stalk point only if both sit at one place: they do not
    if (near(a.pts, q.pts, 0, 0)) { const k = `${a.kind}-${q.kind}`; kinds[k] = (kinds[k] ?? 0) + 1; }
  }
  return { total: Object.values(kinds).reduce((s, v) => s + v, 0), kinds };
}

