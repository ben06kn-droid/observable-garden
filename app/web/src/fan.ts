// The fan: a background of random paths for the run page, below the hourglass's travel.
//
// Fine hairlines start at the left edge and travel right, each a random walk (its slope an AR(1)
// process, so it wanders smoothly), the paths of one start spreading apart as they go. Most are a faint
// off-white; about one in six is in the sand tone, so several are in view at once, each starting and
// fading in its own time.
// They draw themselves left to right at a pace that follows the scroll's speed and eases back to a slow
// idle, and fade to nothing before they reach the form's fields (`reach`). New ones keep starting.
// Nothing about them is data: no axes, no labels, no scale.
//
// How it is drawn: the paths go into a 2D canvas the width of the fan (off-white in its blue channel,
// sand in its red, added like light), and one WebGL pass composites that over the page's ground, with the
// fade before `reach` and the dimming behind text (and removal under fields) from a mask texture in page
// coordinates. The canvas is fixed to the viewport, behind the page's content.
//
// The cursor's wake (src/wake.ts, after lukres.dev): moving the pointer stirs a small fluid; where it
// flows, the paths bend along it, turn a cool silver-white (a steel grey on the light ground) and split
// into fine red fringes on either side, the split following the flow; as it fades (about a quarter of a
// second) they return to their own white and gold. Only pointer movement drives it (not touch); it
// touches the paths only (the fan is behind the page's text).
//
// Reduced motion: a still fan, no wake.

import { Wake } from "./wake";

export interface FanRect { x: number; y: number; w: number; h: number; keep: number }   // page px; keep 0 = no lines there
export interface FanOptions {
  /** the fan's vertical extent, in page px */
  region: () => { top: number; bottom: number };
  /** for a page y, the x (page px) at which the paths must have faded to nothing */
  reach: (y: number) => number;
  /** text and fields over the fan: the lines are dimmed (keep ~0.3) or removed (keep 0) there */
  masks?: () => FanRect[];
  reduce?: boolean;
  seed?: number;
  /** the cursor's wake (off on a phone) */
  wake?: boolean;
  /** the last `foot` px of the region: paths that start there slow, stop, and stay */
  foot?: number;
}

interface Path {
  y0: number; ys: Float32Array; head: number; delay: number; speed: number;
  life: number; dying: boolean; sand: boolean; minY: number; maxY: number; rest: boolean;
}

