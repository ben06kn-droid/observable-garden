// Flower heads, drawn from real petal shapes (pointed or rounded, overlapping), translucent neon with
// a bright outline, no faces, no sunflowers. Kind and colour are decoration: picked from a run's id (and
// an index, for the bed) so a run keeps its flowers across visits; they read no number.
const NS = "http://www.w3.org/2000/svg";

export const KINDS = ["daisy", "tulip", "forget-me-not", "lily", "hydrangea", "peony", "lavender"] as const;
export type Kind = (typeof KINDS)[number];
// Night City neon, to sit with the tubing on page two: [fill, deeper tone for the kept rule's bloom,
// outline]. The fill is drawn translucent and the outline bright, so a head reads as lit glass.
export const PALETTE: [string, string, string][] = [
  ["#ff2ea6", "#ff0a84", "#ffc4e8"],   // hot magenta
  ["#19e3f0", "#00b4d8", "#ccfbff"],   // cyan
  ["#f3ec3a", "#e2c800", "#fffbc8"],   // electric yellow
  ["#a65cff", "#7c2dff", "#e8d8ff"],   // violet
  ["#ff4f6e", "#ff1f4b", "#ffd2db"],   // neon coral
  ["#3dffb4", "#00e08c", "#d2ffee"],   // acid mint
];

export function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
export const kindOf = (id: string) => KINDS[hash(id + "#kind") % KINDS.length];
export const colourOf = (id: string) => hash(id + "#colour") % PALETTE.length;

function el<K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number>, parent: Element): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  parent.appendChild(e);
  return e;
}
const f = (n: number) => n.toFixed(1);

/** A petal from the origin outward along -y: length `l`, half-width `w`, rounded or pointed tip. */
export function petal(l: number, w: number, tip: "round" | "point" | "notch" = "round"): string {
  if (tip === "point") return `M0 0 C${f(-w)} ${f(-l * 0.3)} ${f(-w * 0.7)} ${f(-l * 0.75)} 0 ${f(-l)} C${f(w * 0.7)} ${f(-l * 0.75)} ${f(w)} ${f(-l * 0.3)} 0 0 Z`;
  if (tip === "notch") return `M0 0 C${f(-w * 1.1)} ${f(-l * 0.35)} ${f(-w)} ${f(-l * 0.95)} ${f(-w * 0.35)} ${f(-l)} L0 ${f(-l * 0.9)} L${f(w * 0.35)} ${f(-l)} C${f(w)} ${f(-l * 0.95)} ${f(w * 1.1)} ${f(-l * 0.35)} 0 0 Z`;
  return `M0 0 C${f(-w * 1.15)} ${f(-l * 0.3)} ${f(-w * 1.05)} ${f(-l)} 0 ${f(-l)} C${f(w * 1.05)} ${f(-l)} ${f(w * 1.15)} ${f(-l * 0.3)} 0 0 Z`;
}

