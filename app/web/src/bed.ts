// The bed along the bottom of page two: small neon flowers growing up from the ground as the run
// proceeds. It reads one number: the run's progress g in 0..1, half from the search (evaluations shown
// / evaluations in the log) and half from the replay (done / total from the worker's progress
// events). Flower i starts growing when g passes its threshold and is full grown a little after; its
// head opens over the replay half. Everything else here (each flower's place, height, lean, kind and
// colour) is decoration, picked from the run's id so a run's bed looks the same on every visit.
//
// The ground is a parabola: lowest at the bottom centre, where the flowers are densest, climbing each
// side to about 18% up the page, where they thin out and lean inwards; nothing grows above it. Under
// the ground line each flower has a faint reflection. The ground and its line are svg (so the line's
// colour can travel when a run is entered); the flowers and their reflections are drawn into one
// canvas, at most about six times a second while they grow and not at all otherwise: as elements they
// were thousands of transformed paths, which the compositor re-sorted on every frame of the page.
import { colourOf, canvasSink, drawHead, drawStem, hash, kindOf, type Sink } from "./heads";

const NS = "http://www.w3.org/2000/svg";

interface Bloom { x: number; base: number; h: number; t: number; lean: number; kind: ReturnType<typeof kindOf>; colour: number; r: number; seed: number }
export interface BedHandle { grow(g: number): void; reset(runId: string): void; heads(): [number, number][] }

const el = <K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
};
const f = (n: number) => n.toFixed(1);
const STEM = "#2fd6a6";

export function makeBed(svg: SVGSVGElement, page: HTMLElement, n = 230): BedHandle {
  svg.setAttribute("aria-hidden", "true");
  const cv = document.createElement("canvas"); cv.className = "bed-cv"; cv.setAttribute("aria-hidden", "true");
  svg.after(cv);
  let flowers: Bloom[] = [], grown: number[] = [], last = -1, id = "", size = [0, 0], dpr = 1;

  function reset(runId: string) {
    id = runId;
    const r = svg.getBoundingClientRect(), W = Math.max(320, r.width), Hb = Math.max(120, r.height), P = page.clientHeight || innerHeight;
    svg.setAttribute("viewBox", `0 0 ${f(W)} ${f(Hb)}`);
    svg.replaceChildren();
    size = [W, Hb]; dpr = Math.min(devicePixelRatio || 1, 2);
    cv.width = Math.ceil(W * dpr); cv.height = Math.ceil(Hb * dpr);
    const c = W / 2, yv = Hb - 0.07 * P, ye = Hb - 0.18 * P;
    const ground = (x: number) => { const u = (x - c) / c; return yv - (yv - ye) * u * u; };
    flowers = []; grown = []; last = -1; window.clearTimeout(timer); timer = 0;
    for (let i = 0; i < n; i++) {
      const fid = `${runId}:${i}`, hsh = hash(fid), q = (k: number) => ((hsh >>> k) % 1000) / 1000;
      // densest at the centre: |u| = q^1.7; a small gap left for the run's trunk
      const side = hsh % 2 ? 1 : -1, au = 0.03 + 0.97 * Math.pow(q(3), 1.7), u = side * au, x = c + u * c * 0.985;
      const hmax = P * (0.058 - 0.026 * au);
      flowers.push({ x, base: ground(x) + q(7) * 6, h: hmax * (0.45 + 0.55 * q(10)), t: q(4) * 0.42, lean: 20 * u * au,
        kind: kindOf(fid), colour: colourOf(fid), r: 3.4 + q(16) * 3.2, seed: hsh });
      grown.push(0);
    }
    flowers.sort((a, b) => a.base - b.base || b.h - a.h);   // higher up the slope behind
    // the ground: the dark ground below the line; the line itself a lit hairline in short segments, so
    // colour can travel along it (runView.ts); its glow is a wider faint stroke under it, not a filter
    let d = "";
    for (let k = 0; k <= 64; k++) { const x = (k / 64) * W; d += `${k ? "L" : "M"}${f(x)} ${f(ground(x) + 4)}`; }
    el("path", { d: `${d} L${f(W)} ${f(Hb)} L0 ${f(Hb)} Z`, class: "ground-fill", "data-tide": "" }, svg);
    for (let j = 0; j < 24; j++) {
      let sd = "";
      for (let k = Math.floor((j * 64) / 24); k <= Math.floor(((j + 1) * 64) / 24); k++) { const x = (k / 64) * W; sd += `${sd ? "L" : "M"}${f(x)} ${f(ground(x) + 4)}`; }
      const seg = el("g", { class: "ground-line", "data-tide": "" }, svg);
      el("path", { d: sd, class: "glow" }, seg); el("path", { d: sd, class: "lit" }, seg);
    }
    const ctx = cv.getContext("2d"); ctx?.clearRect(0, 0, cv.width, cv.height);
  }

  // redrawn at most about six times a second (the latest progress wins)
  let pending = -1, timer = 0, lastPaint = 0;
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
    const c = cv.getContext("2d");
    if (!c) return;
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height);
    let alpha = 1;
    const sink: Sink = canvasSink(c, () => alpha, STEM);
    for (const mirror of [true, false]) {                   // the reflections first, faint, under the ground line
      flowers.forEach((fl, i) => {
        const u = Math.max(0, Math.min(1, (g - fl.t) / 0.45));   // this flower's own growth
        grown[i] = u;
        if (u <= 0) return;
        const op = Math.max(0, Math.min(1, (g - 0.5 - 0.3 * fl.t) / 0.06));   // its head opens over the replay half
        c.setTransform(dpr, 0, 0, dpr, 0, 0);
        if (mirror) { c.translate(0, 2 * fl.base + 8); c.scale(1, -1); }
        c.translate(fl.x, fl.base); c.transform(1, 0, Math.tan((fl.lean * Math.PI) / 180), 1, 0, 0); c.scale(u, u);
        alpha = mirror ? 0.13 : 1;
        const [hx, top] = drawStem(sink, 0, 0, -fl.h, fl.seed, STEM, 0.3);
        c.translate(hx, top); c.scale(0.3 + 0.7 * op, 0.3 + 0.7 * op);
        alpha = (mirror ? 0.13 : 1) * (0.55 + 0.45 * op);
        drawHead(sink, fl.kind, fl.colour, fl.r, 1);
      });
    }
    c.globalAlpha = 1;
  }
  /** where the grown heads stand, in the page section's pixels (the bed sits at the section's foot) */
  function headPoints(): [number, number][] {
    const off = page.clientHeight - size[1];
    return flowers.flatMap((fl, i) => (grown[i] > 0 ? [[fl.x, off + fl.base - fl.h * grown[i]] as [number, number]] : []));
  }
  return { grow, reset, heads: headPoints };
}
