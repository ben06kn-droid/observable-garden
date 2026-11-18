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

// the dye's line: tops the dye up to its strength along the stretch (never piles up where the cursor circles)
const DYE_SPLAT = HEAD + `
uniform sampler2D uVel; uniform vec2 uA, uB, uForce; uniform float uR;
void main() {
  vec2 p = gl_FragCoord.xy;
  vec2 ab = uB - uA; float t = clamp(dot(p - uA, ab) / max(dot(ab, ab), 1e-4), 0.0, 1.0);
  float d = length(p - (uA + ab * t));
  o = vec4(max(texture(uVel, p * uTex).rg, vec2(uForce.x * exp(-d * d / (uR * uR)))), 0.0, 1.0);
}`;
// the dye (a page that draws the wake as a trail): carried by the fluid, fading
const DYE_ADVECT = HEAD + `
uniform sampler2D uVel, uSrc; uniform float uDt, uFade, uFade2; uniform vec2 uView;
// r: the dye; g: a copy fading twice as fast, so g / r tells each point's age
void main() {
  vec2 uv = gl_FragCoord.xy * uTex;
  vec2 v = texture(uVel, uv).xy;                     // px/s, GL frame
  vec2 c = texture(uSrc, uv - uDt * v / uView).rg;
  o = vec4(c.r * uFade, c.g * uFade2, 0.0, 1.0);
}`;

interface Target { tex: WebGLTexture; fb: WebGLFramebuffer }
interface Prog { p: WebGLProgram; u: Record<string, WebGLUniformLocation | null> }

export const CELL = 8;          // css px per simulation texel
const DELAY = 70;               // ms the wake follows the pointer by: a deliberate beat, not lag
const FLOW = 0.55;              // how fast the fluid carries itself (1 = its own velocity): slower, more liquid
const FADE = 0.45;              // its fade's time constant, s (gone in about a second and a half)
const TRAIL = 1.8;              // each push reaches this far back along the pointer's path: a longer trail
const DYE_FADE = 0.55;           // the dye's fade, s: the trail is gone well before the fluid is still
export const STILL = 1.8;       // s after the last push: the fluid is still, and nothing is stepped or drawn

/** a layer's own scale for the fluid; the push (its delay, its dose for the cursor's speed) is the same everywhere */
export interface WakeScale {
  /** css px per simulation texel (8): smaller makes finer curls and a narrower trail */
  cell?: number;
  /** how fast the fluid carries itself (0.55): lower keeps the curls close to the cursor's path */
  flow?: number;
  /** how strongly small curls are kept alive (22) */
  curl?: number;
  /** a dye laid along the cursor's path and carried by the fluid (the trail a page draws): css px per
   *  dye texel, finer than the fluid. Off by default. */
  dye?: number;
  /** how fast the fluid carries the dye, as a fraction of its velocity (0.1): its velocity is scaled to
   *  bend strokes, far quicker than a trail should drift */
  dyeFlow?: number;
  /** the dye line's half width in dye texels (0.7) and its fade's time constant in s (0.55) */
  dyeWidth?: number;
  dyeFade?: number;
  /** how much wider the dye line grows with the cursor's speed: dye texels per √dose (0: a fixed width) */
  dyeGrow?: number;
  /** the force the cursor puts in, × the run page's (1) */
  force?: number;
  /** the fluid's fade's time constant, s (0.45): longer lives longer */
  fade?: number;
}

export class Wake {
  private gl: WebGL2RenderingContext; private w = 0; private h = 0; private ok = false;
  private vel: [Target, Target] | null = null; private pres: [Target, Target] | null = null; private div: Target | null = null; private curl: Target | null = null;
  private progs: Record<string, Prog> = {};
  /** seconds since the fluid last had anything pushed into it; it is still after about 0.6 s */
  idle = 99;
  /** pointer movement still waiting to be pushed in (the wake's delay) */
  get pending() { return this.queue.length > 0; }

