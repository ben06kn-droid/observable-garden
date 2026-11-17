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
  /** whether this browser can run it at all (half-float targets, the programs compiled) */
  get supported() { return this.ok; }
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

// ---------- the overlay: the wake over a layer drawn as SVG and 2D canvases
//
// The layer stays the page's own (its SVG keeps its clicks, focus and animation). Over it sits one WebGL
// canvas, clear everywhere except in the wake: there it repaints the layer, bent along the flow, its
// strokes turned toward the tone (by --wake-tone-mix) and split into fringes. The picture it repaints is
// the layer's parts, bottom to top: canvases that other loops draw each frame (copied only where the wake
// is), and still pictures (an SVG, replayed into a 2D canvas by `svgPart`), painted once and again only
// after `invalidate()`. Under them, the page's ground. Asleep when the fluid is still or the layer is off
// screen; nothing at all without a fine hovering pointer, or under reduced motion.

export interface Box { x: number; y: number; w: number; h: number }
/** a part of the layer: a canvas drawn by another loop, or a still picture painted in host px */
export type Part = HTMLCanvasElement | { paint: (c: CanvasRenderingContext2D) => void };
export interface WakeLayerOptions {
  /** positioned; the overlay covers its box */
  host: HTMLElement;
  /** the ground under the layer, in host px (w x h) */
  ground: (c: CanvasRenderingContext2D, w: number, h: number) => void;
  /** the layer's parts, bottom to top */
  parts: () => Part[];
  /** boxes (host px) the wake must leave alone: text, controls */
  keep?: () => Box[];
  /** the overlay's place in the host: inserted before this child (else appended) */
  before?: () => Element | null;
  /** redraw the still parts every frame while this holds (a tree swaying) */
  moving?: () => boolean;
}

