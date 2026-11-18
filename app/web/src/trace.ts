// The cursor's tail on a plain ground: Sancho's tail (src/dusk.ts), one to one, on any section's flat backdrop. One
// canvas in the section's backdrop, fixed to the viewport, painting the ground (--ground) and, over it, the tail in the
// run page's form with the docs page's toned-down fluid: a glossy trace (a --wake-core highlight, a --wake-shade shade, a
// --wake-fringe hairline rim, Sancho's own colours) that distorts nothing and fades out before the text it is given.
// Draws only while the backdrop can be seen and the fluid is moving. Phone: no tail. Reduced motion: the ground only.
import { followPointer, rgb, Wake, WAKE_GLSL, wakeWanted, type RGB } from "./cursorwake";

// Sancho's tail: the docs page's, toned down (force 60%, swirl 60%, its own motion 75%, life +20%)
const TAIL = { force: 0.6, curl: 22 * 0.6, flow: 0.55 * 0.75, fade: 0.45 * 1.2 };
// Sancho's colours for it (sancho.css): the highlight, the shade, the rim
const CORE = "#f2d7a6", SHADE = "#14070a", RIM = "#b5391c";

const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr; uniform vec3 uGround, uCore, uShade, uFringe;
uniform sampler2D uVel; uniform float uWake; uniform vec4 uText, uText2;
out vec4 o;
${WAKE_GLSL}
vec2 flowAt(vec2 p) { return wakeFlow(uVel, p, uSize); }
float awayFrom(vec4 r, vec2 p) { vec2 tq = max(r.xy - p, p - (r.xy + r.zw)); return smoothstep(0.0, 24.0, max(tq.x, tq.y)); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  vec3 col = uGround;
  // the tail, as on Sancho: a glossy trace laid over the ground, never behind the text (it fades out over 24 px before it)
  float away = min(awayFrom(uText, p), awayFrom(uText2, p));
  if (uWake > 0.0 && away > 0.0) {
    vec2 d = flowAt(p) * away; float s = wakeStrength(d);
    if (s > 0.0) {
      vec2 gr = vec2(length(flowAt(p + vec2(6.0, 0.0))) - length(flowAt(p - vec2(6.0, 0.0))),
                     length(flowAt(p + vec2(0.0, 6.0))) - length(flowAt(p - vec2(0.0, 6.0))));
      col = wakeTrace(col, gr, s, 1.0, uCore, uShade, uFringe, 1.0).rgb;
    }
  }
  o = vec4(col, 1.0);
}`;

export interface Box { x: number; y: number; w: number; h: number }
export interface TraceOptions { reduce: boolean; small: () => boolean; /** the areas of text it keeps clear of (viewport px) */ text: () => Box[] }

export class Trace {
  readonly canvas: HTMLCanvasElement;
  private gl: WebGL2RenderingContext | null = null; private prog: WebGLProgram | null = null; private u: Record<string, WebGLUniformLocation | null> = {};
  private wake: Wake | null = null; private ground: RGB = [0, 0, 0]; private W = 1; private H = 1; private dpr = 1; private raf = 0; private active = false;

  constructor(host: HTMLElement, private o: TraceOptions) {
    this.canvas = document.createElement("canvas"); this.canvas.className = "trace"; this.canvas.setAttribute("aria-hidden", "true");
    host.append(this.canvas);
    const gl = this.canvas.getContext("webgl2", { antialias: false, alpha: false }); if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uGround", "uCore", "uShade", "uFringe", "uVel", "uWake", "uText", "uText2"]) this.u[n] = gl.getUniformLocation(p, n);
    this.gl = gl; this.prog = p;
    if (!o.reduce && wakeWanted() && !o.small()) {
      const w = new Wake(gl, TAIL);
      if (w.supported) { this.wake = w; followPointer((x, y) => { w.move(x, y); this.kick(); }, () => w.lift(), () => this.active && !document.hidden && !this.o.small()); }
    }
    addEventListener("resize", () => this.layout(), { passive: true });
    this.layout();
  }
  /** sizes and colours: after a layout change */
  layout() {
    if (!this.gl) return;
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.W = Math.max(1, this.canvas.clientWidth); this.H = Math.max(1, this.canvas.clientHeight);
    this.canvas.width = Math.round(this.W * this.dpr); this.canvas.height = Math.round(this.H * this.dpr);
    this.ground = rgb(getComputedStyle(this.canvas).getPropertyValue("--ground") || "#c4f042");
    this.wake?.resize(innerWidth, innerHeight);
    this.draw();
  }
  /** draw only while the backdrop can be seen (src/onepage/boot.ts onBackdrop) */
  setActive(on: boolean) { this.active = on; if (on) this.kick(); }
  private kick() { if (this.raf || !this.gl || !this.active) return; this.raf = requestAnimationFrame(this.frame); }
  private frame = () => {
    this.raf = 0;
    const w = this.wake;
    w?.step(0, innerHeight);
    this.draw();
    if (w && w.ready && (w.idle < w.still || w.pending) && this.active) this.kick();
  };
  private draw() {
    const gl = this.gl; if (!gl || !this.prog) return;
    const u = this.u, w = this.wake, on = !!w?.ready && w.idle < w.still;
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.uniform2f(u.uSize, this.W, this.H); gl.uniform1f(u.uDpr, this.dpr);
    gl.uniform3f(u.uGround, ...this.ground); gl.uniform3f(u.uCore, ...rgb(CORE)); gl.uniform3f(u.uShade, ...rgb(SHADE)); gl.uniform3f(u.uFringe, ...rgb(RIM));
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(u.uVel, 0); gl.uniform1f(u.uWake, on ? 1 : 0);
    const t = on ? this.o.text() : [], far = { x: -1e5, y: -1e5, w: 0, h: 0 }, a = t[0] ?? far, b = t[1] ?? far;
    gl.uniform4f(u.uText, a.x, a.y, a.w, a.h); gl.uniform4f(u.uText2, b.x, b.y, b.w, b.h);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
}
