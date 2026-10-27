// Flower heads, drawn from real petal shapes (pointed or rounded, overlapping), translucent neon with
// a bright outline, no faces, no sunflowers. Kind and colour are decoration: picked from a run's id (and
// an index, for the bed) so a run keeps its flowers across visits; they read no number.
const NS = "http://www.w3.org/2000/svg";

export const KINDS = ["daisy", "tulip", "forget-me-not", "lily", "hydrangea", "peony", "lavender"] as const;
export type Kind = (typeof KINDS)[number];
// The flowers' one family on page two, a narrow pastel range at low saturation (magenta is the trees',
// cyan the cables' and the bar's, white the type's): [fill, deeper tone for the kept rule's bloom,
// outline]. The fill is drawn translucent and the outline light.
export const PALETTE: [string, string, string][] = [
  ["#efc9d5", "#e2aabd", "#fbe9ef"],   // blush
  ["#ece8f1", "#d6cfe0", "#fbfaff"],   // white
  ["#cfc2e3", "#b8a6d6", "#efe9f8"],   // lilac
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

/** Where a flower is drawn: into svg elements (the blossoms on the run's tree) or straight into a
 *  canvas (the bed, which as elements would be thousands of transformed paths). Transforms are the
 *  small set used here: translate, rotate, scale, in order. */
export interface Sink {
  path(d: string, tf: string, fill: string, stroke: string, sw: number, cls: string): void;
  circle(r: number, fill: string, cls: string): void;
  line(x2: number, y2: number, stroke: string, sw: number, cls: string): void;
  group(tf: string, fn: () => void): void;
}
/** Into svg elements, every transform baked into the coordinates (`at` places the whole head): a head
 *  is plain paths in one group, not one transformed element per petal, which the compositor would
 *  otherwise sort one by one on every frame. */
export function svgSink(root: SVGGElement, at: DOMMatrix = new DOMMatrix()): Sink {
  let m = at;
  const mat = (tf: string) => { let k = m; for (const x of tf.matchAll(TF)) { const v = x[2].split(/[ ,]+/).filter(Boolean).map(Number); k = x[1] === "translate" ? k.translate(v[0], v[1] ?? 0) : x[1] === "rotate" ? k.rotate(v[0]) : k.scale(v[0], v[1] ?? v[0]); } return k; };
  const pt = (k: DOMMatrix, x: number, y: number) => { const p = k.transformPoint(new DOMPoint(x, y)); return `${f(p.x)} ${f(p.y)}`; };
  const bake = (d: string, k: DOMMatrix) => d.replace(/(-?\d*\.?\d+)[ ,]+(-?\d*\.?\d+)/g, (_, x, y) => pt(k, Number(x), Number(y)));
  const scale = (k: DOMMatrix) => Math.hypot(k.a, k.b);
  return {
    path: (d, tf, fill, stroke, sw, cls) => { const k = tf ? mat(tf) : m; el("path", { d: bake(d, k), fill, stroke, "stroke-width": f(sw * scale(k)), class: cls, ...(cls === "stem" ? { "stroke-linecap": "round" } : {}) }, root); },
    circle: (r, fill, cls) => { const p = m.transformPoint(new DOMPoint(0, 0)); el("circle", { cx: f(p.x), cy: f(p.y), r: f(r * scale(m)), fill, class: cls }, root); },
    line: (x2, y2, stroke, sw, cls) => { const a = m.transformPoint(new DOMPoint(0, 0)), b = m.transformPoint(new DOMPoint(x2, y2)); el("line", { x1: f(a.x), y1: f(a.y), x2: f(b.x), y2: f(b.y), stroke, "stroke-width": f(sw * scale(m)), class: cls }, root); },
    group: (tf, fn) => { const prev = m; m = mat(tf); fn(); m = prev; },
  };
}
const TF = /(translate|rotate|scale)\(([^)]*)\)/g;
const paths = new Map<string, Path2D>();
const P2 = (d: string) => { let p = paths.get(d); if (!p) { p = new Path2D(d); paths.set(d, p); } return p; };
/** The bed's look, as its css had it: translucent petals with a bright outline, hairline stems. */
export function canvasSink(c: CanvasRenderingContext2D, alpha: () => number, stem: string): Sink {
  const apply = (tf: string) => {
    for (const m of tf.matchAll(TF)) {
      const v = m[2].split(/[ ,]+/).filter(Boolean).map(Number);
      if (m[1] === "translate") c.translate(v[0], v[1] ?? 0);
      else if (m[1] === "rotate") c.rotate((v[0] * Math.PI) / 180);
      else c.scale(v[0], v[1] ?? v[0]);
    }
  };
  const col = (x: string) => (x === "var(--stem)" ? stem : x);
  return {
    path: (d, tf, fill, stroke, sw, cls) => {
      c.save(); if (tf) apply(tf);
      const p = P2(d), a = alpha();
      if (fill !== "none") { c.globalAlpha = a * (cls === "petal" ? 0.3 : cls === "leaf-on-stem" ? 0.2 : 1); c.fillStyle = col(fill); c.fill(p); }
      if (cls === "leaf-on-stem") { c.globalAlpha = a; c.strokeStyle = stem; c.lineWidth = 2.4; c.stroke(p); }
      else if (stroke !== "none") { c.globalAlpha = a * (cls === "stem" ? 0.75 : 1); c.strokeStyle = col(stroke); c.lineWidth = cls === "petal" ? 0.7 : cls === "stem" ? 1 : sw; c.lineCap = "round"; c.stroke(p); }
      c.restore();
    },
    circle: (r, fill) => { c.globalAlpha = alpha(); c.fillStyle = col(fill); c.beginPath(); c.arc(0, 0, r, 0, 6.2832); c.fill(); },
    line: (x2, y2, stroke, sw) => { c.globalAlpha = alpha(); c.strokeStyle = col(stroke); c.lineWidth = sw; c.beginPath(); c.moveTo(0, 0); c.lineTo(x2, y2); c.stroke(); },
    group: (tf, fn) => { c.save(); apply(tf); fn(); c.restore(); },
  };
}