const DX = 3;                                  // the walk's step, css px
const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uView; uniform float uDpr, uScroll; uniform vec2 uRegion;   // the canvas (css px); its page y; the fan's extent
uniform vec2 uVp; uniform float uVpOff;            // the viewport, and the canvas's top in it
uniform vec3 uGround, uLine, uSand, uSilver, uRed, uHi, uShade; uniform float uWA, uSA, uRedA;
uniform sampler2D uPaths; uniform float uFanW;
uniform sampler2D uMask; uniform vec4 uMaskBox;
uniform sampler2D uVel; uniform float uWake;
out vec4 o;
vec2 maskAt(vec2 p) { return texture(uMask, (vec2(p.x, p.y + uScroll) - uMaskBox.xy) / uMaskBox.zw).rg; }
// the lines' coverage at a canvas point: (white, gold), faded before the fields and dimmed behind text
vec2 cov(vec2 p) {
  if (p.x < 0.0 || p.x > uFanW || p.y < 0.0 || p.y > uView.y) return vec2(0.0);
  vec4 t = texture(uPaths, vec2(p.x / uFanW, p.y / uView.y));
  return clamp(vec2(t.b * uWA, t.r * uSA) * maskAt(p).r, 0.0, 1.0);
}
// the wake's displacement at a canvas point (css px), from the viewport's fluid
vec2 flowAt(vec2 p) {
  vec2 vp = vec2(p.x, p.y + uVpOff);
  vec2 v = texture(uVel, vec2(vp.x, uVp.y - vp.y) / uVp).xy;
  vec2 d = vec2(v.x, -v.y) * 0.016; float l = length(d);
  return l > 26.0 ? d * 26.0 / l : d;
}
void main() {
  vec2 pc = vec2(gl_FragCoord.x, uView.y * uDpr - gl_FragCoord.y) / uDpr;
  float py = pc.y + uScroll;
  if (py < uRegion.x || py > uRegion.y) { o = vec4(0.0); return; }
  vec2 d = uWake > 0.0 ? flowAt(pc) : vec2(0.0);
  float s = uWake * smoothstep(0.6, 7.0, length(d));
  vec2 a = cov(pc - d);
  vec3 col = mix(mix(uGround, uLine, a.x), uSand, a.y);
  float alpha = max(a.x, a.y);
  if (s > 0.0) {
    // the lines: silver-white where it flows, a thin red fringe each side, across them along the flow
    float line = max(a.x * 2.4, a.y * 1.2);
    col = mix(col, mix(uGround, uSilver, clamp(line, 0.0, 1.0)), s);
    vec2 n = normalize(d) * mix(0.7, 1.3, s);
    vec2 f0 = cov(pc - d - n), f1 = cov(pc - d + n);
    float fr = clamp(max(max(f0.x * 2.4, f0.y * 1.2), max(f1.x * 2.4, f1.y * 1.2)) - line, 0.0, 1.0) * s;
    col = mix(col, uRed, clamp(fr * 0.6 * uRedA, 0.0, 1.0));
    alpha = max(alpha, max(line * s, fr));
    // the blank space: the wake itself, glossy. Its strength is read as a surface: a bright highlight on the
    // side that faces a light from the upper left, a soft shade on the other, a fine red line at its rim; no
    // flat tint (which reads as dust). Never under a field.
    float blank = (1.0 - clamp(line, 0.0, 1.0)) * maskAt(pc).g;
    vec2 gr = vec2(length(flowAt(pc + vec2(6.0, 0.0))) - length(flowAt(pc - vec2(6.0, 0.0))),
                   length(flowAt(pc + vec2(0.0, 6.0))) - length(flowAt(pc - vec2(0.0, 6.0))));
    float slope = smoothstep(0.6, 6.0, length(gr));
    float face = dot(gr / (length(gr) + 1e-4), normalize(vec2(-0.6, -0.8)));
    float spec = pow(max(face, 0.0), 2.0) * slope * s, shade = max(-face, 0.0) * slope * s;
    float rim = smoothstep(0.82, 0.97, slope) * (1.0 - smoothstep(0.97, 1.0, slope)) * s;   // a hairline
    vec3 base = alpha > 0.0 ? col : uGround;
    vec3 g = mix(base, uHi, clamp(0.22 * spec * blank, 0.0, 1.0));
    g = mix(g, uShade, clamp(0.10 * shade * blank, 0.0, 1.0));
    g = mix(g, uRed, clamp(0.08 * uRedA * rim * blank, 0.0, 1.0));
    float ga = clamp((0.22 * spec + 0.10 * shade + 0.08 * rim) * blank, 0.0, 1.0);
    col = g; alpha = max(alpha, ga);
  }
  o = vec4(col, alpha > 0.0 ? 1.0 : 0.0);
}`;

function rgb(s: string): [number, number, number] {
  let h = s.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1];
  if (h) { if (h.length === 3) h = h.replace(/./g, "$&$&"); const n = parseInt(h, 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
  const r = s.match(/(\d+(\.\d+)?)/g); return r ? [Number(r[0]) / 255, Number(r[1]) / 255, Number(r[2]) / 255] : [0, 0, 0];
}
function mulberry(a: number) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

export class Fan {
  readonly canvas: HTMLCanvasElement;
  private o: FanOptions; private gl: WebGL2RenderingContext | null = null; private u: Record<string, WebGLUniformLocation | null> = {};
  private paths: Path[] = []; private ctx: CanvasRenderingContext2D; private pcv: HTMLCanvasElement;
  private texP: WebGLTexture | null = null; private texM: WebGLTexture | null = null;
  private maskBox = [0, 0, 1, 1]; private fanW = 300; private dpr = 1; private vw = 0; private vh = 0;
  // the canvas sits in the page (it scrolls with the text, so the two never drift apart): the viewport and
  // a margin above and below, re-anchored to the scroll each frame it draws
  private margin = 0; private ch = 0; private top = 0; private redA = 1;
  private rnd: () => number; private raf = 0; private last = 0; private running = false;
  private speed = 55; private scrollV = 0; private lastScroll = 0; private lastScrollT = 0; private sinceSpawn = 9;
  private ground: [number, number, number] = [0, 0, 0]; private line: [number, number, number] = [1, 1, 1];
  private sand: [number, number, number] = [0.84, 0.7, 0.48]; private wa = 0.2;
  private silver: [number, number, number] = [0.86, 0.89, 0.94]; private red: [number, number, number] = [0.9, 0.28, 0.3];
  private prog: WebGLProgram | null = null; private wake: Wake | null = null;
  private hi: [number, number, number] = [1, 1, 1]; private shade: [number, number, number] = [0, 0, 0];
  private onMove = (e: PointerEvent) => { if (e.pointerType !== "touch") this.wake?.move(e.clientX, e.clientY); };
  private onLeave = () => this.wake?.lift();
  private onScroll = () => {
    const now = performance.now(), y = scrollY, dt = Math.max(8, now - this.lastScrollT);
    this.scrollV = 0.6 * this.scrollV + 0.4 * ((y - this.lastScroll) / dt) * 1000;
    this.lastScroll = y; this.lastScrollT = now;
    if (this.o.reduce) this.render(); else this.wakeUp();
  };
  private onResize = () => { this.layout(); };

  constructor(host: HTMLElement, o: FanOptions) {
    this.o = o; this.rnd = mulberry(o.seed ?? 11);
    this.canvas = document.createElement("canvas"); this.canvas.className = "fan"; this.canvas.setAttribute("aria-hidden", "true");
    host.prepend(this.canvas);
    this.pcv = document.createElement("canvas"); this.ctx = this.pcv.getContext("2d")!;
    this.initGL(); this.readPalette(); this.layout();
    this.lastScroll = scrollY; this.lastScrollT = performance.now();
    addEventListener("scroll", this.onScroll, { passive: true });
    addEventListener("resize", this.onResize);
    if (this.wake) { addEventListener("pointermove", this.onMove, { passive: true }); document.documentElement.addEventListener("pointerleave", this.onLeave, { passive: true }); }
    if (o.reduce) this.still(); else this.wakeUp();
  }
  destroy() {
    this.running = false; cancelAnimationFrame(this.raf); removeEventListener("scroll", this.onScroll); removeEventListener("resize", this.onResize);
    removeEventListener("pointermove", this.onMove); document.documentElement.removeEventListener("pointerleave", this.onLeave); this.canvas.remove();
  }

  /** read the colours from the page's tokens (after a palette swap, for one) */
  refreshPalette() { this.readPalette(); this.render(); }
  private readPalette() {
    const cs = getComputedStyle(this.canvas);
    this.ground = rgb(cs.getPropertyValue("--fan-ground") || "#121416"); this.line = rgb(cs.getPropertyValue("--fan-line") || "#f0f1fa");
    this.sand = rgb(cs.getPropertyValue("--fan-sand") || "#d6b27b"); this.wa = Number(cs.getPropertyValue("--fan-alpha")) || 0.2;
    this.silver = rgb(cs.getPropertyValue("--wake-silver") || "#dce2ef"); this.red = rgb(cs.getPropertyValue("--wake-red") || "#e5484d");
    this.redA = Number(cs.getPropertyValue("--wake-red-alpha")) || 1;
    this.hi = rgb(cs.getPropertyValue("--wake-hi") || "#ffffff"); this.shade = rgb(cs.getPropertyValue("--wake-shade") || "#000000");
  }

  /** sizes, the reach, the masks: call after a layout change */
  layout() {
    this.dpr = Math.min(2, devicePixelRatio || 1); this.vw = innerWidth; this.vh = innerHeight;
    const r = this.o.region();
    let maxReach = 0; for (let y = r.top; y <= r.bottom; y += 40) maxReach = Math.max(maxReach, this.o.reach(y));
    this.fanW = Math.max(40, Math.min(this.vw, Math.ceil(maxReach + 8)));
    this.margin = Math.round(this.vh * 0.35); this.ch = this.vh + 2 * this.margin;
    this.canvas.style.setProperty("--fan-h", `${this.ch}px`);
    this.canvas.width = Math.round(this.vw * this.dpr); this.canvas.height = Math.round(this.ch * this.dpr);
    this.wake?.resize(this.vw, this.vh);
    this.pcv.width = Math.round(this.fanW * this.dpr); this.pcv.height = Math.round(this.ch * this.dpr);
    this.buildMask();
    if (this.o.reduce) this.still(); else this.render();
  }

  // ---------- the mask: the fade before the reach, dimmed behind text, none under fields
  private buildMask() {
    const gl = this.gl; if (!gl) return;
    const r = this.o.region(), k = 0.25, W = Math.ceil(this.vw * k), H = Math.max(1, Math.ceil((r.bottom - r.top) * k));
    const data = new Uint8Array(W * H * 4);
    for (let j = 0; j < H; j++) {
      const y = r.top + (j + 0.5) / k, reach = this.o.reach(y), fade0 = reach * 0.72;
      for (let i = 0; i < W; i++) {
        const x = (i + 0.5) / k;
        const t = Math.max(0, Math.min(1, (x - fade0) / Math.max(1, reach - fade0)));
        let keep = 1 - t * t * (3 - 2 * t); if (x < 6) keep *= x / 6;
        const o = (j * W + i) * 4; data[o] = Math.round(keep * 255); data[o + 1] = 255; data[o + 3] = 255;
      }
    }
    for (const m of this.o.masks?.() ?? []) {
      const i0 = Math.max(0, Math.floor(m.x * k)), i1 = Math.min(W - 1, Math.ceil((m.x + m.w) * k));
      const j0 = Math.max(0, Math.floor((m.y - r.top) * k)), j1 = Math.min(H - 1, Math.ceil((m.y + m.h - r.top) * k));
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) { const o = (j * W + i) * 4; data[o] = Math.round(data[o] * m.keep); if (m.keep === 0) data[o + 1] = 0; }
    }
    gl.bindTexture(gl.TEXTURE_2D, this.texM);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, W, H, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
    this.maskBox = [0, r.top, W / k, H / k];
  }

  private initGL() {
    const gl = this.canvas.getContext("webgl2", { antialias: false, premultipliedAlpha: false, alpha: true });
    if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    gl.useProgram(p); this.prog = p;
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uView", "uDpr", "uScroll", "uRegion", "uVp", "uVpOff", "uRedA", "uHi", "uShade", "uGround", "uLine", "uSand", "uSilver", "uRed", "uWA", "uSA", "uPaths", "uFanW", "uMask", "uMaskBox", "uVel", "uWake"]) this.u[n] = gl.getUniformLocation(p, n);
    const tex = () => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
    this.texP = tex(); this.texM = tex();
    this.gl = gl;
    if (this.o.wake && !this.o.reduce) { const w = new Wake(gl); if (w) this.wake = w; }
  }

  // ---------- the paths
  private spawn(y0: number) {
    const reach = this.o.reach(y0), n = Math.ceil(reach / DX) + 2;
    const r = this.o.region(), rest = !!this.o.foot && y0 > r.bottom - this.o.foot;
    const count = 7 + Math.floor(this.rnd() * 6), phi = 0.9;
    // the paths' wander grows with their length, so a long fan opens as wide, for its length, as a short one
    const spread = (70 + this.rnd() * 90) * Math.sqrt(Math.max(1, reach / 320));
    for (let q = 0; q < count; q++) {
      const ys = new Float32Array(n); let v = 0, y = y0, mn = y0, mx = y0;
      const sigma = spread * (1 - phi) / Math.sqrt(n) * (0.7 + this.rnd() * 0.6);
      const drift = ((q + 0.5) / count - 0.5) * spread * 0.9 / n;   // a slight lean each, so they open like a fan
      for (let i = 0; i < n; i++) {
        const g = Math.sqrt(-2 * Math.log(this.rnd() + 1e-9)) * Math.cos(2 * Math.PI * this.rnd());
        v = phi * v + sigma * g; y += v + drift; ys[i] = y; mn = Math.min(mn, y); mx = Math.max(mx, y);
      }
      this.paths.push({ rest, y0, ys, head: 0, delay: q * (0.08 + this.rnd() * 0.16) + this.rnd() * 0.3, speed: 0.85 + this.rnd() * 0.3,
        life: 1, dying: false, sand: this.rnd() < 1 / 6, minY: mn - 2, maxY: mx + 2 });
    }
  }
  private visibleBand() { const r = this.o.region(); return [Math.max(r.top + 20, scrollY - this.vh * 0.1), Math.min(r.bottom - 20, scrollY + this.vh * 1.05)]; }
  private step(dt: number) {
    // the pace: a slow idle, quicker while the page scrolls, easing back
    this.scrollV *= Math.exp(-dt / 0.25);
    const target = 55 + Math.min(1300, Math.abs(this.scrollV) * 1.4);
    this.speed += (target - this.speed) * (1 - Math.exp(-dt / (target > this.speed ? 0.18 : 0.6)));
    const [b0, b1] = this.visibleBand();
    // new starts while there is room in view, each at least 60 px from the others' starts
    this.sinceSpawn += dt * this.speed / 55;
    const live = this.paths.filter((p) => !p.dying && p.y0 > b0 - 200 && p.y0 < b1 + 200);
    if (b1 > b0 && this.sinceSpawn > 0.6 && new Set(live.map((p) => p.y0)).size < Math.max(3, Math.round((b1 - b0) / 110))) {
      for (let a = 0; a < 8; a++) {
        const y = b0 + this.rnd() * (b1 - b0);
        if (!live.some((p) => Math.abs(p.y0 - y) < 60)) { this.spawn(y); this.sinceSpawn = 0; break; }
      }
    }
    for (const p of this.paths) {
      if (p.delay > 0) { p.delay -= dt; continue; }
      const n = p.ys.length - 1;
      // in the foot the paths slow as they go and come to rest, and stay
      const pace = p.rest ? 0.4 * Math.pow(Math.max(0, 1 - p.head / (n * 0.8)), 0.7) : 1;
      p.head = Math.min(p.rest ? n * 0.8 : n, p.head + (this.speed * p.speed * pace * dt) / DX);
      if (!p.rest && p.head >= n) p.dying = true;
      if (p.dying) p.life -= dt / 2.4;
    }
    this.paths = this.paths.filter((p) => p.life > 0);
  }

  private drawPaths() {
    const x = this.ctx, k = this.dpr;
    x.setTransform(1, 0, 0, 1, 0, 0); x.globalCompositeOperation = "source-over"; x.fillStyle = "#000"; x.fillRect(0, 0, this.pcv.width, this.pcv.height);
    x.setTransform(k, 0, 0, k, 0, -this.top * k); x.globalCompositeOperation = "lighter";
    x.lineJoin = "round"; x.lineCap = "round";
    const top = this.top - 4, bot = this.top + this.ch + 4;
    for (const p of this.paths) {
      if (p.delay > 0 || p.maxY < top || p.minY > bot || p.head < 1) continue;
      const n = Math.floor(p.head), f = p.head - n, a = Math.max(0, Math.min(1, p.life));
      x.beginPath(); x.moveTo(0, p.ys[0]);
      for (let i = 1; i < n; i++) x.quadraticCurveTo(i * DX, p.ys[i], (i + 0.5) * DX, (p.ys[i] + p.ys[i + 1]) / 2);
      if (n + 1 < p.ys.length) x.lineTo((n + f) * DX, p.ys[n] + (p.ys[n + 1] - p.ys[n]) * f); else x.lineTo(n * DX, p.ys[n]);
      x.lineWidth = p.sand ? 1.0 : 0.8;
      x.strokeStyle = p.sand ? `rgba(255,0,0,${a.toFixed(3)})` : `rgba(0,0,255,${a.toFixed(3)})`;
      x.stroke();
    }
  }

  render() {
    const gl = this.gl; if (!gl || !this.prog) return;
    // anchor: the margin above the viewport, kept inside the page (so it never lengthens it)
    const docH = document.documentElement.scrollHeight;
    this.top = Math.max(0, Math.min(scrollY - this.margin, docH - this.ch));
    this.canvas.style.transform = `translate3d(0, ${this.top}px, 0)`;
    this.drawPaths();
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    const r = this.o.region();
    gl.uniform2f(this.u.uView, this.vw, this.ch); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uScroll, this.top);
    gl.uniform2f(this.u.uVp, this.vw, this.vh); gl.uniform1f(this.u.uVpOff, this.top - scrollY); gl.uniform1f(this.u.uRedA, this.redA);
    gl.uniform2f(this.u.uRegion, r.top, r.bottom);
    gl.uniform3f(this.u.uGround, ...this.ground); gl.uniform3f(this.u.uLine, ...this.line); gl.uniform3f(this.u.uSand, ...this.sand);
    gl.uniform1f(this.u.uWA, this.wa); gl.uniform1f(this.u.uSA, 0.95);
    gl.uniform3f(this.u.uSilver, ...this.silver); gl.uniform3f(this.u.uRed, ...this.red); gl.uniform3f(this.u.uHi, ...this.hi); gl.uniform3f(this.u.uShade, ...this.shade);
    const w = this.wake, on = !!w?.ready && w.idle < 0.8;
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(this.u.uVel, 2); gl.uniform1f(this.u.uWake, on ? 1 : 0);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.texP);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.pcv); gl.uniform1i(this.u.uPaths, 0);
    gl.uniform1f(this.u.uFanW, this.fanW);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.texM); gl.uniform1i(this.u.uMask, 1);
    gl.uniform4f(this.u.uMaskBox, this.maskBox[0], this.maskBox[1], this.maskBox[2], this.maskBox[3]);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  // ---------- the loop: runs while the fan is in view, else sleeps until a scroll
  private wakeUp() { if (this.running || this.o.reduce) return; this.running = true; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
    const r = this.o.region(), inView = r.bottom > scrollY && r.top < scrollY + this.vh;
    if (!inView) { this.render(); this.running = false; return; }
    this.step(dt); this.wake?.step(dt, this.vh); this.render();
    this.raf = requestAnimationFrame(this.frame);
  };

  /** reduced motion: the fan drawn once, its paths complete and still; redrawn on scroll */
  private still() {
    if (!this.paths.length) {
      const r = this.o.region();
      for (let y = r.top + 60; y < r.bottom - 40; y += 150 + this.rnd() * 60) this.spawn(y);
      for (const p of this.paths) { p.delay = 0; p.head = (p.ys.length - 1) * (0.55 + this.rnd() * 0.45); }
    }
    this.render();
  }
}
