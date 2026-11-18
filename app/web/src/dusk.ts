// The Sancho page's dusk: one canvas behind everything, fixed to the viewport, on the docs page's pattern (src/sky.ts):
// a plain, rich backdrop, one object in the margin, the shared cursor tail. It sits behind the content and never styles it.
//
// - The backdrop: a deep red sunset as one vertical gradient (--d0 at the top to --d3 at the horizon, 72% of the height;
//   --d4 directly below it to --d5 at the foot), one soft glow where the sun has just set (--glow at 30%, about 60vh
//   across, centred on the horizon at 70% across; a third as strong on the ground), and a hairline along the horizon
//   (--glow at 35%). No other shapes.
// - The windmill, the page's one object: the approved ink drawing (eleven brush strokes: leaning strokes for the body, a
//   cap, the ground, a door; four crossed strokes for the sails; the hub), in --mill, standing on the horizon in the right
//   margin, a silhouette against the glow. A turn in 14 s; in 3 s while the tail passes within 200px of its hub, easing
//   back over about 4 s.
// - Heat, subtle: the horizon line, the glow and the windmill's lower half waver by 1.5px sideways, rising slowly (and
//   0.6px up and down, without which a level line cannot be seen to waver). Nothing is drawn to show it.
// - The cursor's tail (src/cursorwake.ts), in the run page's form with the docs page's toned-down fluid: a glossy trace
//   (a --wake-core highlight, a --wake-shade shade, a --wake-fringe hairline rim) laid over the backdrop, the horizon and
//   the windmill alike; it distorts none of them. It fades out before the reading sheet's text.
// - Light and scroll: as the page scrolls the glow sinks by 6vh and the whole backdrop darkens by 15%. Nothing else.
//
// Phone: a band at the top of the page (the gradient, the glow, a small windmill), no tail. Reduced motion: drawn once,
// still. Paused while hidden or off screen.
import { followPointer, rgb, Wake, WAKE_GLSL, wakeColours, wakeWanted, type RGB } from "./cursorwake";

export const HORIZON = 0.72;
const STOPS = [0, 0.3, 0.55, 0.72, 0.73, 1];
const GLOW = { x: 0.7, w: 0.6, a: 0.3, line: 0.35, sink: 0.06 };   // centre (of the width), width and sink (of the height)
const MILL = { x: 0.84, h: 0.16 };                               // foot (of the width, on the horizon), height (of the height)
const HUB = 0.56;                                                // the hub's height, of the windmill's
const START_ANGLE = 0.35;                                         // the sails' angle on the first frame
const TURN_REST = 14, TURN_WIND = 3, EASE_BACK = 4, NEAR_MILL = 200;
const HEAT = 1.5, RISE = 10;                                     // px; px/s
// the docs page's tail: the run page's, toned down (force 60%, swirl 60%, its own motion 75%, life +20%)
const TAIL = { force: 0.6, curl: 22 * 0.6, flow: 0.55 * 0.75, fade: 0.45 * 1.2 };

// ---------- the windmill's strokes, in its own frame (units of its height, y up from its foot; sails about the hub)
interface Stroke { a: [number, number]; c: [number, number]; b: [number, number]; w0: number; w1: number }
const BODY: Stroke[] = [
  { a: [-0.15, 0.0], c: [-0.135, 0.27], b: [-0.085, 0.53], w0: 0.03, w1: 0.012 },     // the left wall, leaning in
  { a: [0.142, 0.015], c: [0.125, 0.29], b: [0.08, 0.52], w0: 0.026, w1: 0.009 },      // the right wall
  { a: [-0.04, 0.05], c: [-0.035, 0.22], b: [-0.012, 0.4], w0: 0.012, w1: 0.004 },    // a dry stroke down the body
  { a: [-0.115, 0.525], c: [0.0, 0.65], b: [0.112, 0.53], w0: 0.028, w1: 0.012 },     // the cap
  { a: [-0.25, 0.0], c: [0.02, -0.014], b: [0.27, 0.008], w0: 0.02, w1: 0.006 },      // the ground
  { a: [0.012, 0.0], c: [-0.008, 0.06], b: [0.016, 0.11], w0: 0.026, w1: 0.016 },     // the door, one dab
  { a: [-0.02, HUB - 0.012], c: [0.0, HUB + 0.012], b: [0.018, HUB - 0.006], w0: 0.03, w1: 0.022 },   // the hub
];
const SAIL: Stroke = { a: [0.0, 0.04], c: [0.03, 0.22], b: [0.0, 0.42], w0: 0.034, w1: 0.011 };
const NS = BODY.length + 4, SEG = 7;

