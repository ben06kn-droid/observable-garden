// The docs page's glass bubbles: a few large translucent bubbles drifting slowly up the margin beside the
// text, in soft blue, white and fresh green. Few, large and calm, of clearly different sizes, never
// a swarm. (Eight, so five to eight are in view.) They keep to their lane (the empty ground right of the text) and never pass behind words: where
// the cue or the footer rises into the lane, they fade before it.
//
// They are glass, in the run page's language (src/hero.ts): what is behind each (the sky) is seen through
// it gently magnified toward the middle, each colour channel bent a little differently; a thin bright rim;
// a soft highlight toward a light at the upper left; a faint tint and a brighter edge (fresnel).
//
// They drift up at a slow idle with a little sway, and respond to the scroll's speed (quicker up while the
// page scrolls down, easing back). The cursor's wake (src/cursorwake.ts), in this page's form: where the
// cursor passes, a bubble nearby wobbles like soft glass (a damped squash, set going when the wake takes in
// each stretch of the cursor's path, with its delay and its dose) and its rim splits into fringes of the
// theme's --wake-tone and --wake-fringe where the fluid flows, then settles. Cursor movement only.
//
// One WebGL canvas fixed over the lane. Reduced motion: the bubbles drawn once, still, and no wake. Paused
// while the page is hidden. No lane (a phone): no bubbles.
import { followPointer, rgb, STILL, Wake, WAKE_GLSL, wakeColours, wakeWanted, type RGB } from "./cursorwake";

export interface Lane { x0: number; x1: number; top: number; bottom: number }   // viewport px
export interface BubblesOptions {
  /** the lane, viewport px; null: no bubbles (a phone) */
  lane: () => Lane | null;
  reduce: boolean;
}
interface Bubble {
  r: number; x: number; y: number; vy: number; sway: number; period: number; ph: number; tint: number;
  px: number; vx: number;                          // a soft sideways push, and its velocity
  a2: number; v2: number; t2: number; a3: number; v3: number; t3: number;   // the wobble: two lobes, three lobes
}

