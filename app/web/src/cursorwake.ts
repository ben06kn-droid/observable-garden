// The cursor's wake: the site's signature, the same on every page that has it, only its colours
// changing with the page's theme (DESIGN.md 3, "The cursor's wake"). After lukres.dev's cursor effect.
//
// What it is: a small fluid simulation (`Wake`). The pointer's movement pushes velocity into the fluid
// along its path; small curls are kept alive (vorticity confinement); the fluid is made incompressible
// (a few pressure iterations) and fades slowly (gone about a second and a half after the cursor stops).
// A page's drawn layer reads the velocity to bend its strokes along the wake, turn them the page's
// tone and split them into fine fringes in the page's fringe colour.
//
// How a page uses it, by one of two routes:
//   - a layer that already composites its own pixels in WebGL (the run page's fan and hero layer) runs
//     a `Wake` in its own context, follows the pointer with `followPointer`, includes `WAKE_GLSL` in its
//     shader and reads its colours with `wakeColours`;
//   - a layer drawn as SVG and 2D canvases (the home page's grove, the demo's scene) gets a `WakeLayer`:
//     an overlay that repaints, only where the wake is, a picture of that layer, bent and fringed.
// It acts on the drawn layer only: never on text, controls or the header.
//
// The two colours are theme tokens: `--wake-tone` (the tone the bent strokes turn) and `--wake-fringe`
// (the fringes). Optional tuning tokens: `--wake-tone-mix` (0 keeps the strokes' own colours; 1 by
// default), `--wake-fringe-alpha`, `--wake-gloss` (the glossy trace in the blank space, 0 for none),
// `--wake-hi` and `--wake-shade` (that trace's highlight and shade).
//
// Rules on every page: only cursor movement drives it (pressing and dragging do nothing, touch does
// nothing); nothing under reduced motion; asleep when its layer is off screen or the fluid is still.
//
// The simulation runs at an eighth of the viewport's size on half-float targets
// (EXT_color_buffer_float). Without them there is no wake and the layer is drawn as before. Velocity is
// stored in CSS px per second, in the GL frame (y up).

const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const HEAD = `#version 300 es
precision highp float; precision highp sampler2D;
uniform vec2 uTex;   // 1 / the sim's size in texels
out vec4 o;
`;
const ADVECT = HEAD + `
uniform sampler2D uVel; uniform float uDt, uCell, uFade;
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  vec2 v = texture(uVel, uv).xy;
  vec2 back = uv - uDt * v / uCell * uTex;   // where this fluid was a step ago (velocity in px/s, cells of uCell px)
  o = vec4(texture(uVel, back).xy * uFade, 0.0, 1.0);
}`;
const SPLAT = HEAD + `
uniform sampler2D uVel; uniform vec2 uA, uB, uForce; uniform float uR;
void main() {
  vec2 p = gl_FragCoord.xy;
  vec2 ab = uB - uA; float t = clamp(dot(p - uA, ab) / max(dot(ab, ab), 1e-4), 0.0, 1.0);
  float d = length(p - (uA + ab * t));
  vec2 v = texture(uVel, p * uTex).xy;
  o = vec4(v + uForce * exp(-d * d / (uR * uR)), 0.0, 1.0);
}`;
const CURL = HEAD + `
uniform sampler2D uVel;
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  float l = texture(uVel, uv - vec2(uTex.x, 0)).y, r = texture(uVel, uv + vec2(uTex.x, 0)).y;
  float b = texture(uVel, uv - vec2(0, uTex.y)).x, t = texture(uVel, uv + vec2(0, uTex.y)).x;
  o = vec4(0.5 * (r - l - t + b), 0.0, 0.0, 1.0);
}`;
const VORT = HEAD + `
uniform sampler2D uVel, uCurl; uniform float uEps, uDt;
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  float l = texture(uCurl, uv - vec2(uTex.x, 0)).x, r = texture(uCurl, uv + vec2(uTex.x, 0)).x;
  float b = texture(uCurl, uv - vec2(0, uTex.y)).x, t = texture(uCurl, uv + vec2(0, uTex.y)).x;
  float c = texture(uCurl, uv).x;
  vec2 f = 0.5 * vec2(abs(t) - abs(b), abs(r) - abs(l));
  f = f / (length(f) + 1e-4) * uEps * c * vec2(1.0, -1.0);
  o = vec4(texture(uVel, uv).xy + f * uDt, 0.0, 1.0);
}`;
const DIV = HEAD + `
uniform sampler2D uVel;
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  float l = texture(uVel, uv - vec2(uTex.x, 0)).x, r = texture(uVel, uv + vec2(uTex.x, 0)).x;
  float b = texture(uVel, uv - vec2(0, uTex.y)).y, t = texture(uVel, uv + vec2(0, uTex.y)).y;
  o = vec4(0.5 * (r - l + t - b), 0.0, 0.0, 1.0);
}`;
const PRES = HEAD + `
uniform sampler2D uP, uDiv;
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  float l = texture(uP, uv - vec2(uTex.x, 0)).x, r = texture(uP, uv + vec2(uTex.x, 0)).x;
  float b = texture(uP, uv - vec2(0, uTex.y)).x, t = texture(uP, uv + vec2(0, uTex.y)).x;
  o = vec4(0.25 * (l + r + b + t - texture(uDiv, uv).x), 0.0, 0.0, 1.0);
}`;
const GRAD = HEAD + `
uniform sampler2D uVel, uP;
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  float l = texture(uP, uv - vec2(uTex.x, 0)).x, r = texture(uP, uv + vec2(uTex.x, 0)).x;
  float b = texture(uP, uv - vec2(0, uTex.y)).x, t = texture(uP, uv + vec2(0, uTex.y)).x;
  o = vec4(texture(uVel, uv).xy - 0.5 * vec2(r - l, t - b), 0.0, 1.0);
}`;

