// The leaves (page one) and petals (page two): a small particle simulation drawn into two canvases per
// page, one for what is in the air and one for the pile on the ground, so there is no element per
// leaf. Everything here is decoration; it reads no number from the gate.
//
// In the air, a piece relaxes toward its own slow terminal fall and a sideways sway, plus the wind.
// Pieces are released from points spread over the branches (garden tips and along the limbs,
// weighted toward the outer canopy, woods.ts), each starting with the small drift of its branch.
// The cursor is the wind: its movement leaves short-lived puffs of velocity that push what they pass
// through sideways and up, in proportion to the cursor's speed and falling off with distance; a slow
// pass barely stirs, a fast swipe scatters, and pieces lying in the pile are lifted and resettle.
// Nothing is spawned by the cursor. Every half minute to a minute a gust crosses the page: the falling
// pieces lean with it and a few in the pile lift. Each page opens with a small pile already gathered;
// the pile stays for the visit (memory only) and is capped so it never covers text.
// The simulation runs only while its page is on screen, at half rate while a run is computing, and not
// at all under reduced motion (the pieces are then drawn once, still).
import { SHAPES } from "./leaves";

export interface Source { x: number; y: number; vx: number; w: number }   // section pixels, drift, weight
interface Piece { x: number; y: number; vx: number; vy: number; a: number; va: number; s: number; vt: number; ph: number; ph2: number; rest: boolean; bin: number; fade: number }

const BIN = 8, THICK = 2.2, R = 110, PUFF_LIFE = 0.35;
const rnd = Math.random;

export interface FieldOptions {
  box: HTMLElement;                 // the page's section
  air: HTMLCanvasElement; pile: HTMLCanvasElement;
  kind: "leaf" | "petal";
  count: number;                    // pieces in the air
  start: number;                    // pieces in the pile when the page opens
  ground: (x: number) => number;    // the ground's y at x, section pixels
  cap: (x: number) => number;       // the pile's height limit at x
}

export class Field {
  o: FieldOptions; W = 0; H = 0; dpr = 1;
  air: Piece[] = []; rest: Piece[] = []; bins: number[] = [];
  sources: Source[] = []; cum: number[] = [];
  pileDirty = true; visible = false;
  private shape: Path2D;
  constructor(o: FieldOptions) { this.o = o; this.shape = new Path2D(SHAPES[o.kind]); }

  resize() {
    const W = this.o.box.clientWidth, H = this.o.box.clientHeight;
    const k = W / Math.max(1, this.W);
    if (this.W) for (const p of [...this.air, ...this.rest]) p.x *= k;
    this.W = W; this.H = H;
    this.dpr = Math.min(devicePixelRatio || 1, 2, Math.sqrt(5e6 / Math.max(1, W * H)));
    for (const c of [this.o.air, this.o.pile]) { c.width = Math.ceil(W * this.dpr); c.height = Math.ceil(H * this.dpr); c.style.setProperty("--w", `${W}px`); c.style.setProperty("--h", `${H}px`); }
    // rebuild the pile on its new ground
    const pieces = this.rest; this.rest = []; this.bins = [];
    for (const p of pieces) this.settle(p, true);
    this.pileDirty = true;
  }

