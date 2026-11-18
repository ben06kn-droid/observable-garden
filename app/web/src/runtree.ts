// The demo's run tree (DESIGN.md 3, demo): one logged search drawn as one tree, in fine lines, built with the
// home section's birch generator (src/birch.ts: its tapered strokes and its no-crossing test). Pure geometry,
// no DOM, so it can be checked on its own.
//
// What the log sets, and what it does not:
//  - one stem per start of the search: the first from the ground, and one more for each restart (a restart
//    starts again from the ground), all from one foot;
//  - one length of stem per kept move, in search order from the foot up;
//  - one branch per run of consecutive rules a move scored that add a feature of the same family (mom60,
//    rev5, vol20, noise), in the order scored, attached where the stem had reached when the move scored them;
//  - one twig per rule scored, on its branch; its length is the rule's in-sample Sharpe within the search, in
//    three even steps from the worst rule to the best;
//  - the submitted rule's twig, and the stem and branch below it, are the pink path.
// Stem heights, leans and spacing, the crown's outline and every jitter are decoration and claim nothing.
//
// Growth: each stroke carries the span of the search it grows over, in evaluations (a twig over its own
// evaluation, a branch over its run, a stem over its moves; the first stem's bare foot in the unit before the
// first evaluation), so a renderer draws the tree at any point of the search (drawRunTree's `at`).
import { near, quad, taper, type P } from "./birch";
import type { SearchTree, TreeMove } from "./types";

export type Kind = "stem" | "branch" | "twig";
export interface Stroke {
  kind: Kind; pts: P[]; w0: number; w1: number;
  /** when it grows, in evaluations (0 is the first; the bare foot grows from -1) */
  t0: number; t1: number;
  stem: number; move: number; pink?: boolean;
  /** a twig: its evaluation's global index and the rule's Sharpe */
  eval?: number; sharpe?: number;
}
export interface RunTree {
  strokes: Stroke[]; evaluations: number; stems: number;
  l: number; r: number; top: number;
  /** pink: the submitted path's strokes (pieces of the stem and branch below it, and its twig) */
  pink: Stroke[];
  /** the submitted twig's tip, if there is one */
  mark: P | null;
  /** strokes that found no clear place (drawn at their planned place) */
  forced: number;
  /** where one kept move's length of stem ends and the next begins: a small mark, shown once the stem passes it */
  nodes: { p: P; t: number; stem: number }[];
}

const hash = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const norm = (v: P): P => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };
const rot = (v: P, a: number): P => [v[0] * Math.cos(a) - v[1] * Math.sin(a), v[0] * Math.sin(a) + v[1] * Math.cos(a)];
const family = (tok: string) => tok.replace(/^[+-]/, "").split("_")[0];
const key = (rule: string) => rule.split(" ").filter(Boolean).sort().join(" ");

/** a polyline cut at fraction f of its length */
export function cut(pts: P[], f: number): P[] {
  if (f >= 1) return pts;
  if (f <= 0) return [pts[0], pts[0]];
  let total = 0; for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  let want = total * f; const out: P[] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const s = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    if (s >= want) { const t = want / (s || 1); out.push([lerp(pts[i - 1][0], pts[i][0], t), lerp(pts[i - 1][1], pts[i][1], t)]); return out; }
    want -= s; out.push(pts[i]);
  }
  return out;
}
function plen(pts: P[]) { let t = 0; for (let i = 1; i < pts.length; i++) t += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return t; }
function cubic(a: P, b: P, c: P, d: P, n: number): P[] {
  const out: P[] = [];
  for (let i = 0; i <= n; i++) { const t = i / n, u = 1 - t; out.push([u * u * u * a[0] + 3 * u * u * t * b[0] + 3 * u * t * t * c[0] + t * t * t * d[0], u * u * u * a[1] + 3 * u * u * t * b[1] + 3 * u * t * t * c[1] + t * t * t * d[1]]); }
  return out;
}

