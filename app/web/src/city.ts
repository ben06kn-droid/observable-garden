// Night City around page two's garden, all drawn in code, thin and precise: two pylons at the edges
// with three cables strung between them in shallow catenaries across the upper part of the page, a
// pulse of light running along one cable every few seconds, and two dim static signs at the edges (a
// vertical strip of glyphs, a thin ring). Decoration, except one thing: when a verdict lands, one
// pulse runs along a cable and down to the run's tree (index.ts says where the tree stands).
//
// The cables answer a click (or Enter: each is focusable): the cable vibrates at that point, a damped
// oscillation of under a second, and one bolt leaves along it toward its farther end (fx.ts). Hovering
// brightens a cable. Each cable is drawn in short segments so that colour can travel along it when the
// visitor enters a run (runView.ts reads them by [data-tide]).
//
// The pulses animate stroke-dashoffset on one short path at a time (a small repaint, a few times a
// minute), and none runs while the page is covered or a carry or zoom is playing.
import type { Fx } from "./fx";

const NS = "http://www.w3.org/2000/svg";
const el = <K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
};
const f = (n: number) => n.toFixed(1);
const GLYPHS = "7F3A·0E9C·41B8·D2";

export interface City { draw(): void; pulseTo(x: number, y: number): void; start(quiet: () => boolean): void; points(): [number, number][] }
const SEGS = 20;

export function makeCity(svg: SVGSVGElement, reduce: boolean, fx: Fx): City {
  svg.setAttribute("role", "group"); svg.setAttribute("aria-label", "Power lines");
  let W = 0, H = 0, cables: { pts: [number, number][]; segs: SVGGElement[]; shake: number }[] = [], pulses: SVGGElement;
  // a cable segment: a wider faint stroke for its glow under the lit hairline (no filter, so the
  // compositor has nothing extra to sort each frame)
  const seg = (g: Element, d: string) => { const s = el("g", { class: "cable", "data-tide": "" }, g) as SVGGElement; el("path", { d, class: "glow" }, s); el("path", { d, class: "lit" }, s); return s; };
  const setSeg = (s: SVGGElement, d: string) => s.querySelectorAll("path").forEach((p) => p.setAttribute("d", d));

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
    el("path", { d: d.join(" "), class: "pylon", "data-tide": "" }, g);
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
      const segs: SVGGElement[] = [];
      for (let j = 0; j < SEGS; j++) segs.push(seg(g, line(pts.slice(Math.floor((j * 80) / SEGS), Math.floor(((j + 1) * 80) / SEGS) + 1))));
      // a wide invisible stroke over the cable: hover brightens it, a click or Enter strikes it
      const hit = el("path", { d: line(pts), class: "cable-hit", tabindex: 0, role: "button", "aria-label": `Power line ${i + 1}: strike it` }, g);
      const lit = (on: boolean) => segs.forEach((p) => p.classList.toggle("hot", on));
      hit.addEventListener("pointerenter", () => lit(true));
      hit.addEventListener("pointerleave", () => lit(false));
      const cable = { pts, segs, shake: 0 };
      hit.addEventListener("click", (e) => { const r = svg.getBoundingClientRect(); strike(cable, (e as MouseEvent).clientX - r.left); });
      hit.addEventListener("keydown", (e) => { if ((e as KeyboardEvent).key === "Enter" || (e as KeyboardEvent).key === " ") { e.preventDefault(); strike(cable, W / 2); } });
      cables.push(cable);
    });
    // the signs: a vertical strip of glyphs at the right, a thin ring at the left; dim and static
    const strip = el("text", { x: f(W * 0.966), y: f(H * 0.3), class: "glyphs", "data-tide": "" }, g);
    [...GLYPHS].forEach((ch, i) => { const t = el("tspan", { x: f(W * 0.966), dy: i ? "1.25em" : "0" }, strip); t.textContent = ch; });
    const rr = Math.min(24, W * 0.016);
    el("circle", { cx: f(W * 0.036), cy: f(H * 0.68), r: f(rr), class: "ring", "data-tide": "" }, g);
    el("circle", { cx: f(W * 0.036), cy: f(H * 0.68), r: f(rr * 0.7), class: "ring inner", "data-tide": "" }, g);
    pulses = el("g", { class: "pulses" }, svg) as SVGGElement;
  }

  // the strike: a damped vibration around the point (the cable's segments redrawn each frame for under
  // a second) and one bolt toward the farther end
  function strike(c: (typeof cables)[number], x: number) {
    let k = 0; while (k < c.pts.length - 1 && c.pts[k][0] < x) k++;
    const toEnd = k < c.pts.length / 2 ? c.pts.slice(k) : c.pts.slice(0, k + 1).reverse();
    fx.bolt(toEnd, reduce);
    if (reduce) return;
    const xc = c.pts[k][0], id = ++c.shake, t0 = performance.now();
    const frame = (now: number) => {
      if (id !== c.shake) return;
      const t = (now - t0) / 1000, done = t > 0.85;
      const off = c.pts.map(([px, py]) => [px, py + (done ? 0 : 7 * Math.exp(-(((px - xc) / 90) ** 2)) * Math.sin(2 * Math.PI * 9 * t) * Math.exp(-t / 0.22))] as [number, number]);
      c.segs.forEach((p, j) => setSeg(p, line(off.slice(Math.floor((j * 80) / SEGS), Math.floor(((j + 1) * 80) / SEGS) + 1))));
      if (!done) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
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
  /** points along every cable and up the pylons (the section's pixels), for text to keep clear of */
  const points = () => [...cables.flatMap((c) => c.pts), ...[W * 0.018, W * 0.982].flatMap((x) => Array.from({ length: 30 }, (_, i) => [x, H * (0.075 + 0.87 * i / 29)] as [number, number]))];
  return { draw, pulseTo, start, points };
}
