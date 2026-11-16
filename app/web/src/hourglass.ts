// The run page's hourglass: drawn in code, the page's one image. A search spends a budget of moves; the
// gate is the narrow neck everything passes through.
//
// Three layers in one box, the hourglass turning about its centre:
//  - behind the glass (WebGL2): the page ground, the frame's two rear posts and any page rule passing
//    behind, all hairlines evaluated analytically per pixel at the point the glass refracts it from, so
//    lines stay sharp at any pixel ratio and nothing is uploaded per frame. A bulb acts as a thick
//    cylinder: what is behind its middle is magnified, what is behind its edges is pulled outward and
//    bent. Without WebGL2, or under reduced motion, the same lines are drawn straight (2D).
//  - the sand (2D): a falling-sand grid in the hourglass's own frame; gravity turns with the glass, so a
//    tilt or a flip sends the sand back through the neck. Grains pile at their angle of repose; the
//    cursor stirs those near it.
//  - the glass and frame (2D): hairline walls with an inner wall line, two caps, two front posts.
//
// Dragging turns it like a dial: a spring with inertia follows the hand; released, it settles upright or
// flipped with a slight, weighty overshoot. Enter or Space flips it. It is decoration and claims nothing.

export interface HourglassOptions {
  height: number;                 // css px, cap to cap
  reduce?: boolean;
  /** elements whose text passes behind the glass: drawn into the glass, bent; real text stays in the page */
  behind?: HTMLElement[];
  /** a full flip by hand came to rest: the page swaps its palette, spreading from the neck (page coords) */
  onFlip?: (flipped: boolean, neck: { x: number; y: number }) => void;
  /** the first drag of the visit */
  onFirstTurn?: () => void;
}

// the sand: one warm tone, four close shades; the glass's colours come from the page's tokens
// (--hg-ground, --hg-line), so they follow the page's palette
const SAND = ["#d6b27b", "#d1ab73", "#dbb883", "#cea86f"];
const SAND_RGB = SAND.map((h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]);
const SUB = 2;   // the sand's drawing: samples per grid cell, each way
const rgb = (c: string): [number, number, number] => {
  const m = c.trim().match(/^#([0-9a-f]{6})$/i);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)) as [number, number, number];
  const n = c.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0]; return [n[0], n[1], n[2]];
};

