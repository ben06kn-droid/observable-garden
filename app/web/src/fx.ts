// Page two's effects canvas: one canvas over the scene, drawn only while an effect plays (a bolt along
// a cable, the blue ring entering or leaving a run and the lightning it strikes from petals), cleared
// and idle otherwise. Coordinates are the section's pixels.
type Effect = (c: CanvasRenderingContext2D, t: number) => boolean;   // false when done
type Pt = [number, number];

export class Fx {
  private effects: { f: Effect; t0: number }[] = [];
  private running = false; private dpr = 1; private W = 0; private H = 0;
  constructor(private canvas: HTMLCanvasElement, private box: HTMLElement) { this.resize(); window.addEventListener("resize", () => this.resize()); }
  resize() {
    this.W = this.box.clientWidth; this.H = this.box.clientHeight; this.dpr = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = Math.ceil(this.W * this.dpr); this.canvas.height = Math.ceil(this.H * this.dpr);
    this.canvas.style.setProperty("--w", `${this.W}px`); this.canvas.style.setProperty("--h", `${this.H}px`);
  }
  add(f: Effect) {
    this.effects.push({ f, t0: performance.now() });
    if (!this.running) { this.running = true; requestAnimationFrame(this.frame); }
  }
  private frame = (now: number) => {
    const c = this.canvas.getContext("2d");
    if (!c) return;
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.canvas.width, this.canvas.height);
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.effects = this.effects.filter((e) => e.f(c, (now - e.t0) / 1000));
    if (this.effects.length) requestAnimationFrame(this.frame);
    else { this.running = false; c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.canvas.width, this.canvas.height); }
  };

  /** A bolt from the first point of `pts` along the polyline to its end: a white core travelling at
   *  speed, a jagged fringe in neon pink and neon blue fading out behind it. Reduced motion: the
   *  whole bolt at once, fading where it stands. */
  bolt(pts: Pt[], reduce: boolean) {
    const L: number[] = [0];
    for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    const total = L[L.length - 1], SPEED = 1700, CORE = 46, TAIL = 170;
    const at = (s: number): [number, number, number, number] => {      // point and unit normal at arc length s
      s = Math.max(0, Math.min(total, s));
      let i = 1; while (i < L.length - 1 && L[i] < s) i++;
      const a = pts[i - 1], b = pts[i], seg = L[i] - L[i - 1] || 1, u = (s - L[i - 1]) / seg;
      const dx = (b[0] - a[0]) / seg, dy = (b[1] - a[1]) / seg;
      return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, -dy, dx];
    };
    const strand = (c: CanvasRenderingContext2D, s0: number, s1: number, colour: string, amp: number, alpha: (s: number) => number) => {
      let prev: Pt | null = null;
      for (let s = s0; s <= s1; s += 8) {
        const [x, y, nx, ny] = at(s), j = (Math.random() - 0.5) * 2 * amp, p: Pt = [x + nx * j, y + ny * j];
        if (prev) { c.globalAlpha = Math.max(0, Math.min(1, alpha(s))); c.strokeStyle = colour; c.beginPath(); c.moveTo(prev[0], prev[1]); c.lineTo(p[0], p[1]); c.stroke(); }
        prev = p;
      }
    };
    const core = (c: CanvasRenderingContext2D, s0: number, s1: number, a: number) => {
      c.globalAlpha = a; c.strokeStyle = "#effdff"; c.lineWidth = 2; c.shadowColor = "#3ff0ff"; c.shadowBlur = 6; c.lineCap = "round";
      c.beginPath(); for (let s = s0; s <= s1; s += 6) { const [x, y] = at(s); if (s === s0) c.moveTo(x, y); else c.lineTo(x, y); } c.stroke();
      c.shadowBlur = 0;
    };
    this.add((c, t) => {
      if (reduce) {
        const a = 1 - t / 0.6;
        if (a <= 0) return false;
        c.lineWidth = 1.2; strand(c, 0, total, "#ff3fd2", 5, () => a); strand(c, 0, total, "#44b8ff", 5, () => a); core(c, 0, total, a);
        return true;
      }
      const head = t * SPEED;
      if (head - TAIL > total) return false;
      const s1 = Math.min(head, total), s0 = Math.max(0, head - TAIL);
      const fade = (s: number) => (s - (head - TAIL)) / TAIL;
      c.lineWidth = 1.3; strand(c, s0, s1, "#ff3fd2", 6, fade); strand(c, s0, s1, "#44b8ff", 6, (s) => fade(s) * 0.9);
      if (head - CORE < total) core(c, Math.max(0, head - CORE), s1, 1);
      c.globalAlpha = 1;
      return true;
    });
  }

  /** The ring: blue spreading from `c` out to `max` (or back in from it), at `speed` px/s; each of
   *  `sparks` (petal heads) glows with blue lightning for a moment as the ring crosses it. */
  ring(o: { c: Pt; speed: number; max: number; dir: 1 | -1; sparks: Pt[] }) {
    const T = o.max / o.speed, hits = o.sparks.map((p) => {
      const d = Math.hypot(p[0] - o.c[0], p[1] - o.c[1]);
      return { p, t: o.dir > 0 ? d / o.speed : (o.max - d) / o.speed };
    });
    this.add((c, t) => {
      if (t > T + 0.45) return false;
      if (t <= T) {
        const r = o.dir > 0 ? t * o.speed : o.max - t * o.speed;
        c.globalAlpha = 0.22; c.strokeStyle = "#44b8ff"; c.lineWidth = 12; c.beginPath(); c.arc(o.c[0], o.c[1], Math.max(0, r), 0, 6.2832); c.stroke();
        c.globalAlpha = 0.95; c.strokeStyle = "#bfe6ff"; c.lineWidth = 1.6; c.beginPath(); c.arc(o.c[0], o.c[1], Math.max(0, r), 0, 6.2832); c.stroke();
      }
      c.lineWidth = 1.1;
      for (const h of hits) {
        const u = (t - h.t) / 0.35;
        if (u < 0 || u > 1) continue;
        c.globalAlpha = 1 - u; c.strokeStyle = Math.random() < 0.5 ? "#7fd0ff" : "#e8f7ff";
        c.beginPath();
        const rr = 6 + Math.random() * 3;
        for (let k = 0; k <= 9; k++) { const a = (k / 9) * 6.2832, j = rr + (Math.random() - 0.5) * 4, x = h.p[0] + Math.cos(a) * j, y = h.p[1] + Math.sin(a) * j; if (k) c.lineTo(x, y); else c.moveTo(x, y); }
        c.stroke();
      }
      c.globalAlpha = 1;
      return true;
    });
    return T;
  }
}