  setSources(s: Source[]) {
    const first = !this.sources.length;
    this.sources = s; let c = 0; this.cum = s.map((x) => (c += x.w));
    if (first) for (let i = this.air.length; i < this.o.count; i++) this.release(undefined, true);   // the air already full when the trees arrive
  }
  private source(from?: Source[]): Source | null {
    const s = from ?? this.sources;
    if (!s.length) return null;
    if (from) return s[Math.floor(rnd() * s.length)];
    const t = rnd() * this.cum[this.cum.length - 1];
    let lo = 0, hi = this.cum.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (this.cum[m] < t) lo = m + 1; else hi = m; }
    return s[lo];
  }
  private piece(x: number, y: number, vx: number): Piece {
    const big = this.o.kind === "leaf";
    return { x, y, vx, vy: 0, a: rnd() * 6.28, va: (rnd() < 0.5 ? -1 : 1) * (0.6 + rnd() * 1.4), s: big ? 11 + rnd() * 9 : 9 + rnd() * 8,
      vt: (innerHeight * 1.04) / (16 + rnd() * 18), ph: rnd() * 6.28, ph2: rnd() * 6.28, rest: false, bin: -1, fade: 1 };
  }
  /** a piece released from a branch (or one of `from`), optionally anywhere along its fall already */
  release(from?: Source[], midway = false, kick = 0) {
    const s = this.source(from);
    if (!s) return;
    const p = this.piece(s.x + (rnd() - 0.5) * 6, s.y + (rnd() - 0.5) * 6, s.vx);
    if (midway) p.y += rnd() * Math.max(0, this.o.ground(p.x) - p.y);
    if (kick) { p.vx += (rnd() - 0.5) * kick; p.vy = -rnd() * kick * 0.4; }
    this.air.push(p);
  }
  burst(from: Source[], n: number) { for (let i = 0; i < n; i++) this.release(from, false, 60); }

  /** lay a piece on the pile where it is (or at its x), if the pile there has room */
  settle(p: Piece, force = false): boolean {
    const bin = Math.max(0, Math.floor(p.x / BIN)), h = this.bins[bin] ?? 0;
    if (!force && h >= this.o.cap(p.x)) return false;
    p.rest = true; p.bin = bin; p.vx = p.vy = 0; p.y = this.o.ground(p.x) - h - 3;
    this.bins[bin] = h + THICK;
    this.rest.push(p); this.pileDirty = true;
    return true;
  }
  /** take a piece off the pile into the air with a velocity */
  lift(p: Piece, vx: number, vy: number) {
    p.rest = false; this.bins[p.bin] = Math.max(0, (this.bins[p.bin] ?? 0) - THICK); p.bin = -1;
    p.vx = vx; p.vy = vy; p.va = (rnd() < 0.5 ? -1 : 1) * (2 + rnd() * 4);
    this.rest.splice(this.rest.indexOf(p), 1); this.air.push(p); this.pileDirty = true;
  }

  seed() {   // the pile the page opens with, and the pieces already in the air
    for (let i = 0; i < this.o.start; i++) { const p = this.piece(this.W * (0.02 + 0.96 * rnd()), 0, 0); p.a = rnd() * 6.28; this.settle(p); }
    for (let i = 0; i < this.o.count; i++) this.release(undefined, true);
  }

  step(dt: number, t: number, wind: Wind) {
    const g = wind.gust(t);
    const out: Piece[] = [];
    for (const p of this.air) {
      const [ax, ay] = wind.at(p.x, p.y, this.o.box);
      const sway = 22 * Math.cos(p.ph + t * 0.9);
      const k = 1 - Math.exp(-1.3 * dt);
      p.vx += ((sway + g) - p.vx) * k * 0.35 + ax * dt;   // the branch's drift decays into the sway
      p.vy += (p.vt - p.vy) * k + ay * dt;
      p.x += p.vx * dt; p.y += p.vy * dt;
      p.a += p.va * dt; p.va += ((p.va > 0 ? 1 : -1) * 0.8 - p.va) * k * 0.3;
      if (p.x < -40 || p.x > this.W + 40) { out.push(p); continue; }
      if (p.fade < 1) { p.fade -= dt; if (p.fade <= 0) out.push(p); continue; }
      const floor = this.o.ground(p.x) - (this.bins[Math.max(0, Math.floor(p.x / BIN))] ?? 0) - 3;
      if (p.vy > 0 && p.y >= floor) { if (this.settle(p)) out.push(p); else p.fade = 0.99; }
    }
    if (out.length) this.air = this.air.filter((p) => !out.includes(p));
    // the wind on the pile: a strong enough push lifts a piece
    if (wind.active()) for (const p of this.rest.slice()) {
      const [ax, ay] = wind.at(p.x, p.y, this.o.box);
      const dv = Math.hypot(ax, ay) * dt;
      if (dv > 9) this.lift(p, ax * dt * 1.2, -Math.abs(ay * dt) - dv * 0.6);
    }
    if (g !== 0 && wind.gustKick() && this.rest.length) for (let i = 0; i < 2; i++) { const p = this.rest[Math.floor(rnd() * this.rest.length)]; this.lift(p, g * 1.5, -(40 + rnd() * 70)); }
    // keep the air full: new pieces leave the branches
    let n = this.o.count - this.air.length;
    while (n-- > 0 && rnd() < 0.08) this.release();
  }

  draw() {
    const c = this.o.air.getContext("2d");
    if (c) { c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.o.air.width, this.o.air.height); for (const p of this.air) this.paint(c, p); }
    if (this.pileDirty) {
      const q = this.o.pile.getContext("2d");
      if (q) { q.setTransform(1, 0, 0, 1, 0, 0); q.clearRect(0, 0, this.o.pile.width, this.o.pile.height); for (const p of this.rest) this.paint(q, p); }
      this.pileDirty = false;
    }
  }
  private paint(c: CanvasRenderingContext2D, p: Piece) {
    const k = (this.dpr * p.s) / 20, ca = Math.cos(p.a) * k, sa = Math.sin(p.a) * k;
    const sy = p.rest ? 0.62 : 0.35 + 0.65 * Math.abs(Math.cos(p.ph2 + p.y * 0.02));   // flat on the ground; tumbling in the air
    c.globalAlpha = p.fade < 1 ? Math.max(0, p.fade) : 1;
    c.setTransform(ca, sa * sy, -sa, ca * sy, p.x * this.dpr, p.y * this.dpr);
    if (this.o.kind === "leaf") { c.fillStyle = "#e2b33a"; c.strokeStyle = "#8a6a12"; c.lineWidth = 0.8; c.fill(this.shape); c.stroke(this.shape); }
    else { c.fillStyle = "#ffb3d1"; c.fill(this.shape); }
  }
}

