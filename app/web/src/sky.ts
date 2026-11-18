// The docs page's sky: one canvas behind everything, fixed to the viewport, drawing the ground, its light,
// the cursor's tail and the glass bubbles. It sits behind and beside the content and never styles it.
//
// - The ground: a muted vertical gradient (slate blue, soft sky, grey aqua, sage, pale green-white), three
//   large soft light fields (white upper right, cyan centre left, green lower right; each about 70vh across
//   at 15%, drifting about 15vh along its own slow loop of 30 to 45 s), and a static fine grain at 2%.
// - The cursor's tail, in the run page's form (src/cursorwake.ts: its fluid read as a glossy trace, a pale
//   core with cyan on one edge of the flow and green on the other), toned down for this page: 60% of the
//   force, 60% of the swirl, its own motion at 75%, its core #E6EEF4 at 85% in place of white, and 20% more
//   life. It lies on the ground, so it shows in the margins and faintly through the reading sheet, and is
//   never over text.
// - The bubbles: five glass bubbles of clearly different sizes drifting slowly up the margin right of the
//   text (three or four in view), never behind words, fading before the cue and the footer, and fading out
//   over 600 ms as each reaches the top of its path, to rise again from below. Each is softly blue or green
//   (never two of a colour side by side as they appear): a body tint deepening along its lower edge, a bright
//   rim tinted to its colour, a white highlight toward the upper left, a thin soap-film band inside the rim,
//   and the sky behind seen magnified, each channel bent a little differently (the run page's glass). Where
//   the cursor passes over or near one, its rim is framed with thin blue and green fringes and it wobbles
//   softly, settling in about a second.
//
// Phone: the ground and its light (the fields at half size), no tail, no bubbles. Reduced motion: drawn once,
// still. Paused while the page is hidden.
import { followPointer, rgb, Wake, WAKE_GLSL, wakeColours, wakeWanted, type RGB } from "./cursorwake";

/** viewport px; `under`: how far the bubbles may drift in under the pane at its left (behind the glass, short of the text) */
export interface Lane { x0: number; x1: number; top: number; bottom: number; under?: number }
export interface SkyOptions {
  /** the bubbles' lane, viewport px; null: no bubbles (a phone) */
  lane: () => Lane | null;
  /** a phone: the light fields at half size, no tail */
  small: () => boolean;
  /** the area behind the text (viewport px): the tail fades before it, so it shows only through the glass's edges */
  text?: () => { x: number; y: number; w: number; h: number } | null;
  reduce: boolean;
}
interface Bubble {
  i: number; r: number; x: number; y: number; vy: number; sway: number; period: number; ph: number; tint: number;
  px: number; vx: number;                          // a soft sideways push, and its velocity
  a2: number; v2: number; t2: number; a3: number; v3: number; t3: number;   // the wobble: two lobes, three lobes
  out: number;                                     // fading out at the top of its path, since this time (s); 0: not
}

