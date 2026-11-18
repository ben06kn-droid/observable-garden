// The demo's run tree in the page (DESIGN.md 3, demo): a RunTree (src/runtree.ts) drawn into an SVG at any point of
// its search. Each stroke's path is written only when it changes, so a frame of growth touches the few strokes
// growing at that moment. Stems are drawn whole from their centre line and width (the growing tip narrows to a fine
// point); branches and twigs as tapered strokes; the move marks as the stem passes them; the pink path once the
// search has submitted. The active element (the twig being scored, then the submitted rule) carries the page's one
// glow: a tight bloom, a blurred copy of it 1.6 px wide at most.
import { taper, type P } from "./birch";
import { strokePath, type RunTree, type Stroke } from "./runtree";

const NS = "http://www.w3.org/2000/svg";
const el = <K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
};
const clamp = (x: number) => Math.max(0, Math.min(1, x));

/** the stem from its foot to u, its width its own, the last stretch narrowing to a point while it grows */
function stemD(axis: P[], w: (u: number) => number, u: number, growing: boolean): string {
  const n = axis.length - 1, x = u * n, i = Math.floor(x);
  if (u <= 0) return "";
  const pts = axis.slice(0, i + 1);
  if (i < n) { const a = axis[i], b = axis[i + 1], t = x - i; pts.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); }
  if (pts.length < 2) return "";
  if (pts.length === 2) pts.splice(1, 0, [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2]);
  const tipLen = 0.03 / Math.max(u, 0.03);
  return taper(pts, (t) => {
    const k = growing && t > 1 - tipLen ? Math.max(0.12, (1 - t) / tipLen) : 1;
    return w(t * u) * k;
  }, true);
}

export interface TreeView {
  /** draw the search up to `at` evaluations (fractional) */
  setAt(at: number): void;
  /** the pink path and its mark, faded in */
  showPink(on: boolean): void;
  /** the bloom: on the twig being scored (by `setAt`), on the submitted rule, or none */
  bloom(on: "growing" | "submitted" | "none"): void;
  done(): boolean;
}

export function drawTree(svg: SVGSVGElement, rt: RunTree): TreeView {
  svg.replaceChildren();
  // one fixed scale for every search (a small search stands smaller), the foot on the ground at the bottom
  const half = Math.max(160, Math.max(-rt.l, rt.r) + 24);
  svg.setAttribute("viewBox", `${-half} -745 ${2 * half} 790`);
  svg.setAttribute("preserveAspectRatio", "xMidYMax meet");
  const defs = el("defs", {}, svg);
  const f = el("filter", { id: "dm-bloom", x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
  el("feGaussianBlur", { stdDeviation: "1.6" }, f);
  el("line", { class: "ground", x1: -half, x2: half, y1: 0.3, y2: 0.3 }, svg);
  const gStem = el("g", { class: "stems" }, svg), gBr = el("g", { class: "branches" }, svg), gTw = el("g", { class: "twigs" }, svg);
  const gNode = el("g", { class: "nodes" }, svg);
  const gPink = el("g", { class: "pinkpath" }, svg);
  const bloomP = el("path", { class: "bloom", filter: "url(#dm-bloom)" }, svg);
  const stems = rt.stemGeo.map((g) => ({ g, path: el("path", { class: "stem" }, gStem), u: -1 }));
  const rest = rt.strokes.filter((s) => s.kind !== "stem").map((s) => ({ s, path: null as SVGPathElement | null, f: -1 }));
  const nodes = rt.nodes.map((nd) => ({ nd, c: null as SVGCircleElement | null }));
  // the pink path, drawn once (it is hidden until the search has submitted)
  for (const ps of rt.pinkStems) { const g = rt.stemGeo[ps.stem]; el("path", { class: "stem pink", d: stemD(g.axis, g.w, ps.u, false) }, gPink); }
  for (const s of rt.pink) if (s.kind !== "stem") el("path", { class: `${s.kind} pink`, d: strokePath(s, 1) }, gPink);
  if (rt.mark) el("circle", { class: "mark", cx: rt.mark[0], cy: rt.mark[1], r: 2 }, gPink);
  const subTwig = rt.pink.find((s) => s.kind === "twig") ?? null;

  let at = -Infinity, bloomMode: "growing" | "submitted" | "none" = "none", active: Stroke | null = null, activeF = -1;
  function setAt(a: number) {
    at = a;
    for (const st of stems) {
      let u = 0, growing = false;
      for (const sp of st.g.spans) {
        const k = clamp((a - sp.t0) / (sp.t1 - sp.t0));
        if (k > 0) { u = Math.max(u, sp.u0 + (sp.u1 - sp.u0) * k); if (k < 1) growing = true; }
      }
      if (Math.abs(u - st.u) > 1e-4) { st.u = u; st.path.setAttribute("d", stemD(st.g.axis, st.g.w, u, growing)); }
    }
    let newest: { s: Stroke; f: number } | null = null;
    for (const r of rest) {
      const k = clamp((a - r.s.t0) / (r.s.t1 - r.s.t0));
      if (k === r.f) continue;
      r.f = k;
      if (k <= 0) { r.path?.remove(); r.path = null; continue; }
      if (!r.path) r.path = el("path", { class: r.s.kind }, r.s.kind === "twig" ? gTw : gBr);
      r.path.setAttribute("d", strokePath(r.s, k));
      if (r.s.kind === "twig" && k < 1) newest = { s: r.s, f: k };
    }
    for (const n of nodes) {
      const on = a >= n.nd.t;
      if (on && !n.c) n.c = el("circle", { class: "node", cx: n.nd.p[0], cy: n.nd.p[1], r: n.nd.stem ? 1.5 : 1.9 }, gNode);
      else if (!on && n.c) { n.c.remove(); n.c = null; }
    }
    if (newest) { active = newest.s; activeF = newest.f; }
    paintBloom();
  }
  function paintBloom() {
    if (bloomMode === "growing" && active && at < active.t1 + 0.8) { bloomP.setAttribute("class", "bloom"); bloomP.setAttribute("d", strokePath(active, Math.max(activeF, at >= active.t1 ? 1 : activeF))); }
    else if (bloomMode === "submitted" && subTwig) { bloomP.setAttribute("class", "bloom p"); bloomP.setAttribute("d", strokePath(subTwig, 1)); }
    else bloomP.setAttribute("d", "");
  }
  return {
    setAt,
    showPink(on) { gPink.classList.toggle("on", on); },
    bloom(on) { bloomMode = on; paintBloom(); },
    done: () => at >= rt.evaluations,
  };
}

/** the tree's ground line and scale, for anything drawn in its frame (the bed): svg units → the element's px */
export function treeFrame(svg: SVGSVGElement, host: HTMLElement): ((x: number, y: number) => [number, number]) | null {
  const m = svg.getScreenCTM();
  if (!m) return null;
  const hb = host.getBoundingClientRect();
  return (x, y) => [m.a * x + m.c * y + m.e - hb.left, m.b * x + m.d * y + m.f - hb.top];
}