// a spatial index of placed polylines, so a twig is tested only against what lies near it
class Grid {
  cells = new Map<string, number[]>(); items: P[][] = [];
  constructor(private s = 24) {}
  private keys(pts: P[], pad: number): string[] {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const p of pts) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
    const out: string[] = [];
    for (let i = Math.floor((x0 - pad) / this.s); i <= Math.floor((x1 + pad) / this.s); i++)
      for (let j = Math.floor((y0 - pad) / this.s); j <= Math.floor((y1 + pad) / this.s); j++) out.push(i + "," + j);
    return out;
  }
  add(pts: P[]): number { const id = this.items.push(pts) - 1; for (const k of this.keys(pts, 0)) { const c = this.cells.get(k); if (c) c.push(id); else this.cells.set(k, [id]); } return id; }
  hits(pts: P[], gap: number, skip: Set<number>): boolean {
    const seen = new Set<number>();
    for (const k of this.keys(pts, gap)) for (const id of this.cells.get(k) ?? []) {
      if (seen.has(id) || skip.has(id)) continue; seen.add(id);
      if (near(pts, this.items[id], gap)) return true;
    }
    return false;
  }
}

export interface RunTreeOptions { height?: number; submitted?: { rule: string; sharpe: number } | null; seed?: number }

/** Build the run's tree from its search (the gate's search tree, as the worker returns it). */
export function buildRunTree(tree: SearchTree, o: RunTreeOptions = {}): RunTree {
  const Hmax = o.height ?? 720;
  let sid = (o.seed ?? 1) * 7919;
  const rnd = () => hash(sid++);
  const moves = tree.moves;
  // global evaluation index of each move's first rule
  const first: number[] = []; { let k = 0; for (const m of moves) { first.push(k); k += m.candidates.length; } }
  const E = moves.reduce((n, m) => n + m.candidates.length, 0);
  const allS = moves.flatMap((m) => m.candidates.map((c) => c.sharpe)), lo = Math.min(...allS), hi = Math.max(...allS);
  const tier = (s: number) => Math.round(2 * (s - lo) / Math.max(1e-9, hi - lo));   // 0, 1, 2
  // the tree's height grows with the number of rules scored (a search of 400 rules or more stands full height)
  const H = Hmax * (0.5 + 0.5 * Math.min(1, Math.sqrt(E / 400)));

  // ---- stems: a new one where the search starts from the ground
  const stemMoves: number[][] = [];
  moves.forEach((m, i) => { if (m.from_ground || !stemMoves.length) stemMoves.push([i]); else stemMoves[stemMoves.length - 1].push(i); });
  const S = stemMoves.length;

  // placement: the first start is the trunk, standing in the middle, tallest. Each restart (a start from the
  // ground again) is a limb leaving the trunk low down, alternately right and left; a later restart leaves lower
  // and reaches further out, so no limb crosses another; each a little shorter than the one inside it
  const slot = (s: number) => s === 0 ? 0 : (s % 2 ? 1 : -1) * Math.ceil(s / 2);
  const maxSlot = Math.max(0, ...Array.from({ length: S }, (_, s) => Math.abs(slot(s))));
  const d = S > 1 ? Math.min(H * 0.13, H * 0.66 / (2 * maxSlot)) : 0;      // between neighbouring crowns
  const reachMax = S > 1 ? d * 0.5 : H * 0.24;                                // a crown's half width
  const bareOf = (s: number) => S === 1 ? 0.2 : s === 0 ? 0.4 : 0.3;      // the bare foot, a share of the stem
  const strokes: Stroke[] = [];
  const grid = new Grid(20);
  const stemIds: number[] = [];
  let forced = 0;

  interface StemGeo { axis: P[]; u: number[]; w: (u: number) => number; H: number; dir: number; bare: number }
  const geos: StemGeo[] = [];
  for (let s = 0; s < S; s++) {
    const k = Math.abs(slot(s)), sg = Math.sign(slot(s)) || 1;
    const Hs = H * (1 - 0.085 * k);
    let axis: P[];
    if (s === 0) {
      const lean = H * 0.01 * (rnd() - 0.5);
      axis = cubic([0, 0], [0, -H * 0.35], [lean, -H * 0.7], [lean * 1.6, -H], 72);
    } else {
      // leaving the trunk at a share of its height: the first restart highest, the last lowest
      const ua = S > 2 ? lerp(0.3, 0.1, (s - 1) / (S - 2)) : 0.25;
      const tr = geos[0].axis, n = tr.length - 1, A = tr[Math.round(ua * n)];
      const cx = slot(s) * d + (rnd() - 0.5) * d * 0.1;
      const out = Math.abs(cx - A[0]);
      const B: P = [A[0] + sg * out * 0.38, A[1] - out * 0.5];
      const C: P = [cx - sg * d * 0.04, lerp(A[1], -Hs, 0.42)];
      axis = cubic(A, B, C, [cx, -Hs], 72);
    }
    const wb = s === 0 ? (S > 1 ? 4.05 : 3.9) : 1.45 - 0.05 * k, wt = s === 0 ? 0.75 : 0.42;   // the trunk 1.5x the first draft
    // the trunk: 1.5 times as wide at the foot, narrowing fastest near it, back to the limbs' taper by mid-height
    const w = s === 0 ? (u: number) => wt + (wb * 1.5 - wt) * Math.pow(1 - u, 2.2) : (u: number) => lerp(wb, wt, Math.pow(u, 0.8));
    // lengths per move: the bare foot is the first move's; the rest shared by the moves' rules
    const ms = stemMoves[s], bare = bareOf(s);
    const need = ms.map((i) => Math.pow(moves[i].candidates.length, 0.7) + 1.2), tot = need.reduce((a, v) => a + v, 0);
    const u: number[] = [0]; let at = bare;
    ms.forEach((_, j) => { at += (1 - bare) * need[j] / tot; u.push(at); });
    geos.push({ axis, u, w, H: Hs, dir: sg, bare });
  }
  // the stems' centre lines go into the index first: nothing else may touch them
  for (let s = 0; s < S; s++) stemIds.push(grid.add(geos[s].axis));

  // point on a stem's axis at fraction u of its length
  const at = (g: StemGeo, u: number): { p: P; d: P } => {
    const n = g.axis.length - 1, x = Math.max(0, Math.min(n - 1e-6, u * n)), i = Math.floor(x), t = x - i;
    const a = g.axis[i], b = g.axis[i + 1];
    return { p: [lerp(a[0], b[0], t), lerp(a[1], b[1], t)], d: norm([b[0] - a[0], b[1] - a[1]]) };
  };
  const env = (u: number, bare: number) => { const v = Math.max(0, Math.min(1, (u - bare + 0.04) / (1 - bare + 0.04))); return Math.max(0.28, Math.pow(Math.sin(Math.PI * Math.min(1, v * 0.92 + 0.04)), 0.7)); };

  const ls = Math.max(6, H * 0.018) * (S === 1 ? 2.1 : 1);   // a twig's base length; longer on a small tree
  // the submitted path, found while the twigs are placed
  const sub: { twig?: Stroke; branch?: { stroke: Stroke; upTo: number }; stem?: { s: number; u: number } } = {};
  // which rule is the submitted one: the first kept evaluation of it at its score
  let subAt: { move: number; cand: number } | null = null;
  if (o.submitted) {
    const want = key(o.submitted.rule);
    for (let i = 0; i < moves.length && !subAt; i++) {
      const m = moves[i];
      if (!m.kept || !m.candidates[m.chosen]) continue;
      const c = m.candidates[m.chosen];
      if (key(c.rule) === want && Math.abs(c.sharpe - o.submitted.sharpe) < 1e-9) subAt = { move: i, cand: m.chosen };
    }
  }

  // ---- the stems' strokes (the axis's growth follows the moves), and a mark where each length ends
  const nodes: RunTree["nodes"] = [];
  for (let s = 0; s < S; s++) { const g = geos[s], ms = stemMoves[s]; for (let j = 1; j < ms.length; j++) nodes.push({ p: at(g, g.u[j]).p, t: first[ms[j]], stem: s }); }
  for (let s = 0; s < S; s++) {
    const g = geos[s], ms = stemMoves[s];
    ms.forEach((mi, j) => {
      const u0 = j === 0 ? 0 : g.u[j], u1 = g.u[j + 1];
      const pts = g.axis.slice(Math.floor(u0 * (g.axis.length - 1)), Math.ceil(u1 * (g.axis.length - 1)) + 1);
      // the first move: the bare foot grows in the unit before its first rule
      strokes.push({ kind: "stem", pts, w0: g.w(u0), w1: g.w(u1), t0: j === 0 ? first[mi] - 1 : first[mi], t1: first[mi] + moves[mi].candidates.length, stem: s, move: mi });
    });
  }

  // ---- branches and twigs, move by move in search order
  let side = 1;
  for (let s = 0; s < S; s++) {
    const g = geos[s], ms = stemMoves[s];
    ms.forEach((mi, j) => {
      const m: TreeMove = moves[mi], n = m.candidates.length;
      // the parent rule: the stem's rule before this move (what each candidate added is told against it)
      const prev = j > 0 ? moves[ms[j - 1]] : null;
      const parent = new Set(prev && prev.kept ? prev.candidates[prev.chosen].rule.split(" ") : []);
      const fam = m.candidates.map((c) => { const add = c.rule.split(" ").filter((t) => !parent.has(t)); return add.length ? family(add[add.length - 1]) : "same"; });
      // runs of one family, in the order scored
      const runs: number[][] = [];
      fam.forEach((f, i) => { if (i && fam[i - 1] === f && runs[runs.length - 1].length < 6) runs[runs.length - 1].push(i); else runs.push([i]); });
      // the stem's length for this move: from where it stood to where it ends
      const uA = j === 0 ? g.bare : g.u[j], uB = g.u[j + 1];
      for (const run of runs) {
        const startE = first[mi] + run[0], endE = first[mi] + run[run.length - 1] + 1;
        // attached where the stem's tip is when the run starts
        const ua = lerp(uA, uB, (run[0] + 0.5) / n);
        const { p: A, d: T } = at(g, ua);
        // alternate sides up each stem; a restart's stems lean their branches outward more often
        side = -side;
        let sd = side;
        if (S > 1 && s > 0 && rnd() < 0.35) sd = g.dir;
        // a restart's stem reaches mostly outward: toward its neighbours its branches stay short
        const inner = S > 1 && s > 0 && sd !== g.dir;
        const reach = reachMax * env(ua, g.bare) * (0.7 + rnd() * 0.3) * (inner ? 0.55 : 1);
        const mTw = run.length;
        let placedBranch: P[] | null = null, bid = -1;
        // try the planned angle, then steeper and shorter until it is clear
        for (const [angF, lenF, flip] of [[1, 1, 1], [0.8, 0.9, 1], [1, 1, -1], [0.65, 0.75, 1], [0.8, 0.9, -1], [0.5, 0.6, 1], [0.5, 0.6, -1], [0.4, 0.45, 1], [0.4, 0.45, -1]] as [number, number, number][]) {
          const sgn = sd * flip;
          const theta = (S === 1 ? lerp(58, 36, ua) : lerp(46, 30, ua) + (rnd() - 0.5) * 6) * Math.PI / 180 * angF;
          const L = Math.max(reach / Math.sin(Math.max(0.3, theta)) * 0.9, mTw * ls * 0.75 + ls * 0.6) * lenF;
          const dir = rot(T, sgn * theta);
          const B: P = [A[0] + dir[0] * L * 0.45, A[1] + dir[1] * L * 0.45];
          const tipDir = rot(T, sgn * theta * 0.55);
          const C: P = [A[0] + dir[0] * L * 0.75 + tipDir[0] * L * 0.05, A[1] + dir[1] * L * 0.75 + tipDir[1] * L * 0.05];
          const D: P = [C[0] + tipDir[0] * L * 0.25, C[1] + tipDir[1] * L * 0.25];
          const pts = cubic(A, B, C, D, 18);
          const skip = new Set([stemIds[s]]);
          if (!grid.hits(pts.slice(1), 2.2, skip)) { placedBranch = pts; break; }
          if (!placedBranch) placedBranch = null;
        }
        if (!placedBranch) {   // last resort: very short and steep, along the stem
          forced++;
          const dir = rot(T, sd * 0.25), L = mTw * ls * 0.6 + ls;
          placedBranch = cubic(A, [A[0] + dir[0] * L * 0.3, A[1] + dir[1] * L * 0.3], [A[0] + dir[0] * L * 0.7, A[1] + dir[1] * L * 0.7], [A[0] + dir[0] * L, A[1] + dir[1] * L], 18);
        }
        bid = grid.add(placedBranch);
        const bLen = plen(placedBranch);
        const branch: Stroke = { kind: "branch", pts: placedBranch, w0: Math.min(0.95, g.w(ua) * 0.55), w1: 0.36, t0: startE, t1: endE, stem: s, move: mi };
        strokes.push(branch);
        // twigs: one per rule, alternately on the branch's two sides, spread along its outer part
        let lastU = 0;
        run.forEach((ci, q) => {
          const c = m.candidates[ci], eIdx = first[mi] + ci;
          const tl = ls * (0.7 + 0.45 * tier(c.sharpe)) * (0.85 + rnd() * 0.3);
          let placed: P[] | null = null, uo = 0;
          const u0 = mTw === 1 ? 0.62 : (S === 1 ? 0.2 : 0.3) + (S === 1 ? 0.74 : 0.62) * (q / (mTw - 1));
          const tries: number[] = [u0]; for (let e = 1; e <= 16; e++) { const v = u0 + Math.ceil(e / 2) * 0.04 * (e % 2 ? 1 : -1); if (v > 0.15 && v < 0.99) tries.push(v); }
          const sides = q % 2 ? [1, -1] : [-1, 1];
          outer: for (const lf of [1, 0.8, 0.62]) for (const tw of sides) for (const uu of tries) {
            const n2 = placedBranch!.length - 1, x = uu * n2, i = Math.min(n2 - 1, Math.floor(x));
            const O: P = [lerp(placedBranch![i][0], placedBranch![i + 1][0], x - i), lerp(placedBranch![i][1], placedBranch![i + 1][1], x - i)];
            const bt = norm([placedBranch![i + 1][0] - placedBranch![i][0], placedBranch![i + 1][1] - placedBranch![i][1]]);
            // a short kick out from the branch, then hanging: the birch's sprig
            const ang = (40 + rnd() * 26) * Math.PI / 180, droop = 0.12 + rnd() * 0.2;
            const dd = rot(bt, tw * ang), len = tl * lf;
            const Cc: P = [O[0] + dd[0] * len * 0.55, O[1] + dd[1] * len * 0.55];
            const Ee: P = [O[0] + dd[0] * len * 0.96, O[1] + dd[1] * len * 0.96 + droop * len];
            const pts = quad(O, Cc, Ee, 8);
            if (!grid.hits(pts.slice(1), 1.6, new Set([bid]))) { placed = pts; uo = uu; break outer; }
          }
          if (!placed) {
            forced++;
            const n2 = placedBranch!.length - 1, i = Math.min(n2 - 1, Math.floor(u0 * n2)), O = placedBranch![i];
            const bt = norm([placedBranch![i + 1][0] - O[0], placedBranch![i + 1][1] - O[1]]), dd = rot(bt, (q % 2 ? 1 : -1) * 0.7);
            placed = quad(O, [O[0] + dd[0] * tl * 0.3, O[1] + dd[1] * tl * 0.3], [O[0] + dd[0] * tl * 0.5, O[1] + dd[1] * tl * 0.5], 8); uo = u0;
          }
          grid.add(placed);
          lastU = Math.max(lastU, uo);
          // a twig grows in its own evaluation, once its branch has reached its place
          const reachT = startE + (endE - startE) * uo;
          const t0 = Math.max(eIdx, reachT - 0.2);
          const twig: Stroke = { kind: "twig", pts: placed, w0: 0.5, w1: 0.38, t0, t1: t0 + 1, stem: s, move: mi, eval: eIdx, sharpe: c.sharpe };
          strokes.push(twig);
          if (subAt && subAt.move === mi && subAt.cand === ci) { sub.twig = twig; sub.branch = { stroke: branch, upTo: uo }; sub.stem = { s, u: ua }; }
        });
        void bLen; void lastU;
      }
    });
  }

  // ---- the pink path: the stem from the foot to the branch (for a restart's limb, the trunk to where the limb
  // leaves it first), the branch to the twig, the twig
  const pink: Stroke[] = [];
  let mark: P | null = null;
  if (sub.twig && sub.branch && sub.stem) {
    const { twig, branch: pb, stem: ps } = sub;
    const g = geos[ps.s], n = g.axis.length - 1;
    if (ps.s > 0) {   // the trunk up to the limb's foot
      const tr = geos[0], foot = g.axis[0], k = tr.axis.findIndex((p) => p[0] === foot[0] && p[1] === foot[1]);
      if (k > 0) pink.push({ kind: "stem", pts: tr.axis.slice(0, k + 1), w0: tr.w(0), w1: tr.w(k / n), t0: 0, t1: 0, stem: 0, move: -1, pink: true });
    }
    const sp = g.axis.slice(0, Math.ceil(ps.u * n) + 1); sp[sp.length - 1] = at(g, ps.u).p;
    pink.push({ kind: "stem", pts: sp, w0: g.w(0), w1: g.w(ps.u), t0: 0, t1: 0, stem: ps.s, move: -1, pink: true });
    const bp = pb.stroke.pts, bn = bp.length - 1, bx = pb.upTo * bn, bi = Math.min(bn - 1, Math.floor(bx));
    const bpts = bp.slice(0, bi + 1); bpts.push([lerp(bp[bi][0], bp[bi + 1][0], bx - bi), lerp(bp[bi][1], bp[bi + 1][1], bx - bi)]);
    pink.push({ kind: "branch", pts: bpts, w0: pb.stroke.w0, w1: lerp(pb.stroke.w0, pb.stroke.w1, pb.upTo), t0: 0, t1: 0, stem: ps.s, move: -1, pink: true });
    pink.push({ ...twig, pink: true });
    mark = twig.pts[twig.pts.length - 1];
  }

  let l = 0, r = 0, top = 0;
  for (const st of strokes) for (const p of st.pts) { l = Math.min(l, p[0]); r = Math.max(r, p[0]); top = Math.min(top, p[1]); }
  return { strokes, evaluations: E, stems: S, l: l - 6, r: r + 6, top: top - 6, pink, mark, forced, nodes };
}