const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr, uTime, uDark, uMove;
uniform vec3 uG[6]; uniform float uGS[6];
uniform vec3 uGlow; uniform vec4 uGlowP;          // (x, y, radius, alpha)
uniform float uLineA;
uniform vec3 uMill; uniform vec3 uInk;            // foot x, foot y, height; ink
uniform vec4 uS[${NS * (SEG + 1)}]; uniform vec4 uK[${NS}]; uniform vec4 uBox;
uniform vec3 uTone, uFringe, uCore, uShade;
uniform sampler2D uVel; uniform float uWake; uniform vec4 uText;
out vec4 o;
${WAKE_GLSL}
float h3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vnoise(vec3 x) {
  vec3 i = floor(x), f = fract(x); f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
vec3 gradientAt(float v) {
  vec3 c = uG[0];
  for (int i = 1; i < 6; i++) c = mix(c, uG[i], clamp((v - uGS[i - 1]) / max(1e-4, uGS[i] - uGS[i - 1]), 0.0, 1.0));
  return c;
}
// the approved ink: each stroke thick to thin, a blunt uneven start, dry-brush gaps opening toward its end
float ink(vec2 q) {
  if (q.x < uBox.x || q.x > uBox.z || q.y < uBox.y || q.y > uBox.w) return 0.0;
  float cov = 0.0;
  for (int k = 0; k < ${NS}; k++) {
    vec4 K = uK[k];
    float best = 1e9, s = 0.0, side = 0.0;
    for (int j = 0; j < ${SEG}; j++) {
      vec4 A = uS[k * ${SEG + 1} + j], B = uS[k * ${SEG + 1} + j + 1];
      vec2 ab = B.xy - A.xy, aq = q - A.xy;
      float h = clamp(dot(aq, ab) / max(dot(ab, ab), 1e-4), 0.0, 1.0);
      vec2 d = aq - ab * h; float dd = dot(d, d);
      if (dd < best) { best = dd; s = mix(A.z, B.z, h); side = sign(ab.x * aq.y - ab.y * aq.x); }
    }
    float d = sqrt(best), sl = s * K.z;
    float w = mix(K.x, K.y, pow(s, 0.75));
    w *= mix(0.55, 1.0, smoothstep(0.0, 0.06, s)) * (1.0 - 0.5 * smoothstep(0.82, 1.0, s));
    w *= 0.82 + 0.36 * vnoise(vec3(sl / 7.0, K.w, 0.5));
    float r = 0.5 * w;
    if (d > r + 1.0) continue;
    float a = clamp((r - d) * uDpr + 0.5, 0.0, 1.0);
    a *= step(s, 0.995 - 0.05 * vnoise(vec3(side * d / max(w, 0.5) * 3.0, K.w, 2.0))) * step(0.004, s);
    float across = side * d / max(w, 0.6);
    float b = vnoise(vec3(sl / 26.0, across * 3.2 + K.w * 3.1, K.w));
    float dry = 0.14 + 0.5 * smoothstep(0.45, 1.0, s);
    a *= smoothstep(dry - 0.05, dry + 0.05, b);
    cov = max(cov, a);
  }
  return cov;
}
// the backdrop at q: the gradient, the glow, the hairline, the windmill
vec3 backdrop(vec2 q) {
  float hor = uGS[3] * uSize.y;
  vec3 c = gradientAt(q.y / uSize.y);
  vec2 g = (q - uGlowP.xy) / uGlowP.z;
  c = mix(c, uGlow, uGlowP.w * exp(-2.4 * dot(g, g)) * (q.y > hor ? 0.35 : 1.0));
  c = mix(c, uGlow, uLineA * clamp(1.0 - abs(q.y - hor) * uDpr + 0.5, 0.0, 1.0));
  c *= uDark;
  return mix(c, uInk, ink(q));
}
vec2 flowAt(vec2 p) { return wakeFlow(uVel, p, uSize); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  float t = uTime, hor = uGS[3] * uSize.y;
  // heat: the horizon, the glow's lower part and the windmill's lower half waver, rising slowly
  vec2 q = p;
  float band = smoothstep(hor - 0.55 * uMill.z, hor - 0.05 * uMill.z, p.y) * (1.0 - smoothstep(hor + 4.0, hor + 0.04 * uSize.y, p.y));
  if (band > 0.0 && uMove > 0.0) {
    vec3 n = vec3(p.x / 140.0 + 0.02 * t, (p.y + ${RISE.toFixed(1)} * t) / 50.0, t * 0.25);
    q += band * vec2(${HEAT.toFixed(1)} * (vnoise(n) * 2.0 - 1.0) * 1.6, 0.6 * (vnoise(n + 5.3) * 2.0 - 1.0) * 1.6);
  }
  // the tail, in the run page's form: a glossy trace (a highlight toward an upper-left light, a soft shade, a hairline
  // rim) laid over everything. It distorts nothing: the horizon and the windmill stay where they are, under it.
  vec3 col = backdrop(q);
  vec2 tq = max(uText.xy - p, p - (uText.xy + uText.zw)); float away = smoothstep(0.0, 24.0, max(tq.x, tq.y));
  if (uWake > 0.0 && away > 0.0) {
    vec2 d = flowAt(p) * away; float s = wakeStrength(d);
    if (s > 0.0) {
      vec2 gr = vec2(length(flowAt(p + vec2(6.0, 0.0))) - length(flowAt(p - vec2(6.0, 0.0))),
                     length(flowAt(p + vec2(0.0, 6.0))) - length(flowAt(p - vec2(0.0, 6.0))));
      col = wakeTrace(col, gr, s, 1.0, uCore, uShade, uFringe, 1.0).rgb;
    }
  }
  o = vec4(col, 1.0);
}`;

export interface DuskOptions {
  reduce: boolean;
  /** a phone: a band at the top, no tail */
  small: () => boolean;
  /** the area behind the text (viewport px): the tail fades before it */
  text?: () => { x: number; y: number; w: number; h: number } | null;
  /** how far through the page the reader is, 0-1 (the one-page site: through the Sancho section); else the document */
  progress?: () => number;
}

export class Dusk {
  readonly canvas = document.createElement("canvas");
  private o: DuskOptions; private gl: WebGL2RenderingContext | null = null; private prog: WebGLProgram | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {}; private wake: Wake | null = null;
  private W = 1; private H = 1; private dpr = 1; private raf = 0; private last = 0; private t = 0; private visible = true;
  private ang = START_ANGLE; private omega = (2 * Math.PI) / TURN_REST; private windT = -99;
  private pal: Record<string, RGB> = {};

  constructor(host: HTMLElement, o: DuskOptions) {
    this.o = o;
    this.canvas.className = "dusk"; this.canvas.setAttribute("aria-hidden", "true");
    const gl = this.canvas.getContext("webgl2", { antialias: false, alpha: false }); if (!gl) return;
    const sh = (t: number, src: string) => {
      const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { if (import.meta.env.DEV) console.error("dusk:", gl.getShaderInfoLog(s)); return null; }
      return s;
    };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    this.gl = gl; this.prog = p;
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uTime", "uDark", "uMove", "uG", "uGS", "uGlow", "uGlowP", "uLineA", "uMill", "uInk", "uS", "uK", "uBox", "uTone", "uFringe", "uCore", "uShade", "uVel", "uWake", "uText"]) this.u[n] = gl.getUniformLocation(p, n);
    host.prepend(this.canvas);
    if (!o.reduce && wakeWanted() && !o.small()) {
      const w = new Wake(gl, TAIL);
      if (w.supported) {
        this.wake = w;
        w.onPush = (x, y) => { const r = this.canvas.getBoundingClientRect(), hub = this.hub(); if (Math.hypot(x - r.left - hub[0], y - r.top - hub[1]) < NEAR_MILL) this.windT = this.t; };
        followPointer((x, y) => { w.move(x, y); this.kick(); }, () => w.lift(), () => !document.hidden && !this.o.small());
      }
    }
    addEventListener("scroll", () => { if (this.o.reduce) this.draw(); else this.kick(); }, { passive: true });
    document.addEventListener("visibilitychange", () => this.kick());
    new IntersectionObserver(([e]) => { this.visible = e.isIntersecting; this.kick(); }).observe(this.canvas);
    this.layout();
  }

  /** sizes and colours: after a layout change */
  layout() {
    const gl = this.gl; if (!gl) return;
    const cs = getComputedStyle(this.canvas);
    for (const k of ["--d0", "--d1", "--d2", "--d3", "--d4", "--d5", "--glow", "--mill", "--wake-core", "--wake-shade"]) this.pal[k] = rgb(cs.getPropertyValue(k) || "#808080");
    const w = wakeColours(this.canvas); this.pal.tone = w.tone; this.pal.fringe = w.fringe;
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.W = Math.max(1, this.canvas.clientWidth); this.H = Math.max(1, this.canvas.clientHeight);
    this.canvas.width = Math.round(this.W * this.dpr); this.canvas.height = Math.round(this.H * this.dpr);
    this.wake?.resize(innerWidth, innerHeight);
    const wk = this.wake; if (wk) (typeof requestIdleCallback === "function" ? requestIdleCallback : (f: () => void) => setTimeout(f, 300))(() => wk.warm(innerHeight));
    if (this.o.reduce) this.draw(); else this.kick();
  }
  private hub(): [number, number] { return [MILL.x * this.W, (HORIZON - MILL.h * HUB) * this.H]; }
  /** scroll progress through the page, 0-1 (none under reduced motion: still) */
  private progress() {
    if (this.o.reduce) return 0;
    if (this.o.progress) return Math.max(0, Math.min(1, this.o.progress()));
    const max = document.documentElement.scrollHeight - innerHeight;
    return Math.max(0, Math.min(1, max > 0 ? scrollY / max : 0));
  }

  private active = true;
  /** the one-page site: draw only while this section's backdrop can be seen (src/onepage/boot.ts onBackdrop) */
  setActive(on: boolean) { if (this.active === on) return; this.active = on; if (on) { if (this.o.reduce) this.draw(); else this.kick(); } }
  private kick() {
    if (this.raf || !this.gl || this.o.reduce || document.hidden || !this.visible || !this.active) return;
    this.last = performance.now(); this.raf = requestAnimationFrame(this.frame);
  }
  private frame = (now: number) => {
    this.raf = 0;
    if (document.hidden || !this.visible || !this.active) return;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now; this.t += dt;
    const fast = (2 * Math.PI) / TURN_WIND, rest = (2 * Math.PI) / TURN_REST;
    if (this.t - this.windT < 0.12) this.omega += (fast - this.omega) * (1 - Math.exp(-dt / 0.4));
    else this.omega += (rest - this.omega) * (1 - Math.exp(-dt / (EASE_BACK / 3.5)));
    this.ang += this.omega * dt;
    this.wake?.step(dt, innerHeight);
    this.draw();
    this.kick();                       // the sails always turn and the air always moves
  };

  /** the strokes in canvas css px: points (x, y, s) and (w0, w1, length, seed) */
  private strokes(): { S: number[]; K: number[]; box: number[] } {
    const Hw = MILL.h * this.H, fx = MILL.x * this.W, fy = HORIZON * this.H, S: number[] = [], K: number[] = [];
    const put = (st: Stroke, tf: (x: number, y: number) => [number, number], seed: number) => {
      const pts: [number, number][] = [];
      for (let j = 0; j <= SEG; j++) {
        const t = j / SEG, m = 1 - t;
        pts.push(tf(m * m * st.a[0] + 2 * m * t * st.c[0] + t * t * st.b[0], m * m * st.a[1] + 2 * m * t * st.c[1] + t * t * st.b[1]));
      }
      let len = 0; const acc = [0];
      for (let j = 1; j <= SEG; j++) { len += Math.hypot(pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]); acc.push(len); }
      pts.forEach((p, j) => S.push(p[0], p[1], acc[j] / Math.max(1e-3, len), 0));
      K.push(st.w0 * Hw, st.w1 * Hw, len, seed);
    };
    const body = (x: number, y: number): [number, number] => [fx + x * Hw, fy - y * Hw];
    BODY.forEach((st, i) => put(st, body, 1 + i * 1.37));
    for (let k = 0; k < 4; k++) {
      const a = this.ang + (k * Math.PI) / 2, ca = Math.cos(a), sa = Math.sin(a);
      put(SAIL, (x, y) => body(x * ca - y * sa, HUB + x * sa + y * ca), 20 + k * 2.71);
    }
    const r = 0.5 * Hw;
    return { S, K, box: [fx - r - 6, fy - Hw - 8, fx + r + 6, fy + 8] };
  }

  private draw() {
    const gl = this.gl, p = this.prog; if (!gl || !p) return;
    const W = this.W, H = this.H, P = this.progress(), pal = this.pal, u = this.u;
    gl.useProgram(p); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.uniform2f(u.uSize, W, H); gl.uniform1f(u.uDpr, this.dpr); gl.uniform1f(u.uTime, this.t);
    gl.uniform1f(u.uDark, 1 - 0.15 * P); gl.uniform1f(u.uMove, this.o.reduce ? 0 : 1);
    gl.uniform3fv(u.uG, ["--d0", "--d1", "--d2", "--d3", "--d4", "--d5"].flatMap((k) => pal[k])); gl.uniform1fv(u.uGS, STOPS);
    // the glow: a third of a viewport across on each side, sinking 6vh over the page (on a phone, of the band)
    gl.uniform3f(u.uGlow, ...pal["--glow"]); gl.uniform4f(u.uGlowP, GLOW.x * W, (HORIZON + GLOW.sink * P) * H, (GLOW.w / 2) * H, GLOW.a);
    gl.uniform1f(u.uLineA, GLOW.line);
    const st = this.strokes();
    gl.uniform3f(u.uMill, MILL.x * W, HORIZON * H, MILL.h * H); gl.uniform3f(u.uInk, ...pal["--mill"]);
    gl.uniform4fv(u.uS, st.S); gl.uniform4fv(u.uK, st.K); gl.uniform4f(u.uBox, st.box[0], st.box[1], st.box[2], st.box[3]);
    gl.uniform3f(u.uTone, ...pal.tone); gl.uniform3f(u.uFringe, ...pal.fringe); gl.uniform3f(u.uCore, ...pal["--wake-core"]); gl.uniform3f(u.uShade, ...pal["--wake-shade"]);
    const w = this.wake, on = !!w?.ready && w.idle < w.still;
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(u.uVel, 0); gl.uniform1f(u.uWake, on ? 1 : 0);
    const tx = on ? this.o.text?.() : null; gl.uniform4f(u.uText, tx?.x ?? -1e5, tx?.y ?? -1e5, tx?.w ?? 0, tx?.h ?? 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
}
