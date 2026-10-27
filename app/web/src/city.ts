// Night City around page two's garden, all drawn in code, thin and precise: two pylons at the edges
// with three cables strung between them in shallow catenaries across the upper part of the page, a
// pulse of light running along one cable every few seconds, and two dim static signs at the edges (a
// vertical strip of glyphs, a thin ring). Decoration, except one thing: when a verdict lands, one
// pulse runs along a cable and down to the run's tree (index.ts says where the tree stands).
//
// The pulses animate stroke-dashoffset on one short path at a time (a small repaint, a few times a
// minute), and none runs while the page is covered or a carry or zoom is playing.
const NS = "http://www.w3.org/2000/svg";
const el = <K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
};
const f = (n: number) => n.toFixed(1);
const GLYPHS = "7F3A·0E9C·41B8·D2";

export interface City { draw(): void; pulseTo(x: number, y: number): void; start(quiet: () => boolean): void }

export function makeCity(svg: SVGSVGElement, reduce: boolean): City {
  svg.setAttribute("aria-hidden", "true");
  let W = 0, H = 0, cables: { pts: [number, number][]; path: SVGPathElement }[] = [], pulses: SVGGElement;

  // a cable hung from (x0, y0) to (x1, y1) sagging by `sag` mid-span: y = a cosh((x - m) / a), with
  // a solved so that a (cosh(L / a) - 1) = sag for the half-span L
  function catenary(x0: number, y0: number, x1: number, y1: number, sag: number): [number, number][] {
    const L = (x1 - x0) / 2, m = (x0 + x1) / 2;
    let lo = 1, hi = 1e7;
    for (let i = 0; i < 80; i++) { const a = Math.sqrt(lo * hi); if (a * (Math.cosh(L / a) - 1) > sag) lo = a; else hi = a; }
    const a = Math.sqrt(lo * hi), pts: [number, number][] = [];
    for (let i = 0; i <= 80; i++) {
      const t = i / 80, x = x0 + (x1 - x0) * t;
      pts.push([x, y0 + (y1 - y0) * t + sag - a * (Math.cosh((x - m) / a) - 1)]);
    }
    return pts;
  }
  const line = (pts: [number, number][]) => pts.map((p, i) => `${i ? "L" : "M"}${f(p[0])} ${f(p[1])}`).join(" ");

  function pylon(g: Element, x: number, top: number, foot: number, w: number) {
    const d: string[] = [];
    d.push(`M${f(x - w)} ${f(foot)} L${f(x - w * 0.18)} ${f(top)} L${f(x + w * 0.18)} ${f(top)} L${f(x + w)} ${f(foot)}`);
    const n = 9;
    for (let i = 0; i < n; i++) {                              // the lattice: crossed bracing up the legs
      const t0 = i / n, t1 = (i + 1) / n, y0 = foot + (top - foot) * t0, y1 = foot + (top - foot) * t1;
      const h0 = w - (w - w * 0.18) * t0, h1 = w - (w - w * 0.18) * t1;
      d.push(`M${f(x - h0)} ${f(y0)} L${f(x + h1)} ${f(y1)} M${f(x + h0)} ${f(y0)} L${f(x - h1)} ${f(y1)}`);
    }
    for (const k of [0, 0.09, 0.18]) d.push(`M${f(x - w * 1.5)} ${f(top + (foot - top) * k)} L${f(x + w * 1.5)} ${f(top + (foot - top) * k)}`);   // the cross-arms
    el("path", { d: d.join(" "), class: "pylon" }, g);
  }

  function draw() {
    const r = svg.getBoundingClientRect(); W = r.width; H = r.height;
    if (!W || !H) return;
    svg.setAttribute("viewBox", `0 0 ${f(W)} ${f(H)}`);
    svg.replaceChildren();
    const g = el("g", { class: "grid" }, svg);
    const foot = H * 0.94, top = H * 0.075, pw = Math.max(14, W * 0.012);
    const xl = W * 0.018, xr = W * 0.982;
    pylon(g, xl, top, foot, pw); pylon(g, xr, top, foot, pw);
    cables = [];
    [0, 0.09, 0.18].forEach((k, i) => {
      const y = top + (foot - top) * k, pts = catenary(xl + (i - 1) * pw * 1.2, y, xr + (i - 1) * pw * 1.2, y, H * (0.05 + 0.02 * i));
      const path = el("path", { d: line(pts), class: "cable" }, g) as SVGPathElement;
      cables.push({ pts, path });
    });
    // the signs: a vertical strip of glyphs at the right, a thin ring at the left; dim and static
    const strip = el("text", { x: f(W * 0.966), y: f(H * 0.3), class: "glyphs" }, g);
    [...GLYPHS].forEach((ch, i) => { const t = el("tspan", { x: f(W * 0.966), dy: i ? "1.25em" : "0" }, strip); t.textContent = ch; });
    const rr = Math.min(24, W * 0.016);
    el("circle", { cx: f(W * 0.036), cy: f(H * 0.68), r: f(rr), class: "ring" }, g);
    el("circle", { cx: f(W * 0.036), cy: f(H * 0.68), r: f(rr * 0.7), class: "ring inner" }, g);
    pulses = el("g", { class: "pulses" }, svg) as SVGGElement;
  }

  function run(pts: [number, number][], ms: number) {
    if (reduce || !pulses) return;
    const p = el("path", { d: line(pts), class: "pulse", pathLength: 1 }, pulses) as SVGPathElement;
    const a = p.animate([{ strokeDashoffset: 1.06 }, { strokeDashoffset: -0.06 }], { duration: ms, easing: "cubic-bezier(.35, 0, 0, 1)" });
    a.onfinish = () => p.remove();
  }

  function pulseTo(x: number, y: number) {
    if (!cables.length) return;
    const c = cables[cables.length - 1].pts;                   // the lowest cable, then straight down
    let k = 0; while (k < c.length - 1 && c[k][0] < x) k++;
    run([...c.slice(0, k + 1), [x, y]], 1800);
  }

  function start(quiet: () => boolean) {
    const tick = () => {
      if (!quiet() && cables.length) {
        const c = cables[Math.floor(Math.random() * cables.length)].pts;
        run(Math.random() < 0.5 ? c : c.slice().reverse(), 2600);
      }
      window.setTimeout(tick, 3500 + Math.random() * 3000);
    };
    window.setTimeout(tick, 2000);
  }
  return { draw, pulseTo, start };
}
