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
  let flowers: Bloom[] = [], groups: SVGGElement[] = [], heads: SVGGElement[] = [], grown: number[] = [], last = -1, id = "";
  let refl: SVGImageElement | null = null, size = [0, 0];

  function reset(runId: string) {
    id = runId;
    const r = svg.getBoundingClientRect(), W = Math.max(320, r.width), Hb = Math.max(120, r.height), P = page.clientHeight || innerHeight;
    svg.setAttribute("viewBox", `0 0 ${f(W)} ${f(Hb)}`);
    svg.replaceChildren();
    const c = W / 2, yv = Hb - 0.07 * P, ye = Hb - 0.18 * P;
    const ground = (x: number) => { const u = (x - c) / c; return yv - (yv - ye) * u * u; };
    flowers = []; groups = []; heads = []; grown = []; last = -1; lastTenth = -1; window.clearTimeout(timer); timer = 0;
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
    // the reflection: one image of the mirrored flowers, redrawn now and then (as hundreds of mirrored
    // groups it doubled what the compositor sorts on every frame of the run and slowed it fourfold)
    refl = el("image", { class: "reflection", x: 0, y: 0, width: f(W), height: f(Hb), preserveAspectRatio: "none" }, svg) as SVGImageElement;
    size = [W, Hb];
    el("path", { d, class: "ground-line" }, svg);
    const live = el("g", { class: "flowers" }, svg);
    for (const fl of flowers) {
      const g = el("g", { class: "bf" }, live) as SVGGElement;
      const [hx, top] = drawStem(g, 0, 0, -fl.h, fl.seed, "var(--stem)", 0.3);
      const head = el("g", { transform: `translate(${f(hx)} ${f(top)})` }, g);
      const inner = el("g", { class: "bloom" }, head) as SVGGElement;
      drawHead(inner, fl.kind, fl.colour, fl.r, 1);
      groups.push(g); heads.push(inner); grown.push(-1);
    }
  }

  // Each repaint of the bed rasterises every flower, so it is redrawn at most about six times a second
  // (the latest progress wins), and the reflections, which double that cost, only at each tenth of
  // the run and at its end.
  let pending = -1, timer = 0, lastPaint = 0, lastTenth = -1;
  function grow(g: number) {
    if (!id || Math.abs(g - last) < 0.004) return;
    pending = g;
    const wait = 160 - (performance.now() - lastPaint);
    if (g >= 1 || wait <= 0) paint();
    else if (!timer) timer = window.setTimeout(paint, wait);
  }
  function paint() {
    window.clearTimeout(timer); timer = 0;
    const g = pending; last = g; lastPaint = performance.now();
    const tenth = g >= 1 ? 10 : Math.floor(g * 10), mirror = tenth !== lastTenth;
    lastTenth = tenth;
    flowers.forEach((fl, i) => {
      const u = Math.round(Math.max(0, Math.min(1, (g - fl.t) / 0.45)) * 200) / 200;   // this flower's own growth
      const t = `translate(${f(fl.x)} ${f(fl.base)}) skewX(${f(fl.lean)}) scale(${u.toFixed(3)})`;
      if (u !== grown[i]) { grown[i] = u; groups[i].setAttribute("transform", t); }   // only the flowers that changed are touched
      const open = g > 0.5 + 0.3 * fl.t;                        // heads open over the replay half
      if (heads[i].classList.contains("open") !== open) heads[i].classList.toggle("open", open);
    });
    if (mirror) reflect();
  }
  // the flowers as they stand, each mirrored about its foot, serialised into an svg image (data: is
  // allowed by img-src); the bed's own styles go with it, since page css does not reach into images
  function reflect() {
    if (!refl) return;
    const parts = flowers.map((fl, i) => `<g transform="translate(0 ${f(2 * fl.base + 8)}) scale(1 -1) ${groups[i].getAttribute("transform") ?? ""}">${groups[i].innerHTML}</g>`);
    const css = ".petal{fill-opacity:.3;stroke-width:.7px}.stem{stroke-width:1px;opacity:.75}.leaf-on-stem{fill-opacity:.2;stroke:#2fd6a6;stroke-width:2.4}"
      + ".bloom{opacity:.55;transform:scale(.3);transform-box:fill-box;transform-origin:center}.bloom.open{opacity:1;transform:none}";
    const doc = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f(size[0])} ${f(size[1])}"><style>${css}</style>${parts.join("").replaceAll("var(--stem)", "#2fd6a6")}</svg>`;
    refl.setAttribute("href", "data:image/svg+xml;charset=utf-8," + encodeURIComponent(doc));
  }
  return { grow, reset };
}