const N = 8, SIZES = [0.07, 0.09, 0.115, 0.14, 0.17, 0.205, 0.245, 0.29];   // radius as a fraction of the lane's width
const MAXN = 8;
const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr, uX0, uScroll; uniform vec2 uView;
uniform vec3 uSky0, uSky1, uSky2, uTone, uFringe;
uniform vec4 uB[${MAXN}]; uniform vec4 uW[${MAXN}]; uniform vec3 uT[${MAXN}]; uniform int uN;
uniform sampler2D uVel; uniform float uWake;
out vec4 o;
${WAKE_GLSL}
// the page's sky at a page y (the stops of docs.css)
vec3 sky(float y) { return y < 640.0 ? mix(uSky0, uSky1, clamp(y / 640.0, 0.0, 1.0)) : mix(uSky1, uSky2, clamp((y - 640.0) / 760.0, 0.0, 1.0)); }
void main() {
  vec2 vp = vec2(uX0 + gl_FragCoord.x / uDpr, (uSize.y * uDpr - gl_FragCoord.y) / uDpr);   // viewport px
  float s = 0.0;
  if (uWake > 0.0) s = smoothstep(1.5, 12.0, length(wakeFlow(uVel, vp, uView)));   // only where the wake runs strong: near the cursor
  vec4 acc = vec4(0.0);
  for (int i = 0; i < ${MAXN}; i++) {
    if (i >= uN) break;
    vec2 c = uB[i].xy; float R = uB[i].z, vis = uB[i].w;
    vec2 q = vp - c; float L = length(q);
    if (vis <= 0.0 || L > R * 1.3 + 4.0) continue;
    float th = atan(q.y, q.x);
    float rr = R * (1.0 + uW[i].x * cos(2.0 * (th - uW[i].y)) + uW[i].z * cos(3.0 * (th - uW[i].w)));
    float d = L - rr;                                   // px from the rim, negative inside
    float off = 1.3 * s;                                // the fringes' split, in the wake
    if (d > 2.0 + off) continue;
    float u = clamp(L / rr, 0.0, 1.0);
    // the sky behind, magnified toward the middle, each channel a little differently
    vec3 bg;
    for (int k = 0; k < 3; k++) { float m = 0.6 + 0.4 * u * u + (float(k) - 1.0) * 0.035 * u * u; bg[k] = sky(c.y + q.y * m + uScroll)[k]; }
    vec3 col = mix(bg, uT[i], 0.16 + 0.34 * pow(u, 3.0));
    col = mix(col, vec3(1.0), 0.45 * pow(u, 7.0));     // a brighter edge
    // a soft highlight toward the light at the upper left
    vec2 hq = q / rr - vec2(-0.36, -0.42); float ca = 0.8, sa = 0.6;
    vec2 hr = vec2(ca * hq.x + sa * hq.y, -sa * hq.x + ca * hq.y);
    col = mix(col, vec3(1.0), 0.8 * exp(-(hr.x * hr.x / 0.05 + hr.y * hr.y / 0.012)));
    // and a fainter one opposite, low right
    vec2 lq = q / rr - vec2(0.42, 0.5); col = mix(col, vec3(1.0), 0.25 * exp(-dot(lq, lq) / 0.012));
    // the thin bright rim
    float rim = exp(-(d + 0.9) * (d + 0.9) / 0.9);
    col = mix(col, vec3(0.42, 0.62, 0.78), 0.32 * exp(-(d - 0.2) * (d - 0.2) / 0.5));   // a faint darker line just outside it
    col = mix(col, vec3(1.0), 0.95 * rim);
    float a = 1.0 - smoothstep(0.2, 1.2, d);
    // in the wake: the rim split, the tone just outside and the fringe just inside
    if (s > 0.0) {
      float ro = exp(-(d + 0.9 - off) * (d + 0.9 - off) / 0.6), ri = exp(-(d + 0.9 + off) * (d + 0.9 + off) / 0.6);
      col = mix(col, uTone, clamp(0.55 * ro * s, 0.0, 1.0)); col = mix(col, uFringe, clamp(0.5 * ri * s, 0.0, 1.0));
      a = max(a, 0.55 * ro * s);
    }
    a *= vis;
    acc = vec4(col * a, a) + acc * (1.0 - a);
  }
  o = acc;
}`;

export class Bubbles {
  readonly canvas = document.createElement("canvas");
  private o: BubblesOptions; private gl: WebGL2RenderingContext | null = null; private prog: WebGLProgram | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {}; private wake: Wake | null = null;
  private b: Bubble[] = []; private lane: Lane | null = null; private dpr = 1;
  private raf = 0; private last = 0; private t = 0; private boost = 0; private scrollV = 0; private lastY = 0; private lastYT = 0;
  private sky: RGB[] = []; private tone: RGB = [0.2, 0.6, 0.9]; private fringe: RGB = [0.25, 0.75, 0.45]; private tints: RGB[] = [];
  private seed = 7;
  private rnd = () => { this.seed = (this.seed * 16807) % 2147483647; return (this.seed - 1) / 2147483646; };

  constructor(host: HTMLElement, o: BubblesOptions) {
    this.o = o;
    this.canvas.className = "bubbles"; this.canvas.setAttribute("aria-hidden", "true");
    const gl = this.canvas.getContext("webgl2", { antialias: false, alpha: true, premultipliedAlpha: true }); if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    this.gl = gl; this.prog = p; gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uX0", "uScroll", "uView", "uSky0", "uSky1", "uSky2", "uTone", "uFringe", "uB", "uW", "uT", "uN", "uVel", "uWake"]) this.u[n] = gl.getUniformLocation(p, n);
    host.append(this.canvas);
    // the cursor's wake: only with a fine pointer that hovers and motion allowed
    if (!o.reduce && wakeWanted()) {
      const w = new Wake(gl);
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
    const cs = getComputedStyle(document.documentElement);
    this.sky = ["--sky-0", "--sky-1", "--sky-2"].map((k) => rgb(cs.getPropertyValue(k) || "#eef6fd"));
    this.tints = [rgb("#bfe1f9"), rgb("#dceefe"), rgb("#c6ecd3"), rgb("#cfe7fb")];   // soft blue, pale sky, fresh green (never white: it would vanish on the white sky)
    const w = wakeColours(document.documentElement); this.tone = w.tone; this.fringe = w.fringe;
    const lane = this.o.lane();
    this.lane = lane && lane.x1 - lane.x0 >= 160 ? lane : null;
    this.canvas.hidden = !this.lane;
    if (!this.lane) return;
    const L = this.lane, W = L.x1 - L.x0;
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.canvas.width = Math.round(W * this.dpr); this.canvas.height = Math.round(innerHeight * this.dpr);
    this.canvas.style.setProperty("--x", `${L.x0}px`); this.canvas.style.setProperty("--w", `${W}px`);
    this.wake?.resize(innerWidth, innerHeight);
    // the fluid's passes compiled in idle time, not on the cursor's first stroke
    const wk = this.wake; if (wk) (typeof requestIdleCallback === "function" ? requestIdleCallback : (f: () => void) => setTimeout(f, 300))(() => wk.warm(innerHeight));
    const first = !this.b.length;
    if (first) for (let i = 0; i < N; i++) this.b.push(this.spawn(i, true));
    for (const b of this.b) { b.r = SIZES[this.b.indexOf(b)] * W; b.x = Math.max(L.x0 + b.r + 6, Math.min(L.x1 - b.r - 10, b.x)); }
    if (this.o.reduce) this.draw(); else this.kick();
  }

  private spawn(i: number, anywhere: boolean): Bubble {
    const L = this.lane ?? { x0: 0, x1: 300, top: 0, bottom: innerHeight }, W = L.x1 - L.x0, r = SIZES[i] * W;
    // a place clear of the others: of a few tries, the one with the most room around it (spread through the
    // lane's height at first; later each re-enters below it)
    let best = { x: 0, y: 0, room: -Infinity };
    for (let k = 0; k < 40; k++) {
      const y = anywhere ? L.top + r * 0.5 + this.rnd() * (L.bottom - L.top + 80) : L.bottom + r + 20 + this.rnd() * 160;
      const m = r * 1.13 + 16, x = L.x0 + m + this.rnd() * Math.max(0, W - 2 * m);
      let room = Infinity;
      for (const o of this.b) if (o !== this.b[i]) room = Math.min(room, Math.hypot(o.x - x, o.y - y) - o.r - r);
      if (room > best.room) best = { x, y, room };
    }
    const { x, y } = best;
    return { r, x, y, vy: 16 - 18 * SIZES[i] + this.rnd() * 4,
      sway: 5 + this.rnd() * 9, period: 10 + this.rnd() * 8, ph: this.rnd() * 6.28, tint: i % 4, px: 0, vx: 0, a2: 0, v2: 0, t2: 0, a3: 0, v3: 0, t3: 0 };
  }

  /** the wake took in a stretch of the cursor's path at (x, y): bubbles near it wobble, and give a little */
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

  private kick() { if (this.raf || !this.gl || !this.lane || this.o.reduce || document.hidden) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    this.raf = 0;
    if (document.hidden || !this.lane) return;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now; this.t += dt;
    this.step(dt);
    this.wake?.step(dt, innerHeight);
    this.draw();
    this.kick();                                                   // the bubbles always drift
  };

  private step(dt: number) {
    const L = this.lane!;
    // the scroll's speed: quicker up while the page scrolls down (slower, or down, while it scrolls up), easing back
    this.scrollV *= Math.exp(-dt / 0.25);
    const target = Math.max(-90, Math.min(160, this.scrollV * 0.22));
    this.boost += (target - this.boost) * (1 - Math.exp(-dt / (Math.abs(target) > Math.abs(this.boost) ? 0.12 : 0.6)));
    for (let i = 0; i < this.b.length; i++) {
      const b = this.b[i];
      b.y -= (b.vy + this.boost * (0.6 + SIZES[i])) * dt;
      // the soft push springs back; the wobble rings and settles (about a second)
      b.vx += (-b.px * 2.2 - b.vx * 2.4) * dt; b.px += b.vx * dt;
      const w2 = 2 * Math.PI * 1.6, w3 = 2 * Math.PI * 2.3, z = 0.22;
      b.v2 += (-w2 * w2 * b.a2 - 2 * z * w2 * b.v2) * dt; b.a2 = Math.max(-0.055, Math.min(0.055, b.a2 + b.v2 * dt));
      b.v3 += (-w3 * w3 * b.a3 - 2 * z * w3 * b.v3) * dt; b.a3 = Math.max(-0.03, Math.min(0.03, b.a3 + b.v3 * dt));
      if (b.y + b.r < L.top - 30) { const nb = this.spawn(i, false); Object.assign(b, nb); }
      else if (b.y - b.r > L.bottom + 260) { const nb = this.spawn(i, false); Object.assign(b, nb, { y: L.top - nb.r - 20 }); }
    }
  }

  private draw() {
    const gl = this.gl, L = this.lane; if (!gl || !this.prog || !L) return;
    // where the cue or the footer rises into the lane, the bubbles fade before it
    const bottom = Math.min(L.bottom, this.blocker());
    const B: number[] = [], Wv: number[] = [], T: number[] = [];
    for (let i = 0; i < this.b.length; i++) {
      // never past the lane's edges, sway, push and wobble included
      const b = this.b[i], m = b.r * 1.13 + 2, x = Math.max(L.x0 + m, Math.min(L.x1 - m, b.x + b.px + b.sway * Math.sin(this.t * 6.28 / b.period + b.ph)));
      const fadeLow = Math.max(0, Math.min(1, (bottom - (b.y + b.r)) / (0.6 * b.r) + 1)), fadeTop = Math.max(0, Math.min(1, (b.y - L.top) / (0.8 * b.r)));
      B.push(x, b.y, b.r, Math.min(fadeLow, fadeTop)); Wv.push(b.a2, b.t2, b.a3, b.t3); T.push(...this.tints[b.tint]);
    }
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.uniform2f(this.u.uSize, L.x1 - L.x0, innerHeight); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uX0, L.x0); gl.uniform1f(this.u.uScroll, scrollY);
    gl.uniform2f(this.u.uView, innerWidth, innerHeight);
    gl.uniform3f(this.u.uSky0, ...this.sky[0]); gl.uniform3f(this.u.uSky1, ...this.sky[1]); gl.uniform3f(this.u.uSky2, ...this.sky[2]);
    gl.uniform3f(this.u.uTone, ...this.tone); gl.uniform3f(this.u.uFringe, ...this.fringe);
    gl.uniform4fv(this.u.uB, B); gl.uniform4fv(this.u.uW, Wv); gl.uniform3fv(this.u.uT, T); gl.uniform1i(this.u.uN, this.b.length);
    const w = this.wake, on = !!w?.ready && w.idle < STILL;
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(this.u.uVel, 0); gl.uniform1f(this.u.uWake, on ? 1 : 0);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  private blockers: HTMLElement[] = [];
  /** the top of whatever full-width block (the cue, the footer) has risen into view, viewport px */
  watch(...els: (HTMLElement | null)[]) { this.blockers = els.filter((e): e is HTMLElement => !!e); }
  private blocker() { let y = Infinity; for (const e of this.blockers) { const t = e.getBoundingClientRect().top; if (t < innerHeight) y = Math.min(y, t - 24); } return y; }
}
