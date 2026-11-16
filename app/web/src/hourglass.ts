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
  rules?: number[];               // page rules passing behind, as y in the box's css px
  reduce?: boolean;
}

const C = {
  ground: [0x12, 0x14, 0x16], line: [0xf0, 0xf1, 0xfa], rule: [0x2c, 0x2f, 0x35],
  sand: ["#d6b27b", "#d1ab73", "#dbb883", "#cea86f"],     // one sand, four close tones
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
uniform vec4 uRules;       // up to four page rules, y in css px (negative = none)
uniform vec3 uGround, uLine, uRule;
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
  vec2 s = q; float px = 1.0 / uDpr;
  if (abs(v) < 1.0) {
    float r = halfWidth(v, uH);
    float a = q.x / r;
    if (abs(a) < 1.0) {
      // a thick cylinder: magnified behind the middle, pulled outward and bent toward the edges
      float m = sign(a) * pow(abs(a), 1.65);
      s = vec2(m * r * 0.98, q.y * (1.0 - 0.035 * (1.0 - a * a)));
      px *= 0.6;                                                             // lines seen magnified: keep them fine
    }
  }
  vec3 col = uGround;
  // the frame's rear posts, behind the glass
  float post = 0.0;
  if (abs(s.y) < gy) post = max(cover(s.x - uPostX, uPostW, px), cover(s.x + uPostX, uPostW, px));
  col = mix(col, uLine, post * 0.26);
  // page rules passing behind, fixed to the page
  vec2 sp = rot(s, uAngle) + c;
  for (int i = 0; i < 4; i++) { float y = uRules[i]; if (y >= 0.0) col = mix(col, uRule, cover(sp.y - y, 1.0, px)); }
  o = vec4(col, 1.0);
}`;

export class Hourglass {
  readonly el: HTMLDivElement;
  private back: HTMLCanvasElement; private front: HTMLCanvasElement;
  private gl: WebGL2RenderingContext | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {};
  private size = 0; private dpr = 1;
  private H: number; private glass: number; private capT: number; private rules: number[]; private reduce: boolean;
  // turning
  angle = 0; private vel = 0; private target = 0; private dragging = false; private grab = 0;
  // sand
  private cs = 1.75; private gw = 0; private gh = 0; private mask!: Uint8Array; private cell!: Uint8Array; private stamp!: Uint16Array; private tick = 1;
  private order: Int32Array | null = null; private orderR: Int32Array | null = null; private orderG = [9, 9];
  private img!: ImageData; private sandCanvas!: HTMLCanvasElement;
  private stir: { x: number; y: number; vx: number; vy: number; t: number } | null = null;
  private raf = 0; private last = 0; private running = false;

  constructor(host: HTMLElement, o: HourglassOptions) {
    this.H = o.height; this.capT = Math.round(o.height * 0.03); this.glass = o.height - 2 * this.capT - 6;
    this.rules = o.rules ?? []; this.reduce = !!o.reduce;
    this.el = document.createElement("div"); this.el.className = "hourglass";
    this.el.tabIndex = 0; this.el.setAttribute("role", "button");
    this.el.setAttribute("aria-label", "Hourglass: drag to turn it, or press Enter to flip it");
    this.back = document.createElement("canvas"); this.front = document.createElement("canvas");
    this.back.className = "hg-back"; this.front.className = "hg-front";
    for (const c of [this.back, this.front]) c.setAttribute("aria-hidden", "true");
    this.el.append(this.back, this.front);
    host.appendChild(this.el);
    this.layout();
    if (!this.reduce) this.initGL();
    this.initSand();
    this.bind();
    this.render();
    if (!this.reduce) this.start();
  }

  private layout() {
    this.size = Math.ceil(Math.hypot(this.H, 2 * PROFILE.bulb * this.H + 40) + 24);
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.el.style.setProperty("--hg", `${this.size}px`);
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
    for (const n of ["uSize", "uDpr", "uAngle", "uH", "uGlass", "uPostX", "uPostW", "uRules", "uGround", "uLine", "uRule"]) this.u[n] = gl.getUniformLocation(p, n);
    this.gl = gl;
  }
  private postX() { return PROFILE.bulb * this.H * 0.62; }
  private drawBack() {
    const gl = this.gl;
    if (gl) {
      gl.viewport(0, 0, this.back.width, this.back.height);
      gl.uniform2f(this.u.uSize, this.size, this.size); gl.uniform1f(this.u.uDpr, this.dpr); gl.uniform1f(this.u.uAngle, this.angle);
      gl.uniform1f(this.u.uH, this.H); gl.uniform1f(this.u.uGlass, this.glass); gl.uniform1f(this.u.uPostX, this.postX()); gl.uniform1f(this.u.uPostW, 1.5);
      const r = [0, 1, 2, 3].map((i) => this.rules[i] ?? -1); gl.uniform4f(this.u.uRules, r[0], r[1], r[2], r[3]);
      const f = (c: number[]) => c.map((x) => x / 255) as [number, number, number];
      gl.uniform3f(this.u.uGround, ...f(C.ground)); gl.uniform3f(this.u.uLine, ...f(C.line)); gl.uniform3f(this.u.uRule, ...f(C.rule));
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      return;
    }
    // no WebGL2 (or reduced motion): the same lines, straight
    const x = this.back.getContext("2d")!, k = this.dpr, c = this.size / 2;
    x.setTransform(k, 0, 0, k, 0, 0);
    x.fillStyle = `rgb(${C.ground.join(",")})`; x.fillRect(0, 0, this.size, this.size);
    x.fillStyle = `rgb(${C.rule.join(",")})`; for (const y of this.rules) x.fillRect(0, Math.round(y), this.size, 1);
    x.translate(c, c); x.rotate(this.angle);
    x.fillStyle = `rgba(${C.line.join(",")},0.26)`;
    for (const sx of [-1, 1]) x.fillRect(sx * this.postX() - 0.75, -this.glass / 2, 1.5, this.glass);
  }

  // ---------- the sand
  private initSand() {
    const cs = this.cs, R = PROFILE.bulb * this.H, gy = this.glass / 2;
    this.gw = Math.ceil((2 * R) / cs); this.gh = Math.ceil(this.glass / cs);
    const n = this.gw * this.gh; this.mask = new Uint8Array(n); this.cell = new Uint8Array(n); this.stamp = new Uint16Array(n);
    const wall = 2.6;
    for (let j = 0; j < this.gh; j++) for (let i = 0; i < this.gw; i++) {
      const x = (i + 0.5) * cs - R, y = (j + 0.5) * cs - gy;
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
    const shade = () => 1 + Math.floor(rnd() * C.sand.length);
    for (let q = 0; q < inTop; q++) this.cell[top[q]] = shade();
    for (let q = 0; q < total - inTop; q++) this.cell[bot[q]] = shade();
    this.img = new ImageData(this.gw, this.gh);
    this.sandCanvas = document.createElement("canvas"); this.sandCanvas.width = this.gw; this.sandCanvas.height = this.gh;
    for (let s = 0; s < 220; s++) this.stepSand(rnd);   // let it settle
  }
  private gravity(): [number, number] { return [Math.sin(this.angle), Math.cos(this.angle)]; }
  private stepSand(rnd: () => number = Math.random) {
    const W = this.gw, Hh = this.gh, cell = this.cell, mask = this.mask, st = this.stamp;
    const g = this.gravity();
    // process cells from the bottom (along gravity) up, so each grain moves once; across each level,
    // alternately from one side and the other, so the sand favours neither
    if (!this.order || Math.abs(g[0] - this.orderG[0]) + Math.abs(g[1] - this.orderG[1]) > 0.03) {
      const idx: number[] = []; for (let k = 0; k < W * Hh; k++) if (mask[k]) idx.push(k);
      const key = (k: number) => Math.round(((k % W) * g[0] + Math.floor(k / W) * g[1]) * 2);
      const side = (k: number) => (k % W) * g[1] - Math.floor(k / W) * g[0];
      idx.sort((a, b) => key(b) - key(a) || side(a) - side(b));
      this.order = Int32Array.from(idx);
      idx.sort((a, b) => key(b) - key(a) || side(b) - side(a));
      this.orderR = Int32Array.from(idx); this.orderG = g;
    }
    // the eight directions; the primary is the one nearest gravity, then its neighbours either side
    const ang = Math.atan2(g[1], g[0]), oct = Math.round(ang / (Math.PI / 4));
    const dir = (o: number) => { const a = o * Math.PI / 4; return [Math.round(Math.cos(a)), Math.round(Math.sin(a))]; };
    const d0 = dir(oct), dl = dir(oct - 1), dr = dir(oct + 1), sl = dir(oct - 2), sr = dir(oct + 2);
    const t = (this.tick = (this.tick + 1) & 0xffff) || (this.tick = 1);
    const ok = (i: number, j: number) => i >= 0 && j >= 0 && i < W && j < Hh && mask[j * W + i] === 1 && cell[j * W + i] === 0;
    const inside = (i: number, j: number) => i >= 0 && j >= 0 && i < W && j < Hh && mask[j * W + i] === 1;
    const wallBy = (i: number, j: number) => !inside(i - 1, j) || !inside(i + 1, j);
    for (const k of (t & 1 ? this.order : this.orderR!)) {
      const v = cell[k]; if (!v || st[k] === t) continue;
      const i = k % W, j = (k / W) | 0;
      let to = -1;
      if (ok(i + d0[0], j + d0[1])) to = (j + d0[1]) * W + i + d0[0];
      // friction: a grain falls whenever it can, but slides only some of the time, and against the glass
      // less often still, so the top drains from its middle into a crater while the sand on the walls holds
      else if (rnd() < (wallBy(i, j) ? 0.18 : 0.5)) {
        const first = rnd() < 0.5 ? dl : dr, second = first === dl ? dr : dl;
        if (ok(i + first[0], j + first[1])) to = (j + first[1]) * W + i + first[0];
        else if (ok(i + second[0], j + second[1])) to = (j + second[1]) * W + i + second[0];
        else if (rnd() < 0.06) {   // a little slide along the surface: a gentler angle of repose
          const side = rnd() < 0.5 ? sl : sr, below = side === sl ? dl : dr;
          if (ok(i + side[0], j + side[1]) && ok(i + side[0] + below[0] - d0[0], j + side[1] + below[1] - d0[1])) to = (j + side[1]) * W + i + side[0];
        }
      }
      if (to >= 0) { cell[to] = v; cell[k] = 0; st[to] = t; }
    }
    // the cursor stirs grains near it, in the direction it moves
    const s = this.stir;
    if (s && performance.now() - s.t < 120) {
      const sp = Math.hypot(s.vx, s.vy); if (sp > 1) {
        const ux = s.vx / sp, uy = s.vy / sp, rad = 7, p = Math.min(0.9, sp / 900);
        const ci = Math.round(s.x), cj = Math.round(s.y);
        for (let j = cj - rad; j <= cj + rad; j++) for (let i = ci - rad; i <= ci + rad; i++) {
          if (i < 0 || j < 0 || i >= W || j >= Hh || (i - ci) ** 2 + (j - cj) ** 2 > rad * rad) continue;
          const k = j * W + i; if (!cell[k] || rnd() > p) continue;
          const ti = i + Math.round(ux * 2), tj = j + Math.round(uy * 2) - (rnd() < 0.5 ? 1 : 0);
          if (ok(ti, tj)) { cell[tj * W + ti] = cell[k]; cell[k] = 0; }
        }
      }
    }
  }
  private paintSand() {
    const d = this.img.data, cell = this.cell, cols = C.sand.map((h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]);
    for (let k = 0; k < cell.length; k++) {
      const v = cell[k], o = k * 4;
      if (v) { const c = cols[v - 1]; d[o] = c[0]; d[o + 1] = c[1]; d[o + 2] = c[2]; d[o + 3] = 255; } else d[o + 3] = 0;
    }
    this.sandCanvas.getContext("2d")!.putImageData(this.img, 0, 0);
  }

  // ---------- glass, frame, sand
  private drawFront() {
    const x = this.front.getContext("2d")!, k = this.dpr, c = this.size / 2, H = this.H, gy = this.glass / 2, R = PROFILE.bulb * H;
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, this.front.width, this.front.height);
    x.setTransform(k, 0, 0, k, 0, 0); x.translate(c, c); x.rotate(this.angle);
    // the sand, cell by cell (crisp: no smoothing)
    this.paintSand();
    x.imageSmoothingEnabled = false;
    x.drawImage(this.sandCanvas, -R, -gy, this.gw * this.cs, this.gh * this.cs);
    const line = (a: number) => `rgba(${C.line.join(",")},${a})`;
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
    x.fillStyle = `rgb(${C.ground.join(",")})`; x.strokeStyle = line(0.9); x.lineWidth = 1;
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
    el.addEventListener("pointerdown", (e) => {
      if (this.reduce) return;
      const [px, py] = this.local(e);
      this.dragging = true; this.grab = Math.atan2(py, px) - this.angle; this.target = this.angle;
      el.setPointerCapture(e.pointerId); el.classList.add("dragging");
    });
    el.addEventListener("pointermove", (e) => {
      const [px, py] = this.local(e);
      if (this.dragging) {
        let a = Math.atan2(py, px) - this.grab;
        while (a - this.target > Math.PI) a -= 2 * Math.PI; while (a - this.target < -Math.PI) a += 2 * Math.PI;   // continuous
        this.target = a; return;
      }
      // the cursor over the glass stirs the sand: its position and velocity in the grid's frame
      const now = performance.now();
      const ca = Math.cos(-this.angle), sa = Math.sin(-this.angle), lx = ca * px - sa * py, ly = sa * px + ca * py;
      const gi = (lx + PROFILE.bulb * this.H) / this.cs, gj = (ly + this.glass / 2) / this.cs;
      if (lastP) { const dt = Math.max(8, now - lastP[2]) / 1000; this.stir = { x: gi, y: gj, vx: (gi - lastP[0]) / dt * this.cs, vy: (gj - lastP[1]) / dt * this.cs, t: now }; }
      lastP = [gi, gj, now];
    });
    const up = () => { if (!this.dragging) return; this.dragging = false; el.classList.remove("dragging"); this.target = Math.round(this.angle / Math.PI) * Math.PI; };
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    el.addEventListener("pointerleave", () => { lastP = null; });
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      this.target = Math.round(this.angle / Math.PI) * Math.PI + Math.PI;
      if (this.reduce) { this.angle = this.target; this.order = null; for (let s = 0; s < 400; s++) this.stepSand(); this.render(); }
    });
  }
  private physics(dt: number) {
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
      const moving = this.dragging || this.vel !== 0 || this.angle !== this.target;
      if (moving) this.physics(dt);
      for (let s = 0; s < 3; s++) this.stepSand();
      if (moving || this.gl === null) this.drawBack();
      this.drawFront();
    };
    this.raf = requestAnimationFrame(frame);
  }
  stop() { this.running = false; cancelAnimationFrame(this.raf); }
}

function mulberry(a: number) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