  private cell: number; private flow: number; private eps: number; private dyeCell: number; private dyeFlow: number; private dyeWidth: number; private dyeGrow: number; private dyeFade: number; private dyeDose = 0; private force: number; private fadeT: number;
  private dye: [Target, Target] | null = null; private dw = 0; private dh = 0; private vw = 1; private vh = 1;
  /** each stretch of the cursor's path as it is pushed in (after the delay): viewport css px, its velocity
   *  in px/s and its dose (0-1, how strongly it stirs the fluid) */
  onPush: ((x: number, y: number, vx: number, vy: number, dose: number) => void) | null = null;
  constructor(gl: WebGL2RenderingContext, scale: WakeScale = {}) {
    this.gl = gl; this.cell = scale.cell ?? CELL; this.flow = scale.flow ?? FLOW; this.eps = scale.curl ?? 22; this.dyeCell = scale.dye ?? 0; this.dyeFlow = scale.dyeFlow ?? 0.1; this.dyeWidth = scale.dyeWidth ?? 0.7; this.dyeGrow = scale.dyeGrow ?? 0; this.dyeFade = scale.dyeFade ?? DYE_FADE; this.force = scale.force ?? 1; this.fadeT = scale.fade ?? FADE;
    if (!gl.getExtension("EXT_color_buffer_float")) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT); if (!vs) return;
    for (const [name, src] of Object.entries({ advect: ADVECT, splat: SPLAT, curl: CURL, vort: VORT, div: DIV, pres: PRES, grad: GRAD, ...(this.dyeCell ? { dyeAdvect: DYE_ADVECT, dyeSplat: DYE_SPLAT } : {}) })) {
      const fs = sh(gl.FRAGMENT_SHADER, src); if (!fs) return;
      const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
      const u: Record<string, WebGLUniformLocation | null> = {};
      for (const n of ["uTex", "uVel", "uDt", "uCell", "uFade", "uA", "uB", "uForce", "uR", "uCurl", "uEps", "uP", "uDiv", "uSrc", "uView", "uFade2"]) u[n] = gl.getUniformLocation(p, n);
      this.progs[name] = { p, u };
    }
    this.ok = true;
  }
  get ready() { return this.ok && !!this.vel; }
  /** whether this browser can run it at all (half-float targets, the programs compiled) */
  get supported() { return this.ok; }
  /** the velocity texture, for the composite */
  get texture() { return this.vel?.[0].tex ?? null; }
  /** s after the last push until the wake is still: longer while a slow dye is still fading */
  /** the dye's fade (s), for reading its age */
  get fadeTime() { return this.dyeFade; }
  get still() { return this.dye ? Math.max(STILL, this.dyeFade * 5) : Math.max(STILL, this.fadeT * 4); }
  /** the dye texture (covers the viewport, GL frame), when the layer asked for one */
  get dyeTexture() { return this.dye?.[0].tex ?? null; }

  /** size the simulation to the viewport (css px) */
  resize(vw: number, vh: number) {
    if (!this.ok) return;
    const gl = this.gl, w = Math.max(8, Math.ceil(vw / this.cell)), h = Math.max(8, Math.ceil(vh / this.cell));
    this.vw = vw; this.vh = vh;
    if (w === this.w && h === this.h) return;
    this.w = w; this.h = h;
    const target = (fmt: number, inner: number, w = this.w, h = this.h): Target => {
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
    if (this.dyeCell) {
      this.dw = Math.max(8, Math.ceil(vw / this.dyeCell)); this.dh = Math.max(8, Math.ceil(vh / this.dyeCell));
      this.dye = [target(gl.RG, gl.RG16F, this.dw, this.dh), target(gl.RG, gl.RG16F, this.dw, this.dh)];
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) this.ok = false;
  }

  /** the pointer moved to (x, y), viewport css px: kept, and pushed into the fluid DELAY ms later */
  move(x: number, y: number) { this.queue.push({ t: performance.now(), x, y }); if (this.queue.length > 240) this.queue.shift(); }
  /** the pointer left: the next movement starts a new stroke */
  lift() { this.queue.push({ t: performance.now(), x: NaN, y: NaN }); }
  private queue: { t: number; x: number; y: number }[] = []; private prev: { t: number; x: number; y: number } | null = null;

  private pass(name: string, out: Target, set: (u: Prog["u"]) => void, w = this.w, h = this.h) {
    const gl = this.gl, pr = this.progs[name];
    gl.useProgram(pr.p); gl.bindFramebuffer(gl.FRAMEBUFFER, out.fb); gl.viewport(0, 0, w, h);
    gl.uniform2f(pr.u.uTex, 1 / w, 1 / h);
    set(pr.u);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  private bind(unit: number, t: Target) { const gl = this.gl; gl.activeTexture(gl.TEXTURE0 + 4 + unit); gl.bindTexture(gl.TEXTURE_2D, t.tex); return 4 + unit; }

  /** run every pass once, changing nothing (a push of no force, a step of no time): the GPU compiles them
   *  now, in idle time, not on the wake's first frame */
  warm(vh: number) {
    if (!this.ready || !this.vel) return;
    const gl = this.gl, V = this.vel;
    this.pass("splat", V[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform2f(u.uA, 0, 0); gl.uniform2f(u.uB, 1, 1); gl.uniform2f(u.uForce, 0, 0); gl.uniform1f(u.uR, 1); });
    const t = V[0]; V[0] = V[1]; V[1] = t;
    const D = this.dye;
    if (D) { this.pass("dyeSplat", D[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, D[0])); gl.uniform2f(u.uA, 0, 0); gl.uniform2f(u.uB, 1, 1); gl.uniform2f(u.uForce, 0, 0); gl.uniform1f(u.uR, 1); }, this.dw, this.dh);
      const d = D[0]; D[0] = D[1]; D[1] = d; }
    const idle = this.idle; this.idle = -1; this.step(0, vh); this.idle = idle;
  }

  /** one step of the fluid; vh is the viewport's height (css px), for the GL frame's flip */
  step(dt: number, vh: number) {
    if (!this.ready || !this.vel || !this.pres || !this.div || !this.curl) return;
    const gl = this.gl, V = this.vel, P = this.pres;
    this.idle += dt;
    const swap = () => { const t = V[0]; V[0] = V[1]; V[1] = t; };
    // the push, a beat behind the pointer (DELAY ms, on purpose): each stretch of its path, along a capsule
    // that widens with its speed, its strength rising steeply with speed (a slow drift barely stirs it, a
    // quick flick throws a long, wide wake)
    const toTex = (x: number, y: number): [number, number] => [x / this.cell, (vh - y) / this.cell];
    const due = performance.now() - DELAY;
    let pushes = 0;
    while (this.queue.length && this.queue[0].t <= due) {
      const q = this.queue.shift()!;
      if (Number.isNaN(q.x)) { this.prev = null; continue; }
      const a = this.prev; this.prev = q;
      if (!a) continue;
      const dx = q.x - a.x, dy = q.y - a.y, d = Math.hypot(dx, dy), ms = Math.max(4, q.t - a.t);
      if (d < 0.5) continue;
      const sp = Math.min(5000, (d / ms) * 1000);                        // px/s
      const dose = Math.pow(Math.min(1, Math.max(0, (sp - 90) / 1400)), 1.6);   // slow: next to nothing
      if (dose <= 0.002) continue;
      // the dye: a line along every stretch of the path (so the trail never skips), its strength smoothed
      // over the last few stretches (so it does not bead where the pointer's speed jitters)
      const D = this.dye;
      if (D) {
        this.dyeDose += (dose - this.dyeDose) * 0.35;
        const c = this.dyeCell, P0: [number, number] = [a.x / c, (vh - a.y) / c], P1: [number, number] = [q.x / c, (vh - q.y) / c], amt = 0.45 + 0.55 * Math.sqrt(this.dyeDose);
        this.pass("dyeSplat", D[1], (u) => {
          gl.uniform1i(u.uVel, this.bind(0, D[0]));
          gl.uniform2f(u.uA, P0[0], P0[1]); gl.uniform2f(u.uB, P1[0], P1[1]);
          gl.uniform2f(u.uForce, amt, 0); gl.uniform1f(u.uR, this.dyeWidth + this.dyeGrow * Math.sqrt(this.dyeDose));
        }, this.dw, this.dh);
        const t = D[0]; D[0] = D[1]; D[1] = t; this.idle = 0;
      }
      if (pushes >= 8) continue;
      const k = (sp / d) * 3.4 * dose * this.force, A = toTex(q.x - dx * TRAIL, q.y - dy * TRAIL), B = toTex(q.x, q.y);
      this.pass("splat", V[1], (u) => {
        gl.uniform1i(u.uVel, this.bind(0, V[0]));
        gl.uniform2f(u.uA, A[0], A[1]); gl.uniform2f(u.uB, B[0], B[1]);
        gl.uniform2f(u.uForce, dx * k, -dy * k); gl.uniform1f(u.uR, 4 + 6 * Math.sqrt(dose));
      });
      swap(); this.idle = 0; pushes++;
      this.onPush?.(q.x, q.y, (dx / ms) * 1000, (dy / ms) * 1000, dose);
    }
    if (this.idle > this.still) return;     // still: nothing to step
    // curls, kept alive
    this.pass("curl", this.curl, (u) => gl.uniform1i(u.uVel, this.bind(0, V[0])));
    this.pass("vort", V[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform1i(u.uCurl, this.bind(1, this.curl!)); gl.uniform1f(u.uEps, this.eps); gl.uniform1f(u.uDt, dt); });
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
    this.pass("advect", V[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform1f(u.uDt, dt * this.flow); gl.uniform1f(u.uCell, this.cell); gl.uniform1f(u.uFade, Math.exp(-dt / this.fadeT)); });
    swap();
    // the dye, carried by the fluid (its wisps curl where the fluid curls) and fading
    const D = this.dye;
    if (D) {
      this.pass("dyeAdvect", D[1], (u) => { gl.uniform1i(u.uVel, this.bind(0, V[0])); gl.uniform1i(u.uSrc, this.bind(1, D[0])); gl.uniform1f(u.uDt, dt * this.dyeFlow); gl.uniform1f(u.uFade, Math.exp(-dt / this.dyeFade)); gl.uniform1f(u.uFade2, Math.exp(-2 * dt / this.dyeFade)); gl.uniform2f(u.uView, this.vw, this.vh); }, this.dw, this.dh);
      const t = D[0]; D[0] = D[1]; D[1] = t;
    }
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
export interface WakeColours { tone: RGB; fringe: RGB; fringeA: number; toneMix: number; gloss: number; hi: RGB; shade: RGB; trail: number; refract: number; warp: number; tint: number; edgeOut: RGB; edgeIn: RGB }
/** the wake's colours, from the theme tokens in force at `el` */
export function wakeColours(el: Element): WakeColours {
  const cs = getComputedStyle(el), v = (k: string) => cs.getPropertyValue(k).trim();
  const num = (k: string, d: number) => { const x = v(k); return x === "" || Number.isNaN(Number(x)) ? d : Number(x); };
  return { tone: rgb(v("--wake-tone") || "#dce2ef"), fringe: rgb(v("--wake-fringe") || "#e5484d"), fringeA: num("--wake-fringe-alpha", 1),
    toneMix: num("--wake-tone-mix", 1), gloss: num("--wake-gloss", 1), hi: rgb(v("--wake-hi") || "#ffffff"), shade: rgb(v("--wake-shade") || "#000000"), trail: num("--wake-trail", 0), refract: num("--wake-refract", 0), warp: num("--wake-warp", 0),
    tint: num("--wake-tint", 0.16), edgeOut: rgb(v("--wake-edge-out") || "#ff4769"), edgeIn: rgb(v("--wake-edge-in") || "#33c7e6") };
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

// ---------- the overlay: the wake over a layer drawn as SVG and 2D canvases
//
// The layer stays the page's own (its SVG keeps its clicks, focus and animation). Over it sits one WebGL
// canvas, clear everywhere except in the wake: there it repaints the layer, bent along the flow, its
// strokes turned toward the tone (by --wake-tone-mix) and split into fringes. The picture it repaints is
// the layer's parts, bottom to top: canvases that other loops draw each frame (each copied to the GPU
// whole, each frame the wake shows, a copy on the GPU), and still pictures (an SVG, replayed into a 2D
// canvas by `svgPart`), painted in idle time and again only after `invalidate()`. Under them, the page's
// ground. Asleep when the fluid is still or the layer is off screen; nothing at all without a fine
// hovering pointer, or under reduced motion.

export interface Box { x: number; y: number; w: number; h: number }
/** a part of the layer: a canvas drawn by another loop, or a still picture painted in host px */
export type Part = HTMLCanvasElement | { paint: (c: CanvasRenderingContext2D) => void };
export interface WakeLayerOptions {
  /** positioned; the overlay covers its box */
  host: HTMLElement;
  /** the ground under the layer, in host px (w x h) */
  ground: (c: CanvasRenderingContext2D, w: number, h: number) => void;
  /** the layer's parts, bottom to top (at most six textures: consecutive still parts share one) */
  parts: () => Part[];
  /** boxes (host px) the wake must leave alone: text, controls */
  keep?: () => Box[];
  /** the overlay's place in the host: inserted before this child (else appended) */
  before?: () => Element | null;
  /** or its place elsewhere inside the host (its stacking among the page's layers): inserted into
   *  `parent` before `before`, and placed to cover the host's box all the same */
  mount?: { parent: HTMLElement; before: Element | null };
  /** the wake follows the cursor only while this holds (else it is cleared) */
  active?: () => boolean;
  /** ms between repaints of the still parts while the wake shows them and they keep changing (0) */
  minRepaint?: number;
  /** redraw the still parts every frame while this holds (a tree swaying) */
  moving?: () => boolean;
  /** which parts the wake bends (and fringes); the others stay exactly where they are and the trace
   *  passes over them. All of them by default. */
  bends?: (p: Part) => boolean;
  /** the fluid's scale on this page (the run page's by default); with `dye`, the wake is also drawn as a
   *  trail (--wake-trail its strength): a thin line along the cursor's path whose wisps curl off with the
   *  fluid, --wake-hi at its core and --wake-fringe at its edges */
  scale?: WakeScale;
  /** each stretch of the cursor's path as the fluid takes it in (after the delay, with its dose) */
  onPush?: (x: number, y: number, vx: number, vy: number, dose: number) => void;
}

const MAXL = 6;
const LAYER_FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr; uniform vec2 uHostVp, uView;   // the host (css px), its place in the viewport
uniform sampler2D uVel;
uniform sampler2D uL0, uL1, uL2, uL3, uL4, uL5; uniform vec4 uLB[${MAXL}]; uniform int uN;   // the layer's parts, bottom to top, premultiplied, each over its box (host px)
uniform float uBend[${MAXL}];                     // 1: the wake bends that part; 0: it stays put
uniform sampler2D uGround, uKeep;                 // the ground; where the wake may act (r)
uniform vec3 uTone, uFringe, uHi, uShade; uniform float uFringeA, uToneMix, uGloss;
uniform sampler2D uDye; uniform float uTrail;     // the trail's dye (viewport, GL frame) and its strength
uniform float uRefract, uAnyBend;
uniform float uTime, uWarp, uDyeFade;
uniform float uTint; uniform vec3 uEdgeOut, uEdgeIn;   // the trail's tint; its chromatic edge, outside and inside             // s; how far the trail's edges wander (px); the dye's fade (s)                 // how far the trail refracts (px per unit of slope); whether any part bends
out vec4 o;
${WAKE_GLSL}
// (a sampler array may only be indexed by a constant in GLSL ES 3.00, so the six are named)
vec4 part(sampler2D t, vec4 b, vec2 p, vec4 c) {
  vec2 u = (p - b.xy) / b.zw;   // (p: where this part is read)
  if (u.x < 0.0 || u.x > 1.0 || u.y < 0.0 || u.y > 1.0) return c;
  vec4 s = texture(t, u); return s + c * (1.0 - s.a);
}
// the layer at p, the parts that bend read from p - d. only: just the parts that bend (for their strokes)
vec4 layer(vec2 p, vec2 d, bool only) {
  vec4 c = vec4(0.0);
  #define PART(i, t) if (uN > i && (!only || uBend[i] > 0.0)) c = part(t, uLB[i], p - d * uBend[i], c);
  PART(0, uL0) PART(1, uL1) PART(2, uL2) PART(3, uL3) PART(4, uL4) PART(5, uL5)
  return c;
}
vec3 groundAt(vec2 p) { return texture(uGround, p / uSize).rgb; }
// how much of a bending stroke is at p (read from p - d): its difference from the ground there
float ink(vec2 p, vec2 d) { vec4 c = layer(p, d, true); vec3 g = groundAt(p); return clamp(length(c.rgb + g * (1.0 - c.a) - g) * 3.0, 0.0, 1.0); }
// the fluid and its dye are kept in the host's own coordinates, so the wake stays where it is on the page
// when the page scrolls
vec2 flowAt(vec2 p) { return wakeFlow(uVel, p, uSize); }
// a slowly drifting noise that warps where the dye is read: the trail's edges are irregular and contoured
// from the moment it is drawn, before the fluid's own curls have formed
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
vec2 warp(vec2 p) {
  vec2 a = p / 22.0 + vec2(uTime * 0.35, -uTime * 0.27), b = p / 9.0 + vec2(-uTime * 0.6, uTime * 0.45);
  return (vec2(vnoise(a), vnoise(a + 17.3)) - 0.5) * 2.0 * uWarp + (vec2(vnoise(b + 5.1), vnoise(b + 31.7)) - 0.5) * 0.9 * uWarp;
}
vec2 dye2(vec2 p) { p += warp(p); return texture(uDye, vec2(p.x, uSize.y - p.y) / uSize).rg; }
float dyeAt(vec2 p) { return dye2(p).r; }
vec2 dyeGrad(vec2 p, float e) { return vec2(dyeAt(p + vec2(e, 0.0)) - dyeAt(p - vec2(e, 0.0)), dyeAt(p + vec2(0.0, e)) - dyeAt(p - vec2(0.0, e))) / (2.0 * e); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  vec2 d = flowAt(p);
  float keep = texture(uKeep, p / uSize).r;
  float s = wakeStrength(d) * keep;
  // the trail: its dye read as a liquid surface over the page (the run page's trace, on the dye). What is
  // under it is seen refracted along the surface's slope, each colour channel bent a little differently;
  // it is tinted the fringe colour, with a highlight toward a light at the upper left, a soft shade on the
  // other side and hairline ripples where it thins.
  vec3 tc = vec3(0.0); float ta = 0.0;
  if (uTrail > 0.0) {
    vec2 qq = dye2(p); float q = qq.r;
    if (q > 0.02) {
      // its age, from the fast copy's share of the dye: the colour comes in as the trail ages (0.2 to 0.5 s)
      float age = -uDyeFade * log(clamp(qq.g / max(q, 1e-4), 1e-3, 1.0));
      float chroma = smoothstep(0.2, 0.5, age);
      // its slope, over two widths (a smooth surface, not the dye's grain)
      vec2 gq = (dyeGrad(p, 2.5) + dyeGrad(p, 5.0)) * 0.5;
      float body = smoothstep(0.05, 0.5, q);
      vec2 r = -gq * uRefract; float rl = length(r); if (rl > 6.0) r *= 6.0 / rl;   // px, at most 6
      vec3 under;
      for (int k = 0; k < 3; k++) {
        vec2 pk = p + r * (1.0 + (float(k) - 1.0) * 0.18 * chroma);
        vec4 c = uN > 0 ? layer(pk, vec2(0.0), false) : vec4(0.0); vec3 gk = groundAt(pk);
        under[k] = (c.rgb + gk * (1.0 - c.a))[k];
      }
      float slope = smoothstep(0.004, 0.04, length(gq));
      float face = dot(-gq / (length(gq) + 1e-5), normalize(vec2(-0.6, -0.8)));   // 1: facing the light
      float spec = pow(max(face, 0.0), 4.0) * slope, dark = max(-face, 0.0) * slope;
      float ripple = pow(abs(sin(q * 22.0)), 14.0) * (1.0 - body) * smoothstep(0.03, 0.08, q);
      tc = mix(under, uFringe, uTint * body);
      tc = mix(tc, uShade, 0.25 * dark);
      tc = mix(tc, uFringe, 0.55 * ripple);
      tc = mix(tc, uHi, 0.75 * spec);
      // at its outermost edge, always, a faint chromatic split: red just outside, cyan just inside
      float outer = smoothstep(0.02, 0.045, q) * (1.0 - smoothstep(0.045, 0.075, q));
      float inner = smoothstep(0.06, 0.09, q) * (1.0 - smoothstep(0.09, 0.13, q));
      tc = mix(tc, uEdgeOut, 0.32 * outer * chroma);
      tc = mix(tc, uEdgeIn, 0.26 * inner * chroma);
      // over text too: the overlay lies under the text, so the trail shows behind the letters and never moves them
      ta = smoothstep(0.02, 0.07, q) * uTrail;
    }
  }
  if (s <= 0.0 || uN == 0 || uAnyBend == 0.0) { o = vec4(tc * ta, ta); return; }
  vec3 g = groundAt(p);
  vec4 c = layer(p, d, false);
  vec3 col = c.rgb + g * (1.0 - c.a);
  float line = ink(p, d);
  col = mix(col, mix(g, uTone, line), s * uToneMix);
  vec2 n = wakeAcross(d, s);
  float fr = clamp(max(ink(p, d + n), ink(p, d - n)) - line, 0.0, 1.0) * s;
  col = mix(col, uFringe, clamp(fr * 0.6 * uFringeA, 0.0, 1.0));
  if (uGloss > 0.0) {
    vec2 gr = vec2(length(flowAt(p + vec2(6.0, 0.0))) - length(flowAt(p - vec2(6.0, 0.0))),
                   length(flowAt(p + vec2(0.0, 6.0))) - length(flowAt(p - vec2(0.0, 6.0))));
    col = wakeTrace(col, gr, s, (1.0 - line) * uGloss, uHi, uShade, uFringe, uFringeA).rgb;
  }
  col = mix(col, tc, ta);
  float a = max(clamp(s * 4.0, 0.0, 1.0), ta);
  o = vec4(col * a, a);
}`;

export class WakeLayer {
  readonly canvas: HTMLCanvasElement | null = null;
  private o: WakeLayerOptions; private gl: WebGL2RenderingContext | null = null; private wake: Wake | null = null;
  private prog: WebGLProgram | null = null; private u: Record<string, WebGLUniformLocation | null> = {};
  private texL: WebGLTexture[] = []; private texG: WebGLTexture | null = null; private texK: WebGLTexture | null = null;
  private w = 0; private h = 0; private dpr = 1; private col: WakeColours | null = null;
  private stills: HTMLCanvasElement[] = []; private dirty = true; private uploaded = new Set<number>();
  private raf = 0; private last = 0; private shown = false; private lastPaint = -1e9; private warm = false; private visible: () => boolean = () => true; private idleT = 0;
  /** ms the last repaint of the still parts took (the demo's growing tree reads it) */
  paintMs = 0;

  constructor(o: WakeLayerOptions) {
    this.o = o;
    if (!wakeWanted()) return;
    const cv = document.createElement("canvas"); cv.className = "wake-layer"; cv.setAttribute("aria-hidden", "true");
    const gl = cv.getContext("webgl2", { antialias: false, alpha: true, premultipliedAlpha: true }); if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, LAYER_FRAG);
    if (!vs || !fs) { if (import.meta.env.DEV) console.error("cursorwake: the layer's shader did not compile"); return; }
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    const wake = new Wake(gl, o.scale); if (!wake.supported) return;
    this.wake = wake; this.gl = gl; this.prog = p; this.canvas = cv;
    gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uHostVp", "uView", "uVel", "uL0", "uL1", "uL2", "uL3", "uL4", "uL5", "uLB", "uBend", "uN", "uGround", "uKeep", "uTone", "uFringe", "uHi", "uShade", "uFringeA", "uToneMix", "uGloss", "uDye", "uTrail", "uRefract", "uAnyBend", "uTime", "uWarp", "uDyeFade", "uTint", "uEdgeOut", "uEdgeIn"]) this.u[n] = gl.getUniformLocation(p, n);
    const tex = () => { const t = gl.createTexture()!; gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
    for (let i = 0; i < MAXL; i++) this.texL.push(tex());
    this.texG = tex(); this.texK = tex();
    for (let i = 0; i < MAXL; i++) gl.uniform1i(this.u[`uL${i}`], i);   // the parts on units 0-5
    gl.uniform1i(this.u.uGround, 6); gl.uniform1i(this.u.uKeep, 7); gl.uniform1i(this.u.uVel, 8); gl.uniform1i(this.u.uDye, 9);
    const push = o.onPush;   // handed on in viewport coordinates
    wake.onPush = push ? (x, y, vx, vy, dose) => { const r = o.host.getBoundingClientRect(); push(x + r.left, y + r.top, vx, vy, dose); } : null;
    if (o.mount) o.mount.parent.insertBefore(cv, o.mount.before); else o.host.insertBefore(cv, o.before?.() ?? null);
    this.visible = onScreen(o.host);
    // the cursor in the host's coordinates (as it moves), so the wake is fixed to the page, not the screen
    followPointer((x, y) => { const r = o.host.getBoundingClientRect(); wake.move(x - r.left, y - r.top); this.kick(); }, () => wake.lift(),
      () => this.visible() && (o.active?.() ?? true));
    let t = 0; new ResizeObserver(() => { cancelAnimationFrame(t); t = requestAnimationFrame(() => this.layout()); }).observe(o.host);
    this.layout();
  }

  /** the still parts changed (a redraw, a tree done swaying): painted again in idle time, so the wake's
   *  first frame never waits for it */
  invalidate() {
    this.dirty = true; if (!this.gl || this.idleT) return;
    const go = () => {
      this.idleT = 0; if (!this.dirty || this.raf || this.o.moving?.()) return;
      this.paintStills(this.o.parts());
      // and one draw, cleared at once: the shader is compiled and the picture uploaded now, not on the
      // wake's first frame
      if (!this.warm && this.wake?.ready) { this.warm = true; this.wake.warm(this.h); this.draw(); this.shown = true; this.clear(); }
    };
    this.idleT = typeof requestIdleCallback === "function" ? requestIdleCallback(go, { timeout: 1000 }) : setTimeout(go, 200);
  }
  /** the ground, the keep mask and the sizes: after a layout change (called on the host's resize) */
  layout() {
    const gl = this.gl, cv = this.canvas; if (!gl || !cv) return;
    this.dpr = Math.min(2, devicePixelRatio || 1); this.w = Math.max(1, this.o.host.clientWidth); this.h = Math.max(1, this.o.host.clientHeight);
    cv.width = Math.round(this.w * this.dpr); cv.height = Math.round(this.h * this.dpr);
    cv.style.setProperty("--w", `${this.w}px`); cv.style.setProperty("--h", `${this.h}px`);
    if (this.o.mount) {   // mounted inside another element: placed back over the host's box
      const hb = this.o.host.getBoundingClientRect(), pb = this.o.mount.parent.getBoundingClientRect();
      cv.style.setProperty("--x", `${hb.left - pb.left}px`); cv.style.setProperty("--y", `${hb.top - pb.top}px`);
    }
    this.wake?.resize(this.w, this.h);
    this.col = wakeColours(cv);
    // the ground, at a quarter of the size (it is smooth)
    const k = 0.25, gw = Math.ceil(this.w * k), gh = Math.ceil(this.h * k), gc = document.createElement("canvas"); gc.width = gw; gc.height = gh;
    const g = gc.getContext("2d")!; g.scale(k, k); this.o.ground(g, this.w, this.h);
    gl.activeTexture(gl.TEXTURE6); gl.bindTexture(gl.TEXTURE_2D, this.texG); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, gc);
    this.keepMask();
    this.shown = true; this.clear(); this.invalidate();
  }
  /** the keep mask again (the text moved) */
  keepMask() {
    const gl = this.gl; if (!gl) return;
    const k = 0.25, kw = Math.ceil(this.w * k), kh = Math.ceil(this.h * k), kc = document.createElement("canvas"); kc.width = kw; kc.height = kh;
    const c = kc.getContext("2d")!; c.fillStyle = "#fff"; c.fillRect(0, 0, kw, kh); c.fillStyle = "#000";
    for (const b of this.o.keep?.() ?? []) c.fillRect(Math.floor(b.x * k) - 1, Math.floor(b.y * k) - 1, Math.ceil(b.w * k) + 2, Math.ceil(b.h * k) + 2);
    gl.activeTexture(gl.TEXTURE7); gl.bindTexture(gl.TEXTURE_2D, this.texK); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, kc);
  }

  // the still parts, painted into canvases the size of the host (consecutive still parts share one)
  private paintStills(parts: Part[]) {
    const t0 = performance.now(), W = Math.round(this.w * this.dpr), H = Math.round(this.h * this.dpr);
    const groups: Part[][] = []; let cur: Part[] | null = null;
    for (const p of parts) { if (p instanceof HTMLCanvasElement) cur = null; else { if (!cur) { cur = []; groups.push(cur); } cur.push(p); } }
    while (this.stills.length < groups.length) this.stills.push(document.createElement("canvas"));
    groups.forEach((g, i) => {
      const cv = this.stills[i];
      if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
      const c = cv.getContext("2d")!; c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, H);
      for (const p of g) { c.save(); c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); (p as { paint: (c: CanvasRenderingContext2D) => void }).paint(c); c.restore(); }
    });
    this.dirty = false; this.uploaded.clear(); this.paintMs = performance.now() - t0;
  }

  private kick() { if (this.raf || !this.gl) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    this.raf = 0;
    const w = this.wake!, dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
    if (!this.visible() || !(this.o.active?.() ?? true)) { this.clear(); return; }
    w.step(dt, this.h);
    if (w.idle >= w.still && !w.pending) { this.clear(); return; }
    if (w.ready) this.draw();
    this.kick();
  };
  private clear() {
    const gl = this.gl; if (!gl || !this.shown) return;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas!.width, this.canvas!.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); this.shown = false;
  }
  private draw() {
    const gl = this.gl!, cv = this.canvas!, col = this.col!, hb = this.o.host.getBoundingClientRect();
    const parts = this.o.parts();
    const gap = this.o.minRepaint ?? 0, now = performance.now();
    if ((this.dirty || this.o.moving?.()) && now - this.lastPaint >= gap) { this.paintStills(parts); this.lastPaint = now; }
    // the parts, bottom to top: each still group's canvas (uploaded once after a repaint), each live canvas
    // (uploaded each frame, a copy on the GPU), with its box in the host
    const boxes: number[] = [], bend: number[] = []; let n = 0, si = 0, inStill = false;
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    for (const p of parts) {
      if (n >= MAXL) break;
      if (p instanceof HTMLCanvasElement) {
        inStill = false;
        const r = p.getBoundingClientRect(); if (!r.width || !r.height || !p.width || !p.height) continue;
        gl.activeTexture(gl.TEXTURE0 + n); gl.bindTexture(gl.TEXTURE_2D, this.texL[n]);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, p);
        boxes.push(r.left - hb.left, r.top - hb.top, r.width, r.height); bend.push(this.o.bends?.(p) ?? true ? 1 : 0); n++;
      } else if (!inStill) {
        inStill = true; const s = this.stills[si++]; if (!s) continue;
        gl.activeTexture(gl.TEXTURE0 + n); gl.bindTexture(gl.TEXTURE_2D, this.texL[n]);
        if (!this.uploaded.has(n)) { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, s); this.uploaded.add(n); }
        boxes.push(0, 0, this.w, this.h); bend.push(this.o.bends?.(p) ?? true ? 1 : 0); n++;
      }
    }
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    while (boxes.length < MAXL * 4) boxes.push(0, 0, 1, 1);
    while (bend.length < MAXL) bend.push(0);
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, cv.width, cv.height);
    gl.activeTexture(gl.TEXTURE6); gl.bindTexture(gl.TEXTURE_2D, this.texG);
    gl.activeTexture(gl.TEXTURE7); gl.bindTexture(gl.TEXTURE_2D, this.texK);
    gl.activeTexture(gl.TEXTURE8); gl.bindTexture(gl.TEXTURE_2D, this.wake!.texture);
    gl.activeTexture(gl.TEXTURE9); gl.bindTexture(gl.TEXTURE_2D, this.wake!.dyeTexture);
    gl.uniform4fv(this.u.uLB, boxes); gl.uniform1fv(this.u.uBend, bend); gl.uniform1i(this.u.uN, n);
    gl.uniform2f(this.u.uSize, this.w, this.h); gl.uniform1f(this.u.uDpr, this.dpr);
    gl.uniform2f(this.u.uHostVp, hb.left, hb.top); gl.uniform2f(this.u.uView, innerWidth, innerHeight);
    gl.uniform3f(this.u.uTone, ...col.tone); gl.uniform3f(this.u.uFringe, ...col.fringe); gl.uniform3f(this.u.uHi, ...col.hi); gl.uniform3f(this.u.uShade, ...col.shade);
    gl.uniform1f(this.u.uFringeA, col.fringeA); gl.uniform1f(this.u.uToneMix, col.toneMix); gl.uniform1f(this.u.uGloss, col.gloss); gl.uniform1f(this.u.uTrail, this.wake!.dyeTexture ? col.trail : 0);
    gl.uniform1f(this.u.uRefract, col.refract); gl.uniform1f(this.u.uTime, performance.now() / 1000 % 1000);
    gl.uniform1f(this.u.uWarp, col.warp); gl.uniform1f(this.u.uTint, col.tint); gl.uniform3f(this.u.uEdgeOut, ...col.edgeOut); gl.uniform3f(this.u.uEdgeIn, ...col.edgeIn); gl.uniform1f(this.u.uDyeFade, this.wake!.fadeTime); gl.uniform1f(this.u.uAnyBend, bend.some((b) => b > 0) ? 1 : 0);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.shown = true;
  }
}

// ---------- a still part from SVG: the elements replayed into a 2D canvas
//
// Each shape is drawn from its own geometry with its computed style (fill, stroke, widths, opacities,
// dashes, non-scaling strokes), under its transform within the SVG and the SVG's own CSS transform (a tree
// mid-sway). A group with opacity or a filter is drawn into its own canvas and composited (a CSS
// drop-shadow or blur carries over; an SVG filter's Gaussian blur becomes a blur). Text is never drawn: the
// wake never touches text, and the page keeps it clear (`keep`). Gradient fills are drawn with their first
// stop's colour.
const SKIP = new Set(["defs", "clipPath", "mask", "filter", "linearGradient", "radialGradient", "pattern", "marker", "symbol", "title", "desc", "style", "text", "foreignObject", "use", "script", "image"]);
const paths = new WeakMap<Element, { key: string; p: Path2D }>();
function shapePath(el: SVGElement): Path2D | null {
  const a = (n: string) => Number(el.getAttribute(n) ?? 0);
  let key: string;
  switch (el.tagName) {
    case "path": key = el.getAttribute("d") ?? ""; break;
    case "line": key = `M${a("x1")} ${a("y1")}L${a("x2")} ${a("y2")}`; break;
    case "polyline": case "polygon": key = "M" + (el.getAttribute("points") ?? "").trim().replace(/\s+/g, " ") + (el.tagName === "polygon" ? "Z" : ""); break;
    case "circle": key = `c${a("cx")},${a("cy")},${a("r")}`; break;
    case "ellipse": key = `e${a("cx")},${a("cy")},${a("rx")},${a("ry")}`; break;
    case "rect": key = `r${a("x")},${a("y")},${a("width")},${a("height")}`; break;
    default: return null;
  }
  const hit = paths.get(el); if (hit && hit.key === key) return hit.p;
  let p: Path2D;
  if (el.tagName === "circle") { p = new Path2D(); p.arc(a("cx"), a("cy"), a("r"), 0, Math.PI * 2); }
  else if (el.tagName === "ellipse") { p = new Path2D(); p.ellipse(a("cx"), a("cy"), a("rx"), a("ry"), 0, 0, Math.PI * 2); }
  else if (el.tagName === "rect") { p = new Path2D(); p.rect(a("x"), a("y"), a("width"), a("height")); }
  else if (el.tagName === "polyline" || el.tagName === "polygon") { const n = (el.getAttribute("points") ?? "").trim().split(/[\s,]+/).map(Number); p = new Path2D(); for (let i = 0; i + 1 < n.length; i += 2) i ? p.lineTo(n[i], n[i + 1]) : p.moveTo(n[i], n[i + 1]); if (el.tagName === "polygon") p.closePath(); }
  else p = new Path2D(key);
  paths.set(el, { key, p }); return p;
}
// a fill or stroke for the canvas: a colour, or a linear gradient built from the SVG's own (its stops'
// colours and opacities; in the shape's bounding box unless it says userSpaceOnUse)
function paintOf(v: string, el: Element, c: CanvasRenderingContext2D): string | CanvasGradient | null {
  if (!v || v === "none") return null;
  const m = v.match(/url\(["']?#([^"')]+)["']?\)/);
  if (!m) return v;
  const g = el.ownerDocument.getElementById(m[1]); if (!g) return null;
  const stops = [...g.querySelectorAll("stop")]; if (!stops.length) return null;
  if (g.tagName !== "linearGradient") return getComputedStyle(stops[0]).stopColor;
  const num = (n: string, d: number) => { const a = g.getAttribute(n); if (a === null) return d; return a.endsWith("%") ? parseFloat(a) / 100 : Number(a); };
  let [x1, y1, x2, y2] = [num("x1", 0), num("y1", 0), num("x2", 1), num("y2", 0)];
  if (g.getAttribute("gradientUnits") !== "userSpaceOnUse") {
    const b = (el as SVGGraphicsElement).getBBox();
    [x1, y1, x2, y2] = [b.x + x1 * b.width, b.y + y1 * b.height, b.x + x2 * b.width, b.y + y2 * b.height];
  }
  const grad = c.createLinearGradient(x1, y1, x2, y2);
  for (const st of stops) {
    const o = st.getAttribute("offset") ?? "0", cs = getComputedStyle(st), off = Math.max(0, Math.min(1, o.endsWith("%") ? parseFloat(o) / 100 : Number(o)));
    const [r, gg, bb] = rgb(cs.stopColor), a = Number(cs.stopOpacity || 1);
    grad.addColorStop(off, `rgba(${Math.round(r * 255)},${Math.round(gg * 255)},${Math.round(bb * 255)},${a})`);
  }
  return grad;
}
// a CSS filter for the canvas: lengths scaled to the canvas's pixels; an SVG filter's blur as a blur
function canvasFilter(f: string, scale: number, el: Element): string {
  if (!f || f === "none") return "none";
  const m = f.match(/url\(["']?#([^"')]+)["']?\)/);
  if (m) { const b = el.ownerDocument.getElementById(m[1])?.querySelector("feGaussianBlur"); const sd = Number(b?.getAttribute("stdDeviation") ?? 0); return sd ? `blur(${(sd * scale).toFixed(2)}px)` : "none"; }
  return f.replace(/(-?\d*\.?\d+)px/g, (_, n) => `${(Number(n) * scale).toFixed(2)}px`);
}

/** a still part: the SVGs returned by `svgs`, as they stand now, in the host's px */
export function svgPart(host: HTMLElement, svgs: () => SVGSVGElement[]): Part {
  return { paint(c) {
    const hb = host.getBoundingClientRect(), base = c.getTransform();
    const pool: HTMLCanvasElement[] = [];
    const layerCv = (depth: number) => { const cv = pool[depth] ??= document.createElement("canvas"); if (cv.width !== c.canvas.width || cv.height !== c.canvas.height) { cv.width = c.canvas.width; cv.height = c.canvas.height; } const x = cv.getContext("2d")!; x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, cv.width, cv.height); return x; };
    for (const svg of svgs()) {
      const cs = getComputedStyle(svg); if (cs.display === "none" || cs.visibility === "hidden") continue;
      // the svg's box before its CSS transform, and that transform about its origin
      const w = svg.clientWidth, h = svg.clientHeight, r = svg.getBoundingClientRect();
      let place = new DOMMatrix();
      if (cs.transform && cs.transform !== "none") {
        const [ox, oy] = cs.transformOrigin.split(" ").map(parseFloat), M = new DOMMatrix(cs.transform);
        const T = new DOMMatrix().translate(ox, oy).multiply(M).translate(-ox, -oy);
        const xs = [[0, 0], [w, 0], [0, h], [w, h]].map(([x, y]) => T.transformPoint(new DOMPoint(x, y)));
        place = new DOMMatrix().translate(r.left - hb.left - Math.min(...xs.map((q) => q.x)), r.top - hb.top - Math.min(...xs.map((q) => q.y))).multiply(T);
      } else place = new DOMMatrix().translate(r.left - hb.left, r.top - hb.top);
      const root = base.multiply(place);
      const walk = (el: Element, x: CanvasRenderingContext2D, depth: number) => {
        if (SKIP.has(el.tagName)) return;
        const st = getComputedStyle(el); if (st.display === "none") return;
        const op = el === svg ? Number(cs.opacity) : Number(st.opacity), filt = st.filter;
        const isShape = el instanceof SVGGeometryElement;
        const ctm = el instanceof SVGGraphicsElement ? (el.getCTM() ?? new DOMMatrix()) : new DOMMatrix();
        const full = root.multiply(DOMMatrix.fromMatrix(ctm));
        const scale = Math.hypot(full.a, full.b);
        const group = !isShape && (op < 1 || (filt && filt !== "none"));
        if (op <= 0) return;
        let to = x;
        if (group) to = layerCv(depth + 1);
        if (isShape) {
          if (st.visibility === "hidden") return;
          const p = shapePath(el as SVGElement); if (!p) return;
          to.save(); to.globalAlpha *= op; if (filt && filt !== "none") to.filter = canvasFilter(filt, scale, el);
          const fill = paintOf(st.fill, el, to), stroke = paintOf(st.stroke, el, to);
          if (fill) { to.setTransform(full); to.fillStyle = fill; const a = to.globalAlpha; to.globalAlpha = a * Number(st.fillOpacity); to.fill(p, st.fillRule === "evenodd" ? "evenodd" : "nonzero"); to.globalAlpha = a; }
          const sw = parseFloat(st.strokeWidth);
          if (stroke && sw > 0) {
            const nonScaling = st.vectorEffect === "non-scaling-stroke";
            let path = p, wpx = sw;
            if (nonScaling) { path = new Path2D(); path.addPath(p, DOMMatrix.fromMatrix(ctm)); to.setTransform(root); wpx = sw; }
            else to.setTransform(full);
            to.strokeStyle = stroke; to.lineWidth = wpx; to.lineCap = st.strokeLinecap as CanvasLineCap; to.lineJoin = st.strokeLinejoin as CanvasLineJoin;
            to.miterLimit = Number(st.strokeMiterlimit) || 4;
            if (st.strokeDasharray && st.strokeDasharray !== "none") {
              const pl = Number(el.getAttribute("pathLength") ?? 0), k = pl > 0 ? (el as SVGGeometryElement).getTotalLength() / pl : 1;
              to.setLineDash(st.strokeDasharray.split(/[\s,]+/).map((v) => parseFloat(v) * k)); to.lineDashOffset = parseFloat(st.strokeDashoffset) * k;
            }
            to.globalAlpha *= Number(st.strokeOpacity); to.stroke(path);
          }
          to.restore();
        } else for (const ch of el.children) walk(ch, to, group ? depth + 1 : depth);
        if (group) { x.save(); x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha *= op; x.filter = canvasFilter(filt, scale, el); x.drawImage(to.canvas, 0, 0); x.restore(); }
      };
      walk(svg, c, 0);
    }
  } };
}