const LAYER_FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr; uniform vec2 uHostVp, uView;   // the host (css px), its place in the viewport
uniform sampler2D uVel;
uniform sampler2D uLayer; uniform vec4 uBox;       // the layer's picture over uBox (host px), premultiplied
uniform sampler2D uGround, uKeep;                 // the ground; where the wake may act (r)
uniform vec3 uTone, uFringe, uHi, uShade; uniform float uFringeA, uToneMix, uGloss;
out vec4 o;
${WAKE_GLSL}
vec4 layer(vec2 p) { vec2 u = (p - uBox.xy) / uBox.zw; return (u.x < 0.0 || u.x > 1.0 || u.y < 0.0 || u.y > 1.0) ? vec4(0.0) : texture(uLayer, u); }
vec3 groundAt(vec2 p) { return texture(uGround, p / uSize).rgb; }
// how much of a stroke is at p: the layer's difference from the ground there
float ink(vec2 p) { vec4 c = layer(p); vec3 g = groundAt(p); return clamp(length(c.rgb + g * (1.0 - c.a) - g) * 3.0, 0.0, 1.0); }
vec2 flowAt(vec2 p) { return wakeFlow(uVel, uHostVp + p, uView); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  vec2 d = flowAt(p);
  float keep = texture(uKeep, p / uSize).r;
  vec2 bu = min(p - uBox.xy, uBox.xy + uBox.zw - p);               // inside the picture, away from its edge
  float s = wakeStrength(d) * keep * smoothstep(0.0, 24.0, min(bu.x, bu.y));
  if (s <= 0.0) { o = vec4(0.0); return; }
  vec3 g = groundAt(p);
  vec4 c = layer(p - d);
  vec3 col = c.rgb + g * (1.0 - c.a);
  float line = ink(p - d);
  col = mix(col, mix(g, uTone, line), s * uToneMix);
  vec2 n = wakeAcross(d, s);
  float fr = clamp(max(ink(p - d - n), ink(p - d + n)) - line, 0.0, 1.0) * s;
  col = mix(col, uFringe, clamp(fr * 0.6 * uFringeA, 0.0, 1.0));
  if (uGloss > 0.0) {
    vec2 gr = vec2(length(flowAt(p + vec2(6.0, 0.0))) - length(flowAt(p - vec2(6.0, 0.0))),
                   length(flowAt(p + vec2(0.0, 6.0))) - length(flowAt(p - vec2(0.0, 6.0))));
    col = wakeTrace(col, gr, s, (1.0 - line) * uGloss, uHi, uShade, uFringe, uFringeA).rgb;
  }
  float a = clamp(s * 4.0, 0.0, 1.0);
  o = vec4(col * a, a);
}`;

export class WakeLayer {
  readonly canvas: HTMLCanvasElement | null = null;
  private o: WakeLayerOptions; private gl: WebGL2RenderingContext | null = null; private wake: Wake | null = null;
  private prog: WebGLProgram | null = null; private u: Record<string, WebGLUniformLocation | null> = {};
  private texL: WebGLTexture | null = null; private texG: WebGLTexture | null = null; private texK: WebGLTexture | null = null;
  private w = 0; private h = 0; private dpr = 1; private col: WakeColours | null = null;
  private stills: { cv: HTMLCanvasElement; parts: Part[] }[] = []; private dirty = true;
  private stage = document.createElement("canvas"); private pts: { t: number; x: number; y: number }[] = [];
  private raf = 0; private last = 0; private shown = false; private visible: () => boolean = () => true;
  /** ms the last still repaint took (the demo's growing tree reads it) */
  paintMs = 0;

  constructor(o: WakeLayerOptions) {
    this.o = o;
    if (!wakeWanted()) return;
    const cv = document.createElement("canvas"); cv.className = "wake-layer"; cv.setAttribute("aria-hidden", "true");
    const gl = cv.getContext("webgl2", { antialias: false, alpha: true, premultipliedAlpha: true }); if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, LAYER_FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    const wake = new Wake(gl); if (!wake.supported) return;
    this.wake = wake; this.gl = gl; this.prog = p; this.canvas = cv;
    gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uHostVp", "uView", "uVel", "uLayer", "uBox", "uGround", "uKeep", "uTone", "uFringe", "uHi", "uShade", "uFringeA", "uToneMix", "uGloss"]) this.u[n] = gl.getUniformLocation(p, n);
    const tex = () => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
    this.texL = tex(); this.texG = tex(); this.texK = tex();
    o.host.insertBefore(cv, o.before?.() ?? null);
    this.visible = onScreen(o.host);
    followPointer((x, y) => { this.pts.push({ t: performance.now(), x, y }); if (this.pts.length > 400) this.pts.shift(); wake.move(x, y); this.kick(); },
      () => wake.lift(), () => this.visible());
    let t = 0; new ResizeObserver(() => { cancelAnimationFrame(t); t = requestAnimationFrame(() => this.layout()); }).observe(o.host);
    addEventListener("resize", () => this.wake?.resize(innerWidth, innerHeight));
    this.layout();
  }

  /** the still parts changed (a redraw, a tree done swaying): painted again in idle time, so the wake's
   *  first frame never waits for it */
  invalidate() {
    this.dirty = true; if (!this.gl || this.idleT) return;
    const go = () => { this.idleT = 0; if (this.dirty && !this.raf && !this.o.moving?.()) this.paintStills(this.o.parts()); };
    this.idleT = typeof requestIdleCallback === "function" ? requestIdleCallback(go, { timeout: 1000 }) : setTimeout(go, 200);
  }
  private idleT = 0;
  /** the ground, the keep mask and the sizes: after a layout change (called on the host's resize) */
  layout() {
    const gl = this.gl, cv = this.canvas; if (!gl || !cv) return;
    this.dpr = Math.min(2, devicePixelRatio || 1); this.w = Math.max(1, this.o.host.clientWidth); this.h = Math.max(1, this.o.host.clientHeight);
    cv.width = Math.round(this.w * this.dpr); cv.height = Math.round(this.h * this.dpr);
    cv.style.setProperty("--w", `${this.w}px`); cv.style.setProperty("--h", `${this.h}px`);
    this.wake?.resize(innerWidth, innerHeight);
    this.col = wakeColours(cv);
    // the ground, at a quarter of the size (it is smooth)
    const k = 0.25, gw = Math.ceil(this.w * k), gh = Math.ceil(this.h * k), gc = document.createElement("canvas"); gc.width = gw; gc.height = gh;
    const g = gc.getContext("2d")!; g.scale(k, k); this.o.ground(g, this.w, this.h);
    gl.bindTexture(gl.TEXTURE_2D, this.texG); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, gc);
    this.keepMask();
    this.dirty = true; this.shown = true; this.clear();
  }
  /** the keep mask again (the text moved) */
  keepMask() {
    const gl = this.gl; if (!gl) return;
    const k = 0.25, kw = Math.ceil(this.w * k), kh = Math.ceil(this.h * k), kc = document.createElement("canvas"); kc.width = kw; kc.height = kh;
    const c = kc.getContext("2d")!; c.fillStyle = "#fff"; c.fillRect(0, 0, kw, kh); c.fillStyle = "#000";
    for (const b of this.o.keep?.() ?? []) c.fillRect(Math.floor(b.x * k) - 1, Math.floor(b.y * k) - 1, Math.ceil(b.w * k) + 2, Math.ceil(b.h * k) + 2);
    gl.bindTexture(gl.TEXTURE_2D, this.texK); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, kc);
  }

  // the still parts, painted into canvases the size of the host (consecutive still parts share one)
  private paintStills(parts: Part[]) {
    const t0 = performance.now(), W = Math.round(this.w * this.dpr), H = Math.round(this.h * this.dpr);
    const groups: Part[][] = []; let cur: Part[] | null = null;
    for (const p of parts) { if (p instanceof HTMLCanvasElement) cur = null; else { if (!cur) { cur = []; groups.push(cur); } cur.push(p); } }
    while (this.stills.length < groups.length) this.stills.push({ cv: document.createElement("canvas"), parts: [] });
    this.stills.length = groups.length;
    groups.forEach((g, i) => {
      const s = this.stills[i]; s.parts = g;
      if (s.cv.width !== W || s.cv.height !== H) { s.cv.width = W; s.cv.height = H; }
      const c = s.cv.getContext("2d")!; c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, H);
      for (const p of g) { c.save(); c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); (p as { paint: (c: CanvasRenderingContext2D) => void }).paint(c); c.restore(); }
    });
    this.dirty = false; this.paintMs = performance.now() - t0;
  }

  private kick() { if (this.raf || !this.gl) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    this.raf = 0;
    const w = this.wake!, dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
    if (!this.visible()) { this.clear(); return; }
    w.step(dt, innerHeight);
    if (w.idle >= STILL && !w.pending) { this.clear(); return; }
    if (w.ready) this.draw(now);
    this.kick();
  };
  private clear() {
    const gl = this.gl; if (!gl || !this.shown) return;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas!.width, this.canvas!.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); this.shown = false;
  }
  private draw(now: number) {
    const gl = this.gl!, cv = this.canvas!, col = this.col!, hb = this.o.host.getBoundingClientRect();
    // where the wake can be: the cursor's recent path, widened by what the fluid carries
    const since = now - (STILL * 1000 + 200);
    while (this.pts.length && this.pts[0].t < since) this.pts.shift();
    if (!this.pts.length) { this.clear(); return; }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const q of this.pts) { x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y); x1 = Math.max(x1, q.x); y1 = Math.max(y1, q.y); }
    const M = 220, bx = Math.max(0, Math.floor(x0 - M - hb.left)), by = Math.max(0, Math.floor(y0 - M - hb.top));
    const bw = Math.min(this.w, Math.ceil(x1 + M - hb.left)) - bx, bh = Math.min(this.h, Math.ceil(y1 + M - hb.top)) - by;
    if (bw <= 0 || bh <= 0) { this.clear(); return; }
    // the picture under the wake: the still parts and the live canvases, bottom to top
    const parts = this.o.parts();
    if (this.dirty || this.o.moving?.()) this.paintStills(parts);
    const k = this.dpr, st = this.stage, sw = Math.ceil(bw * k), sh = Math.ceil(bh * k);
    if (st.width !== sw || st.height !== sh) { st.width = sw; st.height = sh; }
    const c = st.getContext("2d")!; c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, sw, sh);
    let si = 0, inStill = false;
    for (const p of parts) {
      if (p instanceof HTMLCanvasElement) {
        inStill = false;
        const r = p.getBoundingClientRect(); if (!r.width || !r.height || !p.width || !p.height) continue;
        const kx = p.width / r.width, ky = p.height / r.height, ox = r.left - hb.left, oy = r.top - hb.top;
        const sx = (bx - ox) * kx, sy = (by - oy) * ky;
        c.drawImage(p, sx, sy, bw * kx, bh * ky, 0, 0, sw, sh);
      } else if (!inStill) {
        inStill = true; const s = this.stills[si++]; if (s) c.drawImage(s.cv, bx * k, by * k, sw, sh, 0, 0, sw, sh);
      }
    }
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, cv.width, cv.height);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.texL); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, st); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.uniform1i(this.u.uLayer, 0);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.texG); gl.uniform1i(this.u.uGround, 1);
    gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D, this.texK); gl.uniform1i(this.u.uKeep, 3);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, this.wake!.texture); gl.uniform1i(this.u.uVel, 2);
    gl.uniform2f(this.u.uSize, this.w, this.h); gl.uniform1f(this.u.uDpr, k);
    gl.uniform2f(this.u.uHostVp, hb.left, hb.top); gl.uniform2f(this.u.uView, innerWidth, innerHeight);
    gl.uniform4f(this.u.uBox, bx, by, bw, bh);
    gl.uniform3f(this.u.uTone, ...col.tone); gl.uniform3f(this.u.uFringe, ...col.fringe); gl.uniform3f(this.u.uHi, ...col.hi); gl.uniform3f(this.u.uShade, ...col.shade);
    gl.uniform1f(this.u.uFringeA, col.fringeA); gl.uniform1f(this.u.uToneMix, col.toneMix); gl.uniform1f(this.u.uGloss, col.gloss);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.SCISSOR_TEST); gl.scissor(Math.floor(bx * k), Math.floor((this.h - by - bh) * k), sw + 1, sh + 1);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.disable(gl.SCISSOR_TEST);
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
function paintOf(v: string, el: Element): string | null {
  if (!v || v === "none") return null;
  const m = v.match(/url\(["']?#([^"')]+)["']?\)/);
  if (m) { const stop = el.ownerDocument.getElementById(m[1])?.querySelector("stop"); return stop ? getComputedStyle(stop).stopColor : null; }
  return v;
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
          const fill = paintOf(st.fill, el), stroke = paintOf(st.stroke, el);
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
