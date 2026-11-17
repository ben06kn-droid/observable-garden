// The fan: a background of random paths for the run page, below the hourglass's travel.
//
// Fine hairlines start at the left edge and travel right, each a random walk (its slope an AR(1)
// process, so it wanders smoothly), the paths of one start spreading apart as they go. All but one are
// a faint off-white; one is in the sand tone, and every so often it fades and another takes the colour.
// They draw themselves left to right at a pace that follows the scroll's speed and eases back to a slow
// idle, and fade to nothing before they reach the form's fields (`reach`). New ones keep starting.
// Nothing about them is data: no axes, no labels, no scale.
//
// The cursor carries a glass lens (about 240 px across): inside it the paths bend around its centre as
// through a thick bead, strongest at the centre and nothing at the rim, and each line splits into thin
// colour fringes that grow toward the rim along the bend. The glass itself shows as a faint tint and a
// thin bright edge on one side. It trails the cursor on a spring and lets go with a soft overshoot. Only
// pointer movement (mouse or pen) drives it; touch never does.
//
// How it is drawn: the paths go into a 2D canvas the width of the fan (off-white in its blue channel,
// sand in its red, added like light), and one WebGL pass composites that over the page's ground, with the
// lens's warp sampled once per colour channel (the fringes), the fade before the fields and the dimming
// behind text from a mask texture in page coordinates. The canvas is fixed to the viewport and behind
// the page's content, so the lens never touches text: it is under it, and dimmed where text is.
//
// Reduced motion: a still fan, no lens.

export interface FanRect { x: number; y: number; w: number; h: number; keep: number }   // page px; keep 0 = no lines there
export interface FanOptions {
  /** the fan's vertical extent, in page px */
  region: () => { top: number; bottom: number };
  /** for a page y, the x (page px) at which the paths must have faded to nothing */
  reach: (y: number) => number;
  /** text and fields over the fan: the lines are dimmed (keep ~0.3) or removed (keep 0) there */
  masks?: () => FanRect[];
  reduce?: boolean;
  lens?: boolean;
  seed?: number;
  /** wait for handover() before any path starts: the stream from the hourglass is the fan's first sand */
  awaitHandover?: boolean;
  /** the last `foot` px of the region: paths that start there slow, stop, and stay */
  foot?: number;
}

interface Path {
  y0: number; ys: Float32Array; head: number; delay: number; speed: number;
  life: number; dying: boolean; sand: number; sandTo: number; minY: number; maxY: number; rest: boolean;
}

