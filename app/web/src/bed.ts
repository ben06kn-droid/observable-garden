// The bed along the bottom of page two: small neon flowers growing up from the ground when a run
// starts. It is decoration and reads nothing from the gate: it keeps its own clock, so it blooms at
// the same pace however fast the gate runs. From the click, flower i starts at its own moment
// (staggered over the first 4.5 s), its stem grows on an eased curve over 1.6 s, and its head opens
// from bud on its own eased curve over 1.8 s; the whole bed is open about 8.5 s after the click, before
// the quickest verdict (about 11 s). Each flower's place, height, lean, kind and colour come from the
// run's id, so a run's bed looks the same on every visit.
//
// The ground is a parabola: lowest at the bottom centre, where the flowers are densest, climbing each
// side to about 18% up the page, where they thin out and lean inwards; nothing grows above it. Under
// the ground line the flowers are reflected as on a wet surface: mirrored, squashed, blurred a little
// and faded to nothing within 28 px of the line, so no flower reads as a copy. The ground and its line are svg (so the line's
// colour can travel when a run is entered); the flowers and their reflections are drawn into one
// canvas, at most about six times a second while they grow and not at all otherwise: as elements they
// were thousands of transformed paths, which the compositor re-sorted on every frame of the page.
import { colourOf, canvasSink, drawHead, drawStem, hash, kindOf, type Sink } from "./heads";

const NS = "http://www.w3.org/2000/svg";

interface Bloom { x: number; base: number; h: number; t: number; lean: number; kind: ReturnType<typeof kindOf>; colour: number; r: number; seed: number }
export interface BedHandle { start(): void; finish(): void; reset(runId: string): void; heads(): [number, number][] }

const el = <K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
};
const f = (n: number) => n.toFixed(1);
const STEM = "#9d93b8";   // the stems in the flowers' own muted lilac, not a fifth colour