/** Draw a head of `kind` at the origin of `g` (an svg group, or a sink), `r` its radius, opened by `o` (0..1). */
export function drawHead(g: SVGGElement | Sink, kind: Kind, colour: number, r: number, o: number, deep = false) {
  const k = "path" in g ? g : svgSink(g);
  const [fill, deeper, line] = PALETTE[colour];
  const c = deep ? deeper : fill;
  const P = (d: string, rot: number, extra = "") => k.path(d, `rotate(${f(rot)})${extra}`, c, line, Math.max(0.6, r * 0.05), "petal");
  const s = 0.25 + 0.75 * o;
  const ring = (n: number, off: number, fn: (a: number, i: number) => void) => { for (let i = 0; i < n; i++) fn(off + (i / n) * 360, i); };
  const heart = (rr: number, col = line) => k.circle(rr, col, "heart");
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
      [[0, -0.55], [-0.6, 0.05], [0.6, 0.05], [-0.25, 0.6], [0.35, 0.58]].slice(0, Math.max(1, Math.ceil(5 * o))).forEach(([dx, dy], j) => {
        k.group(`translate(${f(dx * r)} ${f(dy * r)})`, () => {
          for (let i = 0; i < 5; i++) k.path(petal(r * 0.42 * s, r * 0.2 * s, "round"), `rotate(${f(i * 72 + j * 13)})`, c, line, Math.max(0.5, r * 0.04), "petal");
          k.circle(r * 0.09 * s, line, "heart");
        });
      });
      break;
    case "lily":
      ring(3, 30, (a) => P(petal(r * 1.1 * s, r * 0.3 * s, "point"), a));
      ring(3, 90, (a) => P(petal(r * 1.0 * s, r * 0.26 * s, "point"), a));
      ring(5, 10, (a) => k.line(Math.sin(a * Math.PI / 180) * r * 0.55 * s, -Math.cos(a * Math.PI / 180) * r * 0.55 * s, deeper, r * 0.05, "stamen"));
      break;
    case "hydrangea": {
      const n = Math.max(3, Math.round(13 * o));
      for (let i = 0; i < n; i++) {
        const a = i * 2.4, rr = r * 0.22 * Math.sqrt(i + 0.5);
        k.group(`translate(${f(Math.cos(a) * rr)} ${f(Math.sin(a) * rr * 0.85)})`, () => {
          for (let j = 0; j < 4; j++) k.path(petal(r * 0.3 * s, r * 0.17 * s, "round"), `rotate(${f(j * 90 + i * 17)})`, c, line, Math.max(0.5, r * 0.035), "petal");
        });
      }
      break;
    }
    case "peony":
      ring(9, 0, (a) => P(petal(r * s, r * 0.42 * s, "round"), a));
      ring(7, 20, (a) => P(petal(r * 0.72 * s, r * 0.36 * s, "round"), a));
      ring(5, 8, (a) => P(petal(r * 0.45 * s, r * 0.28 * s, "round"), a));
      break;
    case "lavender":
      [-0.35, 0, 0.35].forEach((dx, j) => {
        const tall = r * (j === 1 ? 1.6 : 1.25), n = Math.max(2, Math.round(7 * o));
        k.path(`M0 0 Q${f(dx * r * 0.4)} ${f(-tall * 0.5)} ${f(dx * r)} ${f(-tall)}`, "", "none", line, r * 0.05, "spike");
        for (let i = 0; i < n; i++) {
          const t = 0.3 + (i / 7) * 0.7, x = dx * r * t, y = -tall * t;
          k.path(petal(r * 0.2, r * 0.09, "point"), `translate(${f(x)} ${f(y)}) rotate(${f(-35)})`, c, line, Math.max(0.4, r * 0.03), "petal");
          k.path(petal(r * 0.2, r * 0.09, "point"), `translate(${f(x)} ${f(y)}) rotate(${f(35)})`, c, line, Math.max(0.4, r * 0.03), "petal");
        }
      });
      break;
  }
}