/** Pairs of strokes that cross, other than a stroke where it leaves its parent (the birch's rule). */
export function runCrossings(t: RunTree, list?: string[]): number {
  let n = 0;
  const S = t.strokes;
  for (let i = 0; i < S.length; i++) for (let j = i + 1; j < S.length; j++) {
    const a = S[i], b = S[j];
    // a stroke touches its parent where it leaves it, and a stem's pieces meet end to end
    if (a.pts[0][0] === b.pts[0][0] && a.pts[0][1] === b.pts[0][1]) continue;
    const touches = (x: Stroke, y: Stroke) => y.pts.some((p) => Math.hypot(p[0] - x.pts[0][0], p[1] - x.pts[0][1]) < 1e-6)
      || near([x.pts[0], x.pts[0]], y.pts, 0.01);
    if (touches(a, b) || touches(b, a)) {
      // still a crossing if they meet again away from the joint
      const rest = (x: Stroke) => x.pts.slice(2);
      if (near(rest(a), rest(b), 0)) { n++; list?.push(`${a.kind}${i}/${b.kind}${j} (joint) s${a.stem}m${a.move} s${b.stem}m${b.move}`); }
      continue;
    }
    if (near(a.pts, b.pts, 0)) { n++; list?.push(`${a.kind}${i}/${b.kind}${j} s${a.stem}m${a.move} s${b.stem}m${b.move}`); }
  }
  return n;
}

/** The SVG path of a stroke drawn up to fraction f of its length (tapered, as the birch's). */
export function strokePath(s: Stroke, f = 1): string {
  const pts = cut(s.pts, f);
  if (pts.length < 2 || plen(pts) < 0.05) return "";
  const wEnd = lerp(s.w0, s.w1, Math.min(1, f));
  return taper(pts.length > 2 ? pts : [pts[0], [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2], pts[1]], (t) => lerp(s.w0, wEnd, t));
}