// ---- the glass's profile: half-width at v ∈ [-1, 1] (cap to cap), the same function in TS and GLSL
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
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize;        // css px
uniform float uDpr, uAngle, uH, uGlass, uPostX, uPostW;
uniform vec3 uGround, uLine;
uniform sampler2D uText;   // the page text behind the glass, drawn in the box's own page coordinates
uniform vec2 uTextOff;     // how far that text has moved relative to the box since it was drawn
out vec4 o;
${GLSL_PROFILE}
vec2 rot(vec2 v, float a) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }
// coverage of a line of css width w at signed distance d (css px), antialiased over one device pixel
float cover(float d, float w, float px) { return clamp((w * 0.5 - abs(d)) / px + 0.5, 0.0, 1.0); }
void main() {
  vec2 pc = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;   // css px, y down
  vec2 c = uSize * 0.5;
  vec2 q = rot(pc - c, -uAngle);                                           // the hourglass's own frame
  float gy = uGlass * 0.5, v = q.y / gy;
  float px = 1.0 / uDpr;
  // outside the glass this layer is clear (the page shows through), but for the rear posts beside the neck
  float r = abs(v) < 1.0 ? halfWidth(v, uH) : 0.0;
  float inside = abs(v) < 1.0 ? clamp((r - abs(q.x)) / px + 0.5, 0.0, 1.0) * clamp((gy - abs(q.y)) / px + 0.5, 0.0, 1.0) : 0.0;
  float postOut = abs(q.y) < gy ? max(cover(q.x - uPostX, uPostW, px), cover(q.x + uPostX, uPostW, px)) : 0.0;
  // inside: a thick cylinder; what is behind its middle is magnified, what is behind its edges is pulled
  // outward and bent
  vec2 s = q; float pin = px;
  if (r > 0.0) {
    float a = clamp(q.x / r, -1.0, 1.0);
    // a steady 1.25x across the middle, easing to compression at the edges (so no letter on the axis
    // smears: the magnification stays finite everywhere)
    s = vec2((a * 0.8 + 0.2 * a * a * a) * r, q.y * (1.0 - 0.03 * (1.0 - a * a)));
    pin = px * 0.6;
  }
  vec3 col = uGround;
  vec2 sp = rot(s, uAngle) + c;                                             // back on the page
  vec4 t = texture(uText, (sp - uTextOff) / uSize);
  col = mix(col, t.rgb / max(t.a, 1e-4), t.a);
  float postIn = abs(s.y) < gy ? max(cover(s.x - uPostX, uPostW, pin), cover(s.x + uPostX, uPostW, pin)) : 0.0;
  col = mix(col, uLine, postIn * 0.26);
  float aOut = postOut * 0.26;
  o = vec4(mix(uLine, col, inside), inside + (1.0 - inside) * aOut);
}`;

export class Hourglass {
  readonly el: HTMLDivElement;
  private back: HTMLCanvasElement; private front: HTMLCanvasElement;
  private gl: WebGL2RenderingContext | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {};
  private size = 0; private dpr = 1;
  private H: number; private glass: number; private capT: number; private reduce: boolean; private o: HourglassOptions;
  private ground: [number, number, number] = [0x12, 0x14, 0x16]; private line: [number, number, number] = [0xf0, 0xf1, 0xfa];
  private textCanvas: HTMLCanvasElement | null = null; private tex: WebGLTexture | null = null;
  // the text behind the glass, relative to the box, when it was painted and now (a sticky glass over
  // scrolling text): the shader shifts the drawing by the difference, so nothing is repainted on scroll
  private paintedAt: [number, number] = [0, 0]; private textOff: [number, number] = [0, 0];
  // turning: the angle springs toward a target, the rest angle (0 or a multiple of pi) plus any lean
  angle = 0; private vel = 0; private target = 0; private rest = 0; private lean = 0; private dragging = false; private grab = 0;
  private arrived = false; private turned = false; private locked = false;
  // a run: the sand that may pass the neck is the share of the move budget spent
  private gate: { total: number; passed: number; share: number } | null = null;
  // after a run's turn, the sand that fell to the far end spreads level (so the run's sand builds one
  // clean cone on it); the neck stays shut until it has
  private level = 0;
  private done: (() => void) | null = null;
  // sand
  private cs = 1.75; private gw = 0; private gh = 0; private mask!: Uint8Array; private cell!: Uint8Array; private stamp!: Uint16Array; private air!: Uint8Array; private drift: [number, number] = [0, 0]; private tick = 1;
  private order: Int32Array | null = null; private orderR: Int32Array | null = null; private orderG = [9, 9];
  private img!: ImageData; private sandCanvas!: HTMLCanvasElement;
  // the sand is drawn smooth: its occupancy, softened, sampled at twice the grid, edged by a smoothstep
  private dirty = true; private occ!: Float32Array; private soft!: Float32Array; private shadeOf!: Uint8Array;
  private stir: { x: number; y: number; vx: number; vy: number; t: number; used?: boolean } | null = null;
  private raf = 0; private last = 0; private running = false; private hint: HTMLElement;

  constructor(host: HTMLElement, o: HourglassOptions) {
    this.o = o; this.H = o.height; this.capT = Math.round(o.height * 0.03); this.glass = o.height - 2 * this.capT - 6;
    this.reduce = !!o.reduce;
    this.el = document.createElement("div"); this.el.className = "hourglass";
    this.el.tabIndex = 0; this.el.setAttribute("role", "button");
    this.el.setAttribute("aria-label", "Hourglass: click or press Enter to turn it over and invert the page; drag to turn it by hand");
    this.back = document.createElement("canvas"); this.front = document.createElement("canvas");
    this.back.className = "hg-back"; this.front.className = "hg-front";
    for (const c of [this.back, this.front]) c.setAttribute("aria-hidden", "true");
    // the hint, until the first turn of the visit
    this.hint = document.createElement("p"); this.hint.className = "hg-hint"; this.hint.textContent = "Drag to turn"; this.hint.setAttribute("aria-hidden", "true");
    let seen = false; try { seen = sessionStorage.getItem("hg-turned") === "1"; } catch { /* no storage: show it */ }
    if (seen || this.reduce) this.hint.classList.add("gone");
    // what takes the pointer: the glass and its caps, not the whole (mostly clear) square it is drawn in,
    // so the page beside it stays clickable
    const hit = document.createElement("div"); hit.className = "hg-hit";
    this.el.append(this.back, this.front, hit, this.hint);
    host.appendChild(this.el);
    this.layout();
    this.readPalette();
    if (!this.reduce) this.initGL();
    this.initSand();
    this.bind();
    if (this.reduce) { this.arrived = true; this.render(); return; }
    // arrival: it comes in tilted and swings itself upright with the same weighted overshoot as a
    // release; the sand holds still until it has settled
    this.angle = -0.62 * Math.PI; this.target = 0; this.el.classList.add("arriving");
    this.render();
    this.start();
  }

  private relative(): [number, number] {
    const t = this.o.behind?.[0]; if (!t) return [0, 0];
    const a = t.getBoundingClientRect(), b = this.back.getBoundingClientRect();
    return [a.left - b.left, a.top - b.top];
  }
  /** the glass's own measures, in px: its height, the bulb's half width, the glass's half height */
  measures() { return { H: this.H, R: PROFILE.bulb * this.H, gy: this.glass / 2, size: this.size }; }
  /** stop drawing and take the glass off the page (a layout change builds a new one) */
  destroy() { this.stop(); this.el.remove(); }

  /** read the glass's colours from the page's tokens (after a palette swap, for one) and redraw */
  refreshPalette() { this.readPalette(); this.paintText(); this.render(); }
  private readPalette() {
    const cs = getComputedStyle(this.el);
    const g = cs.getPropertyValue("--hg-ground"), l = cs.getPropertyValue("--hg-line");
    if (g) this.ground = rgb(g); if (l) this.line = rgb(l);
  }

  /** a run begins: the glass turns over by itself, and from then on the sand that passes the neck is
   *  the share of the move budget spent; it cannot be turned by hand until the run ends */
  beginRun() {
    this.locked = true; this.dragging = false; this.el.classList.add("locked");
    this.rest = this.rest + Math.PI; this.lean = 0; this.target = this.rest;
    this.gate = { total: 0, passed: 0, share: 0 };
    if (this.reduce) { this.angle = this.target; this.order = null; this.armGate(); this.render(); }
  }
  /** the share of the move budget spent, 0..1 */
  setShare(f: number) { if (this.gate) this.gate.share = Math.max(this.gate.share, Math.min(1, Math.max(0, f))); }
  /** the run is over: the rest of the sand runs out; resolves as the last grain lands */
  finish(): Promise<void> {
    if (!this.gate) return Promise.resolve();
    this.gate.share = 1;
    if (this.reduce) { for (let s = 0; s < 8000 && !(this.moved === 0 && this.upperCount() === 0 && s > 10); s++) this.stepSand(); this.render(); this.endRun(); return Promise.resolve(); }
    return new Promise((res) => { this.done = res; window.setTimeout(() => { if (this.done) { this.endRun(); } }, 15000); });
  }
  private endRun() { this.gate = null; this.level = 0; this.locked = false; this.el.classList.remove("locked"); const d = this.done; this.done = null; d?.(); }
  // once the glass has turned over for a run: the grains now above the neck are the whole budget
  private armGate() {
    if (!this.gate || this.gate.total) return;
    const g = this.gravity(), mid = this.gh / 2; let n = 0;
    for (let k = 0; k < this.cell.length; k++) if (this.cell[k] && ((Math.floor(k / this.gw) - mid) * g[1] + ((k % this.gw) - (this.gw - 1) / 2) * g[0]) < 0) n++;
    this.gate.total = Math.max(1, n); this.level = performance.now();
  }
  private upper(k: number, g = this.gravity()) { return ((Math.floor(k / this.gw) - this.gh / 2) * g[1] + ((k % this.gw) - (this.gw - 1) / 2) * g[0]) < 0; }
  private upperCount() { const g = this.gravity(); let n = 0; for (let k = 0; k < this.cell.length; k++) if (this.cell[k] && this.upper(k, g)) n++; return n; }
  // the last grain that will flow has landed: none has passed the neck for a moment and the sand is still
  // (a few may stay on the upper bulb's walls, as in a real glass)
  private settledEmpty() { return performance.now() - this.lastPass > 400 && this.moved === 0 && this.upperCount() === 0; }
  private moved = 0; private lastPass = 0;

  private layout() {
    this.size = Math.ceil(Math.hypot(this.H, 2 * PROFILE.bulb * this.H + 40) + 24);
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.el.style.setProperty("--hg", `${this.size}px`);
    this.el.style.setProperty("--hg-hit-w", `${Math.round(PROFILE.bulb * this.H * 2 + 30)}px`);
    this.el.style.setProperty("--hg-hit-h", `${Math.round(this.H)}px`);
    for (const c of [this.back, this.front]) { c.width = Math.round(this.size * this.dpr); c.height = Math.round(this.size * this.dpr); }
  }

  // ---------- behind the glass
  private initGL() {
    const gl = this.back.getContext("webgl2", { antialias: false, premultipliedAlpha: false, preserveDrawingBuffer: false });
    if (!gl) return;
    const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(p, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uAngle", "uH", "uGlass", "uPostX", "uPostW", "uGround", "uLine", "uText", "uTextOff"]) this.u[n] = gl.getUniformLocation(p, n);
    this.tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
    this.gl = gl;
    this.paintText();
  }

  /** the page text behind the glass, drawn word by word where it sits in the page, in its own font and
   *  colour, into the box's coordinates; the glass shows it bent. Call again after a layout change. */
  paintText() {
    const gl = this.gl; if (!gl || !this.o.behind?.length) return;
    const c = this.textCanvas ?? (this.textCanvas = document.createElement("canvas"));
    c.width = this.back.width; c.height = this.back.height;
    const x = c.getContext("2d")!, k = this.dpr, box = this.back.getBoundingClientRect();
    x.setTransform(k, 0, 0, k, 0, 0); x.clearRect(0, 0, this.size, this.size);
    this.paintedAt = this.relative(); this.textOff = [0, 0];
    for (const el of this.o.behind) {
      const cs = getComputedStyle(el);
      x.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      (x as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = cs.letterSpacing === "normal" ? "0px" : cs.letterSpacing;
      x.fillStyle = cs.color; x.textBaseline = "alphabetic";
      const m = x.measureText("Hg"), asc = m.fontBoundingBoxAscent, desc = m.fontBoundingBoxDescent;
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const text = n.textContent ?? "", range = document.createRange();
        for (const w of text.matchAll(/\S+/g)) {
          range.setStart(n, w.index!); range.setEnd(n, w.index! + w[0].length);
          const r = range.getBoundingClientRect();
          x.fillText(w[0], r.left - box.left, r.top - box.top + (r.height - asc - desc) / 2 + asc);
        }
      }
    }
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
  }
  private postX() { return PROFILE.bulb * this.H * 0.38; }   // seen through the bulbs, a straight rod bows
  private drawBack() {
    const gl = this.gl;
    if (gl) {
      gl.viewport(0, 0, this.back.width, this.back.height);
      gl.uniform2f(this.u.uSize, this.size, this.size); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uAngle, this.angle);
      gl.uniform1f(this.u.uH, this.H); gl.uniform1f(this.u.uGlass, this.glass); gl.uniform1f(this.u.uPostX, this.postX()); gl.uniform1f(this.u.uPostW, 1.5);
      const f = (c: number[]) => c.map((x) => x / 255) as [number, number, number];
      gl.uniform3f(this.u.uGround, ...f(this.ground)); gl.uniform3f(this.u.uLine, ...f(this.line));
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.tex); gl.uniform1i(this.u.uText, 0);
      gl.uniform2f(this.u.uTextOff, this.textOff[0], this.textOff[1]);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      return;
    }
    // no WebGL2 (or reduced motion): clear glass, the rear posts straight; the page shows through
    const x = this.back.getContext("2d")!, k = this.dpr, c = this.size / 2;
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, this.back.width, this.back.height);
    x.setTransform(k, 0, 0, k, 0, 0);
    x.translate(c, c); x.rotate(this.angle);
    x.fillStyle = `rgba(${this.line.join(",")},0.26)`;
    for (const sx of [-1, 1]) x.fillRect(sx * this.postX() - 0.75, -this.glass / 2, 1.5, this.glass);
  }

  // ---------- the sand
  private initSand() {
    const cs = this.cs, R = PROFILE.bulb * this.H, gy = this.glass / 2;
    // an odd number of columns, one of them on the axis, so the neck is exactly one cell wide and the
    // stream a single thread (one cell a step through it: the glass runs through in about 25 s)
    this.gw = 2 * Math.ceil(R / cs) + 1; this.gh = Math.ceil(this.glass / cs);
    const n = this.gw * this.gh; this.mask = new Uint8Array(n); this.cell = new Uint8Array(n); this.stamp = new Uint16Array(n); this.air = new Uint8Array(n);
    const wall = 2.6;
    for (let j = 0; j < this.gh; j++) for (let i = 0; i < this.gw; i++) {
      const x = (i - (this.gw - 1) / 2) * cs, y = (j + 0.5) * cs - gy;
      if (Math.abs(y) < gy - 3 && Math.abs(x) < halfWidth(y / gy, this.H) - wall - cs * 0.3) this.mask[j * this.gw + i] = 1;
    }
    // about two thirds of the top bulb's volume: most in the top, a pile already in the bottom
    const top: number[] = [], bot: number[] = [];
    for (let j = 0; j < this.gh; j++) for (let i = 0; i < this.gw; i++) { const k = j * this.gw + i; if (!this.mask[k]) continue; (j < this.gh / 2 ? top : bot).push(k); }
    const total = Math.round(top.length * 0.68), inTop = Math.round(total * 0.62);
    // the top's sand lies level on the neck: its lowest rows first, each row from the middle out; the
    // bottom's is a mound, highest in the middle
    const row = (k: number) => Math.floor(k / this.gw), dx = (k: number) => Math.abs((k % this.gw) + 0.5 - this.gw / 2);
    top.sort((a, b) => row(b) - row(a) || dx(a) - dx(b));
    bot.sort((a, b) => (row(b) - dx(b) * 0.7) - (row(a) - dx(a) * 0.7));
    const rnd = mulberry(7);
    const shade = () => 1 + Math.floor(rnd() * SAND.length);
    for (let q = 0; q < inTop; q++) this.cell[top[q]] = shade();
    for (let q = 0; q < total - inTop; q++) this.cell[bot[q]] = shade();
    this.img = new ImageData(this.gw * SUB, this.gh * SUB);
    this.sandCanvas = document.createElement("canvas"); this.sandCanvas.width = this.gw * SUB; this.sandCanvas.height = this.gh * SUB;
    this.occ = new Float32Array(n); this.soft = new Float32Array(n); this.shadeOf = new Uint8Array(n);
    for (let s = 0; s < 220; s++) this.stepSand(rnd);   // let it settle
  }
  private gravity(): [number, number] { return [Math.sin(this.angle), Math.cos(this.angle)]; }
  private stepSand(rnd: () => number = Math.random) {
    const W = this.gw, Hh = this.gh, cell = this.cell, mask = this.mask, st = this.stamp;
    const g = this.gravity();
    // process cells from the bottom (along gravity) up, so each grain moves once; across each level,
    // alternately from one side and the other, so the sand favours neither
    if (!this.order || Math.abs(g[0] - this.orderG[0]) + Math.abs(g[1] - this.orderG[1]) > 0.03) {
      // a bucket sort (linear time, so turning the glass never costs a frame): by level along gravity,
      // and within a level by position across it, one way and the other
      const lvl = (k: number) => Math.round(((k % W) * g[0] + Math.floor(k / W) * g[1]) * 2);
      const across = (k: number) => Math.round(((k % W) * g[1] - Math.floor(k / W) * g[0]) * 2);
      let lo = Infinity, hi = -Infinity, alo = Infinity, ahi = -Infinity;
      const cells: number[] = [];
      for (let k = 0; k < W * Hh; k++) if (mask[k]) { cells.push(k); const l = lvl(k), x = across(k); lo = Math.min(lo, l); hi = Math.max(hi, l); alo = Math.min(alo, x); ahi = Math.max(ahi, x); }
      const sortBy = (key: (k: number) => number, from: number, to: number, list: number[], desc: boolean) => {
        const n = to - from + 1, count = new Int32Array(n + 1);
        for (const k of list) count[(desc ? to - key(k) : key(k) - from) + 1]++;
        for (let q = 0; q < n; q++) count[q + 1] += count[q];
        const out = new Array<number>(list.length);
        for (const k of list) out[count[desc ? to - key(k) : key(k) - from]++] = k;
        return out;
      };
      // stable: sort by the secondary key first, then by the primary
      this.order = Int32Array.from(sortBy(lvl, lo, hi, sortBy(across, alo, ahi, cells, false), true));
      this.orderR = Int32Array.from(sortBy(lvl, lo, hi, sortBy(across, alo, ahi, cells, true), true));
      this.orderG = g;
    }
    // the eight directions; the primary is the one nearest gravity, then its neighbours either side
    const ang = Math.atan2(g[1], g[0]), oct = Math.round(ang / (Math.PI / 4));
    const dir = (o: number) => { const a = o * Math.PI / 4; return [Math.round(Math.cos(a)), Math.round(Math.sin(a))]; };
    const d0 = dir(oct), dl = dir(oct - 1), dr = dir(oct + 1);
    const t = (this.tick = (this.tick + 1) & 0xffff) || (this.tick = 1);
    const air = this.air;
    const ok = (i: number, j: number) => i >= 0 && j >= 0 && i < W && j < Hh && mask[j * W + i] === 1 && cell[j * W + i] === 0;
    const inside = (i: number, j: number) => i >= 0 && j >= 0 && i < W && j < Hh && mask[j * W + i] === 1;
    const wallBy = (i: number, j: number) => !inside(i - 1, j) || !inside(i + 1, j);
    // during a run the neck lets through only the spent share of the budget (and nothing until the glass
    // has turned over); the neck's middle row is where a grain counts as through
    const neckRow = Math.floor(Hh / 2), neckCol = (W - 1) / 2, gate = this.gate;
    const ending = !!gate && gate.share >= 1, levelling = !!gate && this.level > 0;
    const across = (sgn: number) => { const d = sgn < 0 ? dl : dr; return [d[0] - d0[0], d[1] - d0[1]]; };   // level, either way
    const up = (i: number, j: number) => ((j - Hh / 2) * g[1] + (i - neckCol) * g[0]) < 0;
    let moved = 0, movedLow = 0;

    for (const k of (t & 1 ? this.order : this.orderR!)) {
      const v = cell[k]; if (!v || st[k] === t) continue;
      // a grain the cursor threw is in the air for a few steps: it drifts with the throw instead of falling
      if (air[k]) {
        const left = air[k] - 1; air[k] = 0;
        const i0 = k % W, j0 = (k / W) | 0, ti = i0 + Math.round(this.drift[0] * rnd() * 1.4), tj = j0 + Math.round(this.drift[1] * rnd() * 1.4);
        const to = ok(ti, tj) ? tj * W + ti : k;
        if (to !== k) { cell[to] = v; cell[k] = 0; }
        air[to] = left; st[to] = t; continue;
      }
      let i = k % W, j = (k / W) | 0, at = k, falls = 0, slides = 0;
      // momentum: within one step a grain falls one cell (so the stream stays a continuous thread), but
      // once it has started to slide it may keep going (up to four moves in all), so a steep face
      // avalanches as a layer instead of creeping
      for (let hop = 0; hop < 4; hop++) {
        let to = -1;
        if (ok(i + d0[0], j + d0[1])) {
          if (falls >= 1) break;
          if (gate && j === neckRow && i === neckCol) {
            if (!gate.total || this.level || gate.passed >= gate.share * gate.total) break;
            gate.passed++; this.lastPass = performance.now();
          }
          to = (j + d0[1]) * W + i + d0[0]; falls++;
        }
        // friction: a grain falls whenever it can, but starts to slide only some of the time, against
        // the glass less often still, so the top drains from its middle into a crater while the sand on
        // the walls holds; a grain already sliding keeps going
        // (a grain that fell this step is in the air, not resting: it does not slide until the next)
        else if (falls === 0 && rnd() < (ending ? 1 : slides ? 0.9 : wallBy(i, j) ? 0.5 : 0.85)) {
          // a grain slides only off an open edge (the cells beside it on that side are empty), so the gap
          // a falling grain leaves rises straight up and the sand beside it caves in along its slope: one
          // across and one down, or, a little less often, two across and one down, so it rests at about
          // the angle real sand does rather than 45 degrees
          const first = rnd() < 0.5 ? -1 : 1;
          for (const sgn of [first, -first]) {
            const d = sgn < 0 ? dl : dr, s1 = [d[0] - d0[0], d[1] - d0[1]];
            if (!ok(i + s1[0], j + s1[1])) continue;
            if (ok(i + d[0], j + d[1])) {
              if (rnd() < 0.4 && ok(i + 2 * s1[0], j + 2 * s1[1]) && ok(i + 2 * s1[0] + d0[0], j + 2 * s1[1] + d0[1])) { to = (j + 2 * s1[1] + d0[1]) * W + i + 2 * s1[0] + d0[0]; break; }
              to = (j + d[1]) * W + i + d[0]; break;
            }
          }
          if (to >= 0) slides++;
        }
        // a grain at rest, during a run: in the lower bulb while the bed levels, it moves one cell toward
        // the nearest drop within reach, so the bed ends flat; in the upper bulb once the run is over, one
        // cell toward the neck, so no grain stays on the glass
        if (to < 0 && hop === 0 && falls === 0 && slides === 0 && (levelling || ending)) {
          const top = up(i, j);
          if (top && ending) {
            for (const sgn of [-1, 1]) { const h = across(sgn); if (h[0] * (neckCol - i) + h[1] * (neckRow - j) > 0 && ok(i + h[0], j + h[1])) { to = (j + h[1]) * W + i + h[0]; break; } }
          } else if (!top && levelling) {
            const first = rnd() < 0.5 ? -1 : 1;
            for (const sgn of [first, -first]) {
              const h = across(sgn);
              for (let q = 1; q <= 16; q++) { const pi = i + h[0] * q, pj = j + h[1] * q; if (!ok(pi, pj)) break; if (ok(pi + d0[0], pj + d0[1])) { to = (j + h[1]) * W + i + h[0]; break; } }
              if (to >= 0) break;
            }
          }
          if (to >= 0) slides++;
        }
        if (to < 0) break;
        if (!up(i, j)) movedLow++;
        cell[to] = v; cell[at] = 0; st[to] = t; at = to; i = to % W; j = (to / W) | 0; moved++;
      }
    }
    this.moved = moved; if (moved) this.dirty = true;
    // the bed is level once nothing in the lower bulb moves (or after three seconds at most)
    if (levelling && (movedLow === 0 || performance.now() - this.level > 3000)) this.level = 0;

    // the cursor is a wind over the sand (as it is over the home page's leaves): grains near it (within
    // about twenty pixels) are thrown up out of the sand and along its path, through open cells only,
    // more of them the faster it moves and the nearer they are; they hang in the air a few steps,
    // drifting, then fall and slump back by the same rules as all the sand
    const s = this.stir;
    if (s && !s.used && performance.now() - s.t < 140) {
      s.used = true;                                   // each movement of the cursor stirs once
      const sp = Math.hypot(s.vx, s.vy);
      if (sp > 30) {
        // its reach grows with its speed, up to about twenty-eight pixels
        const ux = s.vx / sp, uy = s.vy / sp, rad = 4 + 12 * Math.min(1, sp / 400);
        const ci = Math.round(s.x), cj = Math.round(s.y);
        // the throw: up out of the sand (against gravity) and along the cursor's path
        let px = ux * 0.6 - g[0] * 0.8, py = uy * 0.6 - g[1] * 0.8; const pl = Math.hypot(px, py) || 1; px /= pl; py /= pl;
        this.drift = [ux * 0.5 - g[0] * 0.15, uy * 0.5 - g[1] * 0.15];
        // the grains in reach, the uppermost first, so each one lifted leaves room for the one beneath it
        const near: number[] = [];
        const R = Math.ceil(rad);                          // whole cells: the reach itself may be fractional
        for (let j = cj - R; j <= cj + R; j++) for (let i = ci - R; i <= ci + R; i++) {
          if (i < 0 || j < 0 || i >= W || j >= Hh || Math.hypot(i - ci, j - cj) > rad) continue;
          const k = j * W + i; if (cell[k] && st[k] !== t) near.push(k);
        }
        near.sort((a, b) => ((b % W) * px + ((b / W) | 0) * py) - ((a % W) * px + ((a / W) | 0) * py));
        for (const k of near) {
          const i = k % W, j = (k / W) | 0, d = Math.hypot(i - ci, j - cj);
          let ai = i, aj = j;
          // nearer grains are thrown further
          for (let hop = 0, hops = 1 + Math.round((1 - d / rad) * (3 + rnd() * 6)); hop < hops; hop++) {
            const ti = Math.round(ai + px + (rnd() - 0.5) * 0.8), tj = Math.round(aj + py + (rnd() - 0.5) * 0.8);
            if (!ok(ti, tj)) break;
            cell[tj * W + ti] = cell[aj * W + ai]; cell[aj * W + ai] = 0; st[tj * W + ti] = t; ai = ti; aj = tj;
          }
          if (ai !== i || aj !== j) { air[aj * W + ai] = 3 + Math.floor(rnd() * 5); this.dirty = true; }   // in the air a few steps
        }
      }
    }
  }
  private paintSand() {
    if (!this.dirty) return; this.dirty = false;
    const W = this.gw, Hh = this.gh, cell = this.cell, mask = this.mask, occ = this.occ, soft = this.soft, shade = this.shadeOf;
    const at = (i: number, j: number) => (i >= 0 && j >= 0 && i < W && j < Hh ? cell[j * W + i] : 0);
    const neck = Math.max(3, Math.round(Hh * 0.06));
    // occupancy; a cell of glass next to a body of sand counts as sand, so the sand reaches the wall and
    // the wall's smooth curve (the clip) is its edge, not the grid's steps; the neck's thread stays one wide
    for (let j = 0; j < Hh; j++) for (let i = 0; i < W; i++) {
      const k = j * W + i, v = cell[k];
      if (v) { occ[k] = 1; shade[k] = v; continue; }
      let n = 0, sh = 0;
      for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) { const w = at(i + di, j + dj); if (w) { n++; sh = w; } }
      shade[k] = sh;
      occ[k] = !mask[k] && n >= 4 && Math.abs(j - Hh / 2) > neck ? 1 : 0;
    }
    // softened, 1-2-1 each way
    for (let j = 0; j < Hh; j++) for (let i = 0; i < W; i++) {
      const k = j * W + i, l = i > 0 ? occ[k - 1] : 0, r = i < W - 1 ? occ[k + 1] : 0;
      soft[k] = (l + 2 * occ[k] + r) / 4;
    }
    for (let i = 0; i < W; i++) { let prev = 0; for (let j = 0; j < Hh; j++) { const k = j * W + i, cur = soft[k], next = j < Hh - 1 ? soft[k + W] : 0; occ[k] = (prev + 2 * cur + next) / 4; prev = cur; } }
    // sampled at twice the grid between cell centres; the edge where the softened field crosses a half,
    // over about a sample; a grain with few neighbours (the thread, a grain in the air) keeps its own cell
    const d = this.img.data, cols = SAND_RGB, SW = W * SUB, SH = Hh * SUB;
    for (let y = 0; y < SH; y++) {
      const fy = (y + 0.5) / SUB - 0.5, j0 = Math.max(0, Math.min(Hh - 2, Math.floor(fy))), ty = Math.max(0, Math.min(1, fy - j0)), jc = Math.min(Hh - 1, (y / SUB) | 0);
      for (let x = 0; x < SW; x++) {
        const fx = (x + 0.5) / SUB - 0.5, i0 = Math.max(0, Math.min(W - 2, Math.floor(fx))), tx = Math.max(0, Math.min(1, fx - i0)), ic = Math.min(W - 1, (x / SUB) | 0);
        const k0 = j0 * W + i0;
        const v = (occ[k0] * (1 - tx) + occ[k0 + 1] * tx) * (1 - ty) + (occ[k0 + W] * (1 - tx) + occ[k0 + W + 1] * tx) * ty;
        let a = v <= 0.36 ? 0 : v >= 0.64 ? 1 : ((v - 0.36) / 0.28) * ((v - 0.36) / 0.28) * (3 - 2 * ((v - 0.36) / 0.28));
        const kc = jc * W + ic;
        if (cell[kc] && a < 1) {
          let n = 0; for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) if ((di || dj) && at(ic + di, jc + dj)) n++;
          if (n <= 3) a = 1;
        }
        const o = (y * SW + x) * 4;
        if (a <= 0) { d[o + 3] = 0; continue; }
        const c = cols[(shade[kc] || 1) - 1];
        d[o] = c[0]; d[o + 1] = c[1]; d[o + 2] = c[2]; d[o + 3] = Math.round(a * 255);
      }
    }
    this.sandCanvas.getContext("2d")!.putImageData(this.img, 0, 0);
  }

  // ---------- glass, frame, sand
  private drawFront() {
    const x = this.front.getContext("2d")!, k = this.dpr, c = this.size / 2, H = this.H, gy = this.glass / 2, R = PROFILE.bulb * H;
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, this.front.width, this.front.height);
    x.setTransform(k, 0, 0, k, 0, 0); x.translate(c, c); x.rotate(this.angle);
    // the sand, smooth-edged, inside the glass's inner wall
    this.paintSand();
    x.save();
    x.beginPath();
    { const N = 160, ins = 2.3, lim = gy - 3;
      for (let q = 0; q <= N; q++) { const v = -1 + (2 * q) / N, y = Math.max(-lim, Math.min(lim, v * gy)), r = Math.max(0.9, halfWidth(y / gy, H) - ins); q ? x.lineTo(r, y) : x.moveTo(r, y); }
      for (let q = N; q >= 0; q--) { const v = -1 + (2 * q) / N, y = Math.max(-lim, Math.min(lim, v * gy)), r = Math.max(0.9, halfWidth(y / gy, H) - ins); x.lineTo(-r, y); }
      x.closePath(); }
    x.clip();
    x.imageSmoothingEnabled = true; x.imageSmoothingQuality = "high";
    x.drawImage(this.sandCanvas, -this.gw * this.cs / 2, -gy, this.gw * this.cs, this.gh * this.cs);
    x.restore();
    const line = (a: number) => `rgba(${this.line.join(",")},${a})`;
    // the glass: outer wall, and an inner wall line a little inside it
    const outline = (inset: number) => {
      x.beginPath();
      const N = 160;
      for (let q = 0; q <= N; q++) { const v = -1 + (2 * q) / N, r = halfWidth(v, H) - inset; q ? x.lineTo(r, v * gy) : x.moveTo(r, v * gy); }
      x.moveTo(-(halfWidth(-1, H) - inset), -gy);
      for (let q = 0; q <= N; q++) { const v = -1 + (2 * q) / N, r = halfWidth(v, H) - inset; x.lineTo(-r, v * gy); }
    };
    x.lineJoin = "round"; x.lineCap = "round";
    outline(0); x.strokeStyle = line(0.82); x.lineWidth = 1; x.stroke();
    outline(1.8); x.strokeStyle = line(0.2); x.lineWidth = 0.75; x.stroke();     // the glass's thickness
    // one short highlight on the left of each bulb, close to the wall, where the glass catches light
    x.strokeStyle = line(0.34); x.lineWidth = 1;
    for (const sgn of [-1, 1]) {
      x.beginPath();
      for (let q = 0; q <= 30; q++) { const v = sgn * (0.46 + 0.24 * q / 30), r = halfWidth(v, H) - 5.5; q ? x.lineTo(-r, v * gy) : x.moveTo(-r, v * gy); }
      x.stroke();
    }
    // the caps and the front posts
    const capW = R * 2 + 30, ct = this.capT, top = -gy - 3 - ct, bot = gy + 3;
    x.fillStyle = `rgb(${this.ground.join(",")})`; x.strokeStyle = line(0.9); x.lineWidth = 1;
    for (const y of [top, bot]) {
      x.beginPath(); x.roundRect(-capW / 2 + 0.5, y + 0.5, capW - 1, ct - 1, 3); x.fill(); x.stroke();
      // the cap's lip: a hairline along its inner face
      const ly = y === top ? y + ct - 4.5 : y + 4.5;
      x.beginPath(); x.moveTo(-capW / 2 + 6, ly); x.lineTo(capW / 2 - 6, ly); x.strokeStyle = line(0.3); x.stroke(); x.strokeStyle = line(0.9);
    }
    const px = capW / 2 - 9;
    x.fillStyle = line(0.9);
    for (const sx of [-1, 1]) x.fillRect(sx * px - 1.25, top + ct, 2.5, bot - top - ct);
  }

  private render() { this.drawBack(); this.drawFront(); }

  // ---------- turning
  private local(e: PointerEvent) { const b = this.front.getBoundingClientRect(); return [e.clientX - b.left - b.width / 2, e.clientY - b.top - b.height / 2]; }
  private bind() {
    const el = this.el;
    let lastP: [number, number, number] | null = null;
    const canTurn = () => !this.reduce && this.arrived && !this.locked;
    // a press that barely moves and lets go quickly is a click: it turns the glass over (and the page
    // inverts); anything else is a drag, as before
    let press: { x: number; y: number; t: number; moved: boolean } | null = null;
    el.addEventListener("pointerdown", (e) => {
      if (!canTurn()) return;
      const [px, py] = this.local(e);
      press = { x: e.clientX, y: e.clientY, t: performance.now(), moved: false };
      this.dragging = true; this.grab = Math.atan2(py, px) - this.angle; this.target = this.angle;
      el.setPointerCapture(e.pointerId); el.classList.add("dragging");
    });
    // the first drag of the visit: the caption fades for good (a click turns the glass but is not a drag)
    const firstDrag = () => {
      if (this.turned) return;
      this.turned = true; this.hint.classList.add("gone");
      try { sessionStorage.setItem("hg-turned", "1"); } catch { /* no storage */ }
      this.o.onFirstTurn?.();
    };
    el.addEventListener("pointermove", (e) => {
      const [px, py] = this.local(e);
      if (press && !press.moved && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 4) { press.moved = true; firstDrag(); }
      if (this.dragging) {
        if (press && !press.moved) return;   // not a drag yet
        let a = Math.atan2(py, px) - this.grab;
        while (a - this.target > Math.PI) a -= 2 * Math.PI; while (a - this.target < -Math.PI) a += 2 * Math.PI;   // continuous
        this.target = a; return;
      }
      // the cursor over the glass stirs the sand: its position and velocity in the grid's frame
      const now = performance.now();
      const ca = Math.cos(-this.angle), sa = Math.sin(-this.angle), lx = ca * px - sa * py, ly = sa * px + ca * py;
      const gi = lx / this.cs + (this.gw - 1) / 2, gj = (ly + this.glass / 2) / this.cs - 0.5;
      if (lastP) { const dt = Math.max(8, now - lastP[2]) / 1000; this.stir = { x: gi, y: gj, vx: (gi - lastP[0]) / dt * this.cs, vy: (gj - lastP[1]) / dt * this.cs, t: now }; }
      lastP = [gi, gj, now];
    });
    el.addEventListener("pointerleave", () => { lastP = null; });
    // before any click: it leans a few degrees toward a cursor that comes near (within about 380 px),
    // through the same spring, so it has weight and the sand shifts with it
    window.addEventListener("pointermove", (e) => {
      if (!canTurn() || this.dragging) return;
      const b = el.getBoundingClientRect(), dx = e.clientX - (b.left + b.width / 2), dy = e.clientY - (b.top + b.height / 2);
      const d = Math.hypot(dx, dy), near = Math.max(0, Math.min(1, (380 - d) / 240));
      this.lean = near * near * (3 - 2 * near) * Math.max(-1, Math.min(1, dx / 220)) * (5 * Math.PI / 180);
    }, { passive: true });
    document.addEventListener("pointerleave", () => { this.lean = 0; });
    const settle = (rest: number) => {
      const flipped = Math.round(rest / Math.PI) % 2 !== 0, was = Math.round(this.rest / Math.PI) % 2 !== 0;
      this.rest = rest; this.target = rest + this.lean;
      if (flipped !== was) { const b = el.getBoundingClientRect(); this.o.onFlip?.(flipped, { x: b.left + b.width / 2, y: b.top + b.height / 2 }); }
    };
    const up = () => {
      if (!this.dragging) return;
      this.dragging = false; el.classList.remove("dragging"); this.lean = 0;
      const click = press && !press.moved && performance.now() - press.t < 350;
      press = null;
      settle(click ? this.rest + Math.PI : Math.round(this.angle / Math.PI) * Math.PI);
    };
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      if (this.locked || (!this.arrived && !this.reduce)) return;
      this.lean = 0;
      settle(this.rest + Math.PI);
      if (this.reduce) { this.angle = this.target; this.order = null; for (let s = 0; s < 400; s++) this.stepSand(); this.render(); }
    });
  }
  private physics(dt: number) {
    if (!this.dragging && this.arrived) this.target = this.rest + this.lean;
    // a spring with inertia: stiffer and closely damped under the hand; on release, softer, with a
    // slight overshoot, as a heavy glass would settle
    const k = this.dragging ? 70 : 26, z = this.dragging ? 0.92 : 0.62, c = 2 * z * Math.sqrt(k);
    const steps = Math.max(1, Math.ceil(dt / 0.004)), h = dt / steps;
    for (let s = 0; s < steps; s++) { const acc = k * (this.target - this.angle) - c * this.vel; this.vel += acc * h; this.angle += this.vel * h; }
    if (!this.dragging && Math.abs(this.target - this.angle) < 1e-4 && Math.abs(this.vel) < 1e-4) { this.angle = this.target; this.vel = 0; }
  }

  start() {
    if (this.running) return; this.running = true; this.last = performance.now();
    const frame = (now: number) => {
      if (!this.running) return;
      this.raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
      if (this.arrived && !this.dragging) this.target = this.rest + this.lean;
      const moving = this.dragging || this.vel !== 0 || this.angle !== this.target;
      if (moving) this.physics(dt);
      if (!this.arrived) {
        // the arrival: the sand holds still until the glass has settled upright
        if (Math.abs(this.angle - this.target) < 0.003 && Math.abs(this.vel) < 0.02) { this.arrived = true; this.el.classList.remove("arriving"); }
      } else {
        // while it turns, the sand settles faster; during a run, when the sand is behind the budget's share
        // (a quick run), it runs faster still, up to about seven times, so the last grain lands soon after
        const behind = this.gate && this.gate.total ? this.gate.share * this.gate.total - this.gate.passed : 0;
        const steps = Math.max(moving ? 6 : 3, behind > 0 ? Math.min(20, 3 + Math.ceil(behind / 40)) : 0);
        for (let s = 0; s < steps; s++) this.stepSand();
        // a run: once the glass has turned over, the grains above the neck are the budget; when the run is
        // over and the last grain has landed, the page is told
        if (this.gate && !this.gate.total && Math.abs(this.angle - this.rest) < 0.01 && Math.abs(this.vel) < 0.05) this.armGate();
        if (this.gate && this.done && this.gate.share >= 1 && this.settledEmpty()) this.endRun();
      }
      let shifted = false;
      if (this.o.behind?.length && this.gl) {
        const now = this.relative(), off: [number, number] = [now[0] - this.paintedAt[0], now[1] - this.paintedAt[1]];
        if (Math.abs(off[0] - this.textOff[0]) + Math.abs(off[1] - this.textOff[1]) > 0.25) { this.textOff = off; shifted = true; }
      }
      if (moving || shifted || this.gl === null) this.drawBack();
      this.drawFront();
    };
    this.raf = requestAnimationFrame(frame);
  }
  stop() { this.running = false; cancelAnimationFrame(this.raf); }
}

function mulberry(a: number) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
