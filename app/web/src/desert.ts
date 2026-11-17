// The Sancho page's desert: one canvas behind everything, fixed to the viewport (a band across the top on a
// phone). A vintage Western print: flat layers of colour, no outlines, a wide warm sky, red rock and sand.
// It sits behind the content and never styles it (DESIGN.md 3).
//
// - The scene: a sky graded from top to horizon, a low sun, four depth layers of mesas and buttes (flat tops,
//   stepped sides, a talus skirt; the near rock in two outcrops on the sand), a sand ground plane. The horizon
//   at 62% of the height, the largest butte left of centre, open sky upper right. Each layer is a height field
//   (one top per device column), kept in a small float texture; the scene is drawn from it in one pass, and
//   only again when the light changes.
// - The light follows the reader: scroll progress moves the sun from 28 degrees above the horizon down to
//   touching it; cast shadows lengthen from 0.3 to 2.5 times the height of what casts them and swing with the
//   sun (each shadow is found by inverting its projection onto the sand); the shaded faces widen; the sky
//   shifts to its evening colours; every layer darkens by up to 18%. Nothing changes unless the page scrolls.
// - The windmill: a lattice tower, an 18-bladed wheel and a tail vane on the horizon, right of centre, about
//   9% of the height, in the near rock's colour, drawn as distances so it stays crisp. One turn in 14 s; one in
//   3 s while wind passes within 200px of its hub, easing back over about 4 s.
// - Heat shimmer, every frame: in a band from the horizon up 22% of the height everything behind it is
//   displaced sideways by a smooth noise, 2.5px at the ground line falling to nothing at the band's top,
//   rising at 18px/s and drifting slowly sideways (vertical wavelength about 55px). A mirage strip 12px tall
//   just above the horizon reflects the sky at 12% in separate wavering pools.
// - The cursor is hot wind (src/cursorwake.ts: `followPointer` and the `Wake`'s pushes, so its delay and its
//   rise with speed are the site's): within about 160px of each stretch of its path the displacement rises to
//   6px, and that disturbance rises as a plume for 1.6 s before it fades; there the picture turns a little
//   toward --wake-tone with a half-pixel split in --wake-fringe at its edges. In the lower 30% it lifts a low
//   drift of dust that travels a short way downwind and settles in about 2 s. A fast scroll sends one gust.
// - A static print grain at 3% over all of it.
//
// Phone: a band across the top with the shimmer at half strength; no cursor wind. Reduced motion: a still
// afternoon (the sun high, no shimmer, the windmill still), drawn once. Paused while hidden or off screen.
import { followPointer, rgb, Wake, wakeColours, wakeWanted, type RGB } from "./cursorwake";

