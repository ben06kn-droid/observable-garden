// The run page's glass: a large, still hourglass drawn as nothing but its two outline curves, with an
// abstract flow pouring through it. It scrolls with the page like any other element.
//
// The outline: each bulb widens from the neck all the way to its rim (the distance from the centre line
// never decreases away from the neck), so each bulb is widest at its open rim, top and bottom alike.
//
// The flow: fine strokes of varying length, and a few small simple shapes among them, entering across the
// full width of the top rim, drawn together as the glass narrows, through the neck, spreading again through
// the lower bulb and leaving at the bottom rim. Each follows a streamline: its place across the glass is a
// fixed fraction of the glass's half width at its height, so it follows the walls and never crosses them.
// It moves faster where the glass is narrow, as a fluid would, by a fixed profile. Nothing collects: what
// leaves at the bottom is gone, new strokes enter at the top at one steady rate, from the moment the page
// loads (the glass starts already full of flow), and nothing about it changes with the scroll. White with
// an occasional gold stroke, in the page's own tokens; no blur, glow or trails.
//
// The cursor: a smooth, round obstacle in the stream. Every stroke within REACH (140px) of it is moved
// straight away from it by an amount that depends only on the distance (PUSH, 22px, at the cursor, falling
// smoothly to nothing at REACH). The push is an offset added when a stroke is drawn: it never changes the
// flow (where a stroke is on its streamline, how fast it goes) and never accumulates. Each offset eases toward
// its target, quickly as the cursor comes near, and back to zero over about 500 ms (exponential, no overshoot)
// as it moves away or leaves; below a hundredth of a pixel it is exactly zero, and the flow is drawn exactly as
// if it had never been touched. A pushed stroke is held inside the outline, and turns the wake's silver-white
// tone (--wake-tone) with fine red fringes (--wake-fringe), in proportion to how far it is pushed; a gold stroke
// keeps its own gold, with no fringe. Only cursor
// movement (no touch), only where the wake is wanted (a fine pointer, motion allowed).
//
// The glass draws into its own 2D canvas. With `composited`, that canvas is not shown: the page's hero
// layer (src/hero.ts) draws it, together with the headline seen through the glass and the cursor's wake,
// and is told after each frame (onFrame).
//
// The other mode (2026-11-18): inside its outline the glass is the page's other colour mode: the other palette's
// ground (filled here only when the glass is not composited; the hero layer fills it otherwise), the flow in that
// palette's line, tone and fringe colours, the gold strokes gold; the outline in the page's own line colour. At
// the neck, the switch: a sun while the page is dark, a moon while it is light, a real button on a disc of the
// page's ground; it calls onSwitch. The glass itself does nothing when clicked. Reduced motion: one still frame.

import { wakeWanted } from "./cursorwake";

/** the other mode's colours (css colour strings) */
export interface Interior { ground: string; line: string; ink: string; tone: string; fringe: string; fringeA: number }
// the switch's two marks, line icons on a 28 px box in the page's line weight
const SUN = `<svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true"><circle cx="14" cy="14" r="5"/>${Array.from({ length: 8 }, (_, i) => { const a = (i * Math.PI) / 4, c = Math.cos(a), s = Math.sin(a); return `<line x1="${(14 + 8 * c).toFixed(2)}" y1="${(14 + 8 * s).toFixed(2)}" x2="${(14 + 11 * c).toFixed(2)}" y2="${(14 + 11 * s).toFixed(2)}"/>`; }).join("")}</svg>`;
const MOON = `<svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true"><path d="M17.6 5.6A9 9 0 1 0 22.4 18.6A7 7 0 0 1 17.6 5.6Z"/></svg>`;

export interface GlassOptions {
  height: number;
  reduce?: boolean;
  /** drawn by the page's hero layer, not shown itself (its canvas stays the source) */
  composited?: boolean;
  /** after each frame the glass draws */
  onFrame?: () => void;
  /** the other mode's colours, for the inside of the glass (the page's own when absent) */
  interior?: () => Interior | null;
  /** the switch at the neck was pressed: switch the page's mode, spreading from this viewport point */
  onSwitch?: (at: { x: number; y: number }) => void;
  /** the cursor came over the glass or its switch, or left */
  onHover?: (over: boolean) => void;
}

