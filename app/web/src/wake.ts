// The cursor's wake over the fan: a small fluid simulation, after lukres.dev's cursor effect. The
// pointer's movement pushes velocity into the fluid along its path; small curls are kept alive
// (vorticity confinement); the fluid is made incompressible (a few pressure iterations) and fades
// slowly (gone about a second after the cursor stops). The fan's composite reads the
// velocity to bend its paths along the wake and colour them silver-white with fine red fringes there.
//
// It runs at an eighth of the viewport's size, in the fan's own WebGL2 context, on half-float targets
// (EXT_color_buffer_float). Without them there is no wake and the fan is drawn as before. Velocity is
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
