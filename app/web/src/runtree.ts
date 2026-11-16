// The run page's tree: the run's search drawn as the home page's birch (src/birch.ts), one per restart,
// filling the left of the tree area, with the gate's numbers on a Sharpe gauge in the columns beside it.
//
// The birch keeps the home page's rules: a weight hierarchy from trunk to branch to twig to leaf, and
// no stroke crossing another (buildBirch rebuilds it with other jitter until it is clean). One branch per
// (move, feature family), one twig per evaluation, 1 to 3 leaves by the rule's Sharpe within the tree;
// the submitted evaluation's twig, its leaves and its branch are drawn in the accent.
//
// The tree's height is not a Sharpe; the gauge carries the numbers, honestly scaled from zero (or the
// lowest value) to just above the highest: the bar (dotted), and the submitted (or best-so-far) level as
// the notes' tick, with its label; the verdict word at the gauge's top. On a desktop the tree takes
// columns 1–4 of the stage's eight and the gauge 5–8; on a phone the gauge sits above the tree.
//
// It returns what src/notes.ts draws on (a GardenHandle): ySharpe and best are the gauge's.
import { birchGroups, buildBirch, renderPrims, type Prims } from "./birch";
import type { GardenHandle } from "./garden";
import type { AuditResult, SearchTree, TreeMove } from "./types";

const NS = "http://www.w3.org/2000/svg";
const FAMILIES = ["mom60", "rev5", "vol20", "noise"];   // as birchGroups orders them
const f1 = (n: number) => n.toFixed(1);

function el<K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e); return e;
}

/** for each branch group of a restart (in birchGroups' order), the evaluations its twigs stand for */
function groupMembers(moves: TreeMove[]): [number, number][][] {
  const family = (tok: string) => tok.replace(/^[+-]/, "").split("_")[0];
  const out: [number, number][][] = [];
  let parent = new Set<string>();
  moves.forEach((m, mi) => {
    const by = new Map<string, [number, number][]>();
    m.candidates.forEach((c, ci) => {
      const added = c.rule.split(" ").filter((t) => !parent.has(t));
      const fam = added.length ? family(added[added.length - 1]) : "same";
      if (!by.has(fam)) by.set(fam, []);
      by.get(fam)!.push([mi, ci]);
    });
    const order = [...by.keys()].sort((a, b) => (FAMILIES.indexOf(a) + 99) % 99 - (FAMILIES.indexOf(b) + 99) % 99);
    for (const fam of order) out.push(by.get(fam)!);
    if (m.kept) parent = new Set(m.candidates[m.chosen].rule.split(" "));
  });
  return out;
}

export interface RunTreeOptions { gap: number; wordH: number; attempts?: number }