// ---------- the composition (x in fractions of the width, heights in fractions of the height)
interface Tier { l: number; r: number; h: number; s: number; c: number }   // insets (of the feature's width), height, slant width (of the feature's width), the slant's curve (1 straight, >1 a concave skirt)
interface Feature { x0: number; x1: number; tiers: Tier[] }
interface Row { base: number; key: string; k: number; shade: number; features: Feature[] }
const T = (l: number, r: number, h: number, s: number, c = 1): Tier => ({ l, r, h, s, c });
// a talus: the skirt of scree at a foot, concave, reaching in from both edges
const S = (h: number, s: number, l = 0, r = 0): Tier => ({ l, r, h, s, c: 1.6 });
export const HORIZON = 0.62;
const ROWS: Row[] = [
  // the most distant: low tables, the far rock's colour half lost in the horizon's haze
  { base: HORIZON, key: "haze", k: 0.06, shade: 0.28, features: [
    { x0: -0.03, x1: 0.21, tiers: [S(0.03, 0.3), T(0.2, 0.32, 0.068, 0.025)] },
    { x0: 0.33, x1: 0.55, tiers: [S(0.026, 0.32), T(0.3, 0.24, 0.05, 0.03)] },
    { x0: 0.82, x1: 1.04, tiers: [S(0.03, 0.25), T(0.18, 0.08, 0.06, 0.03)] },
  ] },
  { base: HORIZON, key: "--far", k: 0.1, shade: 0.45, features: [
    { x0: 0.06, x1: 0.31, tiers: [S(0.06, 0.3), T(0.2, 0.2, 0.118, 0.035), T(0.36, 0.38, 0.14, 0.02)] },
    { x0: 0.525, x1: 0.6, tiers: [S(0.02, 0.24), T(0.22, 0.22, 0.055, 0.04)] },
    { x0: 0.66, x1: 0.698, tiers: [S(0.014, 0.26), T(0.24, 0.26, 0.036, 0.05)] },
    { x0: 0.855, x1: 1.04, tiers: [S(0.04, 0.24), T(0.16, 0, 0.085, 0.03)] },
  ] },
  { base: HORIZON + 0.006, key: "--mid", k: 0.2, shade: 0.55, features: [
    // the largest butte: a wide skirt, a bench on its right, a sheer caprock
    { x0: 0.2, x1: 0.46, tiers: [S(0.1, 0.3), T(0.16, 0.12, 0.135, 0.03), T(0.27, 0.27, 0.27, 0.012)] },
    { x0: 0.47, x1: 0.522, tiers: [S(0.04, 0.3), T(0.3, 0.3, 0.165, 0.03)] },   // a spire
    { x0: -0.06, x1: 0.15, tiers: [S(0.07, 0.3), T(0.05, 0.24, 0.155, 0.03)] },
    { x0: 0.785, x1: 0.955, tiers: [S(0.04, 0.3), T(0.22, 0.16, 0.072, 0.03)] },
  ] },
  { base: 0.84, key: "--near", k: 0.45, shade: 0.55, features: [
    { x0: -0.05, x1: 0.25, tiers: [S(0.075, 0.24), T(0, 0.3, 0.15, 0.05), T(0, 0.58, 0.19, 0.03)] },
  ] },
  { base: 0.9, key: "--near", k: 0.45, shade: 0.55, features: [
    { x0: 0.85, x1: 1.05, tiers: [S(0.045, 0.35), T(0.26, 0, 0.085, 0.05)] },
  ] },
];
const NR = ROWS.length;
export const MILL = { x: 0.615, h: 0.09 };   // the windmill: its foot (x of the width, on the horizon) and height (of the height)
const HUB = 0.86;                             // the hub's height, of the windmill's
const SUN = { r: 0.042, x0: 0.8, x1: 0.735, e0: 28 };   // radius (of the height); x from afternoon to sunset; elevation, degrees
const TURN_REST = 14, TURN_WIND = 3, EASE_BACK = 4;     // s per turn; s to ease back
const BAND = 0.22, SHIMMER = 2.5, HOT = 6, REACH = 160, PLUME = 1.6, DUST = 2, NEAR_MILL = 200;
const MAXP = 24, MAXD = 16;

const VERT = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
// the windmill as a distance (css px) in its own frame: origin at its foot, y up
const MILL_GLSL = `
float seg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }
float sdBox(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
float halfW(float y, float H) { return mix(0.12, 0.034, clamp(y / (0.78 * H), 0.0, 1.0)) * H; }
float mill(vec2 q, float ang, float H, float lw) {
  if (q.y < -2.0 || q.y > 1.12 * H || q.x < -0.3 * H || q.x > 0.5 * H) return 1e3;
  // the tower: two legs, five bays of girts and crossed braces, the pump rod
  vec2 qa = vec2(abs(q.x), q.y);
  float d = seg(qa, vec2(0.12 * H, 0.0), vec2(0.034 * H, 0.78 * H)) - lw;
  float ys[6] = float[6](0.0, 0.22, 0.4, 0.55, 0.675, 0.78);
  for (int i = 0; i < 5; i++) {
    float y0 = ys[i] * H, y1 = ys[i + 1] * H, w0 = halfW(y0, H), w1 = halfW(y1, H);
    d = min(d, seg(q, vec2(-w1, y1), vec2(w1, y1)) - 0.55 * lw);
    d = min(d, seg(q, vec2(-w0, y0), vec2(w1, y1)) - 0.42 * lw);
    d = min(d, seg(q, vec2(w0, y0), vec2(-w1, y1)) - 0.42 * lw);
  }
  d = min(d, seg(q, vec2(0.0, 0.0), vec2(0.0, 0.8 * H)) - 0.4 * lw);
  d = min(d, sdBox(q - vec2(0.0, 0.795 * H), vec2(0.055 * H, 0.012 * H)));
  // the tail: a boom out to the right and back, and its vane
  vec2 c = vec2(-0.01 * H, ${HUB.toFixed(2)} * H);
  d = min(d, seg(q, c, vec2(0.33 * H, 0.9 * H)) - 0.5 * lw);
  vec2 v = q - vec2(0.33 * H, 0.9 * H); v.y -= v.x * 0.22;
  d = min(d, sdBox(v, vec2(0.075 * H, 0.06 * H)));
  // the wheel, seen a little from the side: a rim, an inner ring, a hub and eighteen blades
  vec2 e = (q - c) * vec2(1.0 / 0.84, 1.0);
  float r = length(e), R = 0.2 * H;
  d = min(d, abs(r - R) - 0.45 * lw);
  d = min(d, abs(r - 0.46 * R) - 0.4 * lw);
  d = min(d, r - 0.08 * R);
  float a = atan(e.y, e.x) + ang, slot = 6.2831853 / 18.0;
  float f = fract(a / slot) - 0.5;
  float bd = (abs(f) - 0.24) * slot * r;
  d = min(d, max(bd, max(0.3 * R - r, r - R)));
  return d;
}`;

