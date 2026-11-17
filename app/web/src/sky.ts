// The docs page's sky: one canvas behind everything, fixed to the viewport, drawing the ground, its light,
// the cursor's tail and the glass bubbles.
//
// - The ground: a vivid vertical gradient (deep azure, sky blue, aqua, mint, pale green-white), three large
//   soft light fields (white upper right, cyan centre left, green lower right; each about 70vh across at 35%,
//   drifting about 15vh along its own slow loop of 30 to 45 s), a static fine grain at 3%, and the whole of it
//   brightening and dimming by 3% on an 8 s cycle.
// - The cursor's tail (src/cursorwake.ts, in this page's calmer tuning): one smooth ribbon about 110px wide
//   laid along the cursor's smoothed path, holding for about 2 s and fading over the last 600 ms, thinning
//   rather than spreading as it ages; a dull pale core (#DCE8F0 at 70%), cyan on one edge and green on the
//   other. It lies on the ground, so it shows at full strength in the margins and faintly through the reading
//   sheet, and is never over text. The fluid under it is pushed gently (40% of the run page's force, capped),
//   swirls little (30%), drifts at half speed and settles quickly.
// - The bubbles: eight glass bubbles of clearly different sizes drifting slowly up the margin right of the
//   text, never behind words, fading before the cue and the footer. Each is clearly blue or green (half of
//   each, never two of a colour side by side as they appear): a body tint deepening along its lower edge (a
//   blue one low on the aqua sky, or a green one high on the blue, lets less of the ground through so its own
//   colour carries), a bright rim tinted to its colour, a white highlight toward the upper left, a thin
//   soap-film band inside the rim, and the sky behind seen magnified, each channel bent a little differently
//   (the run page's glass). Where the tail crosses one, it wobbles gently and its rim takes the tail's colours.
// - The pop (450 ms), on a click or tap, or when a bubble reaches the top of its path: it swells to 108% and
//   its rim goes white (0-60 ms); the film breaks from the point clicked (the top, on its own), the hole's edge
//   running round both ways, the highlight gone at 80 ms and the tint by 140 ms; then the rim flies apart in
//   10 to 14 short arcs, 8 to 12 droplets of its colour shoot out and curve down, and a thin ring spreads to
//   140% of its radius, all gone by 450 ms. Neighbours within one and a half radii are pushed away and
//   wobble. A new bubble of the same colour rises from the bottom 1.5 to 3 s later.
//
// Phone: the ground and its light (the fields at half size), no tail, no bubbles. Reduced motion: drawn once,
// still; a clicked bubble fades out over 150 ms. Paused while the page is hidden.
import { followPointer, rgb, Wake, WAKE_GLSL, wakeColours, wakeWanted, type RGB } from "./cursorwake";

export interface Lane { x0: number; x1: number; top: number; bottom: number }   // viewport px
export interface SkyOptions {
  /** the bubbles' lane, viewport px; null: no bubbles (a phone) */
  lane: () => Lane | null;
  /** a phone: the light fields at half size, no tail */
  small: () => boolean;
  reduce: boolean;
}
interface Pop { t0: number; ang: number; seed: number; burst: boolean; drops: { a: number; v: number; s: number }[] }
interface Bubble {
  i: number; r: number; x: number; y: number; vy: number; sway: number; period: number; ph: number; tint: number;
  px: number; vx: number;                          // a soft sideways push, and its velocity
  a2: number; v2: number; t2: number; a3: number; v3: number; t3: number;   // the wobble: two lobes, three lobes
  pop: Pop | null; gone: number;                   // popping; or gone, rising again at this time (s)
  fade: number;                                    // reduced motion: fading out, from this time (s)
}

