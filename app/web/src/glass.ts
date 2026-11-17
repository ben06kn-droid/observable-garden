// The run page's glass: a large, still hourglass drawn as nothing but its two outline curves and its
// sand. It scrolls with the page like any other element. No frame, no caps, no posts, no turning.
//
// The sand is a falling-sand grid of large grains, few enough that each one can be seen falling and
// landing. The pile's edges are smooth (an occupancy field, softened and edged by a smoothstep, clipped to
// the glass's inner wall); grains in the air and the single thread through the neck are drawn as round
// grains of their own. The cursor scatters the grains it passes through.
//
// The sand follows the page, not a clock: setProgress(p) says how far the reader has come (0 at the top of
// the page, 1 at the rule above 03 Key), and the neck lets through that share of the grains, plus a small
// lead, so a thin stream keeps falling while the reader lingers. Scrolling back up pours the sand back.
// It is decoration and shows no number.
//
// A headline passing behind the upper bulb is drawn bent through the glass (WebGL), each colour channel
// refracted a little differently toward the walls. A click (or Enter) on the glass calls onClick: the page
// inverts its palette. Reduced motion: the glass is still and its sand settled.

export interface GlassOptions {
  height: number;
  reduce?: boolean;
  /** page text that passes behind the glass, drawn bent through it */
  behind?: HTMLElement[];
  /** a click on the glass (or Enter / Space while it has focus), at a viewport point */
  onClick?: (at: { x: number; y: number }) => void;
}