export function drawRunTree(svg: SVGSVGElement, spot: HTMLElement, tree: SearchTree, r: AuditResult | null, o: RunTreeOptions): GardenHandle {
  const w = Math.max(200, spot.clientWidth), h = Math.max(240, spot.clientHeight), phone = w < 600;
  svg.setAttribute("viewBox", `0 0 ${f1(w)} ${f1(h)}`);
  svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
  svg.classList.remove("garden", "growing"); svg.classList.add("runtree");
  svg.replaceChildren();

  // ---- the layout, on the stage's eight columns
  const colW = (w - 7 * o.gap) / 8;
  const tree0 = 0, tree1 = phone ? w : 4 * colW + 3 * o.gap;
  const gx0 = phone ? 26 : 4 * (colW + o.gap) + 26, gx1 = w;
  const gy0 = o.wordH + (phone ? 28 : 44), gy1 = phone ? Math.round(h * 0.4) : h - 1;
  const treeTop = phone ? gy1 + 40 : 6, ground = h - 1;
  spot.style.setProperty("--word-x", `${phone ? 0 : f1(gx0 - 26)}px`);
  spot.style.setProperty("--word-y", "0px");

  // ---- evaluations in search order; the kept ones; the submitted one
  const steps = new Map<string, number>(); let n = 0;
  tree.moves.forEach((m, mi) => m.candidates.forEach((_, ci) => steps.set(`${mi}:${ci}`, ++n)));
  const kept: { step: number; sharpe: number }[] = [];
  tree.moves.forEach((m, mi) => { if (m.kept && m.candidates[m.chosen]) kept.push({ step: steps.get(`${mi}:${m.chosen}`)!, sharpe: m.candidates[m.chosen].sharpe }); });
  const key = (rule: string) => rule.split(" ").sort().join(" ");
  // the submitted evaluation: the kept one of its rule at its score, else the first evaluation of it
  let subAt: string | null = null;
  if (r) {
    const want = key(r.submitted_feature_names.join(" ")); let firstHit: string | null = null;
    tree.moves.forEach((m, mi) => m.candidates.forEach((c, ci) => {
      if (Math.abs(c.sharpe - r.submitted_sharpe) >= 1e-12 || key(c.rule) !== want) return;
      if (m.kept && ci === m.chosen) subAt ??= `${mi}:${ci}`;
      firstHit ??= `${mi}:${ci}`;
    }));
    subAt ??= firstHit;
  }

  // ---- the gauge's scale: from zero (or the lowest value shown) to a little above the highest
  const shown = [...kept.map((k) => k.sharpe), ...(r ? [r.class_bar, r.submitted_sharpe] : [])];
  let lo = Math.min(0, ...shown), hi = Math.max(0.25, ...shown);
  hi += (hi - lo) * 0.08; if (hi - lo < 0.5) hi = lo + 0.5;
  const ySharpe = (s: number) => gy1 - ((s - lo) / (hi - lo)) * (gy1 - gy0);

  const gauge = el("g", { class: "gauge", "aria-hidden": "true" }, svg);
  el("line", { x1: f1(gx0), x2: f1(gx0), y1: f1(gy0), y2: f1(gy1), class: "axis" }, gauge);
  for (let s = Math.ceil(lo); s <= Math.floor(hi); s++) {
    const y = f1(ySharpe(s));
    el("line", { x1: f1(gx0 - 5), x2: f1(gx0), y1: y, y2: y, class: "axis" }, gauge);
    el("text", { x: f1(gx0 - 9), y: f1(ySharpe(s) + 4), "text-anchor": "end" }, gauge).textContent = String(s);
  }
  if (r) { const y = f1(ySharpe(r.class_bar)); el("line", { x1: f1(gx0), x2: f1(gx1), y1: y, y2: y, class: "bar" }, gauge); }
  el("line", { x1: 0, x2: f1(w), y1: f1(ground + 0.5), y2: f1(ground + 0.5), class: "ground", "aria-hidden": "true" }, svg);

  // ---- the birches: one per restart, side by side in the tree's columns, the taller for the better
  const real = el("g", { class: "real" }, svg);
  const stems = [...new Set(tree.moves.map((m) => m.stem))].sort((a, b) => a - b);
  const bestOf = (s: number) => Math.max(...tree.moves.filter((m) => m.stem === s).flatMap((m) => m.candidates.map((c) => c.sharpe)));
  const bests = stems.map(bestOf), bLo = Math.min(...bests), bHi = Math.max(...bests);
  const avail = ground - treeTop, slot = (tree1 - tree0) / Math.max(1, stems.length);
  stems.forEach((stem, si) => {
    const idx = tree.moves.map((m, mi) => [m, mi] as const).filter(([m]) => m.stem === stem);
    const moves = idx.map(([m]) => m), members = groupMembers(moves);
    const groups = birchGroups(moves);
    if (!groups.length) return;
    const rel = stems.length > 1 && bHi > bLo ? (bests[si] - bLo) / (bHi - bLo) : 1;
    const H = avail * 0.86 * (0.62 + 0.38 * rel);
    const b = buildBirch({ height: H, groups, seed: stem + 1, crown: phone ? 1.5 : 1.7, attempts: o.attempts ?? 6 });
    const s = Math.min(1, (H / 0.86) / Math.max(1, -b.top), (slot - 12) / Math.max(1, b.r - b.l));
    const footX = tree0 + slot * si + slot / 2 - ((b.l + b.r) / 2) * s;
    const g = el("g", { class: "stem", transform: `translate(${f1(footX)} ${f1(ground)}) scale(${s.toFixed(4)})`, "data-stem": stem }, real);
    const stepOf = (gi: number, ti: number) => { const [mi, ci] = members[gi][ti]; return steps.get(`${idx[mi][1]}:${ci}`)!; };
    const subOf = (gi: number, ti: number) => { const [mi, ci] = members[gi][ti]; return `${idx[mi][1]}:${ci}` === subAt; };
    const first = Math.min(...members.flat().map(([mi, ci]) => steps.get(`${idx[mi][1]}:${ci}`)!));
    const one = (p: Partial<Prims>) => renderPrims({ k: b.prims.k, branches: [], twigs: [], leaves: [], ...p });
    // branches first (under the twigs), then twigs with their leaves, then the trunk over the branches' feet
    const twigsAt: { gi: number; ti: number; tw: number[]; leaves: number[][] }[] = [];
    let ti0 = 0, li0 = 0;
    groups.forEach((gr, gi) => {
      gr.twigs.forEach((t, ti) => { twigsAt.push({ gi, ti, tw: b.prims.twigs[ti0 + ti], leaves: b.prims.leaves.slice(li0, li0 + t.leaves) }); li0 += t.leaves; });
      ti0 += gr.twigs.length;
    });
    b.prims.branches.forEach((br, gi) => {
      const st = Math.min(...members[gi].map((_, ti) => stepOf(gi, ti)));
      const path = members[gi].some((_, ti) => subOf(gi, ti));
      el("path", { d: one({ branches: [br] }).branches, class: "branch" + (path ? " path" : ""), "data-step": st }, g);
    });
    for (const t of twigsAt) {
      const st = stepOf(t.gi, t.ti), path = subOf(t.gi, t.ti) ? " path" : "";
      el("path", { d: one({ twigs: [t.tw] }).twigs, class: "twig" + path, "data-step": st }, g);
      const lv = one({ leaves: t.leaves }).leaves.join("");
      if (lv) el("path", { d: lv, class: "leaf" + path, "data-step": st }, g);
    }
    el("path", { d: b.trunk, class: "trunk", "data-step": first }, g);
    el("path", { d: b.bark, class: "bark", "data-step": first }, g);
  });

  const growable = svg.querySelectorAll<SVGElement>("[data-step]");
  return {
    total: n,
    grow: () => svg.classList.add("growing"),
    setStep: (k) => growable.forEach((e) => e.classList.toggle("on", Number(e.dataset.step) <= k)),
    verdict: (status) => { svg.dataset.verdict = status; },
    select: () => {}, rectOf: () => null, treeRect: () => real.getBoundingClientRect(),
    toScreen: (x, y) => { const p = svg.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(svg.getScreenCTM() ?? new DOMMatrix()); },
    ySharpe, ends: [gx0, gx1],
    best: (k) => {
      let top: { step: number; sharpe: number } | null = null;
      for (const e of kept) if ((k === undefined || e.step <= k) && (!top || e.sharpe > top.sharpe)) top = e;
      return top ? { x: gx0, y: ySharpe(top.sharpe), sharpe: top.sharpe } : null;
    },
    bloomAll: () => {}, bloom: () => {}, onPick: () => {},
  };
}
