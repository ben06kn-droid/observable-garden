// The demo's tree: one logged search drawn as one tree, with the home grove's geometry (src/birch.ts: tapered
// strokes, quadratic curves, the clearance test), in the demo's line style. Pure geometry, no DOM.
//
// What the log sets, and what it does not:
//  - the search's start is the foot of the tree; with restarts, a short common trunk, and each restart (a
//    stem: the search starting again from the ground) is its own limb, fanning out from it;
//  - each kept move is one length of its limb, in search order from the foot up: the tree grows upward as
//    the search goes on. Every length is the same; the order is all a length says;
//  - each rule a move scored is one twig; a move's twigs hang on short branches, one per feature family of
//    the feature each rule added (as the home birches group them). A move that was not kept is a branch at
//    its limb's tip that goes no further;
//  - the submitted rule's twig, its branch and the lengths from the foot to the move that produced it: pink.
// Angles, spacing, curvature and every bit of jitter are decoration and claim nothing.
//
// No stroke crosses another: each branch and twig is placed in search order, and one that would come too
// close to anything already drawn turns to the other side, then shortens, until it is clear.
import { near, quad, taper, type P } from "./birch";
import type { SearchTree } from "./types";

export type Kind = "trunk" | "length" | "branch" | "twig" | "mark";
/** one drawn piece: its path, the move (step) it belongs to, its kind, whether it is on the submitted path, and
 *  its place in the order of growth */
export interface Piece { d: string; step: number; kind: Kind; pink: boolean; order: number }
export interface SearchTreeDrawing {
  pieces: Piece[]; l: number; r: number; top: number;
  /** the moves drawn, in search order (the steps) */
  steps: number;
  /** branches or twigs that found no clear place (drawn at their shortest) */
  forced: number;
  /** the submitted move, if found: its index in the moves */
  submitted: number | null;
  /** centre lines, for the crossing check */
  lines: { kind: Kind; pts: P[]; parent: number }[];
}
export interface SearchTreeOptions { height: number; seed?: number; /** the submitted rule, as the log's tokens ("-mom60_z +rev5_rank") */ submitted?: string }

const hash = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const norm = (v: P): P => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };
const FAMILIES = ["mom60", "rev5", "vol20", "noise"];
const family = (tok: string) => tok.replace(/^[+-]/, "").split("_")[0];
const sameRule = (a: string, b: string) => { const x = a.split(" ").sort().join(" "), y = b.split(" ").sort().join(" "); return x === y; };

/** The tree, with no stroke crossing another: built with the seed's own jitter, and rebuilt with other jitter
 *  (angles, spacing, lengths; never anything the log sets) until it is clean, at most `attempts` times (8);
 *  the cleanest is kept (as the home birches are). */
export function buildSearchTree(tree: SearchTree, o: SearchTreeOptions & { attempts?: number }): SearchTreeDrawing {
  let best: SearchTreeDrawing | null = null, bestN = Infinity;
  for (let a = 0; a < (o.attempts ?? 8); a++) {
    const t = buildOnce(tree, o, a), n = crossings(t) * 10 + t.forced;
    if (n < bestN) { best = t; bestN = n; }
    if (n === 0) break;
  }
  return best!;
}