/** The wind: the cursor's puffs and the occasional gust, shared by both pages (viewport coordinates). */
export class Wind {
  puffs: { x: number; y: number; vx: number; vy: number; t: number }[] = [];
  g = { dir: 0, t0: 0, dur: 0, kicked: 0 };
  now = 0;
  add(x: number, y: number, vx: number, vy: number) {
    const sp = Math.hypot(vx, vy);
    if (sp < 30) return;
    const k = Math.min(1, 4000 / sp);
    this.puffs.push({ x, y, vx: vx * k, vy: vy * k, t: this.now });
    if (this.puffs.length > 14) this.puffs.shift();
  }
  active() { return this.puffs.length > 0; }
  tick(t: number) { this.now = t; this.puffs = this.puffs.filter((p) => t - p.t < PUFF_LIFE); }
  /** acceleration at a point of a section (its own pixels), in px/s² */
  at(x: number, y: number, box: HTMLElement): [number, number] {
    if (!this.puffs.length) return [0, 0];
    const b = this.rect(box);
    let ax = 0, ay = 0;
    for (const p of this.puffs) {
      const dx = x + b[0] - p.x, dy = y + b[1] - p.y, d2 = dx * dx + dy * dy;
      if (d2 > 9 * R * R) continue;
      const f = Math.exp(-d2 / (R * R)) * (1 - (this.now - p.t) / PUFF_LIFE) * 2.6;   // sideways and up
      ax += p.vx * f; ay += (-Math.abs(p.vx) * 0.35 - Math.abs(p.vy) * 0.25 + p.vy * 0.4) * f;
    }
    return [ax, ay];
  }
  private rects = new Map<HTMLElement, [number, number]>();
  frame() { this.rects.clear(); }
  private rect(box: HTMLElement): [number, number] { let r = this.rects.get(box); if (!r) { const b = box.getBoundingClientRect(); r = [b.left, b.top]; this.rects.set(box, r); } return r; }
  startGust(t: number) { this.g = { dir: rnd() < 0.5 ? -1 : 1, t0: t, dur: 2.4 + rnd() * 1.2, kicked: 0 }; }
  gust(t: number) { const u = (t - this.g.t0) / this.g.dur; return u > 0 && u < 1 ? this.g.dir * 70 * Math.sin(Math.PI * u) : 0; }
  gustKick() { return rnd() < 0.04; }
}

export interface LifeOptions { fields: Field[]; paused: () => boolean; throttled: () => boolean; reduce: boolean; overlay?: () => void }

/** One loop for both pages: input to wind, then each visible field steps and draws. */
export function startLife(o: LifeOptions) {
  const wind = new Wind();
  for (const f of o.fields) { f.resize(); f.seed(); f.draw(); }
  let resizeT = 0;
  window.addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => o.fields.forEach((f) => { f.resize(); f.draw(); }), 200); });
  if (o.reduce) return { wind, fields: o.fields };
  const io = new IntersectionObserver((es) => es.forEach((e) => { const f = o.fields.find((x) => x.o.box === e.target); if (f) f.visible = e.isIntersecting; }));
  o.fields.forEach((f) => io.observe(f.o.box));

  let lx = -1, ly = -1, lt = 0;
  const move = (x: number, y: number) => {
    const t = performance.now() / 1000;
    if (lx >= 0 && t > lt) { const dt = Math.max(0.008, t - lt); wind.add(x, y, (x - lx) / dt, (y - ly) / dt); }
    lx = x; ly = y; lt = t;
  };
  window.addEventListener("pointermove", (e) => { if (!o.paused()) move(e.clientX, e.clientY); }, { passive: true });
  window.addEventListener("touchmove", (e) => { const t = e.touches[0]; if (t && !o.paused()) move(t.clientX, t.clientY); }, { passive: true });
  window.addEventListener("touchend", () => { lx = -1; }, { passive: true });

  const gust = () => { if (!document.hidden) wind.startGust(performance.now() / 1000); window.setTimeout(gust, 30000 + rnd() * 30000); };
  window.setTimeout(gust, 30000 + rnd() * 30000);

  let last = performance.now(), skip = false;
  const frame = (now: number) => {
    requestAnimationFrame(frame);
    if (o.throttled()) { skip = !skip; if (skip) return; }       // half rate while a run computes
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    const t = now / 1000;
    wind.tick(t); wind.frame();
    for (const f of o.fields) if (f.visible && !(o.paused() && f.o.kind === "leaf")) { f.step(dt, t, wind); f.draw(); }
    o.overlay?.();
  };
  requestAnimationFrame(frame);
  return { wind, fields: o.fields };
}