// the outline: the neck's half width, the rim's, and the short straight neck (× height, v from -1 to 1)
export const PROFILE = { neck: 0.011, rim: 0.215, soft: 0.07, pow: 1.32 };
/** half width at v: from the neck, s rises from 0 to 1 and never falls, still widening at the rim, so no
 *  wall turns back in. The waist is round, not a corner: the distance from the neck is softened near it
 *  (sqrt(a² + e²) - e grows like a² there), so the curve passes through the neck smoothly. */
export function halfWidth(v: number, H: number): number {
  const a = Math.min(1, Math.abs(v)), n = PROFILE.neck * H, R = PROFILE.rim * H, e = PROFILE.soft;
  const u = (Math.sqrt(a * a + e * e) - e) / (Math.sqrt(1 + e * e) - e);
  const s = Math.pow(u, PROFILE.pow);
  return n + (R - n) * s;
}
export const GLSL_PROFILE = `
float halfWidth(float v, float H) {
  float a = min(1.0, abs(v)), n = ${PROFILE.neck.toFixed(4)} * H, R = ${PROFILE.rim.toFixed(4)} * H, e = ${PROFILE.soft.toFixed(4)};
  float u = (sqrt(a * a + e * e) - e) / (sqrt(1.0 + e * e) - e);
  float s = pow(u, ${PROFILE.pow.toFixed(4)});
  return n + (R - n) * s;
}`;
function rgb(s: string): [number, number, number] {
  let h = s.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1];
  if (h) { if (h.length === 3) h = h.replace(/./g, "$&$&"); const n = parseInt(h, 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
  const m = s.match(/\d+(\.\d+)?/g); return m ? [Number(m[0]), Number(m[1]), Number(m[2])] : [0, 0, 0];
}
function mulberry(a: number) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

type Kind = 0 | 1 | 2 | 3 | 4;   // a stroke, or a small circle, square, triangle or cross
interface Item { t0: number; lane: number; kind: Kind; tau: number; gold: boolean; size: number; spin: number;
  /** the cursor's push: offsets (px) at K points along a stroke (one for a shape), x then y; null while untouched */
  off: Float32Array | null }

// the flow's constants: entering a little above the top rim and leaving a little below the bottom one
const V0 = -1.06, V1 = 1.06;
const RATE = 34;            // strokes entering per second
const TRAVEL = 9;           // seconds from rim to rim (the profile below sets where it is quick or slow)
// the cursor's push
const PUSH = 22;            // px, at the cursor
const REACH = 140;          // px: nothing beyond
const T_IN = 0.06;          // s: an offset's time constant as the cursor comes near
const T_OUT = 0.12;         // s: and back to zero (98.5% within 0.5 s, 1e-7 within 2 s)
const K = 5;                // points along a stroke where its push is kept (its vertices are interpolated)
const LEVELS = 4;           // how far a stroke is pushed, in steps, for its tone and fringes
/** the push's size at a distance d: PUSH at 0, falling smoothly (no kink at either end) to 0 at REACH */
export const pushAt = (d: number) => (d >= REACH ? 0 : PUSH * (1 - (d / REACH) ** 2) ** 2);

export class Glass {
  readonly el: HTMLDivElement;
  private o: GlassOptions; private H: number; private gy: number; private R: number; private W: number; private dpr = 1;
  private front: HTMLCanvasElement; private edge: HTMLCanvasElement;   // the flow (each frame); the outline (once)
  private line: [number, number, number] = [240, 241, 250];
  private sand = "#d6b27b"; private lineA = 0.72;
  // the switch; the inside's ground and its flow's line colour (the other mode's), the page's mode
  readonly mark: HTMLButtonElement; private iGround = ""; private flowLine: [number, number, number] = [240, 241, 250]; private hover = false;
  private tone: [number, number, number] = [221, 227, 240]; private fringe = "#ef4b55"; private fringeA = 1;
  // the cursor (viewport px) and the glass's top left on the page when it was last seen; whether any offset is not zero
  private cursor: { x: number; y: number } | null = null; private gpage: [number, number] = [0, 0]; private pushed = false; private pdt = 0;
  private pushes = wakeWanted(); private ac = new AbortController();   // the page-wide listeners, removed with the glass
  // the flow: a table of where an item is (v) after a given time since it entered, and the items
  private tv!: Float32Array; private tt!: Float32Array; private items: Item[] = []; private clock = 0; private owed = 0; private rnd = mulberry(29);
  private raf = 0; private last = 0; private running = false; private visible = true; private io: IntersectionObserver | null = null;

  constructor(host: HTMLElement, o: GlassOptions) {
    this.o = o; this.H = o.height; this.gy = this.H / 2; this.R = PROFILE.rim * this.H;
    this.W = Math.ceil(2 * this.R + 8);
    this.el = document.createElement("div"); this.el.className = "glass";
    this.front = document.createElement("canvas"); this.front.className = "glass-front"; this.front.setAttribute("aria-hidden", "true");
    if (o.composited) this.el.classList.add("composited");
    this.edge = document.createElement("canvas"); this.edge.className = "glass-edge"; this.edge.setAttribute("aria-hidden", "true");
    this.el.append(this.front, this.edge);
    // the switch, centred on the neck
    this.mark = document.createElement("button"); this.mark.type = "button"; this.mark.className = "hg-mark";
    this.el.append(this.mark);
    host.append(this.el);
    this.layout(); this.readPalette(); this.drawEdge(); this.initFlow(); this.bind();
    this.io = new IntersectionObserver((es) => { this.visible = es.some((e) => e.isIntersecting); if (this.visible) this.start(); });
    this.io.observe(this.el);
    this.render();
    if (!o.reduce) this.start();
  }
  destroy() { this.ac.abort(); this.running = false; cancelAnimationFrame(this.raf); this.io?.disconnect(); this.el.remove(); }
  /** the glass's own measures, css px */
  measures() { return { H: this.H, R: this.R, W: this.W, gy: this.gy }; }
  /** half width at a height within the glass (v from -1 at the top rim to 1 at the bottom) */
  halfWidthAt(v: number) { return halfWidth(v, this.H); }

  /** whether the cursor is over the glass or its switch */
  get over() { return this.hover; }
  /** read the colours from the page's tokens (after a palette swap) and redraw */
  refreshPalette() { this.readPalette(); this.drawEdge(); this.render(); }
  private readPalette() {
    const cs = getComputedStyle(this.el);
    const l = cs.getPropertyValue("--hg-line");
    if (l) this.line = rgb(l);                            // the outline: the page's own line colour
    this.sand = cs.getPropertyValue("--fan-sand").trim() || "#d6b27b";   // gold stays the page's gold
    this.lineA = Number(cs.getPropertyValue("--flow-alpha")) || 0.72;
    // the inside: the other mode's ground, line, tone and fringe (the page's own when there is no other)
    const io = this.o.interior?.() ?? null;
    this.iGround = io?.ground ?? "";
    this.flowLine = io ? rgb(io.line) : this.line;
    this.tone = rgb(io?.tone || cs.getPropertyValue("--wake-tone") || "#dde3f0");
    this.fringe = io?.fringe || cs.getPropertyValue("--wake-fringe").trim() || "#ef4b55";
    this.fringeA = io?.fringeA ?? (Number(cs.getPropertyValue("--wake-fringe-alpha")) || 1);
  }
  /** the page's mode, for the switch's mark and its label */
  setMode(mode: "dark" | "light") {
    this.mark.innerHTML = mode === "dark" ? SUN : MOON;
    this.mark.setAttribute("aria-label", mode === "dark" ? "Switch to light mode" : "Switch to dark mode");
  }

  private layout() {
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.el.style.setProperty("--glass-w", `${this.W}px`); this.el.style.setProperty("--glass-h", `${this.H}px`);
    for (const c of [this.front, this.edge]) { c.width = Math.round(this.W * this.dpr); c.height = Math.round(this.H * this.dpr); }
  }

  /** the canvas the glass draws into (the hero layer's source when composited) */
  get canvas() { return this.front; }
  /** the outline, drawn once (it does not move) */
  get outline() { return this.edge; }
  private drawEdge() {
    const x = this.edge.getContext("2d")!, k = this.dpr, gy = this.gy;
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, this.edge.width, this.edge.height);
    x.setTransform(k, 0, 0, k, 0, 0); x.translate(this.W / 2, this.H / 2);
    x.strokeStyle = `rgba(${this.line.join(",")},0.85)`; x.lineWidth = 1; x.lineJoin = "round"; x.lineCap = "round";
    for (const side of [-1, 1]) {
      x.beginPath();
      for (let q = 0; q <= 240; q++) { const v = -1 + (2 * q) / 240, r = halfWidth(v, this.H); q ? x.lineTo(side * r, v * gy) : x.moveTo(side * r, v * gy); }
      x.stroke();
    }
  }

  // ---------- the flow
  /** where an item is after a time: a table built once from the speed profile. The speed is inverse to
   *  the glass's width (as a fluid's through a nozzle), softened (to the 0.55 power) and capped, so the
   *  neck runs quick but readable; scaled so a rim-to-rim trip takes TRAVEL seconds. */
  private initFlow() {
    const N = 1600, tv = new Float32Array(N + 1), tt = new Float32Array(N + 1), floor = 0.07 * this.R;
    let t = 0;
    for (let i = 0; i <= N; i++) {
      const v = V0 + (V1 - V0) * (i / N);
      tv[i] = v; tt[i] = t;
      const w = Math.max(floor, halfWidth(v, this.H));
      t += ((V1 - V0) / N) / Math.pow(this.R / w, 0.55);
    }
    for (let i = 0; i <= N; i++) tt[i] *= TRAVEL / t;
    this.tv = tv; this.tt = tt;
    // the glass starts already full: items spread back over one whole trip, as if it had been running
    const n = Math.round(RATE * TRAVEL * 1.1);
    for (let q = 0; q < n; q++) this.items.push(this.item(-(q / RATE)));
  }
  private item(t0: number): Item {
    const r = this.rnd, kind: Kind = r() < 0.08 ? (1 + Math.floor(r() * 4)) as Kind : 0;
    // lanes across the whole rim; a little more often toward the middle, never on the wall
    const u = r() * 2 - 1, lane = Math.sign(u) * Math.pow(Math.abs(u), 0.85) * 0.86;
    return { t0, lane, kind, tau: kind ? 0 : 0.12 + Math.pow(r(), 1.6) * 0.75, gold: r() < 1 / 8, size: 2.2 + r() * 1.6, spin: r() * Math.PI * 2, off: null };
  }
  /** v after `age` seconds in the glass (before it enters: V0; after it leaves: V1) */
  private vAt(age: number) {
    const tt = this.tt, N = tt.length - 1;
    if (age <= 0) return V0; if (age >= tt[N]) return V1 + (age - tt[N]) * 0.5;
    let lo = 0, hi = N;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tt[m] <= age) lo = m; else hi = m; }
    const f = (age - tt[lo]) / Math.max(1e-6, tt[hi] - tt[lo]);
    return this.tv[lo] + (this.tv[hi] - this.tv[lo]) * f;
  }
  /** a point on an item's streamline at v: its lane's share of the half width, kept off the wall */
  private at(lane: number, v: number): [number, number] {
    const hw = halfWidth(v, this.H), room = Math.max(0, hw - Math.min(3, hw * 0.4));
    return [lane * room, v * this.gy];
  }
  private advance(dt: number) {
    this.clock += dt; this.owed += dt * RATE;
    while (this.owed >= 1) { this.owed -= 1; this.items.push(this.item(this.clock - this.owed / RATE)); }
    const end = this.tt[this.tt.length - 1];
    this.items = this.items.filter((it) => this.clock - it.t0 - it.tau < end + 0.2);
  }

  private render() {
    const x = this.front.getContext("2d")!, k = this.dpr, gy = this.gy;
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, this.front.width, this.front.height);
    x.setTransform(k, 0, 0, k, 0, 0); x.translate(this.W / 2, this.H / 2);
    // the flow, inside the glass's height (it enters and leaves through the open rims)
    // the inside's ground, when the glass is shown as itself (composited, the hero layer fills it)
    if (!this.o.composited && this.iGround) {
      x.beginPath();
      for (let q = 0; q <= 120; q++) { const v = -1 + (2 * q) / 120, r = halfWidth(v, this.H); q ? x.lineTo(-r, v * gy) : x.moveTo(-r, v * gy); }
      for (let q = 120; q >= 0; q--) { const v = -1 + (2 * q) / 120; x.lineTo(halfWidth(v, this.H), v * gy); }
      x.closePath(); x.fillStyle = this.iGround; x.fill();
    }
    x.save(); x.beginPath(); x.rect(-this.W / 2, -gy, this.W, 2 * gy); x.clip();
    x.lineCap = "round"; x.lineJoin = "round";
    // the lines crowd together where the glass narrows; each piece of a stroke is drawn as faint as the
    // crowding there asks, so the neck stays a bundle of lines rather than a bar. Pieces go into a few
    // opacity bins, one path each.
    const BINS = 6;
    // paths by colour (white, gold), by how far the cursor pushes them (0: not at all) and by opacity bin;
    // the fringes of pushed strokes by push level and opacity bin. Made only when used.
    const paths: (Path2D | null)[] = new Array(2 * (LEVELS + 1) * BINS).fill(null), fringes: (Path2D | null)[] = new Array((LEVELS + 1) * BINS).fill(null);
    const P = (g: number, l: number, b: number) => paths[(g * (LEVELS + 1) + l) * BINS + b] ??= new Path2D();
    const F = (l: number, b: number) => fringes[l * BINS + b] ??= new Path2D();
    const thin = (v: number) => Math.max(0.16, Math.min(1, (halfWidth(v, this.H) - 2) / (0.22 * this.R)));
    const bin = (a: number) => Math.min(BINS - 1, Math.floor(a * BINS));
    // the cursor in the glass's own frame (centred), when it is near enough to push anything
    const c = this.near();
    const push = !!c || this.pushed, dt = this.pdt; this.pdt = 0;
    let any = false;
    for (const it of this.items) {
      const age = this.clock - it.t0, g = it.gold ? 1 : 0;
      if (it.kind === 0) {
        // a stroke: the stretch of its streamline covered in the last `tau` seconds, so it lengthens where
        // the flow is quick and shortens where it is slow
        const vh = this.vAt(age), vt = this.vAt(age - it.tau);
        if (vh <= V0 || vt >= V1) { it.off = null; continue; }
        const steps = Math.max(2, Math.min(16, Math.ceil(Math.abs(vh - vt) * 40)));
        const base = (j: number) => this.at(it.lane, vt + (vh - vt) * (j / (K - 1)));
        let o = push ? this.ease(it, K, base, c, dt) : 0;
        if (o) any = true;
        const off = it.off;
        // how far it is pushed: as drawn, held inside the outline (a stroke pressed against a wall barely moves)
        if (o && off) { o = 0; for (let j = 0; j < K; j++) { const p = base(j), q = this.inside(p[0] + off[2 * j], p[1] + off[2 * j + 1]); o = Math.max(o, Math.hypot(q[0] - p[0], q[1] - p[1])); } }
        const lvl = o > 0.5 ? 1 + Math.min(LEVELS - 1, Math.floor((o / PUSH) * LEVELS)) : 0;
        // a vertex: its place on the streamline, plus the push interpolated between the kept points, held inside the outline
        const pt = (q: number): [number, number] => {
          const p = this.at(it.lane, vt + (vh - vt) * (q / steps));
          if (!lvl || !off) return p;
          const f = (q / steps) * (K - 1), j = Math.min(K - 2, Math.floor(f)), u = f - j;
          return this.inside(p[0] + off[2 * j] + (off[2 * j + 2] - off[2 * j]) * u, p[1] + off[2 * j + 1] + (off[2 * j + 3] - off[2 * j + 1]) * u);
        };
        let prev = pt(0);
        // the fringes' offset: along the push, about a pixel (as the wake's fringes elsewhere)
        let nx = 0, ny = 0;
        if (lvl && off) { for (let j = 0; j < K; j++) { nx += off[2 * j]; ny += off[2 * j + 1]; } const l = Math.hypot(nx, ny) || 1, k = 0.7 + 0.6 * (o / PUSH); nx *= k / l; ny *= k / l; }
        for (let q = 1; q <= steps; q++) {
          const v = vt + (vh - vt) * (q / steps), p = pt(q), b = bin(thin(v - (vh - vt) / steps / 2));
          const path = P(g, lvl, b); path.moveTo(prev[0], prev[1]); path.lineTo(p[0], p[1]);
          if (lvl && !it.gold) { const fp = F(lvl, b); fp.moveTo(prev[0] + nx, prev[1] + ny); fp.lineTo(p[0] + nx, p[1] + ny); fp.moveTo(prev[0] - nx, prev[1] - ny); fp.lineTo(p[0] - nx, p[1] - ny); }   // gold strokes take no fringe
          prev = p;
        }
      } else {
        // a small shape at its place, turned to the flow; it fades out through the neck
        const v = this.vAt(age); if (v <= V0 || v >= V1) { it.off = null; continue; }
        const hw = halfWidth(v, this.H); if (hw < 16) { it.off = null; continue; }
        let p = this.at(it.lane, v); const q = this.at(it.lane, v + 0.004), ang = Math.atan2(q[1] - p[1], q[0] - p[0]) + it.spin;
        const at0 = p, o = push ? this.ease(it, 1, () => at0, c, dt) : 0;
        if (o) any = true;
        if (o && it.off) p = this.inside(p[0] + it.off[0], p[1] + it.off[1], it.size * 1.15);
        const moved = Math.hypot(p[0] - at0[0], p[1] - at0[1]), lvl = moved > 0.5 ? 1 + Math.min(LEVELS - 1, Math.floor((moved / PUSH) * LEVELS)) : 0;
        const r = it.size, path = P(g, lvl, bin(Math.min(1, (hw - 16) / 30)));
        const cs = Math.cos(ang), sn = Math.sin(ang), Q = (dx: number, dy: number): [number, number] => [p[0] + dx * cs - dy * sn, p[1] + dx * sn + dy * cs];
        if (it.kind === 1) { path.moveTo(p[0] + r, p[1]); path.arc(p[0], p[1], r, 0, Math.PI * 2); }
        else if (it.kind === 2) { const a = Q(-r, -r), b = Q(r, -r), d = Q(r, r), e = Q(-r, r); path.moveTo(...a); path.lineTo(...b); path.lineTo(...d); path.lineTo(...e); path.closePath(); }
        else if (it.kind === 3) { const a = Q(r * 1.1, 0), b = Q(-r * 0.6, r), d = Q(-r * 0.6, -r); path.moveTo(...a); path.lineTo(...b); path.lineTo(...d); path.closePath(); }
        else { const a = Q(-r, 0), b = Q(r, 0), d = Q(0, -r), e = Q(0, r); path.moveTo(...a); path.lineTo(...b); path.moveTo(...d); path.lineTo(...e); }
      }
    }
    this.pushed = any;
    const mix = (a: [number, number, number], t: number) => `rgb(${a.map((x, i) => Math.round(x + (this.tone[i] - x) * t)).join(",")})`;
    // the red fringes of pushed strokes, under every stroke
    if (any) { x.strokeStyle = this.fringe; x.lineWidth = 0.9;
      for (let l = 1; l <= LEVELS; l++) for (let b = 0; b < BINS; b++) {
        const fp = fringes[l * BINS + b]; if (!fp) continue;
        x.globalAlpha = Math.min(1, 0.4 * this.fringeA * ((l - 0.5) / LEVELS)) * ((b + 0.5) / BINS); x.stroke(fp);
      } }
    for (let g = 0; g < 2; g++) for (let l = 0; l <= LEVELS; l++) {
      const t = l ? (l - 0.5) / LEVELS : 0;     // how far this level is pushed: its share of the tone
      for (let b = 0; b < BINS; b++) {
        const path = paths[(g * (LEVELS + 1) + l) * BINS + b]; if (!path) continue;
        const a = (b + 0.5) / BINS;
        x.lineWidth = g ? 1.1 : 0.9;
        x.globalAlpha = (g ? 0.95 : this.lineA) * a;
        // a pushed white stroke takes the tone; a gold one keeps its own gold
        x.strokeStyle = g ? this.sand : l ? mix(this.flowLine, t) : `rgb(${this.flowLine.join(",")})`;
        x.stroke(path);
      }
    }
    x.globalAlpha = 1;
    x.restore();
    this.o.onFrame?.();
  }

  // ---------- the cursor's push
  /** the cursor in the glass's frame (centred, css px), if it is within REACH of the glass's box */
  private near(): { x: number; y: number } | null {
    if (!this.cursor || !this.pushes) return null;
    const x = this.cursor.x - (this.gpage[0] - scrollX) - this.W / 2, y = this.cursor.y - (this.gpage[1] - scrollY) - this.H / 2;
    return Math.abs(x) < this.W / 2 + REACH && Math.abs(y) < this.gy + REACH ? { x, y } : null;
  }
  /** eases an item's offsets at its n kept points (base(j): the point on its streamline) toward the push from c;
   *  returns the largest offset (px), 0 when every one is exactly zero (and the item is untouched again) */
  private ease(it: Item, n: number, base: (j: number) => [number, number], c: { x: number; y: number } | null, dt: number): number {
    let off = it.off, most = 0;
    for (let j = 0; j < n; j++) {
      let tx = 0, ty = 0;
      if (c) {
        const p = base(j), dx = p[0] - c.x, dy = p[1] - c.y, d = Math.hypot(dx, dy), m = pushAt(d);
        if (m > 0) { if (d > 1e-3) { tx = (dx / d) * m; ty = (dy / d) * m; } else { tx = (Math.sign(it.lane) || 1) * m; } }
      }
      if (!off) { if (!tx && !ty) continue; off = it.off = new Float32Array(2 * n); }
      const ox = off[2 * j], oy = off[2 * j + 1];
      const k = 1 - Math.exp(-dt / (tx * tx + ty * ty >= ox * ox + oy * oy ? T_IN : T_OUT));
      let nx = ox + (tx - ox) * k, ny = oy + (ty - oy) * k;
      if (!tx && !ty && nx * nx + ny * ny < 1e-4) { nx = 0; ny = 0; }     // under a hundredth of a pixel: exactly back
      off[2 * j] = nx; off[2 * j + 1] = ny; most = Math.max(most, Math.hypot(nx, ny));
    }
    if (off && !most) it.off = null;
    return most;
  }
  /** a point held inside the outline (as a streamline is: off the wall), at its own height; `r`: a shape's radius,
   *  so all of it stays inside */
  private inside(px: number, py: number, r = 0): [number, number] {
    const hw = halfWidth(py / this.gy, this.H), room = Math.max(0, hw - Math.min(3, hw * 0.4) - r);
    return [Math.max(-room, Math.min(room, px)), py];
  }
  /** the largest offset any stroke has now (px): 0 when the flow is exactly as if never touched */
  maxOffset(): number {
    let m = 0;
    for (const it of this.items) if (it.off) for (let j = 0; j < it.off.length; j += 2) m = Math.max(m, Math.hypot(it.off[j], it.off[j + 1]));
    return m;
  }

  // ---------- the switch, and the cursor over the glass
  private inGlass(e: { clientX: number; clientY: number }) {
    const b = this.front.getBoundingClientRect(), lx = e.clientX - b.left - b.width / 2, ly = e.clientY - b.top - b.height / 2, v = ly / this.gy;
    return Math.abs(v) < 1 && Math.abs(lx) < halfWidth(v, this.H) + 4;
  }
  private bind() {
    // the cursor, for its push: only its movement, never touch; where the glass is on the page, read as it moves
    if (this.pushes) {
      window.addEventListener("pointermove", (e: PointerEvent) => {
        if (e.pointerType === "touch") return;
        this.cursor = { x: e.clientX, y: e.clientY };
        const b = this.front.getBoundingClientRect(); this.gpage = [b.left + scrollX, b.top + scrollY];
      }, { passive: true, signal: this.ac.signal });
      document.documentElement.addEventListener("pointerleave", () => { this.cursor = null; }, { passive: true, signal: this.ac.signal });
      addEventListener("blur", () => { this.cursor = null; }, { signal: this.ac.signal });
    }
    // the switch: a real button (Tab, Enter, Space by the browser); it switches from its own centre
    this.mark.addEventListener("click", () => { const r = this.mark.getBoundingClientRect(); this.o.onSwitch?.({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); });
    // over the glass or the switch (a mouse or pen only; a tap gets no preview)
    const hover = (on: boolean) => { if (on !== this.hover) { this.hover = on; this.o.onHover?.(on); } };
    this.el.addEventListener("pointermove", (e) => { if (e.pointerType !== "touch") hover(this.inGlass(e) || e.target === this.mark || this.mark.contains(e.target as Node)); }, { passive: true });
    this.el.addEventListener("pointerleave", () => hover(false), { passive: true });
  }

  // ---------- the loop: runs while the glass is on screen; its own clock pauses with it
  private start() {
    if (this.running || this.o.reduce || !this.visible) return;
    this.running = true; this.last = performance.now();
    const frame = (now: number) => {
      if (!this.running) return;
      if (!this.visible) { this.running = false; return; }
      const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
      this.advance(dt); this.pdt = dt; this.render();
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }
}