const SIZES = [0.115, 0.17, 0.205, 0.245, 0.29];   // radius as a fraction of the lane's width (three or four in view)
const N = SIZES.length, MAXN = 8, OUT = 0.6;
// the docs page's tail: the run page's, toned down (force 60%, swirl 60%, its own motion 75%, life +20%)
const TAIL = { force: 0.6, curl: 22 * 0.6, flow: 0.55 * 0.75, fade: 0.45 * 1.2 };
const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr, uTime;
uniform vec3 uG[5]; uniform vec4 uF[3]; uniform vec3 uFC[3];   // the gradient's stops; the light fields (x, y, radius, alpha) and colours
uniform vec3 uTone, uFringe;
uniform vec4 uB[${MAXN}]; uniform vec4 uW[${MAXN}]; uniform vec4 uT[${MAXN}]; uniform int uN;   // bubbles: (x, y, r, shown), wobble, (kind: 0 blue, 1 green)
uniform sampler2D uVel; uniform float uWake; uniform vec4 uText;   // the area behind the text (x, y, w, h)
out vec4 o;
${WAKE_GLSL}
vec3 gradientAt(float v) {
  if (v < 0.35) return mix(uG[0], uG[1], v / 0.35);
  if (v < 0.65) return mix(uG[1], uG[2], (v - 0.35) / 0.30);
  if (v < 0.88) return mix(uG[2], uG[3], (v - 0.65) / 0.23);
  return mix(uG[3], uG[4], clamp((v - 0.88) / 0.12, 0.0, 1.0));
}
// the ground without the tail: the gradient and the light fields (viewport css px)
vec3 sky(vec2 p) {
  vec3 c = gradientAt(clamp(p.y / uSize.y, 0.0, 1.0));
  for (int i = 0; i < 3; i++) { vec2 q = (p - uF[i].xy) / uF[i].z; c = mix(c, uFC[i], uF[i].w * exp(-2.6 * dot(q, q))); }
  return c;
}
float grain(vec2 f) { return fract(sin(dot(floor(f), vec2(12.9898, 78.233))) * 43758.5453); }
vec2 flowAt(vec2 p) { return wakeFlow(uVel, p, uSize); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;   // viewport css px
  vec3 col = sky(p);
  // the cursor's tail, in the run page's form: the fluid read as a glossy trace; a pale core (#E6EEF4 at 85%),
  // cyan on one edge of the flow and green on the other
  const vec3 PALE = vec3(0.902, 0.933, 0.957);
  vec2 d = vec2(0.0); float s = 0.0;
  // never behind the text: it fades out over 24px before the text's area
  vec2 tq = max(uText.xy - p, p - (uText.xy + uText.zw)); float away = smoothstep(0.0, 24.0, max(tq.x, tq.y));
  if (uWake > 0.0 && away > 0.0) {
    d = flowAt(p) * away; s = wakeStrength(d);
    if (s > 0.0) {
      vec2 gr = vec2(length(flowAt(p + vec2(6.0, 0.0))) - length(flowAt(p - vec2(6.0, 0.0))),
                     length(flowAt(p + vec2(0.0, 6.0))) - length(flowAt(p - vec2(0.0, 6.0))));
      float st = smoothstep(0.25, 9.0, length(d));
      float core = st * st;
      float slope = smoothstep(0.4, 5.0, length(gr)) * (1.0 - core);
      float side = d.x * gr.y - d.y * gr.x;                 // which edge of the flow this is
      col = mix(col, PALE, 0.85 * 0.62 * core);
      col = mix(col, side > 0.0 ? uTone : uFringe, clamp(0.75 * slope * st * 1.6, 0.0, 0.8));
      col = wakeTrace(col, gr, s, 1.0, PALE, vec3(0.02, 0.2, 0.42), uTone, 1.0).rgb;   // run's gloss: a highlight, a shade, a hairline rim
    }
  }
  // the bubbles, glass over the ground and the tail
  for (int i = 0; i < ${MAXN}; i++) {
    if (i >= uN) break;
    vec2 c = uB[i].xy; float R = uB[i].z, vis = uB[i].w;
    vec2 q = p - c; float L = length(q);
    if (vis <= 0.0 || L > R * 1.2 + 4.0) continue;
    float th = atan(q.y, q.x);
    float rr = R * (1.0 + uW[i].x * cos(2.0 * (th - uW[i].y)) + uW[i].z * cos(3.0 * (th - uW[i].w)));
    float dd = L - rr;
    float off = 1.8 * s;                                    // the fringes' split, where the cursor's wake runs
    if (dd > 2.0 + off) continue;
    float u = clamp(L / rr, 0.0, 1.0);
    bool green = uT[i].x > 0.5;
    vec3 body = green ? vec3(0.435, 0.843, 0.604) : vec3(0.353, 0.663, 0.941);   // #6FD79A, #5AA9F0
    vec3 deep = green ? vec3(0.247, 0.722, 0.467) : vec3(0.184, 0.498, 0.816);   // #3FB877, #2F7FD0
    vec3 rimC = green ? vec3(0.812, 0.984, 0.867) : vec3(0.749, 0.894, 1.0);     // #CFFBDD, #BFE4FF
    // the sky behind, magnified toward the middle, each channel a little differently
    vec3 bg;
    for (int k = 0; k < 3; k++) { float m = 0.62 + 0.38 * u * u + (float(k) - 1.0) * 0.035 * u * u; bg[k] = sky(c + q * m)[k]; }
    // the body: softly blue or green, 30% deepening to 36% along its lower edge
    float low = smoothstep(0.1, 0.95, q.y / rr);
    vec3 g = mix(bg, mix(body, deep, low), mix(0.30, 0.36, low));
    // the soap film: a thin band inside the rim; blue: cyan to blue to violet, green: aqua to green to lime
    float film = smoothstep(0.86, 0.9, u) * (1.0 - smoothstep(0.975, 1.0, u));
    float h = fract(th / 6.2832 + 0.5 + uTime * 0.01);
    vec3 f0 = green ? vec3(0.32, 0.95, 0.9) : vec3(0.25, 0.88, 1.0), f1 = green ? vec3(0.28, 0.9, 0.42) : vec3(0.27, 0.52, 1.0), f2 = green ? vec3(0.76, 0.98, 0.33) : vec3(0.72, 0.56, 1.0);
    vec3 fc = h < 0.333 ? mix(f0, f1, h * 3.0) : h < 0.667 ? mix(f1, f2, h * 3.0 - 1.0) : mix(f2, f0, h * 3.0 - 2.0);
    g = mix(g, fc, 0.42 * film);
    g = mix(g, vec3(1.0), 0.3 * pow(u, 8.0));
    // a bright highlight toward the upper left, a fainter one low right
    vec2 hq = q / rr - vec2(-0.36, -0.42); vec2 hr = vec2(0.8 * hq.x + 0.6 * hq.y, -0.6 * hq.x + 0.8 * hq.y);
    g = mix(g, vec3(1.0), 0.92 * exp(-(hr.x * hr.x / 0.05 + hr.y * hr.y / 0.012)));
    vec2 lq = q / rr - vec2(0.42, 0.5); g = mix(g, vec3(1.0), 0.3 * exp(-dot(lq, lq) / 0.012));
    // the rim: bright, tinted to the bubble
    g = mix(g, rimC, 0.9 * exp(-(dd + 0.9) * (dd + 0.9) / 0.9));
    float a = 1.0 - smoothstep(0.2, 1.2, dd);
    // where the cursor passes over or near it: an aura on the rim, the tone just outside and the fringe colour
    // just inside (the first docs version's hover, in this page's colours)
    if (s > 0.0) {
      float ro = exp(-(dd + 0.9 - off) * (dd + 0.9 - off) / 1.1), ri = exp(-(dd + 0.9 + off) * (dd + 0.9 + off) / 1.1);
      g = mix(g, uTone, clamp(0.8 * ro * s, 0.0, 1.0)); g = mix(g, uFringe, clamp(0.8 * ri * s, 0.0, 1.0));
      a = max(a, 0.85 * ro * s);
    }
    col = mix(col, g, a * vis);
  }
  col = mix(col, vec3(grain(gl_FragCoord.xy)), 0.02);       // a static fine grain
  o = vec4(col, 1.0);
}`;

export class Sky {
  readonly canvas = document.createElement("canvas");
  private o: SkyOptions; private gl: WebGL2RenderingContext | null = null; private prog: WebGLProgram | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {}; private wake: Wake | null = null;
  private b: Bubble[] = []; private lane: Lane | null = null; private dpr = 1;
  private raf = 0; private last = 0; private t = 0; private boost = 0; private scrollV = 0; private lastY = 0; private lastYT = 0;
  private stops: RGB[] = []; private tone: RGB = [0.25, 0.88, 1]; private fringe: RGB = [0.42, 0.95, 0.61];
  private seed = 7;
  private rnd = () => { this.seed = (this.seed * 16807) % 2147483647; return (this.seed - 1) / 2147483646; };

  constructor(host: HTMLElement, o: SkyOptions) {
    this.o = o;
    this.canvas.className = "sky"; this.canvas.setAttribute("aria-hidden", "true");
    const gl = this.canvas.getContext("webgl2", { antialias: false, alpha: false }); if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) { if (import.meta.env.DEV) console.error("sky: the shader did not compile"); return; }
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    this.gl = gl; this.prog = p; gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uTime", "uG", "uF", "uFC", "uTone", "uFringe", "uB", "uW", "uT", "uN", "uVel", "uWake", "uText"]) this.u[n] = gl.getUniformLocation(p, n);
    host.prepend(this.canvas);
    // the cursor's tail: only with a fine pointer that hovers, motion allowed, not on a phone
    if (!o.reduce && wakeWanted() && !o.small()) {
      const w = new Wake(gl, TAIL);
      if (w.supported) {
        this.wake = w;
        w.onPush = (x, y, vx, vy, dose) => this.nudge(x, y, vx, vy, dose);
        followPointer((x, y) => { w.move(x, y); this.kick(); }, () => w.lift(), () => !document.hidden);
      }
    }
    this.lastY = scrollY; this.lastYT = performance.now();
    addEventListener("scroll", () => {
      const now = performance.now(), dt = Math.max(8, now - this.lastYT);
      this.scrollV = 0.6 * this.scrollV + 0.4 * ((scrollY - this.lastY) / dt) * 1000; this.lastY = scrollY; this.lastYT = now;
      if (o.reduce) this.draw(); else this.kick();
    }, { passive: true });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) this.kick(); });
    this.layout();
  }

  /** sizes, colours and the lane: after a layout change */
  layout() {
    const gl = this.gl; if (!gl) return;
    const cs = getComputedStyle(this.canvas);   // its theme where it lies (the page, or on the one page its backdrop)
    this.stops = ["--g0", "--g1", "--g2", "--g3", "--g4"].map((k) => rgb(cs.getPropertyValue(k) || "#4f8fc0"));
    const w = wakeColours(document.documentElement); this.tone = w.tone; this.fringe = w.fringe;
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.canvas.width = Math.round(innerWidth * this.dpr); this.canvas.height = Math.round(innerHeight * this.dpr);
    this.wake?.resize(innerWidth, innerHeight);
    // the fluid's passes compiled in idle time, not on the cursor's first stroke
    const wk = this.wake; if (wk) (typeof requestIdleCallback === "function" ? requestIdleCallback : (f: () => void) => setTimeout(f, 300))(() => wk.warm(innerHeight));
    const lane = this.o.lane();
    this.lane = lane && lane.x1 - lane.x0 >= 160 ? lane : null;
    if (this.lane) {
      const L = this.lane, W = L.x1 - L.x0;
      if (!this.b.length) {
        for (let i = 0; i < N; i++) this.b.push(this.spawn(i, true));
        // half of each, alternating down the lane as they first appear
        [...this.b].sort((a, b) => a.y - b.y).forEach((b, k) => { b.tint = k % 2; });
      }
      for (const b of this.b) { b.r = SIZES[b.i] * W; b.x = Math.max(L.x0 - (L.under ?? 0) + b.r + 6, Math.min(L.x1 - b.r - 10, b.x)); }
    }
    if (this.o.reduce) this.draw(); else this.kick();
  }

  private spawn(i: number, anywhere: boolean, tint?: number): Bubble {
    const L = this.lane ?? { x0: 0, x1: 300, top: 0, bottom: innerHeight }, W = L.x1 - L.x0, r = SIZES[i] * W;
    // a place clear of the others: of a few tries, the one with the most room around it (spread through the
    // lane's height at first; later each re-enters below it)
    let best = { x: 0, y: 0, room: -Infinity };
    for (let k = 0; k < 40; k++) {
      const y = anywhere ? L.top + r * 1.2 + this.rnd() * (L.bottom - L.top + 160) : L.bottom + r + 20 + this.rnd() * 220;
      // two of them (the smallest and the middle) rise close to the pane, so one is often seen passing under its edge
      const m = r * 1.13 + 16, u0 = L.x0 - (L.under ?? 0), near = (i === 0 || i === 2) && !!L.under;
      const x = near ? u0 + r * 0.9 + this.rnd() * r * 0.6 : u0 + m + this.rnd() * Math.max(0, W + (L.under ?? 0) - 2 * m);
      let room = Infinity;
      for (const o of this.b) if (o.i !== i) room = Math.min(room, Math.hypot(o.x - x, o.y - y) - o.r - r);
      if (room > best.room) best = { x, y, room };
    }
    const { x, y } = best;
    // its colour: kept when it rises again; at first, the other one from its nearest neighbour
    if (tint === undefined) {
      tint = i % 2; let nearest = Infinity;
      for (const o of this.b) if (o.i !== i) { const dd = Math.hypot(o.x - x, o.y - y); if (dd < nearest) { nearest = dd; tint = 1 - o.tint; } }
    }
    return { i, r, x, y, vy: 16 - 18 * SIZES[i] + this.rnd() * 4, sway: 5 + this.rnd() * 9, period: 10 + this.rnd() * 8, ph: this.rnd() * 6.28, tint,
      px: 0, vx: 0, a2: 0, v2: 0, t2: 0, a3: 0, v3: 0, t3: 0, out: 0 };
  }

  /** the wake took in a stretch of the cursor's path at (x, y): bubbles near it wobble softly, and give a little */
  private nudge(x: number, y: number, vx: number, vy: number, dose: number) {
    for (const b of this.b) {
      const cx = b.x + b.px, d = Math.hypot(x - cx, y - b.y) - b.r;
      if (d > 70) continue;
      const k = dose * (1 - Math.max(0, d) / 70);
      b.v2 += 0.45 * k; b.t2 = Math.atan2(vy, vx);
      b.v3 += 0.22 * k; b.t3 = Math.atan2(y - b.y, x - cx);
      b.vx += Math.max(-60, Math.min(60, vx * 0.05 * k));
    }
  }

  private active = true;
  /** the one-page site: draw only while this section's backdrop can be seen (src/onepage/boot.ts onBackdrop) */
  setActive(on: boolean) { if (this.active === on) return; this.active = on; if (on) { if (this.o.reduce) this.draw(); else this.kick(); } }
  private kick() { if (this.raf || !this.gl || this.o.reduce || document.hidden || !this.active) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    this.raf = 0;
    if (document.hidden || !this.active) return;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now; this.t += dt;
    if (this.lane) this.step(dt);
    this.wake?.step(dt, innerHeight);
    this.draw();
    this.kick();                                                   // the light and the bubbles always drift
  };

  private step(dt: number) {
    const L = this.lane!, SLOW = 0.6;                          // the drift at 60% of its first speed
    // the scroll's speed: quicker up while the page scrolls down (slower, or down, while it scrolls up), easing back
    this.scrollV *= Math.exp(-dt / 0.25);
    const target = Math.max(-90, Math.min(160, this.scrollV * 0.22));
    this.boost += (target - this.boost) * (1 - Math.exp(-dt / (Math.abs(target) > Math.abs(this.boost) ? 0.12 : 0.6)));
    for (const b of this.b) {
      b.y -= (b.vy * SLOW + this.boost * (0.6 + SIZES[b.i])) * dt;
      // the soft push springs back; the wobble rings and settles (about a second)
      b.vx += (-b.px * 2.2 - b.vx * 2.4) * dt; b.px += b.vx * dt;
      const w2 = 2 * Math.PI * 1.6, w3 = 2 * Math.PI * 2.3, z = 0.22;
      b.v2 += (-w2 * w2 * b.a2 - 2 * z * w2 * b.v2) * dt; b.a2 = Math.max(-0.055, Math.min(0.055, b.a2 + b.v2 * dt));
      b.v3 += (-w3 * w3 * b.a3 - 2 * z * w3 * b.v3) * dt; b.a3 = Math.max(-0.03, Math.min(0.03, b.a3 + b.v3 * dt));
      // at the top of its path it fades out over 600 ms, then rises again from below
      if (!b.out && b.y - b.r <= L.top + 6) b.out = this.t;
      if (b.out && this.t - b.out >= OUT) Object.assign(b, this.spawn(b.i, false, b.tint));
      else if (b.y - b.r > L.bottom + 300) Object.assign(b, this.spawn(b.i, false, b.tint), { y: L.top + b.r * 1.5 });
    }
  }

  private draw() {
    const gl = this.gl; if (!gl || !this.prog) return;
    const W = innerWidth, H = innerHeight, t = this.t, small = this.o.small();
    // the light fields: about 70vh across (half on a phone), at 15%, each on its own slow loop of 30 to 45 s,
    // about 15vh wide, eased in and out (a sine is already eased)
    const R = (small ? 0.175 : 0.35) * H, A = 0.075 * H, F: number[] = [];
    const field = (x: number, y: number, T: number, ph: number) => F.push(x + A * Math.sin(6.2832 * t / T + ph), y + A * Math.sin(2 * 6.2832 * t / T + ph * 1.7) * 0.6, R, 0.15);
    field(W * 0.82, H * 0.14, 38, 0.3); field(W * 0.16, H * 0.5, 31, 2.1); field(W * 0.84, H * 0.86, 44, 4.0);
    const B: number[] = [], Wv: number[] = [], T: number[] = [];
    const L = this.lane;
    if (L) {
      // where the cue or the footer rises into the lane, the bubbles fade before it
      const bottom = Math.min(L.bottom, this.blocker());
      for (const b of this.b) {
        const m = b.r * 1.13 + 2, x = Math.max(L.x0 - (L.under ?? 0) + m, Math.min(L.x1 - m, b.x + b.px + b.sway * Math.sin(t * 6.28 / b.period + b.ph)));
        let vis = Math.max(0, Math.min(1, (bottom - (b.y + b.r)) / (0.6 * b.r) + 1));
        if (b.out) vis *= Math.max(0, 1 - (t - b.out) / OUT);
        B.push(x, b.y, b.r, vis); Wv.push(b.a2, b.t2, b.a3, b.t3); T.push(b.tint, 0, 0, 0);
      }
    }
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.uniform2f(this.u.uSize, W, H); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uTime, t);
    gl.uniform3fv(this.u.uG, this.stops.flat());
    gl.uniform4fv(this.u.uF, F); gl.uniform3fv(this.u.uFC, [1, 1, 1, 0x38 / 255, 0xe1 / 255, 1, 0x6b / 255, 0xf2 / 255, 0x9b / 255]);
    gl.uniform3f(this.u.uTone, ...this.tone); gl.uniform3f(this.u.uFringe, ...this.fringe);
    if (B.length) { gl.uniform4fv(this.u.uB, B); gl.uniform4fv(this.u.uW, Wv); gl.uniform4fv(this.u.uT, T); }
    gl.uniform1i(this.u.uN, B.length / 4);
    const w = this.wake, on = !!w?.ready && w.idle < w.still;
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(this.u.uVel, 0); gl.uniform1f(this.u.uWake, on ? 1 : 0);
    const tx = on ? this.o.text?.() : null; gl.uniform4f(this.u.uText, tx?.x ?? -1e5, tx?.y ?? -1e5, tx?.w ?? 0, tx?.h ?? 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  private blockers: HTMLElement[] = [];
  /** the top of whatever full-width block (the cue, the footer) has risen into view, viewport px */
  watch(...els: (HTMLElement | null)[]) { this.blockers = els.filter((e): e is HTMLElement => !!e); }
  private blocker() { let y = Infinity; for (const e of this.blockers) { const t = e.getBoundingClientRect().top; if (t < innerHeight) y = Math.min(y, t - 24); } return y; }
}
