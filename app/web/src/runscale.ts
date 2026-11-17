// The run page's result: the gate's numbers on a scale, drawn large on the grid. No tree (the run's tree is
// drawn on the home and demo pages only).
//
// The scale runs honestly from zero (or the lowest value shown) to just above the highest: the bar
// (dotted), the submitted level as the notes' tick with its label, and the p-value line under the bar
// (src/notes.ts writes those); the verdict word large at the top. It returns what src/notes.ts draws on
// (a GardenHandle): ySharpe and best are the scale's.
import type { GardenHandle } from "./garden";
import type { AuditResult, SearchTree } from "./types";

const NS = "http://www.w3.org/2000/svg";
const f1 = (n: number) => n.toFixed(1);

function el<K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e); return e;
}

export interface RunScaleOptions { wordH: number }

export function drawRunScale(svg: SVGSVGElement, spot: HTMLElement, tree: SearchTree, r: AuditResult, o: RunScaleOptions): GardenHandle {
  const w = Math.max(200, spot.clientWidth), h = Math.max(240, spot.clientHeight), phone = w < 600;
  svg.setAttribute("viewBox", `0 0 ${f1(w)} ${f1(h)}`);
  svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
  svg.classList.remove("garden", "growing"); svg.classList.add("runscale");
  svg.replaceChildren();

  // the scale across the stage: its axis at the left, its numbers right of the word's column
  const gx0 = phone ? 26 : 34, gx1 = w;
  const gy0 = o.wordH + (phone ? 36 : 56), gy1 = h - 1;
  spot.style.setProperty("--word-x", "0px");
  spot.style.setProperty("--word-y", "0px");

  // the kept evaluations, in search order (the best of them is where the submitted tick starts)
  const kept: { step: number; sharpe: number }[] = []; let n = 0;
  tree.moves.forEach((m) => m.candidates.forEach((c, ci) => { n++; if (m.kept && ci === m.chosen) kept.push({ step: n, sharpe: c.sharpe }); }));

  // the scale: from zero (or the lowest value shown) to a little above the highest
  const shown = [...kept.map((k) => k.sharpe), r.class_bar, r.submitted_sharpe];
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
  { const y = f1(ySharpe(r.class_bar)); el("line", { x1: f1(gx0), x2: f1(gx1), y1: y, y2: y, class: "bar" }, gauge); }
  el("line", { x1: 0, x2: f1(w), y1: f1(gy1 + 0.5), y2: f1(gy1 + 0.5), class: "ground" }, svg);
  const real = el("g", { class: "real" }, svg);

  return {
    total: n,
    grow: () => {}, setStep: () => {},
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