/** Draw a head of `kind` at the origin of `g`, `r` its radius, opened by `o` (0..1). */
export function drawHead(g: SVGGElement, kind: Kind, colour: number, r: number, o: number, deep = false) {
  const [fill, deeper, line] = PALETTE[colour];
  const c = deep ? deeper : fill;
  const P = (d: string, rot: number, extra = "") => el("path", { d, transform: `rotate(${f(rot)})${extra}`, fill: c, stroke: line, "stroke-width": f(Math.max(0.6, r * 0.05)), class: "petal" }, g);
  const s = 0.25 + 0.75 * o;
  const ring = (n: number, off: number, fn: (a: number, i: number) => void) => { for (let i = 0; i < n; i++) fn(off + (i / n) * 360, i); };
  const heart = (rr: number, col = line) => el("circle", { cx: 0, cy: 0, r: f(rr), fill: col, class: "heart" }, g);
  switch (kind) {
    case "daisy":
      ring(12, 0, (a) => P(petal(r * s, r * 0.18 * s, "notch"), a));
      heart(r * 0.24 * s, deep ? fill : deeper);
      break;
    case "tulip": {
      const l = r * 1.2 * s, w = r * 0.42 * s;
      P(petal(l, w, "point"), -18, ` translate(${f(-r * 0.12)} 0)`);
      P(petal(l, w, "point"), 18, ` translate(${f(r * 0.12)} 0)`);
      P(petal(l * 1.04, w * 1.05, "point"), 0);
      break;
    }
    case "forget-me-not":
      [[0, -0.55], [-0.6, 0.05], [0.6, 0.05], [-0.25, 0.6], [0.35, 0.58]].slice(0, Math.max(1, Math.ceil(5 * o))).forEach(([dx, dy], k) => {
        const sub = el("g", { transform: `translate(${f(dx * r)} ${f(dy * r)})` }, g) as SVGGElement;
        for (let i = 0; i < 5; i++) el("path", { d: petal(r * 0.42 * s, r * 0.2 * s, "round"), transform: `rotate(${f(i * 72 + k * 13)})`, fill: c, stroke: line, "stroke-width": f(Math.max(0.5, r * 0.04)), class: "petal" }, sub);
        el("circle", { cx: 0, cy: 0, r: f(r * 0.09 * s), fill: line, class: "heart" }, sub);
      });
      break;
    case "lily":
      ring(3, 30, (a) => P(petal(r * 1.1 * s, r * 0.3 * s, "point"), a));
      ring(3, 90, (a) => P(petal(r * 1.0 * s, r * 0.26 * s, "point"), a));
      ring(5, 10, (a) => el("line", { x1: 0, y1: 0, x2: f(Math.sin(a * Math.PI / 180) * r * 0.55 * s), y2: f(-Math.cos(a * Math.PI / 180) * r * 0.55 * s), stroke: deeper, "stroke-width": f(r * 0.05), class: "stamen" }, g));
      break;
    case "hydrangea": {
      const n = Math.max(3, Math.round(13 * o));
      for (let i = 0; i < n; i++) {
        const a = i * 2.4, rr = r * 0.22 * Math.sqrt(i + 0.5);
        const sub = el("g", { transform: `translate(${f(Math.cos(a) * rr)} ${f(Math.sin(a) * rr * 0.85)})` }, g) as SVGGElement;
        for (let k = 0; k < 4; k++) el("path", { d: petal(r * 0.3 * s, r * 0.17 * s, "round"), transform: `rotate(${f(k * 90 + i * 17)})`, fill: c, stroke: line, "stroke-width": f(Math.max(0.5, r * 0.035)), class: "petal" }, sub);
      }
      break;
    }
    case "peony":
      ring(9, 0, (a) => P(petal(r * s, r * 0.42 * s, "round"), a));
      ring(7, 20, (a) => P(petal(r * 0.72 * s, r * 0.36 * s, "round"), a));
      ring(5, 8, (a) => P(petal(r * 0.45 * s, r * 0.28 * s, "round"), a));
      break;
    case "lavender":
      [-0.35, 0, 0.35].forEach((dx, k) => {
        const tall = r * (k === 1 ? 1.6 : 1.25), n = Math.max(2, Math.round(7 * o));
        el("path", { d: `M0 0 Q${f(dx * r * 0.4)} ${f(-tall * 0.5)} ${f(dx * r)} ${f(-tall)}`, fill: "none", stroke: line, "stroke-width": f(r * 0.05), class: "spike" }, g);
        for (let i = 0; i < n; i++) {
          const t = 0.3 + (i / 7) * 0.7, x = dx * r * t, y = -tall * t;
          el("path", { d: petal(r * 0.2, r * 0.09, "point"), transform: `translate(${f(x)} ${f(y)}) rotate(${f(-35)})`, fill: c, stroke: line, "stroke-width": f(Math.max(0.4, r * 0.03)), class: "petal" }, g);
          el("path", { d: petal(r * 0.2, r * 0.09, "point"), transform: `translate(${f(x)} ${f(y)}) rotate(${f(35)})`, fill: c, stroke: line, "stroke-width": f(Math.max(0.4, r * 0.03)), class: "petal" }, g);
        }
      });
      break;
  }
}

/** A wavy stem from (x, ground) to (x + lean, top) with two or three leaves along it; returns the top. */
export function drawStem(g: SVGGElement, x: number, ground: number, top: number, seed: number, colour = "var(--stem)", leafScale = 1) {
  const len = ground - top, amp = Math.min(22, 5 + len * 0.08), side = seed % 2 ? 1 : -1, hx = x + side * amp * 0.4;
  el("path", { d: `M${f(x)} ${f(ground)} C${f(x + side * amp)} ${f(ground - len * 0.25)} ${f(x + side * amp)} ${f(ground - len * 0.45)} ${f(x)} ${f(ground - len * 0.55)} S${f(hx - side * amp * 1.1)} ${f(top + len * 0.18)} ${f(hx)} ${f(top)}`,
    fill: "none", stroke: colour, "stroke-width": f(Math.max(1.6, len * 0.018)), "stroke-linecap": "round", class: "stem" }, g);
  if (len > 24 * leafScale) {
    const spots = len > 120 ? [0.3, 0.52, 0.72] : [0.35, 0.62];
    spots.forEach((t, i) => {
      const yy = ground - len * t, xx = x + side * amp * (t < 0.55 ? 0.7 * Math.sin((t / 0.55) * Math.PI) : -0.35 * Math.sin(((t - 0.55) / 0.45) * Math.PI));
      const dir = i % 2 ? -side : side, sz = Math.min(1.5, 0.35 + len / 160) * leafScale;
      el("path", { d: `M0 0 C${f(7 * dir)} -4 ${f(20 * dir)} -6 ${f(30 * dir)} -18 C${f(19 * dir)} -1 ${f(9 * dir)} 3 0 0 Z`, transform: `translate(${f(xx)} ${f(yy)}) scale(${f(sz)})`, fill: colour, class: "leaf-on-stem" }, g);
    });
  }
  return [hx, top] as const;
}
