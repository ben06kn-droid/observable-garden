// The bed along the bottom of page two: small neon flowers growing up from the ground as the run
// proceeds. It reads one number: the run's progress g in 0..1, half from the search (evaluations shown
// / evaluations in the log) and half from the replay (done / total from the worker's progress
// events). Flower i starts growing when g passes its threshold and is full grown a little after; its
// head opens over the replay half. Everything else here (each flower's place, height, lean, kind and
// colour) is decoration, picked from the run's id so a run's bed looks the same on every visit.
//
// The ground is a parabola: lowest at the bottom centre, where the flowers are densest, climbing each
// side to about 18% up the page, where they thin out and lean inwards; nothing grows above it. Under
// the ground line each flower has a faint reflection. Drawn in pixels (the viewBox is the box's size),
// so strokes stay hairline-sharp.
import { colourOf, drawHead, drawStem, hash, kindOf } from "./heads";

const NS = "http://www.w3.org/2000/svg";

interface Bloom { x: number; base: number; h: number; t: number; lean: number; kind: ReturnType<typeof kindOf>; colour: number; r: number; seed: number }
export interface BedHandle { grow(g: number): void; reset(runId: string): void }

const el = <K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
};
const f = (n: number) => n.toFixed(1);

export function makeBed(svg: SVGSVGElement, page: HTMLElement, n = 230): BedHandle {
  svg.setAttribute("aria-hidden", "true");
  let flowers: Bloom[] = [], groups: SVGGElement[] = [], mirrors: SVGGElement[] = [], heads: SVGGElement[] = [], grown: number[] = [], last = -1, id = "";

  function reset(runId: string) {
    id = runId;
    const r = svg.getBoundingClientRect(), W = Math.max(320, r.width), Hb = Math.max(120, r.height), P = page.clientHeight || innerHeight;
    svg.setAttribute("viewBox", `0 0 ${f(W)} ${f(Hb)}`);
    svg.replaceChildren();
    const c = W / 2, yv = Hb - 0.07 * P, ye = Hb - 0.18 * P;
    const ground = (x: number) => { const u = (x - c) / c; return yv - (yv - ye) * u * u; };
    flowers = []; groups = []; mirrors = []; heads = []; grown = []; last = -1;
    for (let i = 0; i < n; i++) {
      const fid = `${runId}:${i}`, hsh = hash(fid), q = (k: number) => ((hsh >>> k) % 1000) / 1000;
      // densest at the centre: |u| = q^1.7; a small gap left for the run's trunk
      const side = hsh % 2 ? 1 : -1, au = 0.03 + 0.97 * Math.pow(q(3), 1.7), u = side * au, x = c + u * c * 0.985;
      const hmax = P * (0.058 - 0.026 * au);
      flowers.push({ x, base: ground(x) + q(7) * 6, h: hmax * (0.45 + 0.55 * q(10)), t: q(4) * 0.42, lean: 20 * u * au,
        kind: kindOf(fid), colour: colourOf(fid), r: 3.4 + q(16) * 3.2, seed: hsh });
    }
    flowers.sort((a, b) => a.base - b.base || b.h - a.h);   // higher up the slope behind
    // the ground: below the line, the dark ground with the reflections; the line itself a lit hairline
    let d = "";
    for (let k = 0; k <= 64; k++) { const x = (k / 64) * W; d += `${k ? "L" : "M"}${f(x)} ${f(ground(x) + 4)}`; }
    el("path", { d: `${d} L${f(W)} ${f(Hb)} L0 ${f(Hb)} Z`, class: "ground-fill" }, svg);
    const refl = el("g", { class: "reflection" }, svg);
    el("path", { d, class: "ground-line" }, svg);
    const live = el("g", { class: "flowers" }, svg);
    for (const fl of flowers) {
      const g = el("g", { class: "bf" }, live) as SVGGElement;
      const [hx, top] = drawStem(g, 0, 0, -fl.h, fl.seed, "var(--stem)", 0.3);
      const head = el("g", { transform: `translate(${f(hx)} ${f(top)})` }, g);
      const inner = el("g", { class: "bloom" }, head) as SVGGElement;
      drawHead(inner, fl.kind, fl.colour, fl.r, 1);
      // the reflection: a plain copy mirrored about the flower's foot (a <use> would rebuild its copy
      // on every change to the original)
      const m = g.cloneNode(true) as SVGGElement; refl.appendChild(m);
      groups.push(g); mirrors.push(m); heads.push(inner); grown.push(-1);
    }
  }

  function grow(g: number) {
    if (!id || Math.abs(g - last) < 0.004) return;
    last = g;
    flowers.forEach((fl, i) => {
      const u = Math.round(Math.max(0, Math.min(1, (g - fl.t) / 0.45)) * 200) / 200;   // this flower's own growth
      if (u !== grown[i]) {                                     // only the flowers that changed are touched
        grown[i] = u;
        const t = `translate(${f(fl.x)} ${f(fl.base)}) skewX(${f(fl.lean)}) scale(${u.toFixed(3)})`;
        groups[i].setAttribute("transform", t);
        mirrors[i].setAttribute("transform", `translate(0 ${f(2 * fl.base + 8)}) scale(1 -1) ${t}`);
      }
      const open = g > 0.5 + 0.3 * fl.t;                        // heads open over the replay half
      if (heads[i].classList.contains("open") !== open) { heads[i].classList.toggle("open", open); (mirrors[i].querySelector(".bloom") as Element).classList.toggle("open", open); }
    });
  }
  return { grow, reset };
}