// pass 1: the scene, drawn only when the light changes
const SCENE = `#version 300 es
precision highp float;
uniform vec2 uSize; uniform float uDpr, uHor, uDark, uLen, uSinT, uCosT;
uniform sampler2D uRows;                  // per device column, per row: (top, shade top) in css px
uniform vec3 uRowC[${NR}]; uniform vec3 uRowP[${NR}];   // colour; (base, foreshortening, shade alpha)
uniform vec3 uSkyTop, uSkyHor, uSandFar, uSandNear, uShadow, uSun, uSunP;
uniform vec3 uMill;                       // foot x, foot y, height (css px)
uniform float uMillK;
out vec4 o;
${MILL_GLSL}
vec2 rowAt(int r, float x) {
  int cols = textureSize(uRows, 0).x;
  return texelFetch(uRows, ivec2(clamp(int(floor(x * uDpr)), 0, cols - 1), r), 0).xy;
}
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  float px = 1.0 / uDpr;
  // the sky, graded to the horizon, and the sun behind everything
  vec3 col = mix(uSkyTop, uSkyHor, pow(clamp(p.y / uHor, 0.0, 1.0), 1.5));
  col = mix(col, uSun, clamp(0.5 - (length(p - uSunP.xy) - uSunP.z) * uDpr, 0.0, 1.0));
  // the sand, with the shadows cast on it
  if (p.y > uHor - 1.0) {
    float g = clamp((p.y - uHor) / max(1.0, uSize.y - uHor), 0.0, 1.0);
    // printed in four flat steps, each edge a long gentle swell
    float gw = g + 0.012 * sin(p.x / uSize.x * 9.0 + g * 20.0) + 0.008 * sin(p.x / uSize.x * 23.0 + 1.3);
    float step4 = floor(clamp(pow(gw, 0.8), 0.0, 0.999) * 4.0) / 3.0;
    vec3 sand = mix(uSandFar, uSandNear, step4) * uDark;
    float sh = 0.0;
    for (int r = 0; r < ${NR}; r++) {
      float base = uRowP[r].x, k = uRowP[r].y * uCosT * uLen;
      if (p.y <= base || k <= 0.0) continue;
      float hh = (p.y - base) / k;                 // the height whose shadow falls here
      float hx = base - rowAt(r, p.x + hh * uLen * uSinT).x;   // the height that stands there
      sh = max(sh, clamp((hx - hh) * k * uDpr + 0.5, 0.0, 1.0));
    }
    // the windmill's shadow: its own shape, laid down along the same light
    { float k = uMillK * uCosT * uLen;
      if (p.y > uMill.y && k > 0.0) {
        float hh = (p.y - uMill.y) / k;
        float d = mill(vec2(p.x + hh * uLen * uSinT - uMill.x, hh), 0.0, uMill.z, 1.1);
        sh = max(sh, 0.8 * clamp(0.5 - d * k * uDpr * 2.0, 0.0, 1.0));
      } }
    sand = mix(sand, uShadow * uDark, 0.55 * sh);
    col = mix(col, sand, clamp((p.y - uHor) * uDpr + 0.5, 0.0, 1.0));
  }
  // the rows, far to near: each filled from its top (antialiased across its slope) down to its foot
  for (int r = 0; r < ${NR}; r++) {
    vec2 t = rowAt(r, p.x);
    if (t.x >= uRowP[r].x - 0.01 || p.y < t.x - 2.0 || p.y > uRowP[r].x + 1.0) continue;   // no rock in this column: nothing, not a hairline at the foot
    float tl = rowAt(r, p.x - px).x, tr = rowAt(r, p.x + px).x;
    float slope = (tr - tl) / (2.0 * px);
    float cov = clamp((p.y - t.x) / sqrt(1.0 + slope * slope) * uDpr + 0.5, 0.0, 1.0);
    cov *= clamp((uRowP[r].x - p.y) * uDpr + 0.5, 0.0, 1.0);
    vec3 c = uRowC[r];
    c = mix(c, uShadow * uDark, uRowP[r].z * clamp((p.y - t.y) * uDpr + 0.5, 0.0, 1.0));
    col = mix(col, c, cov);
  }
  o = vec4(col, 1.0);
}`;