const SAND = ["#d6b27b", "#d1ab73", "#dbb883", "#cea86f"];
const FILL = -0.62;          // the top bulb is filled from the neck up to here (v, -1 at the top)
const PROFILE = { neck: 0.0085, bulb: 0.205, aNeck: 0.035, rise: 0.56, shoulder: 0.3 };   // × height
function halfWidth(v: number, H: number): number {
  const a = Math.abs(v), n = PROFILE.neck * H, R = PROFILE.bulb * H;
  if (a <= PROFILE.aNeck) return n;
  const u = (a - PROFILE.aNeck) / (1 - PROFILE.aNeck);
  const s = u < PROFILE.rise ? 0.5 - 0.5 * Math.cos(Math.PI * u / PROFILE.rise) : 1 - PROFILE.shoulder * Math.pow((u - PROFILE.rise) / (1 - PROFILE.rise), 2);
  return n + (R - n) * s;
}
const GLSL_PROFILE = `
float halfWidth(float v, float H) {
  float a = abs(v), n = ${PROFILE.neck.toFixed(4)} * H, R = ${PROFILE.bulb.toFixed(4)} * H;
  if (a <= ${PROFILE.aNeck.toFixed(4)}) return n;
  float u = (a - ${PROFILE.aNeck.toFixed(4)}) / (1.0 - ${PROFILE.aNeck.toFixed(4)});
  float s = u < ${PROFILE.rise.toFixed(4)} ? 0.5 - 0.5 * cos(3.14159265 * u / ${PROFILE.rise.toFixed(4)})
                    : 1.0 - ${PROFILE.shoulder.toFixed(4)} * pow((u - ${PROFILE.rise.toFixed(4)}) / (1.0 - ${PROFILE.rise.toFixed(4)}), 2.0);
  return n + (R - n) * s;
}`;
const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
// behind the glass: the page's ground inside it, and the text behind it bent as through a thick cylinder,
// each colour channel bent a little differently toward the walls; outside, clear
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr, uH, uGy; uniform vec3 uGround; uniform sampler2D uText;
out vec4 o;
${GLSL_PROFILE}
void main() {
  vec2 pc = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  vec2 c = uSize * 0.5, q = pc - c;
  float v = q.y / uGy, px = 1.0 / uDpr;
  if (abs(v) >= 1.0) { o = vec4(0.0); return; }
  float r = halfWidth(v, uH);
  float inside = clamp((r - abs(q.x)) / px + 0.5, 0.0, 1.0);
  if (inside <= 0.0) { o = vec4(0.0); return; }
  float a = clamp(q.x / r, -1.0, 1.0);
  vec2 s = vec2((a * 0.8 + 0.2 * a * a * a) * r, q.y * (1.0 - 0.03 * (1.0 - a * a)));
  float edge = a * a;
  vec3 col;
  for (int k = 0; k < 3; k++) {
    vec2 sk = q + (s - q) * (1.0 + (float(k) - 1.0) * 0.045 * edge);
    vec4 t = texture(uText, (sk + c) / uSize);
    col[k] = mix(uGround[k], (t.rgb / max(t.a, 1e-4))[k], t.a);
  }
  o = vec4(col, inside);
}`;

function rgb(s: string): [number, number, number] {
  let h = s.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1];
  if (h) { if (h.length === 3) h = h.replace(/./g, "$&$&"); const n = parseInt(h, 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
  const m = s.match(/\d+(\.\d+)?/g); return m ? [Number(m[0]), Number(m[1]), Number(m[2])] : [0, 0, 0];
}
function mulberry(a: number) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

export class Glass {
  readonly el: HTMLDivElement;
  private o: GlassOptions; private H: number; private gy: number; private R: number; private W: number; private dpr = 1;
  private back: HTMLCanvasElement | null = null; private front: HTMLCanvasElement;
  private gl: WebGL2RenderingContext | null = null; private u: Record<string, WebGLUniformLocation | null> = {}; private tex: WebGLTexture | null = null;
  private ground: [number, number, number] = [18, 20, 22]; private line: [number, number, number] = [240, 241, 250];
  // the sand
  private cs: number; private gw = 0; private gh = 0; private mask!: Uint8Array; private cell!: Uint8Array; private stamp!: Uint16Array; private air!: Uint8Array;
  private order!: Int32Array; private orderR!: Int32Array; private tick = 1; private drift: [number, number] = [0, 0];
  private occ!: Float32Array; private soft!: Float32Array; private shade!: Uint8Array;
  private total = 0; private passed = 0; private progress = 0; private lead = 0; private moved = 0; private dirty = true;
  private stir: { x: number; y: number; vx: number; vy: number; t: number; used?: boolean } | null = null;
  private raf = 0; private last = 0; private running = false; private visible = true; private io: IntersectionObserver | null = null;

  constructor(host: HTMLElement, o: GlassOptions) {
    this.o = o; this.H = o.height; this.gy = this.H / 2 - 1; this.R = PROFILE.bulb * this.H;
    this.W = Math.ceil(2 * this.R + 24);
    this.cs = Math.max(4, Math.min(7, this.H * 0.0056));
    this.el = document.createElement("div"); this.el.className = "glass";
    this.el.tabIndex = 0; this.el.setAttribute("role", "button");
    this.el.setAttribute("aria-label", "Hourglass: press to invert the page's colours");
    this.front = document.createElement("canvas"); this.front.className = "glass-front"; this.front.setAttribute("aria-hidden", "true");
    if (o.behind?.length && !o.reduce) { this.back = document.createElement("canvas"); this.back.className = "glass-back"; this.back.setAttribute("aria-hidden", "true"); this.el.append(this.back); }
    this.el.append(this.front);
    host.append(this.el);
    this.layout(); this.readPalette(); this.initGL(); this.initSand(); this.bind();
    this.io = new IntersectionObserver((es) => { this.visible = es.some((e) => e.isIntersecting); if (this.visible) this.start(); });
    this.io.observe(this.el);
    if (o.reduce) this.settle(); else this.start();
    this.render();
  }
  destroy() { this.running = false; cancelAnimationFrame(this.raf); this.io?.disconnect(); this.el.remove(); }
  /** the glass's own measures, css px */
  measures() { return { H: this.H, R: this.R, W: this.W, gy: this.gy }; }

  /** how far the reader has come, 0 (top of the page) to 1 (the rule above 03 Key) */
  setProgress(p: number) {
    this.progress = Math.max(0, Math.min(1, p));
    if (this.o.reduce) { window.clearTimeout(this.settleT); this.settleT = window.setTimeout(() => this.settle(), 120); }
    else this.start();
  }
  private settleT = 0;

  /** read the colours from the page's tokens (after a palette swap) and redraw */
  refreshPalette() { this.readPalette(); this.paintText(); this.render(); }
  private readPalette() {
    const cs = getComputedStyle(this.el);
    const g = cs.getPropertyValue("--hg-ground"), l = cs.getPropertyValue("--hg-line");
    if (g) this.ground = rgb(g); if (l) this.line = rgb(l);
  }

  private layout() {
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.el.style.setProperty("--glass-w", `${this.W}px`); this.el.style.setProperty("--glass-h", `${this.H}px`);
    for (const c of [this.front, this.back]) if (c) { c.width = Math.round(this.W * this.dpr); c.height = Math.round(this.H * this.dpr); }
  }

  // ---------- behind the glass: the headline, bent
  private initGL() {
    if (!this.back) return;
    const gl = this.back.getContext("webgl2", { antialias: false, premultipliedAlpha: false }); if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(p, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uH", "uGy", "uGround", "uText"]) this.u[n] = gl.getUniformLocation(p, n);
    this.tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
    this.gl = gl; this.paintText();
  }
  /** the text behind the glass, drawn word by word where it sits, into the glass's own coordinates.
   *  The glass scrolls with the page, so this holds until the layout changes; call it again then. */
  paintText() {
    const gl = this.gl; if (!gl || !this.back || !this.o.behind?.length) return;
    const c = document.createElement("canvas"); c.width = this.back.width; c.height = this.back.height;
    const x = c.getContext("2d")!, k = this.dpr, box = this.back.getBoundingClientRect();
    x.setTransform(k, 0, 0, k, 0, 0);
    for (const el of this.o.behind) {
      const cs = getComputedStyle(el);
      x.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      (x as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = cs.letterSpacing === "normal" ? "0px" : cs.letterSpacing;
      x.fillStyle = cs.color; x.textBaseline = "alphabetic";
      const m = x.measureText("Hg"), asc = m.fontBoundingBoxAscent, desc = m.fontBoundingBoxDescent;
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), range = document.createRange();
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const text = n.textContent ?? "";
        for (const w of text.matchAll(/\S+/g)) {
          range.setStart(n, w.index!); range.setEnd(n, w.index! + w[0].length);
          const r = range.getBoundingClientRect();
          x.fillText(w[0], r.left - box.left, r.top - box.top + (r.height - asc - desc) / 2 + asc);
        }
      }
    }
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
    this.drawBack();
  }
  private drawBack() {
    const gl = this.gl; if (!gl || !this.back) return;
    gl.viewport(0, 0, this.back.width, this.back.height);
    gl.uniform2f(this.u.uSize, this.W, this.H); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uH, this.H); gl.uniform1f(this.u.uGy, this.gy);
    gl.uniform3f(this.u.uGround, this.ground[0] / 255, this.ground[1] / 255, this.ground[2] / 255);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.tex); gl.uniform1i(this.u.uText, 0);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  // ---------- the sand
  private initSand() {
    const cs = this.cs, gy = this.gy;
    // an odd number of columns, one on the axis: the neck is one grain wide, the stream a single thread
    this.gw = 2 * Math.ceil(this.R / cs) + 1; this.gh = Math.ceil((2 * gy) / cs);
    const n = this.gw * this.gh, W = this.gw, axis = (W - 1) / 2;
    this.mask = new Uint8Array(n); this.cell = new Uint8Array(n); this.stamp = new Uint16Array(n); this.air = new Uint8Array(n);
    this.occ = new Float32Array(n); this.soft = new Float32Array(n); this.shade = new Uint8Array(n);
    const wall = 2;
    for (let j = 0; j < this.gh; j++) for (let i = 0; i < W; i++) {
      const x = (i - axis) * cs, y = (j + 0.5) * cs - gy;
      if (Math.abs(y) < gy - cs * 0.6 && (Math.abs(x) < halfWidth(y / gy, this.H) - wall - cs * 0.35 || i === axis)) this.mask[j * W + i] = 1;
    }
    // the top bulb's sand lies level on the neck, up to FILL: all of it above the neck to begin with
    const rnd = mulberry(7), mid = this.gh / 2;
    for (let j = 0; j < this.gh; j++) {
      const v = ((j + 0.5) * cs - gy) / gy;
      if (j >= mid || v < FILL) continue;
      for (let i = 0; i < W; i++) { const k = j * W + i; if (this.mask[k]) { this.cell[k] = 1 + Math.floor(rnd() * SAND.length); this.total++; } }
    }
    // the processing order: from the bottom up, each row one way and the other in turn
    const rows: number[] = [], rowsR: number[] = [];
    for (let j = this.gh - 1; j >= 0; j--) { for (let i = 0; i < W; i++) if (this.mask[j * W + i]) rows.push(j * W + i); for (let i = W - 1; i >= 0; i--) if (this.mask[j * W + i]) rowsR.push(j * W + i); }
    this.order = Int32Array.from(rows); this.orderR = Int32Array.from(rowsR);
    for (let s = 0; s < 60; s++) this.stepSand(rnd);
  }
  private allowed() { return Math.min(this.total, Math.floor(this.progress * this.total + this.lead)); }
  private stepSand(rnd: () => number = Math.random) {
    const W = this.gw, Hh = this.gh, cell = this.cell, mask = this.mask, st = this.stamp, air = this.air;
    const t = (this.tick = (this.tick + 1) & 0xffff) || (this.tick = 1);
    const ok = (i: number, j: number) => i >= 0 && j >= 0 && i < W && j < Hh && mask[j * W + i] === 1 && cell[j * W + i] === 0;
    const inside = (i: number, j: number) => i >= 0 && j >= 0 && i < W && j < Hh && mask[j * W + i] === 1;
    const neckRow = Math.floor(Hh / 2), axis = (W - 1) / 2, allowed = this.allowed();
    let moved = 0;
    for (const k of (t & 1 ? this.order : this.orderR)) {
      const v = cell[k]; if (!v || st[k] === t) continue;
      if (air[k]) {                                   // thrown by the cursor: drifting a few steps before it falls
        const left = air[k] - 1; air[k] = 0;
        const i0 = k % W, j0 = (k / W) | 0, ti = i0 + Math.round(this.drift[0] * rnd() * 1.4), tj = j0 + Math.round(this.drift[1] * rnd() * 1.4);
        const to = ok(ti, tj) ? tj * W + ti : k;
        if (to !== k) { cell[to] = v; cell[k] = 0; moved++; }
        air[to] = left; st[to] = t; continue;
      }
      let i = k % W, j = (k / W) | 0, at = k, falls = 0, slides = 0;
      for (let hop = 0; hop < 3; hop++) {
        let to = -1;
        if (ok(i, j + 1)) {
          if (falls >= 1) break;                      // one grain a step through the air: the thread stays a thread
          if (j === neckRow && i === axis) { if (this.passed >= allowed) break; this.passed++; }
          to = (j + 1) * W + i; falls++;
        } else if (falls === 0 && rnd() < (slides ? 0.9 : (!inside(i - 1, j) || !inside(i + 1, j)) ? 0.5 : 0.85)) {
          const first = rnd() < 0.5 ? -1 : 1;
          for (const s of [first, -first]) {
            if (!ok(i + s, j)) continue;
            if (ok(i + s, j + 1)) {
              if (rnd() < 0.4 && ok(i + 2 * s, j) && ok(i + 2 * s, j + 1)) { to = (j + 1) * W + i + 2 * s; break; }
              to = (j + 1) * W + i + s; break;
            }
          }
          if (to >= 0) slides++;
        }
        if (to < 0) break;
        cell[to] = v; cell[at] = 0; st[to] = t; at = to; i = to % W; j = (to / W) | 0; moved++;
      }
    }
    this.moved = moved; if (moved) this.dirty = true;
    // the cursor scatters the grains it passes through
    const s = this.stir;
    if (s && !s.used && performance.now() - s.t < 140) {
      s.used = true;
      const sp = Math.hypot(s.vx, s.vy);
      if (sp > 30) {
        const ux = s.vx / sp, uy = s.vy / sp, rad = 1.5 + 2.5 * Math.min(1, sp / 500), ci = Math.round(s.x), cj = Math.round(s.y), Rr = Math.ceil(rad);
        let px = ux * 0.6, py = uy * 0.6 - 0.8; const pl = Math.hypot(px, py) || 1; px /= pl; py /= pl;
        this.drift = [ux * 0.5, uy * 0.5 - 0.15];
        const near: number[] = [];
        for (let jj = cj - Rr; jj <= cj + Rr; jj++) for (let ii = ci - Rr; ii <= ci + Rr; ii++) {
          if (ii < 0 || jj < 0 || ii >= W || jj >= Hh || Math.hypot(ii - ci, jj - cj) > rad) continue;
          const kk = jj * W + ii; if (cell[kk] && st[kk] !== t) near.push(kk);
        }
        near.sort((a, b) => ((b % W) * px + ((b / W) | 0) * py) - ((a % W) * px + ((a / W) | 0) * py));
        for (const kk of near) {
          const i0 = kk % W, j0 = (kk / W) | 0, d = Math.hypot(i0 - ci, j0 - cj);
          let ai = i0, aj = j0;
          for (let hop = 0, hops = 1 + Math.round((1 - d / rad) * (2 + rnd() * 3)); hop < hops; hop++) {
            const ti = Math.round(ai + px + (rnd() - 0.5) * 0.8), tj = Math.round(aj + py + (rnd() - 0.5) * 0.8);
            if (!ok(ti, tj)) break;
            cell[tj * W + ti] = cell[aj * W + ai]; cell[aj * W + ai] = 0; st[tj * W + ti] = t; ai = ti; aj = tj;
          }
          if (ai !== i0 || aj !== j0) { air[aj * W + ai] = 3 + Math.floor(rnd() * 4); this.dirty = true; }
        }
      }
    }
  }
  /** the reader scrolled back up: grains go back, from the top of the lower pile to the top of the upper */
  private unpour(n: number) {
    const W = this.gw, Hh = this.gh, cell = this.cell, mask = this.mask, mid = Math.floor(Hh / 2), rnd = Math.random;
    for (let q = 0; q < n && this.passed > this.allowed(); q++) {
      // the lower pile's surface: the top grain of each column
      const tops: number[] = [], spots: number[] = [];
      for (let i = 0; i < W; i++) {
        for (let j = mid + 1; j < Hh; j++) { const k = j * W + i; if (cell[k] && !this.air[k]) { tops.push(k); break; } }
        // the upper sand's surface: the lowest free cell above the sand (or the neck) in each column
        for (let j = mid - 1; j >= 0; j--) {
          const k = j * W + i; if (!mask[k]) continue;
          if (cell[k]) continue;
          const below = (j + 1) * W + i;
          if (j + 1 >= mid || !mask[below] || cell[below]) { spots.push(k); break; }
          break;
        }
      }
      if (!tops.length || !spots.length) break;
      const from = tops[Math.floor(rnd() * tops.length)], to = spots[Math.floor(rnd() * spots.length)];
      cell[to] = cell[from]; cell[from] = 0; this.passed--; this.dirty = true;
    }
  }
  /** reduced motion: the sand settled where the reader is, at once */
  private settle() {
    for (let s = 0; s < 6000; s++) { if (this.passed > this.allowed()) this.unpour(50); this.stepSand(); if (this.moved === 0 && this.passed <= this.allowed()) break; }
    this.dirty = true; this.render();
  }

  private paintSand() {
    if (!this.dirty) return; this.dirty = false;
    const W = this.gw, Hh = this.gh, cell = this.cell, occ = this.occ, soft = this.soft, shade = this.shade;
    const at = (i: number, j: number) => (i >= 0 && j >= 0 && i < W && j < Hh ? cell[j * W + i] : 0);
    const nb = (i: number, j: number) => { let n = 0; for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) if ((di || dj) && at(i + di, j + dj)) n++; return n; };
    // the pile: grains with company; a grain on its own (falling, thrown, the thread) is drawn as a grain
    for (let j = 0; j < Hh; j++) for (let i = 0; i < W; i++) {
      const k = j * W + i, v = cell[k];
      if (v && nb(i, j) > 2) { occ[k] = 1; shade[k] = v; continue; }
      occ[k] = 0; let sh = 0;
      for (let dj = -1; dj <= 1 && !sh; dj++) for (let di = -1; di <= 1; di++) { const w = at(i + di, j + dj); if (w) { sh = w; break; } }
      shade[k] = sh;
      // a cell of glass beside a body of sand counts as sand: the wall's curve (the clip) is the pile's edge
      if (!this.mask[k] && Math.abs(j - Hh / 2) > 3 && (nb(i, j) >= 3 || at(i - 1, j) || at(i + 1, j))) occ[k] = 1;
    }
    for (let j = 0; j < Hh; j++) for (let i = 0; i < W; i++) { const k = j * W + i; soft[k] = ((i > 0 ? occ[k - 1] : 0) + 2 * occ[k] + (i < W - 1 ? occ[k + 1] : 0)) / 4; }
    for (let i = 0; i < W; i++) { let prev = 0; for (let j = 0; j < Hh; j++) { const k = j * W + i, cur = soft[k], next = j < Hh - 1 ? soft[k + W] : 0; occ[k] = (prev + 2 * cur + next) / 4; prev = cur; } }
  }
  /** the pile as one vector shape: the softened field traced at a half (marching squares, each square's
   *  part above the threshold as its own polygon, all filled together so they join without seams) */
  private pilePath(x: CanvasRenderingContext2D) {
    const W = this.gw, Hh = this.gh, f = this.occ, cs = this.cs, ox = -(W - 1) / 2 * cs, oy = -this.gy + cs / 2, T = 0.5;
    x.beginPath();
    for (let j = 0; j < Hh; j++) for (let i = 0; i < W - 1; i++) {
      const k = j * W + i, last = j === Hh - 1, a = f[k], b = f[k + 1], c = last ? b : f[k + W + 1], d = last ? a : f[k + W];
      if (a < T && b < T && c < T && d < T) continue;
      const X = ox + i * cs, Y = oy + j * cs;
      if (a >= T && b >= T && c >= T && d >= T) { x.rect(X, Y, cs, cs); continue; }
      const P: [number, number, number][] = [[X, Y, a], [X + cs, Y, b], [X + cs, Y + cs, c], [X, Y + cs, d]];
      let first = true;
      for (let q = 0; q < 4; q++) {
        const p0 = P[q], p1 = P[(q + 1) % 4];
        if (p0[2] >= T) { first ? x.moveTo(p0[0], p0[1]) : x.lineTo(p0[0], p0[1]); first = false; }
        if ((p0[2] >= T) !== (p1[2] >= T)) {
          const t = (T - p0[2]) / (p1[2] - p0[2]);
          const px = p0[0] + (p1[0] - p0[0]) * t, py = p0[1] + (p1[1] - p0[1]) * t;
          first ? x.moveTo(px, py) : x.lineTo(px, py); first = false;
        }
      }
      x.closePath();
    }
  }
  /** the pile's fill: grains packed in rows, each its own shade, on a slightly darker sand */
  private grainPattern(x: CanvasRenderingContext2D) {
    if (this.pattern) return this.pattern;
    const k = this.dpr, cs = this.cs, cols = 6, rows = 6;
    const tw = Math.round(cols * cs * k), th = Math.round(rows * cs * 0.866 * k);
    const c = document.createElement("canvas"); c.width = tw; c.height = th;
    const g = c.getContext("2d")!, rnd = mulberry(3), sx = tw / cols, sy = th / rows, r = Math.min(sx, sy / 0.866) * 0.5;
    g.fillStyle = "#cca56c"; g.fillRect(0, 0, tw, th);
    for (let j = -1; j <= rows; j++) for (let i = -1; i <= cols; i++) {
      const cx = (i + (j & 1 ? 0.5 : 0)) * sx, cy = (j + 0.5) * sy;
      g.fillStyle = SAND[Math.floor(rnd() * SAND.length)];
      for (const [dx, dy] of [[0, 0], [tw, 0], [-tw, 0], [0, th], [0, -th]]) { g.beginPath(); g.arc(cx + dx, cy + dy, r * 1.02, 0, Math.PI * 2); g.fill(); }
    }
    const pat = x.createPattern(c, "repeat")!;
    pat.setTransform(new DOMMatrix().scale(1 / k));
    return (this.pattern = pat);
  }
  private pattern: CanvasPattern | null = null;

  private outline(x: CanvasRenderingContext2D, inset: number, side: number) {
    const N = 220, gy = this.gy;
    x.beginPath();
    for (let q = 0; q <= N; q++) { const v = -1 + (2 * q) / N, r = halfWidth(v, this.H) - inset; q ? x.lineTo(side * r, v * gy) : x.moveTo(side * r, v * gy); }
  }
  private render() {
    this.drawBack();
    const x = this.front.getContext("2d")!, k = this.dpr, cs = this.cs, W = this.gw, Hh = this.gh, gy = this.gy;
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, this.front.width, this.front.height);
    x.setTransform(k, 0, 0, k, 0, 0); x.translate(this.W / 2, this.H / 2);
    // the pile, smooth-edged, inside the inner wall
    this.paintSand();
    x.save(); x.beginPath();
    { const N = 220, ins = 1.6;
      for (let q = 0; q <= N; q++) { const v = -1 + (2 * q) / N, r = Math.max(0.6, halfWidth(v, this.H) - ins); q ? x.lineTo(r, v * gy) : x.moveTo(r, v * gy); }
      for (let q = N; q >= 0; q--) { const v = -1 + (2 * q) / N, r = Math.max(0.6, halfWidth(v, this.H) - ins); x.lineTo(-r, v * gy); }
      x.closePath(); }
    x.clip();
    this.pilePath(x); x.fillStyle = this.grainPattern(x); x.fill();
    x.restore();
    // grains on their own: round, each one visible as it falls and lands
    const cell = this.cell, at = (i: number, j: number) => (i >= 0 && j >= 0 && i < W && j < Hh ? cell[j * W + i] : 0);
    const r = cs * 0.47;
    for (let c = 0; c < SAND.length; c++) {
      x.fillStyle = SAND[c]; x.beginPath();
      for (let j = 0; j < Hh; j++) for (let i = 0; i < W; i++) {
        const v = cell[j * W + i]; if (v !== c + 1) continue;
        let n = 0; for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) if ((di || dj) && at(i + di, j + dj)) n++;
        if (n > 2) continue;
        const cx = (i - (W - 1) / 2) * cs, cy = (j + 0.5) * cs - gy;
        x.moveTo(cx + r, cy); x.arc(cx, cy, r, 0, Math.PI * 2);
      }
      x.fill();
    }
    // the glass: its two curves, nothing else
    x.strokeStyle = `rgba(${this.line.join(",")},0.82)`; x.lineWidth = 1; x.lineJoin = "round"; x.lineCap = "round";
    for (const side of [-1, 1]) { this.outline(x, 0, side); x.stroke(); }
  }

  // ---------- the cursor and the click
  private inGlass(e: { clientX: number; clientY: number }) {
    const b = this.front.getBoundingClientRect(), lx = e.clientX - b.left - b.width / 2, ly = e.clientY - b.top - b.height / 2, v = ly / this.gy;
    return Math.abs(v) < 1 && Math.abs(lx) < halfWidth(v, this.H) + 4 ? [lx, ly] : null;
  }
  private bind() {
    let last: [number, number, number] | null = null, down: { x: number; y: number } | null = null;
    this.el.addEventListener("pointermove", (e) => {
      const p = this.inGlass(e);
      this.el.classList.toggle("over", !!p);
      if (!p || e.pointerType === "touch" || this.o.reduce) { last = null; return; }
      const gi = p[0] / this.cs + (this.gw - 1) / 2, gj = (p[1] + this.gy) / this.cs - 0.5, now = performance.now();
      if (last) { const dt = Math.max(8, now - last[2]) / 1000; this.stir = { x: gi, y: gj, vx: (gi - last[0]) / dt * this.cs, vy: (gj - last[1]) / dt * this.cs, t: now }; this.start(); }
      last = [gi, gj, now];
    });
    this.el.addEventListener("pointerleave", () => { last = null; this.el.classList.remove("over"); });
    this.el.addEventListener("pointerdown", (e) => { down = this.inGlass(e) ? { x: e.clientX, y: e.clientY } : null; });
    this.el.addEventListener("pointerup", (e) => {
      if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 6 && this.inGlass(e)) this.o.onClick?.({ x: e.clientX, y: e.clientY });
      down = null;
    });
    this.el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault(); const b = this.front.getBoundingClientRect(); this.o.onClick?.({ x: b.left + b.width / 2, y: b.top + b.height / 2 });
    });
  }

  // ---------- the loop: runs while the glass is on screen and its sand has somewhere to go
  private start() {
    if (this.running || this.o.reduce || !this.visible) return;
    this.running = true; this.last = performance.now();
    const frame = (now: number) => {
      if (!this.running) return;
      const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
      // a slow drip ahead of the reader: a grain about every 0.4 s, at most 3.5% of the sand ahead
      this.lead = Math.min(Math.max(3, this.total * 0.035), this.lead + dt * 2.5);
      if (this.passed > this.allowed() + 2) this.unpour(4);
      const behind = this.allowed() - this.passed;
      const steps = behind > 40 ? 3 : 2;
      for (let s = 0; s < steps; s++) this.stepSand();
      if (this.dirty) this.render();
      const idle = this.moved === 0 && this.passed >= this.allowed() && !(this.stir && performance.now() - this.stir.t < 300);
      if (!this.visible || idle) { this.running = false; return; }
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }
}