/** A wavy stem from (x, ground) to (x + lean, top) with two or three leaves along it; returns the top. */
export function drawStem(g: SVGGElement | Sink, x: number, ground: number, top: number, seed: number, colour = "var(--stem)", leafScale = 1) {
  const k = "path" in g ? g : svgSink(g);
  const len = ground - top, amp = Math.min(22, 5 + len * 0.08), side = seed % 2 ? 1 : -1, hx = x + side * amp * 0.4;
  k.path(`M${f(x)} ${f(ground)} C${f(x + side * amp)} ${f(ground - len * 0.25)} ${f(x + side * amp)} ${f(ground - len * 0.45)} ${f(x)} ${f(ground - len * 0.55)} S${f(hx - side * amp * 1.1)} ${f(top + len * 0.18)} ${f(hx)} ${f(top)}`,
    "", "none", colour, Math.max(1.6, len * 0.018), "stem");
  if (len > 24 * leafScale) {
    const spots = len > 120 ? [0.3, 0.52, 0.72] : [0.35, 0.62];
    spots.forEach((t, i) => {
      const yy = ground - len * t, xx = x + side * amp * (t < 0.55 ? 0.7 * Math.sin((t / 0.55) * Math.PI) : -0.35 * Math.sin(((t - 0.55) / 0.45) * Math.PI));
      const dir = i % 2 ? -side : side, sz = Math.min(1.5, 0.35 + len / 160) * leafScale;
      k.path(`M0 0 C${f(7 * dir)} -4 ${f(20 * dir)} -6 ${f(30 * dir)} -18 C${f(19 * dir)} -1 ${f(9 * dir)} 3 0 0 Z`, `translate(${f(xx)} ${f(yy)}) scale(${f(sz)})`, colour, "none", 0, "leaf-on-stem");
    });
  }
  return [hx, top] as const;
}