// pass 2, every frame: the shimmer, the mirage, the windmill, the wind and its dust, the grain
const COMP = `#version 300 es
precision highp float;
uniform sampler2D uScene; uniform vec2 uSize; uniform float uDpr, uTime, uHor, uAmp, uMove;
uniform vec4 uP[${MAXP}]; uniform int uNP;                  // the heat: (x, y, reach, strength)
uniform vec4 uD[${MAXD}]; uniform vec4 uDd[${MAXD}]; uniform int uND;   // dust: (x, y, half length, alpha), (cos, sin, half height, 0)
uniform vec4 uGust;                                         // (front x, strength, half width, 0)
uniform vec3 uMill; uniform float uAng; uniform vec3 uMillC;
uniform vec3 uTone, uFringe, uMirage;
out vec4 o;
${MILL_GLSL}
float h3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vnoise(vec3 x) {
  vec3 i = floor(x), f = fract(x); f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
float grain(vec2 f) { return fract(sin(dot(floor(f), vec2(12.9898, 78.233))) * 43758.5453); }
vec3 sceneAt(vec2 q) {
  vec3 c = texture(uScene, vec2(q.x, uSize.y - q.y) * uDpr / vec2(textureSize(uScene, 0))).rgb;
  float d = mill(vec2(q.x - uMill.x, uMill.y - q.y), uAng, uMill.z, max(0.55, uMill.z / 90.0));
  return mix(c, uMillC, clamp(0.5 - d * uDpr, 0.0, 1.0));
}
void main() {
  vec2 p = vec2(gl_FragCoord.x, uSize.y * uDpr - gl_FragCoord.y) / uDpr;
  float t = uTime, H = uSize.y, band = ${BAND} * H;
  // the resting shimmer's strength: 2.5px at the ground line, nothing at the band's top, gone just below the line
  float u = (uHor - p.y) / band;
  float amp = u >= 0.0 ? ${SHIMMER.toFixed(1)} * pow(clamp(1.0 - u, 0.0, 1.0), 1.6) : ${SHIMMER.toFixed(1)} * (1.0 - smoothstep(0.0, 0.045 * H, -u * band));
  amp *= uAmp;
  // the hot wind: plumes rising from the cursor's path
  float cool = 1.0;
  for (int i = 0; i < ${MAXP}; i++) {
    if (i >= uNP) break;
    vec2 d = p - uP[i].xy; d.y *= d.y < 0.0 ? 0.7 : 1.0;   // drawn out upward, a plume
    cool *= 1.0 - uP[i].w * exp(-3.0 * dot(d, d) / (uP[i].z * uP[i].z));
  }
  float heat = 1.0 - cool;
  // a gust: a front of stronger shimmer crossing the band
  float gx = (p.x - uGust.x) / max(1.0, uGust.z);
  float gust = uGust.y * exp(-gx * gx) * smoothstep(-1.4, 0.0, -u) * (1.0 - smoothstep(0.8, 1.6, u));
  amp = amp + (${HOT.toFixed(1)} - amp) * heat + 3.0 * gust;
  float dx = 0.0;
  if (amp > 0.01 && uMove > 0.0) {
    vec3 q = vec3((p.x + 5.0 * t + 40.0 * gust * t) / 150.0, (p.y + 18.0 * t) / 55.0, t * 0.35);
    float n = 0.64 * vnoise(q) + 0.36 * vnoise(q * vec3(2.03, 1.9, 1.7) + 7.3);
    dx = amp * clamp((n - 0.5) * 2.6, -1.0, 1.0);
  }
  vec2 s = p + vec2(dx, 0.0);
  vec3 col = sceneAt(s);
  // heat bends, it does not make rainbows: a half-pixel split, toned, only where the wind is
  if (heat > 0.01) {
    vec3 a = sceneAt(s + vec2(0.5, 0.0)), b = sceneAt(s - vec2(0.5, 0.0));
    float e = clamp(length(a - b) * 2.5, 0.0, 1.0);
    col = mix(col, uFringe, e * heat * 0.55);
    col = mix(col, uTone, 0.1 * heat);
  }
  // the mirage: a thin strip of the sky's colour just above the horizon, broken into pools, wavering
  { float top = uHor - 13.0 + 2.5 * (vnoise(vec3(s.x / 26.0, 1.7, t * 0.6 * uMove)) - 0.5) * 2.0, bot = uHor - 0.5;
    if (p.y > top - 3.0 && p.y < bot + 1.0) {
      float m = smoothstep(top - 1.5, top + 2.5, p.y) * (1.0 - smoothstep(bot - 2.0, bot + 0.5, p.y));
      float pool = smoothstep(0.46, 0.66, vnoise(vec3(s.x / 140.0 + 0.03 * t * uMove, 3.1, t * 0.18 * uMove)));
      col = mix(col, uMirage, 0.12 * m * pool);
    } }
  // dust: low soft smears of the tone, carried downwind, settling
  for (int i = 0; i < ${MAXD}; i++) {
    if (i >= uND) break;
    vec2 d = p - uD[i].xy; vec2 l = vec2(dot(d, uDd[i].xy), dot(d, vec2(-uDd[i].y, uDd[i].x)));
    float e = dot(l / vec2(uD[i].z, uDd[i].z), l / vec2(uD[i].z, uDd[i].z));
    float m = exp(-2.4 * e) * (0.65 + 0.35 * vnoise(vec3(p / 14.0, float(i))));
    col = mix(col, uTone, clamp(uD[i].w * m, 0.0, 1.0));
  }
  col = mix(col, vec3(grain(p)), 0.03);   // the print's grain, still
  o = vec4(col, 1.0);
}`;