const N = 8, SIZES = [0.07, 0.09, 0.115, 0.14, 0.17, 0.205, 0.245, 0.29];   // radius as a fraction of the lane's width
const MAXN = 8, DROPS = 12, POP = 0.45;
// the docs page's tail: calmer than the run page's (DESIGN.md 3, the cursor's wake)
const TAIL = { force: 0.4, maxSpeed: 900, smooth: 120, flow: 0.275, curl: 6.6, fade: 0.22, dye: 2.5, ribbon: { life: 2.0, width: 16, flow: 0.06 } };
const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr, uTime, uPulse;
uniform vec3 uG[5]; uniform vec4 uF[3]; uniform vec3 uFC[3];   // the gradient's stops; the light fields (x, y, radius, alpha) and colours
uniform vec3 uTone, uFringe;
uniform vec4 uB[${MAXN}]; uniform vec4 uW[${MAXN}]; uniform vec4 uT[${MAXN}]; uniform int uN;   // bubbles: (x, y, r, shown), wobble, (kind, pop ms or -1, pop angle, seed)
uniform vec4 uD[${MAXN * DROPS}];                 // each popping bubble's droplets: (x, y, size, alpha)
uniform sampler2D uRib; uniform float uTail;      // the tail's ribbon: (life, side)
out vec4 o;
${WAKE_GLSL}
const float PI = 3.14159265;
vec3 gradientAt(float v) {
  if (v < 0.35) return mix(uG[0], uG[1], v / 0.35);
  if (v < 0.65) return mix(uG[1], uG[2], (v - 0.35) / 0.30);
  if (v < 0.88) return mix(uG[2], uG[3], (v - 0.65) / 0.23);
  return mix(uG[3], uG[4], clamp((v - 0.88) / 0.12, 0.0, 1.0));
}
// the ground without the tail: the gradient, the light fields, the pulse (viewport css px)
vec3 sky(vec2 p) {
  vec3 c = gradientAt(clamp(p.y / uSize.y, 0.0, 1.0));
  for (int i = 0; i < 3; i++) { vec2 q = (p - uF[i].xy) / uF[i].z; c = mix(c, uFC[i], uF[i].w * exp(-2.6 * dot(q, q))); }
  return c * uPulse;
}
float grain(vec2 f) { return fract(sin(dot(floor(f), vec2(12.9898, 78.233))) * 43758.5453); }
float hash(float n) { return fract(sin(n * 91.345) * 47453.5453); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;   // viewport css px
  vec3 col = sky(p);
  // the tail: a calm ribbon, a dull pale core, cyan on one edge and green on the other
  float ta = 0.0, side = 0.0;
  if (uTail > 0.0) {
    vec2 rb = texture(uRib, vec2(p.x, uSize.y - p.y) / uSize).rg;
    ta = smoothstep(0.03, 0.2, rb.x); side = rb.y;
    float edge = ta * (1.0 - smoothstep(0.2, 0.5, rb.x));
    col = mix(col, vec3(0.863, 0.910, 0.941), 0.7 * ta);
    col = mix(col, side > 0.5 ? uTone : uFringe, 0.48 * edge);
  }
  // the bubbles, glass over the ground and the tail
  for (int i = 0; i < ${MAXN}; i++) {
    if (i >= uN) break;
    vec2 c = uB[i].xy; float R = uB[i].z, vis = uB[i].w, pt = uT[i].y;
    vec2 q = p - c; float L = length(q);
    if (vis <= 0.0 || L > R * (pt >= 0.0 ? 2.3 : 1.2) + 6.0) continue;
    bool green = uT[i].x > 0.5;
    vec3 body = green ? vec3(0.247, 0.878, 0.478) : vec3(0.184, 0.608, 1.0);     // #3FE07A, #2F9BFF
    vec3 deep = green ? vec3(0.071, 0.722, 0.353) : vec3(0.039, 0.435, 0.878);   // #12B85A, #0A6FE0
    vec3 rimC = green ? vec3(0.812, 0.984, 0.867) : vec3(0.749, 0.894, 1.0);     // #CFFBDD, #BFE4FF
    float th = atan(q.y, q.x);
    // after 140 ms of a pop: the rim in flying arcs, a spreading ring, droplets
    if (pt >= 140.0) {
      float k3 = clamp((pt - 140.0) / 310.0, 0.0, 1.0), ease = 1.0 - (1.0 - k3) * (1.0 - k3);
      float n = 10.0 + floor(uT[i].w * 5.0), seg = 2.0 * PI / n, ai = floor((th + PI) / seg), lc = fract((th + PI) / seg);
      float out_ = R * (0.3 + 0.3 * hash(ai + uT[i].w * 17.0)) * ease, half_ = 0.25 * (1.0 - 0.5 * k3);
      float inArc = 1.0 - smoothstep(half_ - 0.04, half_ + 0.02, abs(lc - 0.5));
      float ad = abs(L - (R + out_)), thick = 1.4 * (1.0 - 0.7 * k3) + 0.3;
      float arc = inArc * (1.0 - smoothstep(thick * 0.5, thick, ad)) * (1.0 - k3);
      col = mix(col, rimC, 0.95 * arc * vis);
      float kr = clamp((pt - 140.0) / 160.0, 0.0, 1.0);
      float ring = (1.0 - smoothstep(0.4, 1.2, abs(L - R * (1.0 + 0.4 * kr)))) * (1.0 - kr) * 0.6;
      col = mix(col, vec3(1.0), ring * vis);
      for (int k = 0; k < ${DROPS}; k++) {
        vec4 dr = uD[i * ${DROPS} + k];
        if (dr.w <= 0.0) continue;
        float dd = length(p - dr.xy);
        col = mix(col, mix(body, vec3(1.0), 0.25), dr.w * (1.0 - smoothstep(dr.z * 0.5 - 0.6, dr.z * 0.5 + 0.6, dd)) * vis);
      }
      continue;
    }
    float rr = R * (1.0 + uW[i].x * cos(2.0 * (th - uW[i].y)) + uW[i].z * cos(3.0 * (th - uW[i].w)));
    float dd = L - rr, off = 1.3 * ta;
    if (dd > 2.0 + off) continue;
    float u = clamp(L / rr, 0.0, 1.0);
    // the pop's first 140 ms: the rim whitens; the film breaks from its angle, the hole running round both ways
    float white = pt >= 0.0 ? clamp(pt / 60.0, 0.0, 1.0) : 0.0;
    float hole = 0.0, tintGone = 0.0, hl = 1.0, running = 0.0;
    if (pt >= 60.0) {
      float k2 = clamp((pt - 60.0) / 80.0, 0.0, 1.0), open_ = PI * k2 * k2 * (3.0 - 2.0 * k2);
      float da = abs(mod(th - uT[i].z + PI, 2.0 * PI) - PI);
      hole = 1.0 - smoothstep(open_ - 0.12, open_ + 0.02, da);
      float run_ = (da - open_) * R / 3.0; running = exp(-run_ * run_) * (1.0 - k2 * k2);   // the hole's edge, running round
      tintGone = k2;
    }
    if (pt >= 80.0) hl = 0.0;
    // the sky behind, magnified toward the middle, each channel a little differently
    vec3 bg;
    for (int k = 0; k < 3; k++) { float m = 0.62 + 0.38 * u * u + (float(k) - 1.0) * 0.035 * u * u; bg[k] = sky(c + q * m)[k]; }
    // the body: clearly blue or green, deepening along its lower edge; a blue bubble low on the aqua and mint,
    // or a green one high on the deep blue, lets up to half less of the ground through, so its own colour carries
    float low = smoothstep(0.1, 0.95, q.y / rr), v = c.y / uSize.y;
    float clash = green ? 1.0 - smoothstep(0.2, 0.45, v) : smoothstep(0.5, 0.75, v);
    float ground = (1.0 - mix(green ? 0.50 : 0.48, 0.55, low)) * (1.0 - 0.5 * clash);
    vec3 g = mix(bg, mix(body, deep, low), (1.0 - ground) * (1.0 - tintGone));
    // the soap film: a thin band inside the rim; blue: cyan to blue to violet, green: aqua to green to lime
    float film = smoothstep(0.86, 0.9, u) * (1.0 - smoothstep(0.975, 1.0, u));
    float h = fract(th / 6.2832 + 0.5 + uTime * 0.01);
    vec3 f0 = green ? vec3(0.32, 0.95, 0.9) : vec3(0.25, 0.88, 1.0), f1 = green ? vec3(0.28, 0.9, 0.42) : vec3(0.27, 0.52, 1.0), f2 = green ? vec3(0.76, 0.98, 0.33) : vec3(0.72, 0.56, 1.0);
    vec3 fc = h < 0.333 ? mix(f0, f1, h * 3.0) : h < 0.667 ? mix(f1, f2, h * 3.0 - 1.0) : mix(f2, f0, h * 3.0 - 2.0);
    g = mix(g, fc, 0.42 * film * (1.0 - tintGone));
    g = mix(g, vec3(1.0), 0.3 * pow(u, 8.0));
    // a bright highlight toward the upper left, a fainter one low right
    vec2 hq = q / rr - vec2(-0.36, -0.42); vec2 hr = vec2(0.8 * hq.x + 0.6 * hq.y, -0.6 * hq.x + 0.8 * hq.y);
    g = mix(g, vec3(1.0), hl * 0.92 * exp(-(hr.x * hr.x / 0.05 + hr.y * hr.y / 0.012)));
    vec2 lq = q / rr - vec2(0.42, 0.5); g = mix(g, vec3(1.0), hl * 0.3 * exp(-dot(lq, lq) / 0.012));
    // the rim: bright, tinted to the bubble, going white as it pops
    g = mix(g, mix(rimC, vec3(1.0), white), (0.9 + 0.1 * white) * exp(-(dd + 0.9) * (dd + 0.9) / 0.9));
    float a = 1.0 - smoothstep(0.2, 1.2, dd);
    // in the tail: the rim takes its colours
    if (ta > 0.0) {
      float ro = exp(-(dd + 0.9 - off) * (dd + 0.9 - off) / 0.6);
      g = mix(g, side > 0.5 ? uTone : uFringe, clamp(0.5 * ro * ta, 0.0, 1.0)); a = max(a, 0.5 * ro * ta);
    }
    // the hole: nothing of the film where it has broken; its edge, running round, bright
    a *= 1.0 - hole;
    col = mix(col, g, a * vis);
    col = mix(col, vec3(1.0), 0.9 * running * exp(-(dd + 0.9) * (dd + 0.9) / 2.0) * vis);
  }
  col = mix(col, vec3(grain(gl_FragCoord.xy)), 0.03);       // a static fine grain
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
    for (const n of ["uSize", "uDpr", "uTime", "uPulse", "uG", "uF", "uFC", "uTone", "uFringe", "uB", "uW", "uT", "uN", "uD", "uRib", "uTail"]) this.u[n] = gl.getUniformLocation(p, n);
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
    // a bubble pops on a click or a tap; the cursor shows it can be clicked
    window.addEventListener("click", (e: MouseEvent) => this.click(e), { passive: true });
    window.addEventListener("pointermove", (e: PointerEvent) => { if (e.pointerType !== "touch") document.documentElement.classList.toggle("over-bubble", !!this.hit(e)); }, { passive: true });
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
    const cs = getComputedStyle(document.documentElement);
    this.stops = ["--g0", "--g1", "--g2", "--g3", "--g4"].map((k) => rgb(cs.getPropertyValue(k) || "#1e9bf0"));
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
      for (const b of this.b) { b.r = SIZES[b.i] * W; b.x = Math.max(L.x0 + b.r + 6, Math.min(L.x1 - b.r - 10, b.x)); }
    }
    if (this.o.reduce) this.draw(); else this.kick();
  }

  private spawn(i: number, anywhere: boolean, tint?: number): Bubble {
    const L = this.lane ?? { x0: 0, x1: 300, top: 0, bottom: innerHeight }, W = L.x1 - L.x0, r = SIZES[i] * W;
    // a place clear of the others: of a few tries, the one with the most room around it (spread through the
    // lane's height at first; later each re-enters below it)
    let best = { x: 0, y: 0, room: -Infinity };
    for (let k = 0; k < 40; k++) {
      const y = anywhere ? L.top + r * 1.2 + this.rnd() * (L.bottom - L.top + 80) : L.bottom + r + 20 + this.rnd() * 160;
      const m = r * 1.13 + 16, x = L.x0 + m + this.rnd() * Math.max(0, W - 2 * m);
      let room = Infinity;
      for (const o of this.b) if (o.i !== i && !o.gone) room = Math.min(room, Math.hypot(o.x - x, o.y - y) - o.r - r);
      if (room > best.room) best = { x, y, room };
    }
    const { x, y } = best;
    // its colour: given (a bubble rising again after a pop keeps its colour), or the other one from its
    // nearest neighbour, so no two of a colour appear side by side
    if (tint === undefined) {
      tint = i % 2; let nearest = Infinity;
      for (const o of this.b) if (o.i !== i && !o.gone) { const dd = Math.hypot(o.x - x, o.y - y); if (dd < nearest) { nearest = dd; tint = 1 - o.tint; } }
    }
    return { i, r, x, y, vy: 16 - 18 * SIZES[i] + this.rnd() * 4, sway: 5 + this.rnd() * 9, period: 10 + this.rnd() * 8, ph: this.rnd() * 6.28, tint,
      px: 0, vx: 0, a2: 0, v2: 0, t2: 0, a3: 0, v3: 0, t3: 0, pop: null, gone: 0, fade: 0 };
  }

  /** the wake took in a stretch of the cursor's path at (x, y): bubbles near it wobble gently, and give a little */
  private nudge(x: number, y: number, vx: number, vy: number, dose: number) {
    for (const b of this.b) {
      if (b.pop || b.gone) continue;
      const cx = b.x + b.px, d = Math.hypot(x - cx, y - b.y) - b.r;
      if (d > 70) continue;
      const k = dose * (1 - Math.max(0, d) / 70);
      b.v2 += 0.225 * k; b.t2 = Math.atan2(vy, vx);
      b.v3 += 0.11 * k; b.t3 = Math.atan2(y - b.y, x - cx);
      b.vx += Math.max(-30, Math.min(30, vx * 0.025 * k));
    }
  }

  // ---------- popping
  private centre(b: Bubble) { const L = this.lane!, m = b.r * 1.13 + 2; return { x: Math.max(L.x0 + m, Math.min(L.x1 - m, b.x + b.px + b.sway * Math.sin(this.t * 6.28 / b.period + b.ph))), y: b.y }; }
  /** the bubble under a viewport point, if any */
  private hit(e: { clientX: number; clientY: number }): Bubble | null {
    if (!this.lane) return null;
    for (const b of [...this.b].reverse()) { if (b.pop || b.gone || b.fade) continue; const c = this.centre(b); if (Math.hypot(e.clientX - c.x, e.clientY - c.y) < b.r) return b; }
    return null;
  }
  private click(e: MouseEvent) {
    // only on the empty ground: a click on text, a link, a control or a panel is its own
    if ((e.target as Element | null)?.closest?.("a, button, input, select, textarea, label, summary, details, p, li, td, th, pre, h1, h2, h3, .sheet, .toc, .top, .glass")) return;
    const b = this.hit(e); if (!b) return;
    if (this.o.reduce) { b.fade = performance.now() / 1000; this.fadeLoop(); return; }
    const c = this.centre(b);
    this.popNow(b, Math.atan2(e.clientY - c.y, e.clientX - c.x));
  }
  private popNow(b: Bubble, ang: number) {
    const drops = Array.from({ length: 8 + Math.floor(this.rnd() * 5) }, () => ({ a: this.rnd() * 6.2832, v: 0.7 + this.rnd() * 1.1, s: 2 + this.rnd() * 2 }));
    b.pop = { t0: this.t, ang, seed: this.rnd(), burst: false, drops };
    this.kick();
  }
  // reduced motion: a clicked bubble fades out over 150 ms, and nothing else moves
  private fadeLoop = () => { this.draw(); if (this.b.some((b) => b.fade && performance.now() / 1000 - b.fade < 0.16)) requestAnimationFrame(this.fadeLoop); };

  private kick() { if (this.raf || !this.gl || this.o.reduce || document.hidden) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    this.raf = 0;
    if (document.hidden) return;
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
      if (b.gone) { if (this.t >= b.gone) Object.assign(b, this.spawn(b.i, false, b.tint)); continue; }   // a new one of its colour rises
      if (b.pop) {
        const pt = this.t - b.pop.t0;
        if (!b.pop.burst && pt >= 0.14) {                          // the burst: neighbours pushed away, wobbling
          b.pop.burst = true;
          for (const o of this.b) {
            if (o === b || o.pop || o.gone) continue;
            const dx = o.x - b.x, dy = o.y - b.y, d = Math.hypot(dx, dy);
            if (d - o.r > 1.5 * b.r) continue;
            o.vx += (dx / (d || 1)) * 70; o.y += (dy / (d || 1)) * 4; o.v2 += 0.35; o.t2 = Math.atan2(dy, dx);
          }
        }
        if (pt >= POP) { b.pop = null; b.gone = this.t + 1.5 + this.rnd() * 1.5; }
        continue;
      }
      b.y -= (b.vy * SLOW + this.boost * (0.6 + SIZES[b.i])) * dt;
      // the soft push springs back; the wobble rings and settles (about a second)
      b.vx += (-b.px * 2.2 - b.vx * 2.4) * dt; b.px += b.vx * dt;
      const w2 = 2 * Math.PI * 1.6, w3 = 2 * Math.PI * 2.3, z = 0.22;
      b.v2 += (-w2 * w2 * b.a2 - 2 * z * w2 * b.v2) * dt; b.a2 = Math.max(-0.055, Math.min(0.055, b.a2 + b.v2 * dt));
      b.v3 += (-w3 * w3 * b.a3 - 2 * z * w3 * b.v3) * dt; b.a3 = Math.max(-0.03, Math.min(0.03, b.a3 + b.v3 * dt));
      // at the top of its path it pops, from the top
      if (b.y - b.r <= L.top + 6) this.popNow(b, -Math.PI / 2);
      else if (b.y - b.r > L.bottom + 260) Object.assign(b, this.spawn(b.i, false, b.tint), { y: L.top + b.r * 1.5 });
    }
  }

  private draw() {
    const gl = this.gl; if (!gl || !this.prog) return;
    const W = innerWidth, H = innerHeight, t = this.t, small = this.o.small();
    // the light fields: about 70vh across (half on a phone), each on its own slow loop of 30 to 45 s, about
    // 15vh wide, eased in and out (a sine is already eased)
    const R = (small ? 0.175 : 0.35) * H, A = 0.075 * H, F: number[] = [];
    const field = (x: number, y: number, T: number, ph: number) => F.push(x + A * Math.sin(6.2832 * t / T + ph), y + A * Math.sin(2 * 6.2832 * t / T + ph * 1.7) * 0.6, R, 0.35);
    field(W * 0.82, H * 0.14, 38, 0.3); field(W * 0.16, H * 0.5, 31, 2.1); field(W * 0.84, H * 0.86, 44, 4.0);
    const B: number[] = [], Wv: number[] = [], T: number[] = [], D = new Float32Array(MAXN * DROPS * 4);
    const L = this.lane;
    if (L) {
      // where the cue or the footer rises into the lane, the bubbles fade before it
      const bottom = Math.min(L.bottom, this.blocker()), now = performance.now() / 1000;
      this.b.forEach((b, j) => {
        const c = this.centre(b);
        let vis = b.gone ? 0 : Math.max(0, Math.min(1, (bottom - (b.y + b.r)) / (0.6 * b.r) + 1));
        if (b.fade) vis *= Math.max(0, 1 - (now - b.fade) / 0.15);
        let r = b.r, pt = -1;
        if (b.pop) {
          pt = (t - b.pop.t0) * 1000;
          r = b.r * (1 + 0.08 * Math.min(1, pt / 60) * (2 - Math.min(1, pt / 60)));   // swells to 108% (eased)
          if (pt >= 140) {                                                               // droplets: out, curving down, fading
            const s = (pt - 140) / 1000, k = Math.min(1, (pt - 140) / 310);
            b.pop.drops.forEach((d, n) => {
              const dist = b.r * 1.08 + d.v * b.r * 1.6 * (1 - Math.pow(1 - k, 2)) * 0.6;
              D.set([c.x + Math.cos(d.a) * dist, c.y + Math.sin(d.a) * dist + 140 * s * s * b.r / 60, d.s, 1 - k], (j * DROPS + n) * 4);
            });
          }
        }
        B.push(c.x, c.y, r, vis); Wv.push(b.a2, b.t2, b.a3, b.t3); T.push(b.tint, pt, b.pop?.ang ?? 0, b.pop?.seed ?? 0);
      });
    }
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.uniform2f(this.u.uSize, W, H); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uTime, t);
    gl.uniform1f(this.u.uPulse, 1 + 0.03 * Math.sin(6.2832 * t / 8));          // the whole ground, ±3% over 8 s
    gl.uniform3fv(this.u.uG, this.stops.flat());
    gl.uniform4fv(this.u.uF, F); gl.uniform3fv(this.u.uFC, [1, 1, 1, 0x38 / 255, 0xe1 / 255, 1, 0x6b / 255, 0xf2 / 255, 0x9b / 255]);
    gl.uniform3f(this.u.uTone, ...this.tone); gl.uniform3f(this.u.uFringe, ...this.fringe);
    if (B.length) { gl.uniform4fv(this.u.uB, B); gl.uniform4fv(this.u.uW, Wv); gl.uniform4fv(this.u.uT, T); gl.uniform4fv(this.u.uD, D); }
    gl.uniform1i(this.u.uN, B.length / 4);
    const w = this.wake, on = !!w?.ready && w.idle < w.still;
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, on ? w!.dyeTexture : null); gl.uniform1i(this.u.uRib, 0); gl.uniform1f(this.u.uTail, on ? 1 : 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  private blockers: HTMLElement[] = [];
  /** the top of whatever full-width block (the cue, the footer) has risen into view, viewport px */
  watch(...els: (HTMLElement | null)[]) { this.blockers = els.filter((e): e is HTMLElement => !!e); }
  private blocker() { let y = Infinity; for (const e of this.blockers) { const t = e.getBoundingClientRect().top; if (t < innerHeight) y = Math.min(y, t - 24); } return y; }
}