interface Target { tex: WebGLTexture; fb: WebGLFramebuffer }
interface Prog { p: WebGLProgram; u: Record<string, WebGLUniformLocation | null> }

export const CELL = 8;          // css px per simulation texel
const DELAY = 70;               // ms the wake follows the pointer by: a deliberate beat, not lag
const FLOW = 0.55;              // how fast the fluid carries itself (1 = its own velocity): slower, more liquid
const FADE = 0.45;              // its fade's time constant, s (gone in about a second and a half)
const TRAIL = 1.8;              // each push reaches this far back along the pointer's path: a longer trail
export const STILL = 1.8;       // s after the last push: the fluid is still, and nothing is stepped or drawn

export class Wake {
  private gl: WebGL2RenderingContext; private w = 0; private h = 0; private ok = false;
  private vel: [Target, Target] | null = null; private pres: [Target, Target] | null = null; private div: Target | null = null; private curl: Target | null = null;
  private progs: Record<string, Prog> = {};
  /** seconds since the fluid last had anything pushed into it; it is still after about 0.6 s */
  idle = 99;
  /** pointer movement still waiting to be pushed in (the wake's delay) */
  get pending() { return this.queue.length > 0; }

  constructor(gl: WebGL2RenderingContext) {
    this.gl = gl;
    if (!gl.getExtension("EXT_color_buffer_float")) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT); if (!vs) return;
    for (const [name, src] of Object.entries({ advect: ADVECT, splat: SPLAT, curl: CURL, vort: VORT, div: DIV, pres: PRES, grad: GRAD })) {
      const fs = sh(gl.FRAGMENT_SHADER, src); if (!fs) return;
      const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
      const u: Record<string, WebGLUniformLocation | null> = {};
      for (const n of ["uTex", "uVel", "uDt", "uCell", "uFade", "uA", "uB", "uForce", "uR", "uCurl", "uEps", "uP", "uDiv"]) u[n] = gl.getUniformLocation(p, n);
      this.progs[name] = { p, u };
    }
    this.ok = true;
  }
  get ready() { return this.ok && !!this.vel; }
  /** the velocity texture, for the composite */
  get texture() { return this.vel?.[0].tex ?? null; }

  /** size the simulation to the viewport (css px) */
  resize(vw: number, vh: number) {
    if (!this.ok) return;
    const gl = this.gl, w = Math.max(8, Math.ceil(vw / CELL)), h = Math.max(8, Math.ceil(vh / CELL));
    if (w === this.w && h === this.h) return;
    this.w = w; this.h = h;
    const target = (fmt: number, inner: number): Target => {
      const tex = gl.createTexture()!; gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, inner, w, h, 0, fmt, gl.HALF_FLOAT, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      const fb = gl.createFramebuffer()!; gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
      gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
      return { tex, fb };
    };
    this.vel = [target(gl.RG, gl.RG16F), target(gl.RG, gl.RG16F)];
    this.pres = [target(gl.RED, gl.R16F), target(gl.RED, gl.R16F)];
    this.div = target(gl.RED, gl.R16F); this.curl = target(gl.RED, gl.R16F);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) this.ok = false;
  }

  /** the pointer moved to (x, y), viewport css px: kept, and pushed into the fluid DELAY ms later */
  move(x: number, y: number) { this.queue.push({ t: performance.now(), x, y }); if (this.queue.length > 240) this.queue.shift(); }
  /** the pointer left: the next movement starts a new stroke */
  lift() { this.queue.push({ t: performance.now(), x: NaN, y: NaN }); }
  private queue: { t: number; x: number; y: number }[] = []; private prev: { t: number; x: number; y: number } | null = null;

  private pass(name: string, out: Target, set: (u: Prog["u"]) => void) {
    const gl = this.gl, pr = this.progs[name];
    gl.useProgram(pr.p); gl.bindFramebuffer(gl.FRAMEBUFFER, out.fb); gl.viewport(0, 0, this.w, this.h);
    gl.uniform2f(pr.u.uTex, 1 / this.w, 1 / this.h);
    set(pr.u);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  private bind(unit: number, t: Target) { const gl = this.gl; gl.activeTexture(gl.TEXTURE0 + 4 + unit); gl.bindTexture(gl.TEXTURE_2D, t.tex); return 4 + unit; }

  /** one step of the fluid; vh is the viewport's height (css px), for the GL frame's flip */
  step(dt: number, vh: number) {
    if (!this.ready || !this.vel || !this.pres || !this.div || !this.curl) return;
    const gl = this.gl, V = this.vel, P = this.pres;
    this.idle += dt;
    const swap = () => { const t = V[0]; V[0] = V[1]; V[1] = t; };
    // the push, a beat behind the pointer (DELAY ms, on purpose): each stretch of its path, along a capsule
    // that widens with its speed, its strength rising steeply with speed (a slow drift barely stirs it, a
    // quick flick throws a long, wide wake)
    const toTex = (x: number, y: number): [number, number] => [x / CELL, (vh - y) / CELL];
    const due = performance.now() - DELAY;
    let pushes = 0;
    while (this.queue.length && this.queue[0].t <= due) {
      const q = this.queue.shift()!;
      if (Number.isNaN(q.x)) { this.prev = null; continue; }
      const a = this.prev; this.prev = q;
      if (!a || pushes >= 8) continue;
      const dx = q.x - a.x, dy = q.y - a.y, d = Math.hypot(dx, dy), ms = Math.max(4, q.t - a.t);
      if (d < 0.5) continue;
      const sp = Math.min(5000, (d / ms) * 1000);                        // px/s
      const dose = Math.pow(Math.min(1, Math.max(0, (sp - 90) / 1400)), 1.6);   // slow: next to nothing
      if (dose <= 0.002) continue;
      const k = (sp / d) * 3.4 * dose, A = toTex(q.x - dx * TRAIL, q.y - dy * TRAIL), B = toTex(q.x, q.y);
      this.pass("splat", V[1], (u) => {
        gl.uniform1i(u.uVel, this.bind(0, V[0]));
        gl.uniform2f(u.uA, A[0], A[1]); gl.uniform2f(u.uB, B[0], B[1]);
        gl.uniform2f(u.uForce, dx * k, -dy * k); gl.uniform1f(u.uR, 4 + 6 * Math.sqrt(dose));
      });
      swap(); this.idle = 0; pushes++;
    }
    if (this.idle > STILL) return;          // still: nothing to step
    // curls, kept alive
    this.pass("curl", this.curl, (u) => gl.uniform1i(u.uVel, this.bind(0, V[0])));
    this.pass("vort", V[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform1i(u.uCurl, this.bind(1, this.curl!)); gl.uniform1f(u.uEps, 22); gl.uniform1f(u.uDt, dt); });
    swap();
    // incompressible
    this.pass("div", this.div, (u) => gl.uniform1i(u.uVel, this.bind(0, V[0])));
    for (let i = 0; i < 12; i++) {
      this.pass("pres", P[1], (u) => { gl.uniform1i(u.uP, this.bind(0, P[0])); gl.uniform1i(u.uDiv, this.bind(1, this.div!)); });
      const t = P[0]; P[0] = P[1]; P[1] = t;
    }
    this.pass("grad", V[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform1i(u.uP, this.bind(1, P[0])); });
    swap();
    // carried along by itself, slowly (FLOW), and fading over FADE seconds
    this.pass("advect", V[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform1f(u.uDt, dt * FLOW); gl.uniform1f(u.uCell, CELL); gl.uniform1f(u.uFade, Math.exp(-dt / FADE)); });
    swap();
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }
}