interface Puff { x: number; y: number; t: number; s: number; vx: number }
interface Mote { x: number; y: number; vx: number; vy: number; t: number; a: number }
export interface DesertOptions {
  reduce: boolean;
  /** a phone: the scene is a band at the top, the shimmer at half strength, no wind */
  small: () => boolean;
  /** where the wind may stir the scene (viewport px); outside it the cursor is over the content */
  open?: (x: number, y: number) => boolean;
}

export class Desert {
  readonly canvas = document.createElement("canvas");
  private o: DesertOptions; private gl: WebGL2RenderingContext | null = null;
  private scene: { p: WebGLProgram; u: Record<string, WebGLUniformLocation | null> } | null = null;
  private comp: { p: WebGLProgram; u: Record<string, WebGLUniformLocation | null> } | null = null;
  private rows: WebGLTexture | null = null; private tex: WebGLTexture | null = null; private fb: WebGLFramebuffer | null = null;
  private wake: Wake | null = null;
  private W = 1; private H = 1; private dpr = 1; private cols = 1;
  private prog = 0; private dirty = true; private raf = 0; private last = 0; private t = 0;
  private ang = 0.6; private omega = (2 * Math.PI) / TURN_REST; private windT = -99;
  private puffs: Puff[] = []; private dust: Mote[] = []; private lastPuff = 0; private lastMote = 0;
  private gust = -99; private lastGust = -99; private scrollV = 0; private lastY = 0; private lastYT = 0;
  private visible = true;
  private pal: Record<string, RGB> = {};