const DX = 3;                                  // the walk's step, css px
const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uView; uniform float uDpr, uScroll; uniform vec2 uRegion;
uniform vec3 uGround, uLine, uSand, uHi; uniform float uWA, uSA, uTintA;
uniform sampler2D uPaths; uniform float uFanW;
uniform sampler2D uMask; uniform vec4 uMaskBox;
uniform vec2 uLens; uniform float uLensR, uLensS;
uniform vec4 uStream;   // a handover stream: x from, x to, y (page), alpha
out vec4 o;
vec2 lines(vec2 p) {                     // (off-white, sand) coverage at a viewport point, faded before the fields
  if (p.x < 0.0 || p.x > uFanW || p.y < 0.0 || p.y > uView.y) return vec2(0.0);
  vec4 t = texture(uPaths, vec2(p.x / uFanW, p.y / uView.y));
  float m = texture(uMask, (vec2(p.x, p.y + uScroll) - uMaskBox.xy) / uMaskBox.zw).r;
  return vec2(t.b, t.r) * m;
}
void main() {
  vec2 pc = vec2(gl_FragCoord.x, uView.y * uDpr - gl_FragCoord.y) / uDpr;
  float py = pc.y + uScroll;
  if (py < uRegion.x || py > uRegion.y) { o = vec4(0.0); return; }
  vec2 d = pc - uLens; float u = length(d) / uLensR;
  float inL = step(u, 1.0);
  // the bead: samples drawn toward the centre (magnified), the pull (1-u^2)^2 so it ends smoothly at the rim
  float w = inL * (1.0 - u * u) * (1.0 - u * u);
  float bend = 0.3 * uLensS * w;
  // the fringes: each channel bent a little differently, more toward the rim, easing out at the rim itself
  float chrom = inL * 0.02 * uLensS * u * u * smoothstep(1.0, 0.8, u);
  vec3 col = uGround;
  for (int k = 0; k < 3; k++) {
    float f = (1.0 - bend) * (1.0 + (float(k) - 1.0) * chrom);
    vec2 a = lines(uLens + d * f);
    float c = uGround[k];
    c = mix(c, uLine[k], clamp(a.x * uWA, 0.0, 1.0));
    c = mix(c, uSand[k], clamp(a.y * uSA, 0.0, 1.0));
    col[k] = c;
  }
  // the glass: a very faint tint, soft at its edge, and a thin bright edge on its upper left; never where text is
  float keepText = texture(uMask, (vec2(pc.x, py) - uMaskBox.xy) / uMaskBox.zw).g;
  float edgePx = uLensR * (1.0 - u);                       // distance inside the rim, css px
  float disc = clamp(edgePx / 3.0, 0.0, 1.0) * inL;        // a soft edge three pixels wide, no halo outside
  col = mix(col, uLine, uTintA * clamp(uLensS, 0.0, 1.0) * disc);   // faint enough to sit under text unnoticed
  float side = max(0.0, dot(normalize(d + 1e-5), normalize(vec2(-0.75, -1.0))));
  float rim = clamp(1.0 - abs(edgePx - 1.6) / 1.1, 0.0, 1.0) * side * side;   // a thin line just inside the rim
  // the glass's edge all round, a hairline, so it reads on either ground; then the bright side
  float ring = clamp(1.0 - abs(edgePx - 0.6) / 0.8, 0.0, 1.0) * inL;
  col = mix(col, uLine, 0.13 * clamp(uLensS, 0.0, 1.0) * ring * keepText);
  col = mix(col, uHi, 0.6 * clamp(uLensS, 0.0, 1.0) * rim * keepText);
  // the handover: a thin stream of sand along a rule
  if (uStream.w > 0.0) {
    float x0 = min(uStream.x, uStream.y), x1 = max(uStream.x, uStream.y);
    float dy = abs(py - uStream.z), inX = step(x0, pc.x) * step(pc.x, x1);
    float cov = clamp((0.75 - dy) * uDpr + 0.5, 0.0, 1.0) * inX * uStream.w;
    // a soft head where the stream is running
    cov *= smoothstep(0.0, 18.0, pc.x - x0 + 1.0) * 0.6 + 0.4;
    col = mix(col, uSand, cov);
  }
  o = vec4(col, 1.0);
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
  private rnd: () => number; private raf = 0; private last = 0; private running = false;
  private speed = 55; private scrollV = 0; private lastScroll = 0; private lastScrollT = 0;
  private sinceSpawn = 9; private nextSand = 12; private ground: [number, number, number] = [0, 0, 0]; private line: [number, number, number] = [1, 1, 1];
  private sand: [number, number, number] = [0.84, 0.7, 0.48]; private wa = 0.2; private hi: [number, number, number] = [1, 1, 1]; private tintA = 0.02;
  // the lens: where it is (viewport css px), its velocity, how present it is (a spring too)
  private lens = { x: -999, y: -999, vx: 0, vy: 0, s: 0, vs: 0, tx: -999, ty: -999, ts: 0 };
  private stream: { from: number; y: number; t: number; done?: () => void } | null = null;
  private started = true;
  private onScroll = () => {
    const now = performance.now(), y = scrollY, dt = Math.max(8, now - this.lastScrollT);
    this.scrollV = 0.6 * this.scrollV + 0.4 * ((y - this.lastScroll) / dt) * 1000;
    this.lastScroll = y; this.lastScrollT = now; this.wake();
  };
  private onMove = (e: PointerEvent) => {
    if (e.pointerType === "touch" || this.o.reduce || this.o.lens === false) return;
    const r = this.o.region(), py = e.clientY + scrollY;
    const over = py > r.top && py < r.bottom && e.clientX < Math.max(this.fanW + 160, 0);
    this.lens.tx = e.clientX; this.lens.ty = e.clientY; this.lens.ts = over ? 1 : 0;
    if (over && this.lens.s < 0.02 && this.lens.x < -900) { this.lens.x = e.clientX; this.lens.y = e.clientY; }
    this.wake();
  };
  private onLeave = () => { this.lens.ts = 0; this.wake(); };
  private onResize = () => { this.layout(); };

  constructor(host: HTMLElement, o: FanOptions) {
    this.o = o; this.rnd = mulberry(o.seed ?? 11); this.started = !o.awaitHandover || !!o.reduce;
    this.canvas = document.createElement("canvas"); this.canvas.className = "fan"; this.canvas.setAttribute("aria-hidden", "true");
    host.prepend(this.canvas);
    this.pcv = document.createElement("canvas"); this.ctx = this.pcv.getContext("2d")!;
    this.initGL(); this.readPalette(); this.layout();
    this.lastScroll = scrollY; this.lastScrollT = performance.now();
    addEventListener("scroll", this.onScroll, { passive: true });
    addEventListener("pointermove", this.onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", this.onLeave);
    addEventListener("resize", this.onResize);
    if (o.reduce) this.still(); else this.wake();
  }
  destroy() { this.running = false; cancelAnimationFrame(this.raf); removeEventListener("scroll", this.onScroll); removeEventListener("pointermove", this.onMove); document.documentElement.removeEventListener("pointerleave", this.onLeave); removeEventListener("resize", this.onResize); this.canvas.remove(); }

  /** read the colours from the page's tokens (after a palette swap, for one) */
  refreshPalette() { this.readPalette(); this.render(); }
  private readPalette() {
    const cs = getComputedStyle(this.canvas);
    this.ground = rgb(cs.getPropertyValue("--fan-ground") || "#121416"); this.line = rgb(cs.getPropertyValue("--fan-line") || "#f0f1fa");
    this.sand = rgb(cs.getPropertyValue("--fan-sand") || "#d6b27b"); this.wa = Number(cs.getPropertyValue("--fan-alpha")) || 0.2;
    this.hi = rgb(cs.getPropertyValue("--fan-hi") || "#ffffff"); this.tintA = Number(cs.getPropertyValue("--fan-tint")) || 0.02;
  }

  /** sizes, the reach, the masks: call after a layout change */
  layout() {
    this.dpr = Math.min(2, devicePixelRatio || 1); this.vw = innerWidth; this.vh = innerHeight;
    const r = this.o.region();
    let maxReach = 0; for (let y = r.top; y <= r.bottom; y += 40) maxReach = Math.max(maxReach, this.o.reach(y));
    this.fanW = Math.max(40, Math.min(this.vw, Math.ceil(maxReach + 8)));
    this.canvas.width = Math.round(this.vw * this.dpr); this.canvas.height = Math.round(this.vh * this.dpr);
    this.pcv.width = Math.round(this.fanW * this.dpr); this.pcv.height = Math.round(this.vh * this.dpr);
    this.buildMask();
    if (this.o.reduce) this.still(); else this.render();
  }

  /** the handover: a thin stream of sand from (x, y) along the rule at y to the left edge, which becomes
   *  the first sand-toned path; resolves when the path has started */
  handover(from: { x: number; y: number }): Promise<void> {
    return new Promise((res) => { this.stream = { from: from.x, y: from.y, t: 0, done: res }; this.wake(); });
  }
  /** take the handover back (the visitor scrolled above it): the stream and its path go */
  resetHandover() {
    this.stream = null;
    if (this.o.awaitHandover) { this.started = false; for (const p of this.paths) p.dying = true; }
    else for (const p of this.paths) if (p.sand > 0) p.dying = true;
    this.wake();
  }

  // ---------- the mask: the fade before the fields (r) and where text and fields are (g, for the glass)
  private buildMask() {
    const gl = this.gl; if (!gl) return;
    const r = this.o.region(), k = 0.25, W = Math.ceil(this.vw * k), H = Math.max(1, Math.ceil((r.bottom - r.top) * k));
    const data = new Uint8Array(W * H * 4);
    for (let j = 0; j < H; j++) {
      const y = r.top + (j + 0.5) / k, reach = this.o.reach(y), fade0 = reach * 0.62;
      for (let i = 0; i < W; i++) {
        const x = (i + 0.5) / k;
        // fully drawn until a little over half way, then easing to nothing at the reach
        const t = Math.max(0, Math.min(1, (x - fade0) / Math.max(1, reach - fade0)));
        let keep = 1 - t * t * (3 - 2 * t); if (x < 6) keep *= x / 6;
        const o = (j * W + i) * 4; data[o] = Math.round(keep * 255); data[o + 1] = 255; data[o + 3] = 255;
      }
    }
    for (const m of this.o.masks?.() ?? []) {
      const i0 = Math.max(0, Math.floor(m.x * k)), i1 = Math.min(W - 1, Math.ceil((m.x + m.w) * k));
      const j0 = Math.max(0, Math.floor((m.y - r.top) * k)), j1 = Math.min(H - 1, Math.ceil((m.y + m.h - r.top) * k));
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) { const o = (j * W + i) * 4; data[o] = Math.round(data[o] * m.keep); data[o + 1] = 0; }
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
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    gl.useProgram(p);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(p, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uView", "uDpr", "uScroll", "uRegion", "uGround", "uLine", "uSand", "uHi", "uWA", "uSA", "uTintA", "uPaths", "uFanW", "uMask", "uMaskBox", "uLens", "uLensR", "uLensS", "uStream"]) this.u[n] = gl.getUniformLocation(p, n);
    const tex = () => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
    this.texP = tex(); this.texM = tex();
    this.gl = gl;
  }

  // ---------- the paths
  private spawn(y0: number, opts: { sand?: boolean; down?: boolean; t?: number } = {}) {
    const reach = this.o.reach(y0), n = Math.ceil(reach / DX) + 2;
    const count = opts.sand ? 1 : 7 + Math.floor(this.rnd() * 6);
    const spread = opts.sand ? 45 + this.rnd() * 20 : 70 + this.rnd() * 90, phi = 0.9;   // the handover's path stays near the rule
    for (let q = 0; q < count; q++) {
      const ys = new Float32Array(n); let v = 0, y = y0, mn = y0, mx = y0;
      const sigma = spread * (1 - phi) / Math.sqrt(n) * (0.7 + this.rnd() * 0.6);
      // a slight lean per path, so the paths of one start open like a fan rather than a knot
      const drift = ((q + 0.5) / count - 0.5) * spread * 0.9 / n + (opts.down ? spread * 0.35 / n : 0);
      for (let i = 0; i < n; i++) {
        const g = Math.sqrt(-2 * Math.log(this.rnd() + 1e-9)) * Math.cos(2 * Math.PI * this.rnd());
        v = phi * v + sigma * g; y += v + drift;
        if (opts.down && y < y0 + 2) { y = y0 + 2 + (y0 + 2 - y) * 0.2; v = Math.abs(v) * 0.3; }   // kept below the rule, gently
        ys[i] = y; mn = Math.min(mn, y); mx = Math.max(mx, y);
      }
      const r = this.o.region(), rest = !!this.o.foot && y0 > r.bottom - this.o.foot && !opts.sand;
      this.paths.push({ rest, y0, ys, head: opts.t ?? 0, delay: opts.sand ? 0 : q * (0.08 + this.rnd() * 0.16), speed: 0.85 + this.rnd() * 0.3,
        life: 1, dying: false, sand: opts.sand ? 1 : 0, sandTo: opts.sand ? 1 : 0, minY: mn - 2, maxY: mx + 2 });
    }
  }
  private visibleBand() { const r = this.o.region(); return [Math.max(r.top + 20, scrollY - this.vh * 0.1), Math.min(r.bottom - 20, scrollY + this.vh * 1.05)]; }
  private step(dt: number) {
    // the pace: a slow idle, quicker while the page scrolls, easing back
    this.scrollV *= Math.exp(-dt / 0.25);
    const target = 55 + Math.min(1300, Math.abs(this.scrollV) * 1.4);
    this.speed += (target - this.speed) * (1 - Math.exp(-dt / (target > this.speed ? 0.18 : 0.6)));
    const [b0, b1] = this.visibleBand();
    // new starts, while there is room in view: each at least 70 px from the others' starts
    this.sinceSpawn += dt * this.speed / 55;
    const live = this.paths.filter((p) => !p.dying && p.y0 > b0 - 200 && p.y0 < b1 + 200);
    if (this.started && b1 > b0 && this.sinceSpawn > 0.7 && new Set(live.map((p) => p.y0)).size < Math.max(3, Math.round((b1 - b0) / 115))) {
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
      if (!p.rest && p.head >= n && p.sandTo !== 1) p.dying = true;   // the sand path stays until the tone moves on
      if (p.dying) p.life -= dt / 2.4;
      p.sand += (p.sandTo - p.sand) * (1 - Math.exp(-dt / 0.5));
    }
    this.paths = this.paths.filter((p) => p.life > 0);
    // the sand tone moves on every so often: the sand path fades and a young one in view takes the colour
    this.nextSand -= dt;
    const sandNow = this.paths.find((p) => p.sandTo === 1);
    if (this.started && (!sandNow || this.nextSand <= 0 || sandNow.dying)) {
      const cand = this.paths.filter((p) => p.sandTo === 0 && !p.dying && !p.rest && p.delay <= 0 && p.head > 6 && p.head < p.ys.length * 0.45 && p.y0 > b0 && p.y0 < b1);
      if (cand.length) {
        if (sandNow) { sandNow.sandTo = 0; sandNow.dying = true; }
        cand[Math.floor(this.rnd() * cand.length)].sandTo = 1;
        this.nextSand = 10 + this.rnd() * 6;
      }
    }
    this.stepLens(dt); this.stepStream(dt);
  }
  private stepLens(dt: number) {
    // the lens: its centre trails the cursor on a spring, and its presence springs in and out with a soft
    // overshoot, so the paths come back past straight and settle
    const L = this.lens;
    if (L.tx > -900) {
      const k = 90, c = 2 * 0.62 * Math.sqrt(k);
      if (L.x < -900) { L.x = L.tx; L.y = L.ty; }
      L.vx += (k * (L.tx - L.x) - c * L.vx) * dt; L.vy += (k * (L.ty - L.y) - c * L.vy) * dt;
      L.x += L.vx * dt; L.y += L.vy * dt;
    }
    { const k = 60, c = 2 * 0.45 * Math.sqrt(k); L.vs += (k * (L.ts - L.s) - c * L.vs) * dt; L.s += L.vs * dt; }
  }
  private stepStream(dt: number) {
    // the handover stream: out along the rule (0.9 s), then drawn back into the new path (0.6 s)
    if (this.stream) {
      const s = this.stream; s.t += dt;
      if (s.t >= 0.9 && !this.paths.some((p) => p.sandTo === 1 && p.y0 === s.y + 3)) {
        for (const p of this.paths) if (p.sandTo === 1) { p.sandTo = 0; p.dying = true; }
        this.spawn(s.y + 3, { sand: true, down: true }); this.nextSand = 14; this.started = true; s.done?.(); s.done = undefined;
      }
      if (s.t > 1.6) this.stream = null;
    }
  }

  private drawPaths() {
    const x = this.ctx, k = this.dpr;
    x.setTransform(1, 0, 0, 1, 0, 0); x.globalCompositeOperation = "source-over"; x.fillStyle = "#000"; x.fillRect(0, 0, this.pcv.width, this.pcv.height);
    x.setTransform(k, 0, 0, k, 0, -scrollY * k); x.globalCompositeOperation = "lighter";
    x.lineWidth = 0.8; x.lineJoin = "round"; x.lineCap = "round";
    const top = scrollY - 4, bot = scrollY + this.vh + 4;
    for (const p of this.paths) {
      if (p.delay > 0 || p.maxY < top || p.minY > bot || p.head < 1) continue;
      const n = Math.floor(p.head), f = p.head - n, a = Math.max(0, Math.min(1, p.life));
      const trace = () => {
        x.beginPath(); x.moveTo(0, p.ys[0]);
        for (let i = 1; i < n; i++) x.quadraticCurveTo(i * DX, p.ys[i], (i + 0.5) * DX, (p.ys[i] + p.ys[i + 1]) / 2);
        if (n + 1 < p.ys.length) x.lineTo((n + f) * DX, p.ys[n] + (p.ys[n + 1] - p.ys[n]) * f); else x.lineTo(n * DX, p.ys[n]);
      };
      const w = a * (1 - p.sand), s = a * p.sand;
      if (w > 0.004) { x.strokeStyle = `rgba(0,0,255,${w.toFixed(3)})`; trace(); x.stroke(); }
      if (s > 0.004) { x.strokeStyle = `rgba(255,0,0,${s.toFixed(3)})`; x.lineWidth = 1.0; trace(); x.stroke(); x.lineWidth = 0.8; }
    }
  }

  render() {
    const gl = this.gl; if (!gl) return;
    this.drawPaths();
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    const r = this.o.region(), L = this.lens;
    gl.uniform2f(this.u.uView, this.vw, this.vh); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uScroll, scrollY);
    gl.uniform2f(this.u.uRegion, r.top, r.bottom);
    gl.uniform3f(this.u.uGround, ...this.ground); gl.uniform3f(this.u.uLine, ...this.line); gl.uniform3f(this.u.uSand, ...this.sand);
    gl.uniform1f(this.u.uWA, this.wa); gl.uniform1f(this.u.uSA, 0.95); gl.uniform3f(this.u.uHi, ...this.hi); gl.uniform1f(this.u.uTintA, this.tintA);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.texP);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.pcv); gl.uniform1i(this.u.uPaths, 0);
    gl.uniform1f(this.u.uFanW, this.fanW);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.texM); gl.uniform1i(this.u.uMask, 1);
    gl.uniform4f(this.u.uMaskBox, this.maskBox[0], this.maskBox[1], this.maskBox[2], this.maskBox[3]);
    gl.uniform2f(this.u.uLens, L.x, L.y); gl.uniform1f(this.u.uLensR, 120); gl.uniform1f(this.u.uLensS, this.o.reduce ? 0 : L.s);
    if (this.stream) {
      const s = this.stream, e = (t: number) => { t = Math.max(0, Math.min(1, t)); return 1 - Math.pow(1 - t, 3); };
      const head = s.from * (1 - e(s.t / 0.9)), tail = s.from * (1 - e((s.t - 0.75) / 0.85));
      gl.uniform4f(this.u.uStream, head, tail, s.y - 3, 1);   // just above the rule, which is drawn over the fan
    } else gl.uniform4f(this.u.uStream, 0, 0, 0, 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  // ---------- the loop: runs while the fan is in view (or a handover or the lens is moving), else sleeps
  private wake() { if (this.running || this.o.reduce) return; this.running = true; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
    const r = this.o.region(), inView = r.bottom > scrollY && r.top < scrollY + this.vh;
    if (!inView && !this.stream) {
      // off screen: one last frame (so nothing stale shows if it comes back), then sleep until a scroll
      this.render(); this.running = false; return;
    }
    this.step(dt); this.render();
    this.raf = requestAnimationFrame(this.frame);
  };

  /** reduced motion: the fan drawn once, its paths complete and still, no lens; redrawn on scroll */
  private still() {
    if (!this.paths.length) {
      const r = this.o.region();
      for (let y = r.top + 60; y < r.bottom - 40; y += 150 + this.rnd() * 60) this.spawn(y);
      for (const p of this.paths) { p.delay = 0; p.head = (p.ys.length - 1) * (0.55 + this.rnd() * 0.45); }
      const s = this.paths[Math.floor(this.paths.length * 0.2)]; if (s) { s.sand = s.sandTo = 1; }
      removeEventListener("scroll", this.onScroll); addEventListener("scroll", () => this.render(), { passive: true });
    }
    this.render();
  }
}