// ---------- colours: the page's theme tokens
export type RGB = [number, number, number];
export function rgb(s: string): RGB {
  let h = s.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1];
  if (h) { if (h.length === 3) h = h.replace(/./g, "$&$&"); const n = parseInt(h, 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
  const r = s.match(/(\d+(\.\d+)?)/g); return r ? [Number(r[0]) / 255, Number(r[1]) / 255, Number(r[2]) / 255] : [0, 0, 0];
}
export interface WakeColours { tone: RGB; fringe: RGB; fringeA: number; toneMix: number; gloss: number; hi: RGB; shade: RGB }
/** the wake's colours, from the theme tokens in force at `el` */
export function wakeColours(el: Element): WakeColours {
  const cs = getComputedStyle(el), v = (k: string) => cs.getPropertyValue(k).trim();
  const num = (k: string, d: number) => { const x = v(k); return x === "" || Number.isNaN(Number(x)) ? d : Number(x); };
  return { tone: rgb(v("--wake-tone") || "#dce2ef"), fringe: rgb(v("--wake-fringe") || "#e5484d"), fringeA: num("--wake-fringe-alpha", 1),
    toneMix: num("--wake-tone-mix", 1), gloss: num("--wake-gloss", 1), hi: rgb(v("--wake-hi") || "#ffffff"), shade: rgb(v("--wake-shade") || "#000000") };
}

// ---------- the shader's shared part: included by every layer's composite
export const WAKE_GLSL = `
// the wake's displacement (css px, y down) at a viewport point vp (css px), from the fluid's velocity
vec2 wakeFlow(sampler2D vel, vec2 vp, vec2 view) {
  vec2 v = texture(vel, vec2(vp.x, view.y - vp.y) / view).xy;
  vec2 d = vec2(v.x, -v.y) * 0.016; float l = length(d);
  return l > 26.0 ? d * 26.0 / l : d;
}
// how strongly a point is in the wake (0 outside it)
float wakeStrength(vec2 d) { return smoothstep(0.25, 5.0, length(d)); }
// the fringes' offset: across the strokes, along the flow, about a pixel
vec2 wakeAcross(vec2 d, float s) { return normalize(d) * mix(0.7, 1.3, s); }
// the trace in the blank space, read as a surface from the gradient gr of the wake's strength: a highlight
// on the side facing a light from the upper left, a soft shade on the other, a hairline of the fringe
// colour at its rim; no flat tint (which reads as dust). blank: 1 where no stroke is. (colour, alpha)
vec4 wakeTrace(vec3 base, vec2 gr, float s, float blank, vec3 hi, vec3 shade, vec3 fringe, float fringeA) {
  float slope = smoothstep(0.6, 6.0, length(gr));
  float face = dot(gr / (length(gr) + 1e-4), normalize(vec2(-0.6, -0.8)));
  float spec = pow(max(face, 0.0), 2.0) * slope * s, sh = max(-face, 0.0) * slope * s;
  float rim = smoothstep(0.82, 0.97, slope) * (1.0 - smoothstep(0.97, 1.0, slope)) * s;   // a hairline
  vec3 g = mix(base, hi, clamp(0.22 * spec * blank, 0.0, 1.0));
  g = mix(g, shade, clamp(0.10 * sh * blank, 0.0, 1.0));
  g = mix(g, fringe, clamp(0.08 * fringeA * rim * blank, 0.0, 1.0));
  return vec4(g, clamp((0.22 * spec + 0.10 * sh + 0.08 * rim) * blank, 0.0, 1.0));
}
`;

// ---------- the rules: what drives it
/** whether this visitor gets the wake: a fine pointer that hovers, and motion allowed */
export function wakeWanted(): boolean {
  return !matchMedia("(prefers-reduced-motion: reduce)").matches && matchMedia("(hover: hover) and (pointer: fine)").matches;
}
/** Follow the cursor: only its movement, never touch; a press ends the stroke and nothing moves the fluid
 *  until the button is released (pressing and dragging do nothing). Returns the unsubscribe. */
export function followPointer(move: (x: number, y: number) => void, lift: () => void, active: () => boolean = () => true): () => void {
  let held = false;
  const onMove = (e: PointerEvent) => {
    if (e.pointerType === "touch") return;
    if (e.buttons !== 0) { if (!held) { held = true; lift(); } return; }
    if (held) { held = false; lift(); }
    if (active()) move(e.clientX, e.clientY);
  };
  const onDown = (e: PointerEvent) => { if (e.pointerType !== "touch") { held = true; lift(); } };
  const onLeave = () => lift();
  addEventListener("pointermove", onMove, { passive: true });
  addEventListener("pointerdown", onDown, { passive: true });
  document.documentElement.addEventListener("pointerleave", onLeave, { passive: true });
  return () => { removeEventListener("pointermove", onMove); removeEventListener("pointerdown", onDown); document.documentElement.removeEventListener("pointerleave", onLeave); };
}
/** whether `el` is on screen now (kept by an IntersectionObserver; true until it first reports) */
export function onScreen(el: Element, changed?: (on: boolean) => void): () => boolean {
  let on = true;
  new IntersectionObserver(([e]) => { on = e.isIntersecting; changed?.(on); }, { rootMargin: "64px" }).observe(el);
  return () => on;
}