export function makeBed(svg: SVGSVGElement, page: HTMLElement, n = 230): BedHandle {
  svg.setAttribute("aria-hidden", "true");
  const cv = document.createElement("canvas"); cv.className = "bed-cv"; cv.setAttribute("aria-hidden", "true");
  svg.after(cv);
  let flowers: Bloom[] = [], grown: number[] = [], id = "", size = [0, 0], dpr = 1;
  const wet = document.createElement("canvas"), mask = document.createElement("canvas");

  function reset(runId: string) {
    id = runId;
    const r = svg.getBoundingClientRect(), W = Math.max(320, r.width), Hb = Math.max(120, r.height), P = page.clientHeight || innerHeight;
    svg.setAttribute("viewBox", `0 0 ${f(W)} ${f(Hb)}`);
    svg.replaceChildren();
    size = [W, Hb]; dpr = Math.min(devicePixelRatio || 1, 2);
    cv.width = Math.ceil(W * dpr); cv.height = Math.ceil(Hb * dpr);
    const c = W / 2, yv = Hb - 0.07 * P, ye = Hb - 0.18 * P;
    const ground = (x: number) => { const u = (x - c) / c; return yv - (yv - ye) * u * u; };
    wet.width = mask.width = cv.width; wet.height = mask.height = cv.height;
    // the wet ground's fade: opaque at the line, nothing 28 px below it, following the curve
    const m = mask.getContext("2d");
    if (m) {
      m.setTransform(dpr, 0, 0, dpr, 0, 0); m.clearRect(0, 0, W, Hb);
      for (let x = 0; x < W; x += 8) {
        const y0 = ground(x + 4) + 4, gr = m.createLinearGradient(0, y0, 0, y0 + 28);
        gr.addColorStop(0, "rgba(0,0,0,0.5)"); gr.addColorStop(1, "rgba(0,0,0,0)");
        m.fillStyle = gr; m.fillRect(x, y0, 8, 28);
      }
    }
    flowers = []; grown = []; running = false;
    for (let i = 0; i < n; i++) {
      const fid = `${runId}:${i}`, hsh = hash(fid), q = (k: number) => ((hsh >>> k) % 1000) / 1000;
      // densest at the centre: |u| = q^1.7; a small gap left for the run's trunk
      const side = hsh % 2 ? 1 : -1, au = 0.03 + 0.97 * Math.pow(q(3), 1.7), u = side * au, x = c + u * c * 0.985;
      const hmax = P * (0.046 - 0.02 * au);
      flowers.push({ x, base: ground(x) + q(7) * 6, h: hmax * (0.45 + 0.55 * q(10)), t: q(4) * 0.42, lean: 20 * u * au,
        kind: kindOf(fid), colour: colourOf(fid), r: 2.4 + q(16) * 2.2, seed: hsh });
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

  // the clock: one loop while the bed is growing, drawing every other frame; idle otherwise
  const START = 4.5, GROW = 1.6, OPEN = 1.8, ease = (x: number) => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3);
  const smooth = (x: number) => { const t = Math.max(0, Math.min(1, x)); return t * t * (3 - 2 * t); };
  let t0 = 0, running = false, odd = false;
  const at = (fl: Bloom, t: number) => {
    const s0 = (fl.t / 0.42) * START, h = (fl.seed % 1000) / 1000;
    return [ease((t - s0) / GROW), smooth((t - s0 - 1.2 - 0.8 * h) / OPEN)];   // stem grown, head open
  };
  function start() {
    if (!id) return;
    t0 = performance.now(); if (running) return;
    running = true;
    const frame = (now: number) => {
      const t = (now - t0) / 1000;
      odd = !odd;
      if (odd || t > START + 1.2 + 0.8 + OPEN) paint(t);
      if (t <= START + 1.2 + 0.8 + OPEN + 0.05) requestAnimationFrame(frame); else running = false;
    };
    requestAnimationFrame(frame);
  }
  function finish() { running = false; t0 = performance.now() - 60000; paint(60); }
  function paint(t: number) {
    const c = cv.getContext("2d");
    if (!c) return;
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height);
    let alpha = 1;
    const sink: Sink = canvasSink(c, () => alpha, STEM);
    const state = flowers.map((fl) => at(fl, t));
    const flower = (k: CanvasRenderingContext2D, s: Sink, mirror: boolean) => flowers.forEach((fl, i) => {
      const [u, op] = state[i];
      grown[i] = u;
      if (u <= 0) return;
      k.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (mirror) { const g = fl.base + 4; k.translate(0, g * 1.6); k.scale(1, -0.6); }   // mirrored about the line, squashed
      k.translate(fl.x, fl.base); k.transform(1, 0, Math.tan((fl.lean * Math.PI) / 180), 1, 0, 0); k.scale(u, u);
      alpha = 1;
      const [hx, top] = drawStem(s, 0, 0, -fl.h, fl.seed, STEM, 0.3);
      k.translate(hx, top); k.scale(0.3 + 0.7 * op, 0.3 + 0.7 * op);
      alpha = 0.55 + 0.45 * op;
      drawHead(s, fl.kind, fl.colour, fl.r, 1);
    });
    // the wet ground: the mirrored flowers, faded to nothing 28 px below the line, then laid in blurred
    const w = wet.getContext("2d");
    if (w) {
      w.setTransform(1, 0, 0, 1, 0, 0); w.globalCompositeOperation = "source-over"; w.clearRect(0, 0, wet.width, wet.height);
      flower(w, canvasSink(w, () => alpha, STEM), true);
      w.setTransform(1, 0, 0, 1, 0, 0); w.globalAlpha = 1; w.globalCompositeOperation = "destination-in"; w.drawImage(mask, 0, 0);
      w.globalCompositeOperation = "source-over";
      c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.filter = `blur(${(1.6 * dpr).toFixed(1)}px)`; c.drawImage(wet, 0, 0); c.filter = "none";
    }
    flower(c, sink, false);
    c.globalAlpha = 1;
  }
  /** where the grown heads stand, in the page section's pixels (the bed sits at the section's foot) */
  function headPoints(): [number, number][] {
    const off = page.clientHeight - size[1];
    return flowers.flatMap((fl, i) => (grown[i] > 0 ? [[fl.x, off + fl.base - fl.h * grown[i]] as [number, number]] : []));
  }
  return { start, finish, reset, heads: headPoints };
}