  constructor(host: HTMLElement, o: DesertOptions) {
    this.o = o;
    this.canvas.className = "desert"; this.canvas.setAttribute("aria-hidden", "true");
    const gl = this.canvas.getContext("webgl2", { antialias: false, alpha: false, preserveDrawingBuffer: false }); if (!gl) return;
    const sh = (t: number, src: string) => {
      const s = gl.createShader(t)!; gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { if (import.meta.env.DEV) console.error("desert:", gl.getShaderInfoLog(s)); return null; }
      return s;
    };
    const prog = (fsrc: string, names: string[]) => {
      const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, fsrc); if (!vs || !fs) return null;
      const p = gl.createProgram()!; gl.attachShader(p, vs); gl.attachShader(p, fs); gl.bindAttribLocation(p, 0, "p"); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return null;
      const u: Record<string, WebGLUniformLocation | null> = {}; for (const n of names) u[n] = gl.getUniformLocation(p, n);
      return { p, u };
    };
    this.scene = prog(SCENE, ["uSize", "uDpr", "uHor", "uDark", "uLen", "uSinT", "uCosT", "uRows", "uRowC", "uRowP", "uSkyTop", "uSkyHor", "uSandFar", "uSandNear", "uShadow", "uSun", "uSunP", "uMill", "uMillK"]);
    this.comp = prog(COMP, ["uScene", "uSize", "uDpr", "uTime", "uHor", "uAmp", "uMove", "uP", "uNP", "uD", "uDd", "uND", "uGust", "uMill", "uAng", "uMillC", "uTone", "uFringe", "uMirage"]);
    if (!this.scene || !this.comp) return;
    this.gl = gl;
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    this.rows = gl.createTexture(); this.tex = gl.createTexture(); this.fb = gl.createFramebuffer();
    host.prepend(this.canvas);
    // the hot wind: only with a fine pointer that hovers, motion allowed, not on a phone
    if (!o.reduce && wakeWanted() && !o.small()) {
      const w = new Wake(gl, { force: 0.6 });
      if (w.supported) {
        this.wake = w;
        w.onPush = (x, y, vx, vy, dose) => this.blow(x, y, vx, vy, dose);
        followPointer((x, y) => { w.move(x, y); this.kick(); }, () => w.lift(), () => !document.hidden && !this.o.small());
      }
    }
    this.lastY = scrollY; this.lastYT = performance.now();
    addEventListener("scroll", () => {
      const now = performance.now(), dt = Math.max(8, now - this.lastYT);
      this.scrollV = 0.6 * this.scrollV + 0.4 * ((scrollY - this.lastY) / dt) * 1000; this.lastY = scrollY; this.lastYT = now;
      if (this.o.reduce) return;
      this.light();
      if (Math.abs(this.scrollV) > 2600 && this.t - this.lastGust > 3 && !this.o.small()) { this.gust = this.t; this.lastGust = this.t; }
      this.kick();
    }, { passive: true });
    document.addEventListener("visibilitychange", () => this.kick());
    new IntersectionObserver(([e]) => { this.visible = e.isIntersecting; this.kick(); }).observe(this.canvas);
    this.layout();
  }

  /** sizes and colours: after a layout change */
  layout() {
    const gl = this.gl; if (!gl) return;
    const cs = getComputedStyle(this.canvas);
    for (const k of ["--sky-top", "--sky-hor", "--sky-top-late", "--sky-hor-late", "--far", "--mid", "--near", "--sand-far", "--sand-near", "--shadow", "--sun"]) this.pal[k] = rgb(cs.getPropertyValue(k) || "#888888");
    const w = wakeColours(this.canvas); this.pal.tone = w.tone; this.pal.fringe = w.fringe;
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.W = Math.max(1, this.canvas.clientWidth); this.H = Math.max(1, this.canvas.clientHeight);
    this.canvas.width = Math.round(this.W * this.dpr); this.canvas.height = Math.round(this.H * this.dpr);
    this.cols = this.canvas.width;
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, this.canvas.width, this.canvas.height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.fb); gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.tex, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.wake?.resize(innerWidth, innerHeight);
    this.light(true);
    if (this.o.reduce) this.draw(); else this.kick();
  }

  /** scroll progress through the page: the light */
  private light(force = false) {
    const max = document.documentElement.scrollHeight - innerHeight;
    const p = this.o.reduce ? 0 : Math.max(0, Math.min(1, max > 0 ? scrollY / max : 0));
    if (force || Math.abs(p - this.prog) > 1e-5) { this.prog = p; this.dirty = true; }
  }

  /** the wind took in a stretch of the cursor's path */
  private blow(x: number, y: number, vx: number, vy: number, dose: number) {
    const r = this.canvas.getBoundingClientRect();
    if (x < r.left || x > r.right || y < r.top || y > r.bottom) return;
    if (this.o.open && !this.o.open(x, y)) return;
    const lx = x - r.left, ly = y - r.top, now = this.t, s = Math.min(1, 0.45 + 0.85 * Math.sqrt(dose));
    const lp = this.puffs[this.puffs.length - 1];
    if (!lp || now - this.lastPuff > 0.05 || Math.hypot(lp.x - lx, lp.y - ly) > 36) {
      this.puffs.push({ x: lx, y: ly, t: now, s, vx: Math.max(-160, Math.min(160, vx * 0.08)) }); this.lastPuff = now;
      if (this.puffs.length > MAXP) this.puffs.shift();
    }
    if (ly > 0.7 * this.H && now - this.lastMote > 0.06) {
      const sp = Math.hypot(vx, vy) || 1, v = Math.max(28, Math.min(85, sp * 0.06));
      this.dust.push({ x: lx, y: ly + 4, vx: (vx / sp) * v, vy: (vy / sp) * v * 0.25, t: now, a: 0.35 * s }); this.lastMote = now;
      if (this.dust.length > MAXD) this.dust.shift();
    }
    if (Math.hypot(lx - MILL.x * this.W, ly - (HORIZON - MILL.h * HUB) * this.H) < NEAR_MILL) this.windT = now;
  }

  private kick() {
    if (this.raf || !this.gl || this.o.reduce || document.hidden || !this.visible) return;
    this.last = performance.now(); this.raf = requestAnimationFrame(this.frame);
  }
  private frame = (now: number) => {
    this.raf = 0;
    if (document.hidden || !this.visible) return;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now; this.t += dt;
    this.wake?.step(dt, innerHeight);
    // the windmill: quick while the wind is near its hub (or the gust crosses it), easing back over about 4 s
    const g = this.t - this.gust;
    if (g >= 0 && g < 1.4 && Math.abs(this.gustX(g) - MILL.x * this.W) < NEAR_MILL) this.windT = this.t;
    const fast = (2 * Math.PI) / TURN_WIND, rest = (2 * Math.PI) / TURN_REST;
    if (this.t - this.windT < 0.12) this.omega += (fast - this.omega) * (1 - Math.exp(-dt / 0.4));
    else this.omega += (rest - this.omega) * (1 - Math.exp(-dt / (EASE_BACK / 3.5)));
    this.ang += this.omega * dt;
    // the dust: carried downwind, slowing, settling
    for (const m of this.dust) { const k = Math.exp(-dt / 0.7); m.vx *= k; m.vy = m.vy * k + 6 * dt; m.x += m.vx * dt; m.y += m.vy * dt; }
    this.puffs = this.puffs.filter((p) => this.t - p.t < PLUME);
    this.dust = this.dust.filter((m) => this.t - m.t < DUST);
    this.draw();
    this.kick();          // the air always moves
  };
  private gustX(age: number) { return (-0.2 + (1.4 * age) / 1.4) * this.W; }

  private rowsData(): Float32Array {
    const W = this.W, H = this.H, n = this.cols, d = new Float32Array(n * NR * 4);
    const s = 0.25 + 0.3 * this.prog;                        // the shaded share of each face, widening as the sun drops
    for (let r = 0; r < NR; r++) {
      const row = ROWS[r], base = row.base * H;
      for (let i = 0; i < n; i++) {
        const x = (i + 0.5) / this.dpr;
        let top = 0, shade = Infinity;
        for (const f of row.features) {
          const x0 = f.x0 * W, x1 = f.x1 * W, fw = x1 - x0;
          if (x < x0 || x > x1) continue;
          // the shaded face of the cliffs; a skirt is shaded out to where its cliff's shade ends, so no lit slit between
          let shadeEnd = -Infinity;
          for (const t of f.tiers) if (t.c === 1) { const a = x0 + t.l * fw, b = x1 - t.r * fw; shadeEnd = Math.max(shadeEnd, a + s * (b - a)); }
          for (const t of f.tiers) {
            const a = x0 + t.l * fw, b = x1 - t.r * fw, ch = Math.max(1, t.s * fw), e = Math.min(x - a, b - x);
            const ht = t.h * Math.pow(Math.max(0, Math.min(1, e / ch)), t.c);   // each slant inside the tier's span
            if (ht <= 0) continue;
            top = Math.max(top, ht);
            // the face away from the sun: the left slant and a share of the tier from its left edge
            if (x >= a && x <= (t.c === 1 ? a + s * (b - a) : Math.max(a + s * (b - a), shadeEnd))) shade = Math.min(shade, base - ht * H);
          }
        }
        const o = (r * n + i) * 4;
        d[o] = base - top * H; d[o + 1] = shade === Infinity ? 1e5 : shade;
      }
    }
    return d;
  }

  private draw() {
    const gl = this.gl; if (!gl || !this.scene || !this.comp) return;
    const W = this.W, H = this.H, P = this.prog, hor = HORIZON * H, pal = this.pal;
    const mix = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
    const dark = 1 - 0.18 * P;
    const skyTop = mix(pal["--sky-top"], pal["--sky-top-late"], P), skyHor = mix(pal["--sky-hor"], pal["--sky-hor-late"], P);
    const millC: RGB = pal["--near"].map((c) => c * dark) as RGB;
    if (this.dirty) {
      this.dirty = false;
      const sc = this.scene;
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.rows);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, this.cols, NR, 0, gl.RGBA, gl.FLOAT, this.rowsData());
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.useProgram(sc.p); gl.bindFramebuffer(gl.FRAMEBUFFER, this.fb); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
      gl.uniform1i(sc.u.uRows, 1);
      gl.uniform2f(sc.u.uSize, W, H); gl.uniform1f(sc.u.uDpr, this.dpr); gl.uniform1f(sc.u.uHor, hor); gl.uniform1f(sc.u.uDark, dark);
      // the light: elevation 28 degrees to 0; shadows 0.3 to 2.5 heights, swinging from the left toward the viewer
      const az = ((62 - 34 * P) * Math.PI) / 180;
      gl.uniform1f(sc.u.uLen, 0.3 + 2.2 * P); gl.uniform1f(sc.u.uSinT, Math.sin(az)); gl.uniform1f(sc.u.uCosT, Math.cos(az));
      const rowC: number[] = [], rowP: number[] = [];
      for (const r of ROWS) {
        const c = r.key === "haze" ? mix(pal["--far"], skyHor, 0.45) : pal[r.key];
        rowC.push(...c.map((x) => x * (r.key === "haze" ? 1 - 0.1 * P : dark))); rowP.push(r.base * H, r.k, r.shade);
      }
      gl.uniform3fv(sc.u.uRowC, rowC); gl.uniform3fv(sc.u.uRowP, rowP);
      gl.uniform3f(sc.u.uSkyTop, ...skyTop); gl.uniform3f(sc.u.uSkyHor, ...skyHor);
      gl.uniform3f(sc.u.uSandFar, ...pal["--sand-far"]); gl.uniform3f(sc.u.uSandNear, ...pal["--sand-near"]);
      gl.uniform3f(sc.u.uShadow, ...pal["--shadow"]); gl.uniform3f(sc.u.uSun, ...pal["--sun"]);
      const R = SUN.r * H, e = SUN.e0 * (1 - P);
      gl.uniform3f(sc.u.uSunP, (SUN.x0 + (SUN.x1 - SUN.x0) * P) * W, hor - R - (e / SUN.e0) * (hor - R - 0.16 * H), R);
      gl.uniform3f(sc.u.uMill, MILL.x * W, hor, MILL.h * H); gl.uniform1f(sc.u.uMillK, 0.1);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    const c = this.comp, move = this.o.reduce ? 0 : 1;
    gl.useProgram(c.p); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.tex); gl.uniform1i(c.u.uScene, 0);
    gl.uniform2f(c.u.uSize, W, H); gl.uniform1f(c.u.uDpr, this.dpr); gl.uniform1f(c.u.uTime, this.t); gl.uniform1f(c.u.uHor, hor);
    gl.uniform1f(c.u.uAmp, this.o.small() ? 0.5 : 1); gl.uniform1f(c.u.uMove, move);
    // the plumes: rising about 80px over their 1.6 s, drifting a little downwind, widening, fading
    const Pu: number[] = [];
    for (const p of this.puffs) {
      const a = this.t - p.t, f = a / PLUME;
      Pu.push(p.x + p.vx * a * 0.3, p.y - 50 * a, REACH * (0.75 + 0.35 * f), p.s * Math.min(1, a / 0.1) * Math.pow(1 - f, 1.3));
    }
    if (Pu.length) gl.uniform4fv(c.u.uP, Pu);
    gl.uniform1i(c.u.uNP, Pu.length / 4);
    const D: number[] = [], Dd: number[] = [];
    for (const m of this.dust) {
      const a = (this.t - m.t) / DUST, sp = Math.hypot(m.vx, m.vy) || 1;
      let ca = m.vx / sp, sa = m.vy / sp;
      const lim = 0.26; if (Math.abs(sa) > lim) { sa = Math.sign(sa) * lim; ca = Math.sign(ca || 1) * Math.sqrt(1 - lim * lim); }
      D.push(m.x, m.y, 40 + 40 * a, m.a * Math.min(1, a * 8) * Math.pow(1 - a, 1.5)); Dd.push(ca, sa, 7 + 5 * a, 0);
    }
    if (D.length) { gl.uniform4fv(c.u.uD, D); gl.uniform4fv(c.u.uDd, Dd); }
    gl.uniform1i(c.u.uND, D.length / 4);
    const g = this.t - this.gust;
    gl.uniform4f(c.u.uGust, this.gustX(g), g >= 0 && g < 1.4 ? Math.sin((Math.PI * g) / 1.4) : 0, 0.16 * W, 0);
    gl.uniform3f(c.u.uMill, MILL.x * W, hor, MILL.h * H); gl.uniform1f(c.u.uAng, this.ang); gl.uniform3f(c.u.uMillC, ...millC);
    gl.uniform3f(c.u.uTone, ...pal.tone); gl.uniform3f(c.u.uFringe, ...pal.fringe);
    gl.uniform3f(c.u.uMirage, ...mix(skyTop, skyHor, 0.55));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
}
