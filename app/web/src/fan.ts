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
// The cursor's wake (src/cursorwake.ts, the site's shared effect, after lukres.dev): moving the pointer
// stirs a small fluid; where it flows, the paths bend along it, turn the page's tone (--wake-tone: a cool
// silver-white, a steel grey on the light ground) and split into fine fringes in --wake-fringe (red) on
// either side, the split following the flow; as it fades they return to their own white. The gold paths bend
// with it but keep their own gold throughout: no tone and no fringe on them, in either palette. Only
// cursor movement drives it (not touch, not a drag); it touches the paths only (the fan is behind the
// page's text).
//
// Reduced motion: a still fan, no wake.

import { followPointer, rgb, STILL, Wake, WAKE_GLSL, wakeColours, type RGB } from "./cursorwake";

// page px; keep 0 = no lines there; trace: the share of the wake's glossy trace kept there (default 1, 0 where keep is 0)
export interface FanRect { x: number; y: number; w: number; h: number; keep: number; trace?: number }
/** text whose letters dim the paths behind them (and only its letters, a few px around each, not its box) */
export interface FanGlyphs { el: Element; keep: number; trace?: number }
export interface FanOptions {
  /** the fan's vertical extent, in page px */
  region: () => { top: number; bottom: number };
  /** for a page y, the x (page px) at which the paths must have faded to nothing */
  reach: (y: number) => number;
  /** text and fields over the fan: the lines are dimmed (keep ~0.3) or removed (keep 0) there */
  masks?: () => FanRect[];
  /** text over the fan whose letters themselves dim the lines (keep) and the wake's trace (trace, default keep) */
  glyphs?: () => FanGlyphs[];
  reduce?: boolean;
  seed?: number;
  /** the cursor's wake (off on a phone) */
  wake?: boolean;
  /** the last `foot` px of the region: paths that start there slow, stop, and stay */
  foot?: number;
  /** every path complete and still from the first frame: none grows, starts or fades; the loop runs only while the
   *  wake moves (the Contact page) */
  full?: boolean;
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
uniform vec3 uGround, uLine, uSand, uTone, uFringe, uHi, uShade; uniform float uWA, uSA, uFringeA, uFringeMix; uniform vec2 uFringeOff;
uniform sampler2D uPaths; uniform float uFanW;
uniform sampler2D uMask; uniform vec4 uMaskBox;
uniform sampler2D uGlyph; uniform vec4 uGlyphBox;   // the letters' mask: full resolution, over the text's extent only
uniform sampler2D uVel; uniform float uWake;
out vec4 o;
${WAKE_GLSL}
vec2 glyphAt(vec2 q) {
  if (uGlyphBox.z <= 0.0) return vec2(1.0);
  vec2 uv = (q - uGlyphBox.xy) / uGlyphBox.zw;
  return any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0))) ? vec2(1.0) : texture(uGlyph, uv).rg;
}
vec2 maskAt(vec2 p) { vec2 q = vec2(p.x, p.y + uScroll); return texture(uMask, (q - uMaskBox.xy) / uMaskBox.zw).rg * glyphAt(q); }
// the lines' coverage at a canvas point: (white, gold). The fade before the fields and the dimming behind text are
// applied where a line is drawn (the mask at the output pixel, main()), so a line the wake bends under a letter is
// dimmed there, and one bent out from under it is not
vec2 cov(vec2 p) {
  if (p.x < 0.0 || p.x > uFanW || p.y < 0.0 || p.y > uView.y) return vec2(0.0);
  vec4 t = texture(uPaths, vec2(p.x / uFanW, p.y / uView.y));
  return clamp(vec2(t.b * uWA, t.r * uSA), 0.0, 1.0);
}
// the wake's displacement at a canvas point (css px), from the viewport's fluid
vec2 flowAt(vec2 p) { return wakeFlow(uVel, vec2(p.x, p.y + uVpOff), uVp); }
void main() {
  vec2 pc = vec2(gl_FragCoord.x, uView.y * uDpr - gl_FragCoord.y) / uDpr;
  float py = pc.y + uScroll;
  if (py < uRegion.x || py > uRegion.y) { o = vec4(0.0); return; }
  vec2 d = uWake > 0.0 ? flowAt(pc) : vec2(0.0);
  float s = uWake * wakeStrength(d);
  // dimmed where it is drawn (2026-11-18: by the mask where it came from, a line bent under a letter from open space
  // arrived there undimmed)
  vec2 md = maskAt(pc);
  vec2 a = cov(pc - d) * md.r;
  vec3 col = mix(mix(uGround, uLine, a.x), uSand, a.y);
  float alpha = max(a.x, a.y);
  if (s > 0.0) {
    // the white lines: the tone where it flows, a thin fringe each side, across them along the flow. The gold
    // lines keep their own colour (they bend, but take no tone and no fringe): the white is toned and fringed
    // first, then the gold laid over it by its own coverage, so a gold line stays gold along its whole length,
    // over or beside a toned white one, and as it fades in or out
    float lw = clamp(a.x * 2.4, 0.0, 1.0);
    vec3 cw = mix(mix(uGround, uLine, a.x), mix(uGround, uTone, lw), s);
    vec2 n = normalize(d + 1e-5) * mix(uFringeOff.x, uFringeOff.y, s);    // the fringe's offset (the theme's)
    vec2 f0 = cov(pc - d - n) * md.r, f1 = cov(pc - d + n) * md.r;
    float fr = clamp(max(f0.x, f1.x) * 2.4 - lw, 0.0, 1.0) * s;
    cw = mix(cw, uFringe, clamp(fr * uFringeMix * uFringeA, 0.0, 1.0));
    col = mix(cw, uSand, a.y);
    float line = max(lw, clamp(a.y * 1.2, 0.0, 1.0));
    alpha = max(alpha, max(lw * s, fr));
    // the blank space: the wake itself, a glossy trace (wakeTrace). Never under a field.
    float blank = (1.0 - clamp(line, 0.0, 1.0)) * md.g;
    vec2 gr = vec2(length(flowAt(pc + vec2(6.0, 0.0))) - length(flowAt(pc - vec2(6.0, 0.0))),
                   length(flowAt(pc + vec2(0.0, 6.0))) - length(flowAt(pc - vec2(0.0, 6.0))));
    vec4 tr = wakeTrace(alpha > 0.0 ? col : uGround, gr, s, blank, uHi, uShade, uFringe, uFringeA);
    col = tr.rgb; alpha = max(alpha, tr.a);
  }
  o = vec4(col, alpha > 0.0 ? 1.0 : 0.0);
}`;

function mulberry(a: number) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

export class Fan {
  readonly canvas: HTMLCanvasElement;
  private o: FanOptions; private gl: WebGL2RenderingContext | null = null; private u: Record<string, WebGLUniformLocation | null> = {};
  private paths: Path[] = []; private ctx: CanvasRenderingContext2D; private pcv: HTMLCanvasElement;
  private texP: WebGLTexture | null = null; private texM: WebGLTexture | null = null; private texG: WebGLTexture | null = null;
  private glyphBox = [0, 0, 0, 0];
  private maskBox = [0, 0, 1, 1]; private fanW = 300; private dpr = 1; private vw = 0; private vh = 0;
  // the canvas sits in the page (it scrolls with the text, so the two never drift apart): the viewport and
  // a margin above and below, re-anchored to the scroll each frame it draws
  private margin = 0; private ch = 0; private top = 0; private fringeA = 1;
  private rnd: () => number; private raf = 0; private last = 0; private running = false;
  private speed = 55; private scrollV = 0; private lastScroll = 0; private lastScrollT = 0; private sinceSpawn = 9;
  private ground: RGB = [0, 0, 0]; private line: RGB = [1, 1, 1];
  private sand: RGB = [0.84, 0.7, 0.48]; private wa = 0.2;
  private tone: RGB = [0.86, 0.89, 0.94]; private fringe: RGB = [0.9, 0.28, 0.3]; private fringeMix = 0.6; private fringeOff: [number, number] = [0.7, 1.3];
  private prog: WebGLProgram | null = null; private wake: Wake | null = null;
  private hi: RGB = [1, 1, 1]; private shade: RGB = [0, 0, 0];
  private unfollow = () => {};
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
    if (this.wake) { const w = this.wake; this.unfollow = followPointer((x, y) => { w.move(x, y); this.wakeUp(); }, () => w.lift()); }
    if (o.full) this.fill();
    if (o.reduce) this.still(); else if (o.full) this.render(); else this.wakeUp();
  }
  destroy() {
    this.running = false; cancelAnimationFrame(this.raf); removeEventListener("scroll", this.onScroll); removeEventListener("resize", this.onResize);
    this.unfollow(); this.canvas.remove();
    // the context released at once (it is rebuilt on a resize): left to the collector, contexts piled up until the
    // browser dropped the oldest (its limit is 16 a page), and their GPU memory with them
    this.gl?.getExtension("WEBGL_lose_context")?.loseContext(); this.gl = null;
  }

  /** read the colours from the page's tokens (after a palette swap, for one) */
  refreshPalette() { this.readPalette(); this.render(); }
  private readPalette() {
    const cs = getComputedStyle(this.canvas);
    this.ground = rgb(cs.getPropertyValue("--fan-ground") || "#121416"); this.line = rgb(cs.getPropertyValue("--fan-line") || "#f0f1fa");
    this.sand = rgb(cs.getPropertyValue("--fan-sand") || "#d6b27b"); this.wa = Number(cs.getPropertyValue("--fan-alpha")) || 0.2;
    const w = wakeColours(this.canvas); this.tone = w.tone; this.fringe = w.fringe; this.fringeA = w.fringeA; this.fringeMix = w.fringeMix; this.fringeOff = w.fringeOff; this.hi = w.hi; this.shade = w.shade;
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
      const tr = m.trace ?? (m.keep === 0 ? 0 : 1);
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) { const o = (j * W + i) * 4; data[o] = Math.round(data[o] * m.keep); data[o + 1] = Math.round(data[o + 1] * tr); }
    }
    gl.bindTexture(gl.TEXTURE_2D, this.texM);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, W, H, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
    this.maskBox = [0, r.top, W / k, H / k];
    this.buildGlyphs();
  }

  // ---------- the letters' mask: each letter drawn in its own font where it lies, a few px thicker, at full resolution,
  // over the text's extent only (outside it the shader reads 1). The paths dim behind the letters, not the boxes
  private buildGlyphs() {
    const gl = this.gl; if (!gl) return;
    const items = this.o.glyphs?.() ?? [], y0 = scrollY, SPREAD = 4;
    type Word = { text: string; x: number; y: number; h: number; font: string; ls: string; colour: string };
    const words: Word[] = [], range = document.createRange();
    let x0 = Infinity, x1 = -Infinity, t0 = Infinity, t1 = -Infinity;
    for (const g of items) {
      const colour = `rgb(${Math.round(g.keep * 255)}, ${Math.round((g.trace ?? g.keep) * 255)}, 0)`;
      const walk = document.createTreeWalker(g.el, NodeFilter.SHOW_TEXT);
      for (let n = walk.nextNode() as Text | null; n; n = walk.nextNode() as Text | null) {
        const cs = getComputedStyle(n.parentElement!);
        if (cs.visibility === "hidden" || cs.display === "none") continue;
        const font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
        // letter by letter, each where the browser put it (a long word drawn as one string drifted a few px from the
        // page's own layout: a thin stroke of the email's 'l' escaped the mask)
        for (const m of n.data.matchAll(/\S/gu)) {
          range.setStart(n, m.index!); range.setEnd(n, m.index! + m[0].length);
          const r = range.getBoundingClientRect(); if (!r.width) continue;
          words.push({ text: m[0], x: r.left, y: r.top + y0, h: r.height, font, ls: "0px", colour });
          x0 = Math.min(x0, r.left); x1 = Math.max(x1, r.right); t0 = Math.min(t0, r.top + y0); t1 = Math.max(t1, r.bottom + y0);
        }
      }
    }
    if (!words.length) { this.glyphBox = [0, 0, 0, 0]; return; }
    const pad = SPREAD + 4, bx = Math.floor(x0 - pad), by = Math.floor(t0 - pad);
    const W = Math.max(1, Math.ceil(x1 - x0 + 2 * pad)), H = Math.max(1, Math.ceil(t1 - t0 + 2 * pad));
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const x = c.getContext("2d")!;
    x.fillStyle = "#fff"; x.fillRect(0, 0, W, H);
    x.lineJoin = "round"; x.lineWidth = 2 * SPREAD; x.textBaseline = "alphabetic";
    for (const w of words) {
      x.font = w.font; (x as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = w.ls === "normal" ? "0px" : w.ls;
      const fm = x.measureText(w.text), asc = fm.fontBoundingBoxAscent, desc = fm.fontBoundingBoxDescent;
      const base = w.y - by + (w.h - (asc + desc)) / 2 + asc;   // the line box's content area, centred as the browser does
      x.fillStyle = x.strokeStyle = w.colour;
      x.strokeText(w.text, w.x - bx, base); x.fillText(w.text, w.x - bx, base);
    }
    // a 3x3 minimum over the mask: small separate contours (the dot of an i) came out with a hole in the middle, where a
    // path showed through the letter (measured 3.4:1 on Contact's email); this closes them
    const im = x.getImageData(0, 0, W, H), src = new Uint8ClampedArray(im.data), d = im.data;
    for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
      let r = 255, g = 255;
      for (let dj = -1; dj <= 1; dj++) { const jj = j + dj; if (jj < 0 || jj >= H) continue;
        for (let di = -1; di <= 1; di++) { const ii = i + di; if (ii < 0 || ii >= W) continue; const o = (jj * W + ii) * 4; if (src[o] < r) r = src[o]; if (src[o + 1] < g) g = src[o + 1]; } }
      const o = (j * W + i) * 4; d[o] = r; d[o + 1] = g;
    }
    x.putImageData(im, 0, 0);
    if (import.meta.env.DEV) (window as unknown as { __fanGlyphs?: unknown }).__fanGlyphs = { c, bx, by };   // for checking the mask in development
    gl.bindTexture(gl.TEXTURE_2D, this.texG);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
    this.glyphBox = [bx, by, W, H];
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
    for (const n of ["uView", "uDpr", "uScroll", "uRegion", "uVp", "uVpOff", "uFringeA", "uHi", "uShade", "uGround", "uLine", "uSand", "uTone", "uFringe", "uWA", "uSA", "uFringeMix", "uFringeOff", "uPaths", "uFanW", "uMask", "uMaskBox", "uGlyph", "uGlyphBox", "uVel", "uWake"]) this.u[n] = gl.getUniformLocation(p, n);
    const tex = () => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
    this.texP = tex(); this.texM = tex(); this.texG = tex();
    this.gl = gl;
    // steps of 1/20 s: Safari's look here (about 20 frames a second)
    if (this.o.wake && !this.o.reduce) { const w = new Wake(gl, { step: 1 / 20 }); if (w) this.wake = w; }
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
    if (this.o.full) return;   // complete and still: nothing grows, starts or fades
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
    gl.uniform2f(this.u.uVp, this.vw, this.vh); gl.uniform1f(this.u.uVpOff, this.top - scrollY); gl.uniform1f(this.u.uFringeA, this.fringeA); gl.uniform1f(this.u.uFringeMix, this.fringeMix); gl.uniform2f(this.u.uFringeOff, this.fringeOff[0], this.fringeOff[1]);
    gl.uniform2f(this.u.uRegion, r.top, r.bottom);
    gl.uniform3f(this.u.uGround, ...this.ground); gl.uniform3f(this.u.uLine, ...this.line); gl.uniform3f(this.u.uSand, ...this.sand);
    gl.uniform1f(this.u.uWA, this.wa); gl.uniform1f(this.u.uSA, 0.95);
    gl.uniform3f(this.u.uTone, ...this.tone); gl.uniform3f(this.u.uFringe, ...this.fringe); gl.uniform3f(this.u.uHi, ...this.hi); gl.uniform3f(this.u.uShade, ...this.shade);
    const w = this.wake, on = !!w?.ready && w.idle < STILL;
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(this.u.uVel, 2); gl.uniform1f(this.u.uWake, on ? 1 : 0);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.texP);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.pcv); gl.uniform1i(this.u.uPaths, 0);
    gl.uniform1f(this.u.uFanW, this.fanW);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.texM); gl.uniform1i(this.u.uMask, 1);
    gl.uniform4f(this.u.uMaskBox, this.maskBox[0], this.maskBox[1], this.maskBox[2], this.maskBox[3]);
    gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D, this.texG); gl.uniform1i(this.u.uGlyph, 3);
    gl.uniform4f(this.u.uGlyphBox, this.glyphBox[0], this.glyphBox[1], this.glyphBox[2], this.glyphBox[3]);
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
    // a full fan draws only while the wake moves; the next pointer move wakes it again
    if (this.o.full && !(this.wake && this.wake.idle < STILL)) { this.running = false; return; }
    this.raf = requestAnimationFrame(this.frame);
  };

  /** every path complete across the region, at once (full) */
  private fill() {
    const r = this.o.region();
    for (let y = r.top + 60; y < r.bottom - 40; y += 150 + this.rnd() * 60) this.spawn(y);
    for (const p of this.paths) { p.delay = 0; p.head = p.ys.length - 1; p.rest = true; }
  }
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