function buildOnce(tree: SearchTree, o: SearchTreeOptions, attempt: number): SearchTreeDrawing {
  const H = o.height, moves = tree.moves;
  let sid = (o.seed ?? 1) * 7919 + attempt * 104729;
  const rnd = () => hash(sid++);
  const S = Math.max(1, tree.stems);
  // ---- the moves per stem; kept moves are lengths
  const kept = Array.from({ length: S }, () => 0);
  for (const m of moves) if (m.kept) kept[m.stem]++;
  const maxK = Math.max(1, ...kept);
  // the submitted move: the last kept move whose chosen rule is the submitted one
  let submitted: number | null = null;
  if (o.submitted) moves.forEach((m, i) => { if (m.kept && m.candidates[m.chosen] && sameRule(m.candidates[m.chosen].rule, o.submitted!)) submitted = i; });
  const pinkStem = submitted === null ? -1 : moves[submitted].stem;
  const pinkUpTo = submitted === null ? -1 : moves.slice(0, submitted + 1).filter((m) => m.stem === pinkStem && m.kept).length - 1;

  const pieces: Piece[] = [], lines: SearchTreeDrawing["lines"] = [];
  let order = 0, forced = 0;
  const add = (d: string, step: number, kind: Kind, pink: boolean) => pieces.push({ d, step, kind, pink, order: order++ });

  // ---- the common trunk (with restarts): a short, slightly curved start
  const bole = S > 1 ? H * 0.2 : 0;
  const boleTop: P = [H * 0.004, -bole];
  const bolePts = S > 1 ? quad([0, 0], [H * 0.006, -bole * 0.5], boleTop, 24) : [];
  if (S > 1) {
    add(taper(bolePts, (t) => lerp(3.2, 2.4, t), true), 0, "trunk", submitted !== null);
    lines.push({ kind: "trunk", pts: bolePts, parent: -1 });
  }
  // ---- the limbs: one per stem, fanning out (the first in the middle, the others alternately right and left),
  // each bending back toward upright as it rises
  const spread = S > 1 ? Math.min(50, 8 + 5.4 * S) : 0;
  const slots = Array.from({ length: S }, (_, i) => (S > 1 ? -spread + (2 * spread * i) / (S - 1) : (o.seed ?? 1) % 2 ? 3 : -3));
  const mid = Math.floor((S - 1) / 2), slotOf: number[] = [];
  for (let s = 0, k = 0; s < S; s++) { const off = s === 0 ? 0 : (s % 2 ? 1 : -1) * Math.ceil(s / 2); slotOf.push(Math.max(0, Math.min(S - 1, mid + off))); k++; }
  // (an even count leaves a slot unused at one end only if two stems share one: never, since mid + off covers it)
  const U = Math.min((H * 0.9 - bole) / maxK, H * 0.32);  // one length (a short search is a shorter tree)
  // branches and twigs are sized to a length, so a short search's few moves still read as a tree
  const bScale = Math.max(1, Math.min(2.2, U / 110)), twL = Math.min(15, 7 * Math.sqrt(bScale));
  const limb: { pts: P[]; u: (q: number) => number; w: (u: number) => number; side: number }[] = [];
  for (let s = 0; s < S; s++) {
    const a0 = (slots[slotOf[s]] + (rnd() - 0.5) * 3) * Math.PI / 180, K = Math.max(1, kept[s]);
    const L = U * K * (1 - 0.18 * Math.abs(Math.sin(a0)));    // outer limbs a little shorter, so the crown is rounded
    // where it leaves the trunk: the middle limbs at its top, the outer ones lower (a vase), so they part early
    const off = S > 1 ? Math.abs(slotOf[s] - (S - 1) / 2) / ((S - 1) / 2) : 0;
    const start: P = S > 1 ? bolePts[Math.round((1 - 0.38 * off) * (bolePts.length - 1))] : [0, 0];
    const N = 14 * K, pts: P[] = [start];
    const wob = rnd() * 6;
    for (let i = 1; i <= N; i++) {
      const u = i / N, th = a0 * (1 - 0.55 * u) + 0.03 * Math.sin(wob + 5 * u);
      const p = pts[i - 1]; pts.push([p[0] + Math.sin(th) * (L / N), p[1] - Math.cos(th) * (L / N)]);
    }
    const wb = S > 1 ? 2.4 : 2.6, wt = 1.15;
    limb.push({ pts, u: (q) => q / K, w: (u) => lerp(wb, wt, Math.pow(u, 0.8)), side: Math.sign(a0) || 1 });
    lines.push({ kind: "length", pts, parent: S > 1 ? 0 : -1 });
  }
  const at = (s: number, u: number): { p: P; t: P } => {
    const pts = limb[s].pts, f = Math.max(0, Math.min(1, u)) * (pts.length - 1), i = Math.min(pts.length - 2, Math.floor(f)), r = f - i;
    const p: P = [lerp(pts[i][0], pts[i + 1][0], r), lerp(pts[i][1], pts[i + 1][1], r)];
    return { p, t: norm([pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]]) };
  };

  // everything placed so far, for the clearance test: the trunk and the limbs are there from the start (a branch
  // must clear every limb, including those not yet grown)
  const placed: { pts: P[]; owner: string }[] = lines.map((x, i) => ({ pts: x.pts, owner: `L${i}` }));

  // ---- each move in search order: its length of limb, then its branches and their twigs
  const done = Array.from({ length: S }, () => 0);
  const parent = Array.from({ length: S }, () => new Set<string>());
  moves.forEach((m, step) => {
    const s = m.stem, lb = limb[s];
    let u0: number, u1: number;
    if (m.kept) {
      const q = done[s]++;
      u0 = lb.u(q); u1 = lb.u(q + 1);
      // the length: its part of the limb's centre line, tapered as the limb is
      const pts = lb.pts, i0 = Math.round(u0 * (pts.length - 1)), i1 = Math.round(u1 * (pts.length - 1));
      const seg = pts.slice(i0, i1 + 1);
      add(taper(seg, (t) => lb.w(lerp(u0, u1, t)), q === 0), step, "length", s === pinkStem && q <= pinkUpTo);
    } else {
      // not kept: its rules hang at the limb's tip as it stands; the limb goes no further here
      const q = done[s];
      u0 = Math.max(0.02, lb.u(q) - 0.12 / Math.max(1, kept[s])); u1 = Math.max(0.06, lb.u(q));
    }
    // the move's rules, grouped by the family of the feature each one added
    const by = new Map<string, number[]>();
    m.candidates.forEach((c, j) => {
      const added = c.rule.split(" ").filter((t) => !parent[s].has(t));
      const f = added.length ? family(added[added.length - 1]) : "same";
      if (!by.has(f)) by.set(f, []); by.get(f)!.push(j);
    });
    const groups = [...by.entries()].sort((a, b) => (FAMILIES.indexOf(a[0]) + 99) % 99 - (FAMILIES.indexOf(b[0]) + 99) % 99);
    const n = groups.length;
    groups.forEach(([, js], g) => {
      const mTw = js.length;
      const hasPink = submitted === step && js.includes(m.chosen);
      const first = m.kept && u0 === 0 ? (S > 1 ? 0.4 : 0.3) : 0.12;
      const u = lerp(u0, u1, first + (0.96 - first) * ((g + 0.5) / n) + (rnd() - 0.5) * 0.03);
      const { p: A, t: T } = at(s, u);
      const side0 = (g + done[s] + s) % 2 ? 1 : -1;
      const Lb0 = Math.min(U * 0.62, (12 + 6.8 * mTw) * bScale) * (0.9 + rnd() * 0.2), phi0 = (30 + rnd() * 10) * Math.PI / 180;
      // a branch: out from the limb at phi, curling a little upward; tried on its own side, then the other, then
      // shorter, then at a steeper angle
      let best: { pts: P[]; dir: P } | null = null, ok = false;
      const tries: [number, number, number][] = [];
      for (const k of [1, 0.85, 0.72, 0.6, 0.5, 0.42]) for (const sd of [side0, -side0]) for (const ph of [phi0, phi0 * 0.7]) tries.push([sd, k, ph]);
      for (const [sd, k, ph] of tries) {
        const Nn: P = [-T[1], T[0]], Ns: P = Math.sign(Nn[0]) === sd ? Nn : [-Nn[0], -Nn[1]];
        const D = norm([T[0] * Math.cos(ph) + Ns[0] * Math.sin(ph), T[1] * Math.cos(ph) + Ns[1] * Math.sin(ph)]);
        const Lb = Lb0 * k;
        const pts = quad(A, [A[0] + D[0] * Lb * 0.55, A[1] + D[1] * Lb * 0.55], [A[0] + D[0] * Lb + T[0] * Lb * 0.14, A[1] + D[1] * Lb + T[1] * Lb * 0.14], 14);
        if (!best) best = { pts, dir: D };
        if (!placed.some((x) => x.owner !== `L${S > 1 ? s + 1 : s}` && near(pts, x.pts, 3.2)) && !placed.some((x) => x.owner === `L${S > 1 ? s + 1 : s}` && near(pts, x.pts, 0, 4))) { best = { pts, dir: D }; ok = true; break; }
      }
      if (!ok) forced++;
      const bp = best!.pts, bIdx = lines.length;
      add(taper(bp, (t) => lerp(1.05, 0.42, t)), step, "branch", hasPink);
      lines.push({ kind: "branch", pts: bp, parent: S > 1 ? s + 1 : s });
      placed.push({ pts: bp, owner: `B${bIdx}` });
      // its twigs, one per rule, alternately on each side, short and straight-ish, a small mark at each tip
      js.forEach((j, q) => {
        const f = mTw === 1 ? 0.92 : 0.3 + 0.68 * (q / (mTw - 1));
        const fi = Math.min(bp.length - 2, Math.round(f * (bp.length - 1))), O = bp[fi];
        const bt = norm([bp[fi + 1][0] - bp[fi][0], bp[fi + 1][1] - bp[fi][1]]);
        const pink = hasPink && j === m.chosen;
        const sd0 = q % 2 ? 1 : -1, len0 = twL * (0.85 + rnd() * 0.4);
        let tw: P[] | null = null, ok2 = false;
        for (const sd of [sd0, -sd0]) {
          for (let len = len0; len >= 3.5; len *= 0.85) {
            const ang = sd * (48 + rnd() * 10) * Math.PI / 180, c = Math.cos(ang), sn = Math.sin(ang);
            const d: P = [bt[0] * c - bt[1] * sn, bt[0] * sn + bt[1] * c];
            const E: P = [O[0] + d[0] * len, O[1] + d[1] * len], C: P = [O[0] + d[0] * len * 0.5 - bt[1] * 0, O[1] + d[1] * len * 0.5];
            const pts = quad(O, C, E, 6);
            if (!tw) tw = pts;
            if (!placed.some((x) => x.owner !== `B${bIdx}` && near(pts, x.pts, 2.2)) && !near(pts, bp, 0, 1.2)) { tw = pts; ok2 = true; break; }
          }
          if (ok2) break;
        }
        if (!ok2) forced++;
        add(taper(tw!, (t) => lerp(0.62, 0.42, t)), step, "twig", pink);
        const E = tw![tw!.length - 1];
        add(`M${(E[0] + 1.05).toFixed(2)} ${E[1].toFixed(2)}A1.05 1.05 0 1 0 ${(E[0] - 1.05).toFixed(2)} ${E[1].toFixed(2)}A1.05 1.05 0 1 0 ${(E[0] + 1.05).toFixed(2)} ${E[1].toFixed(2)}Z`, step, "mark", pink);
        lines.push({ kind: "twig", pts: tw!, parent: bIdx });
        placed.push({ pts: tw!, owner: `T${lines.length - 1}` });
      });
    });
    if (m.kept && m.candidates[m.chosen]) parent[s] = new Set(m.candidates[m.chosen].rule.split(" "));
  });

  let l = 0, r = 0, top = 0;
  for (const x of lines) for (const p of x.pts) { l = Math.min(l, p[0]); r = Math.max(r, p[0]); top = Math.min(top, p[1]); }
  return { pieces, l: l - 4, r: r + 4, top: top - 4, steps: moves.length, forced, submitted, lines };
}

/** strokes in one drawing that cross or touch, other than where a stroke leaves its parent */
export function crossings(t: SearchTreeDrawing): number {
  let n = 0;
  const L = t.lines;
  for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) {
    const a = L[i], b = L[j];
    if (a.parent === j || b.parent === i) continue;
    if (a.kind === "length" && b.kind === "length") { if (near(a.pts.slice(3), b.pts.slice(3), 0, 0)) n++; continue; }   // limbs share their start
    if (near(a.pts, b.pts, 0, 0)) n++;
  }
  return n;
}
