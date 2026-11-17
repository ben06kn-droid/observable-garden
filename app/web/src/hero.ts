// The run page's hero layer: the opening text (down to 01 Data) and the glass, drawn together in one WebGL
// canvas that scrolls with the page, so the cursor's wake can bend them as it bends the fan's paths.
//
// The text stays in the page as real text (selectable, read by screen readers, found by search), made
// transparent; this layer draws it from the same words at the same places, in the same fonts and colours
// (paint()). The glass draws its flow and outline into its own canvas, which this layer takes each frame.
//
// Through the glass: inside its outline, the text behind it is seen through a thick cylinder, gently
// magnified toward the middle and compressed toward the walls, with no change of height (the letters
// stay on their line), each colour channel bent a little differently toward the walls. The glass's flow
// fades where it crosses the letters, so they stay legible.
//
// The wake (src/wake.ts): where the cursor's fluid flows, everything here is seen displaced along it, the
// text and the glass turn silver-white and split into fine red fringes; as it fades they return to their
// own colours. Only pointer movement drives it (not touch).
import { GLSL_PROFILE, type Glass } from "./glass";
import { Wake } from "./wake";

const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr;            // the canvas, css px
uniform vec2 uOrigin, uScroll, uView;              // its page position; the page's scroll; the viewport
uniform vec3 uGround, uSilver, uRed;
uniform sampler2D uText; uniform float uTextH;     // the text, painted in the canvas's coordinates, to uTextH
uniform sampler2D uGlass; uniform vec4 uGlassBox;  // the glass's canvas and where it sits (css px, x y w h)
uniform float uH, uGy;
uniform sampler2D uVel; uniform float uWake;
out vec4 o;
${GLSL_PROFILE}
vec4 text(vec2 p) { return (p.y < 0.0 || p.y > uTextH) ? vec4(0.0) : texture(uText, p / vec2(uSize.x, uTextH)); }
// what is seen at p: (colour over the ground, how much of it is foreground)
vec4 seen(vec2 p) {
  vec2 c = uGlassBox.xy + uGlassBox.zw * 0.5, q = p - c;
  float v = q.y / uGy, r = abs(v) < 1.0 ? halfWidth(v, uH) : 0.0;
  bool inside = abs(v) < 1.0 && abs(q.x) < r;
  vec3 col; float t;
  if (inside) {
    // through the cylinder: x magnified toward the middle, compressed toward the walls; y untouched
    float a = clamp(q.x / r, -1.0, 1.0), e = a * a;
    float sx = (a * 0.9 + 0.1 * a * a * a) * r;
    float ta = 0.0;
    for (int k = 0; k < 3; k++) {
      float sk = q.x + (sx - q.x) * (1.0 + (float(k) - 1.0) * 0.05 * e);
      vec4 tk = text(vec2(c.x + sk, p.y));
      col[k] = mix(uGround[k], tk.rgb[k], tk.a); ta = max(ta, tk.a);
    }
    t = ta;
  } else {
    vec4 tk = text(p); col = mix(uGround, tk.rgb, tk.a); t = tk.a;
  }
  vec4 g = vec4(0.0);
  vec2 gu = (p - uGlassBox.xy) / uGlassBox.zw;
  if (gu.x >= 0.0 && gu.x <= 1.0 && gu.y >= 0.0 && gu.y <= 1.0) g = texture(uGlass, gu);
  g.a *= 1.0 - 0.8 * t;                              // the flow fades across the letters
  col = mix(col, g.rgb, g.a);
  return vec4(col, max(max(t, g.a), inside ? 1.0 : 0.0));
}
float ink(vec2 p) {                                  // how much foreground (text, flow, outline) there is at p
  vec2 c = uGlassBox.xy + uGlassBox.zw * 0.5, q = p - c;
  vec4 g = vec4(0.0); vec2 gu = (p - uGlassBox.xy) / uGlassBox.zw;
  if (gu.x >= 0.0 && gu.x <= 1.0 && gu.y >= 0.0 && gu.y <= 1.0) g = texture(uGlass, gu);
  return max(text(p).a, g.a);
}
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  vec2 d = vec2(0.0);
  if (uWake > 0.0) {
    vec2 vp = uOrigin + p - uScroll;                 // this point in the viewport
    vec2 v = texture(uVel, vec2(vp.x, uView.y - vp.y) / uView).xy;
    d = vec2(v.x, -v.y) * 0.016;
    float l = length(d); if (l > 26.0) d *= 26.0 / l;
  }
  float s = uWake * smoothstep(0.6, 7.0, length(d));
  vec4 a = seen(p - d);
  vec3 col = a.rgb; float alpha = a.a;
  if (s > 0.0) {
    float line = ink(p - d);
    col = mix(col, mix(uGround, uSilver, clamp(line, 0.0, 1.0)), s * line);
    vec2 n = normalize(d) * mix(0.7, 1.3, s);
    float fr = clamp(max(ink(p - d - n), ink(p - d + n)) - line, 0.0, 1.0) * s;
    col = mix(col, uRed, fr * 0.6);
    alpha = max(alpha, fr);
  }
  o = vec4(col * alpha, alpha);                      // premultiplied
}`;

function rgb(s: string): [number, number, number] {
  let h = s.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1];
  if (h) { if (h.length === 3) h = h.replace(/./g, "$&$&"); const n = parseInt(h, 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
  const r = s.match(/(\d+(\.\d+)?)/g); return r ? [Number(r[0]) / 255, Number(r[1]) / 255, Number(r[2]) / 255] : [0, 0, 0];
}

export interface HeroOptions {
  /** the element the layer is drawn in (positioned); the canvas covers it from its top */
  host: HTMLElement;
  /** the text it draws */
  text: () => HTMLElement[];
  /** the element whose class "painted" makes that text transparent in the page */
  veil: HTMLElement;
  /** where the text ends (page px): nothing is painted below it */
  textBottom: () => number;
  glass: Glass;
}

export class Hero {
  readonly canvas: HTMLCanvasElement;
  private o: HeroOptions; private gl: WebGL2RenderingContext | null = null; private prog: WebGLProgram | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {};
  private texT: WebGLTexture | null = null; private texG: WebGLTexture | null = null; private paintCv = document.createElement("canvas");
  private wake: Wake | null = null; private dpr = 1; private w = 0; private h = 0; private textH = 0; private origin = [0, 0]; private glassBox = [0, 0, 1, 1];
  private ground: [number, number, number] = [0, 0, 0]; private silver: [number, number, number] = [1, 1, 1]; private red: [number, number, number] = [1, 0, 0];
  private raf = 0; private last = 0; private glassDirty = true; private visible = true; private io: IntersectionObserver;
  private onMove = (e: PointerEvent) => { if (e.pointerType !== "touch" && this.wake) { this.wake.move(e.clientX, e.clientY); this.kick(); } };
  private onLeave = () => this.wake?.lift();

  constructor(o: HeroOptions) {
    this.o = o;
    this.canvas = document.createElement("canvas"); this.canvas.className = "hero-layer"; this.canvas.setAttribute("aria-hidden", "true");
    o.host.prepend(this.canvas);
    this.initGL();
    addEventListener("pointermove", this.onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", this.onLeave, { passive: true });
    this.io = new IntersectionObserver((es) => { this.visible = es.some((e) => e.isIntersecting); if (this.visible) this.kick(); });
    this.io.observe(this.canvas);
  }
  get ok() { return !!this.prog; }
  destroy() {
    cancelAnimationFrame(this.raf); this.raf = 0; this.io.disconnect();
    removeEventListener("pointermove", this.onMove); document.documentElement.removeEventListener("pointerleave", this.onLeave);
    this.canvas.remove();
  }
  /** the glass drew a frame */
  glassFrame() { this.glassDirty = true; this.kick(); }

  private initGL() {
    const gl = this.canvas.getContext("webgl2", { antialias: false, premultipliedAlpha: true, alpha: true, preserveDrawingBuffer: true });
    if (!gl) return;
    const sh = (t: number, src: string) => { const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG); if (!vs || !fs) return;
    const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const n of ["uSize", "uDpr", "uOrigin", "uScroll", "uView", "uGround", "uSilver", "uRed", "uText", "uTextH", "uGlass", "uGlassBox", "uH", "uGy", "uVel", "uWake"]) this.u[n] = gl.getUniformLocation(p, n);
    const tex = () => { const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE); return t; };
    this.texT = tex(); this.texG = tex();
    this.gl = gl; this.prog = p;
    const w = new Wake(gl); this.wake = w;
  }

  /** sizes and places the layer, and paints the text: call after a layout change, a font load, a palette
   *  swap or a disclosure opening */
  layout() {
    const gl = this.gl; if (!gl) return;
    this.dpr = Math.min(2, devicePixelRatio || 1);
    const host = this.o.host.getBoundingClientRect(), g = this.o.glass.el.getBoundingClientRect();
    this.origin = [host.left + scrollX, host.top + scrollY];
    this.w = Math.ceil(host.width);
    this.textH = Math.max(1, Math.ceil(this.o.textBottom() - this.origin[1]));
    this.h = Math.max(this.textH, Math.ceil(g.bottom + scrollY - this.origin[1]) + 2);
    this.canvas.style.setProperty("--hero-h", `${this.h}px`);
    this.canvas.width = Math.round(this.w * this.dpr); this.canvas.height = Math.round(this.h * this.dpr);
    this.glassBox = [g.left - host.left, g.top - host.top, g.width, g.height];
    const cs = getComputedStyle(this.canvas);
    this.ground = rgb(cs.getPropertyValue("--ground") || "#121416");
    this.silver = rgb(cs.getPropertyValue("--wake-silver") || "#dde3f0"); this.red = rgb(cs.getPropertyValue("--wake-red") || "#ef4b55");
    this.wake?.resize(innerWidth, innerHeight);
    this.paint(host);
    this.glassDirty = true; this.draw(true);
  }

  // the text, word by word where the page sets it, into a canvas in the layer's coordinates
  private paint(host: DOMRect) {
    const gl = this.gl!, c = this.paintCv, k = this.dpr;
    c.width = Math.round(this.w * k); c.height = Math.round(this.textH * k);
    const x = c.getContext("2d")!;
    x.setTransform(k, 0, 0, k, 0, 0); x.clearRect(0, 0, this.w, this.textH);
    const range = document.createRange();
    // the text's own colours, read with the veil lifted for a moment (no frame is drawn in between)
    this.o.veil.classList.remove("painted");
    const colors = this.o.text().map((el) => getComputedStyle(el).color);
    this.o.veil.classList.add("painted");
    this.o.text().forEach((el, i) => {
      const cs = getComputedStyle(el);
      x.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      (x as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = cs.letterSpacing === "normal" ? "0px" : cs.letterSpacing;
      x.fillStyle = colors[i]; x.textBaseline = "alphabetic";
      const up = cs.textTransform === "uppercase", m = x.measureText("Hg"), asc = m.fontBoundingBoxAscent, desc = m.fontBoundingBoxDescent;
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const text = n.textContent ?? "";
        for (const w of text.matchAll(/\S+/g)) {
          range.setStart(n, w.index!); range.setEnd(n, w.index! + w[0].length);
          const r = range.getBoundingClientRect(); if (!r.width) continue;
          x.fillText(up ? w[0].toUpperCase() : w[0], r.left - host.left, r.top - host.top + (r.height - asc - desc) / 2 + asc);
        }
      }
      // an underlined link (an inset rule at its foot), and a disclosure's mark
      if (el.dataset.paint === "underline") { const r = el.getBoundingClientRect(); x.fillRect(r.left - host.left, r.bottom - host.top - 1, r.width, 1); }
      if (el.dataset.paint === "summary") {
        const r = el.getBoundingClientRect(), open = !!el.closest("details")?.open, cx = r.left - host.left + 4.5, cy = r.top - host.top + r.height / 2;
        x.save(); x.translate(cx, cy); if (open) x.rotate(Math.PI / 4); x.fillRect(-4.5, -0.5, 9, 1); x.fillRect(-0.5, -4.5, 1, 9); x.restore();
      }
    });
    gl.bindTexture(gl.TEXTURE_2D, this.texT);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
  }

  // ---------- drawing: only when something changed (the glass's frame, the wake, a layout), and only the
  // part of the layer in view
  private kick() { if (this.raf || !this.gl) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }
  private frame = (now: number) => {
    this.raf = 0;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
    const w = this.wake;
    w?.step(dt, innerHeight);
    const waking = !!w?.ready && w.idle < 0.8;
    this.draw(false);
    if (waking) this.kick();
  };
  private draw(all: boolean) {
    const gl = this.gl; if (!gl || !this.prog) return;
    const top = Math.max(0, scrollY - this.origin[1]), bot = Math.min(this.h, scrollY + innerHeight - this.origin[1]);
    if (!all && (bot <= top || !this.visible)) return;
    gl.useProgram(this.prog); gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.enable(gl.SCISSOR_TEST);
    const k = this.dpr, y0 = all ? 0 : top, y1 = all ? this.h : bot;
    gl.scissor(0, Math.floor((this.h - y1) * k), this.canvas.width, Math.ceil((y1 - y0) * k) + 1);
    if (this.glassDirty) {
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.texG);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.o.glass.canvas);
      this.glassDirty = false;
    }
    const m = this.o.glass.measures(), w = this.wake, on = !!w?.ready && w.idle < 0.8;
    gl.uniform2f(this.u.uSize, this.w, this.h); gl.uniform1f(this.u.uDpr, k);
    gl.uniform2f(this.u.uOrigin, this.origin[0], this.origin[1]); gl.uniform2f(this.u.uScroll, scrollX, scrollY); gl.uniform2f(this.u.uView, innerWidth, innerHeight);
    gl.uniform3f(this.u.uGround, ...this.ground); gl.uniform3f(this.u.uSilver, ...this.silver); gl.uniform3f(this.u.uRed, ...this.red);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.texT); gl.uniform1i(this.u.uText, 0); gl.uniform1f(this.u.uTextH, this.textH);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.texG); gl.uniform1i(this.u.uGlass, 1);
    gl.uniform4f(this.u.uGlassBox, this.glassBox[0], this.glassBox[1], this.glassBox[2], this.glassBox[3]);
    gl.uniform1f(this.u.uH, m.H); gl.uniform1f(this.u.uGy, m.gy);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, on ? w!.texture : null); gl.uniform1i(this.u.uVel, 2); gl.uniform1f(this.u.uWake, on ? 1 : 0);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.disable(gl.SCISSOR_TEST);
  }
}
