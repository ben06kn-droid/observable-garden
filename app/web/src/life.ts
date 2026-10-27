// Life on the two pages before anything is clicked. All of it moves by transform (and the individual
// `translate` property, which composes with an element's own transform) or opacity, is throttled to
// the pointer's pace, and is off entirely under reduced motion.
//
// The trail: yellow leaves on page one, pink petals on page two spill from the cursor while it moves
// (or a finger drags) and fall at the ambient leaves' pace, joining the scene. One pool of sprites per
// page, reused oldest first, a dozen or so in the air at a time.
// The wind: ambient leaves and petals near the cursor are pushed away from it, a push that falls off
// with distance and decays back over a few seconds.
// The piles: leaves and petals that reach the ground settle there and stay for the visit, one pile per
// page, in memory only; each pile is capped so it never covers text. Every half minute to a minute a
// gust crosses: the falling leaves lean with it and a few pieces of each pile lift and resettle.
// A pile is drawn into one canvas strip along its ground (as elements, hundreds of transformed pieces
// would each add to what the compositor sorts every frame); a piece the gust lifts flies as a sprite
// and is drawn back in where it lands.
import { SHAPES } from "./leaves";

const NS = "http://www.w3.org/2000/svg";
const POOL = 14, RELEASE_PX = 16, PIECE_CAP = 260, BIN = 8;
const rnd = Math.random;

interface Piece { x: number; y: number; r: number; s: number; bin: number }
interface PageLife {
  box: HTMLElement;              // the page's section
  kind: "leaf" | "petal";
  falling: HTMLElement;          // the ambient leaves or petals
  pool: SVGSVGElement[]; next: number;
  pile: HTMLCanvasElement; top: number; bins: number[]; pieces: Piece[];   // top: the strip's top in the section
  ground: (x: number) => number; // the ground's y at x, in the section's pixels
  cap: (x: number) => number;    // how high the pile may rise at x
}

function sprite(kind: "leaf" | "petal", cls: string): SVGSVGElement {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "-10 -10 20 20");
  svg.setAttribute("class", `${cls} ${kind === "leaf" ? "l" : "p"}`);
  svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", SHAPES[kind]);
  svg.appendChild(p);
  return svg;
}

export interface LifeOptions {
  one: HTMLElement; two: HTMLElement;
  leaves: HTMLElement; petals: HTMLElement;
  textOne: () => DOMRect | null;   // page one's text, which the pile must not reach
  paused: () => boolean;           // a carry or the run view: no trail, no wind
}

export function startLife(o: LifeOptions) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  // section sizes, read once and after a resize, so the handlers below never force a layout
  const sizes = new Map<HTMLElement, [number, number]>();
  const size = (b: HTMLElement) => { let v = sizes.get(b); if (!v) { v = [b.clientWidth, b.clientHeight]; sizes.set(b, v); } return v; };
  window.addEventListener("resize", () => sizes.clear());

  function page(box: HTMLElement, kind: "leaf" | "petal", falling: HTMLElement, ground: PageLife["ground"], cap: PageLife["cap"]): PageLife {
    const trail = document.createElement("div"); trail.className = "trail"; trail.setAttribute("aria-hidden", "true");
    const pile = document.createElement("canvas"); pile.className = "pile"; pile.setAttribute("aria-hidden", "true");
    box.insertBefore(pile, falling.nextSibling); box.insertBefore(trail, pile.nextSibling);
    const pool: SVGSVGElement[] = [];
    for (let i = 0; i < POOL; i++) { const s = sprite(kind, "sprite"); trail.appendChild(s); pool.push(s); }
    return { box, kind, falling, pool, next: 0, pile, top: 0, bins: [], pieces: [], ground, cap };
  }
  // page one's text box, relative to its section, measured once and again after a resize (never in
  // the middle of a frame's work)
  let text: { l: number; r: number; below: number } | null = null;
  const textBox = () => {
    if (!text) { const t = o.textOne(), b = o.one.getBoundingClientRect(); text = t ? { l: t.left - b.left, r: t.right - b.left, below: size(o.one)[1] - (t.bottom - b.top) - 10 } : { l: 0, r: 0, below: 26 }; }
    return text;
  };
  window.addEventListener("resize", () => { text = null; });
  const one = page(o.one, "leaf", o.leaves, () => size(o.one)[1] - 4, (x) => {
    const t = textBox();
    return x > t.l - 20 && x < t.r + 20 ? Math.max(0, Math.min(26, t.below)) : 26;
  });
  const two = page(o.two, "petal", o.petals, (x) => {   // the bed's parabola of ground (bed.ts)
    const [w2, P] = size(o.two), u = (x - w2 / 2) / (w2 / 2);
    return P * (0.93 - 0.11 * u * u);
  }, () => (innerWidth < 760 ? 0 : 12));
  const pages = [one, two];
  const at = (y: number) => { for (const p of pages) { const r = p.box.getBoundingClientRect(); if (y >= r.top && y < r.bottom) return { p, r }; } return null; };

  // ---- the piles. Nothing settles while a carry or the run view plays: what lands then waits in a
  // queue, so no transition frame inserts or measures anything.
  const waiting: [PageLife, number][] = [];
  window.setInterval(() => { if (!o.paused()) waiting.splice(0, 12).forEach(([p, x]) => settle(p, x)); }, 500);
  function land(p: PageLife, x: number) { if (o.paused() || waiting.length) waiting.push([p, x]); else settle(p, x); }
  // the strip: from just above the highest the ground and its pile can reach, to the section's foot
  const shape = { leaf: new Path2D(SHAPES.leaf), petal: new Path2D(SHAPES.petal) };
  function fit(p: PageLife) {
    const [W, H] = size(p.box), dpr = Math.min(2, devicePixelRatio || 1);
    let hi = H; for (let x = 0; x <= W; x += W / 32) hi = Math.min(hi, p.ground(x));
    p.top = Math.max(0, Math.floor(hi - 26 - 30));
    p.pile.width = Math.ceil(W * dpr); p.pile.height = Math.ceil((H - p.top) * dpr);
    p.pile.style.transform = `translate3d(0, ${p.top}px, 0)`;
    p.pile.style.setProperty("--w", `${W}px`); p.pile.style.setProperty("--h", `${H - p.top}px`);
    draw(p);
  }
  function piece(ctx: CanvasRenderingContext2D, p: PageLife, pc: Piece) {
    ctx.save();
    ctx.translate(pc.x, pc.y - p.top); ctx.rotate((pc.r * Math.PI) / 180); ctx.scale(pc.s / 20, (pc.s / 20) * 0.62);
    if (p.kind === "leaf") { ctx.fillStyle = "#e2b33a"; ctx.strokeStyle = "#8a6a12"; ctx.lineWidth = 0.8; ctx.fill(shape.leaf); ctx.stroke(shape.leaf); }
    else { ctx.fillStyle = "#ffb3d1"; ctx.fill(shape.petal); }
    ctx.restore();
  }
  function draw(p: PageLife) {
    const ctx = p.pile.getContext("2d");
    if (!ctx) return;
    const dpr = p.pile.width / Math.max(1, size(p.box)[0]);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, p.pile.width, p.pile.height);
    for (const pc of p.pieces) piece(ctx, p, pc);
  }
  function settle(p: PageLife, x: number) {
    if (p.pieces.length >= PIECE_CAP) return;
    if (!p.pile.width) fit(p);
    const W = size(p.box)[0], bin = Math.max(0, Math.min(Math.floor(W / BIN), Math.floor(x / BIN)));
    const h = p.bins[bin] ?? 0;
    if (h >= p.cap(x)) return;
    const pc = { x, y: p.ground(x) - h - 3, r: rnd() * 360, s: p.kind === "leaf" ? 10 + rnd() * 7 : 8 + rnd() * 6, bin };
    p.bins[bin] = h + 2.2;
    p.pieces.push(pc);
    const ctx = p.pile.getContext("2d");
    if (ctx) { const dpr = p.pile.width / Math.max(1, W); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); piece(ctx, p, pc); }
  }
  window.addEventListener("resize", () => { for (const p of pages) if (p.pile.width) window.setTimeout(() => fit(p), 250); });
  // an ambient leaf or petal finishing a fall settles now and then where it lands
  for (const p of pages) p.falling.addEventListener("animationiteration", (e) => {
    if (rnd() > 0.3) return;
    const el = e.target as SVGSVGElement, xp = parseFloat(el.style.getPropertyValue("--x"));
    if (Number.isFinite(xp)) land(p, (xp / 100) * size(p.box)[0] + 6);
  });

  // ---- the trail
  function release(p: PageLife, x: number, y: number) {
    const s = p.pool[p.next]; p.next = (p.next + 1) % p.pool.length;
    s.getAnimations().forEach((a) => a.cancel());
    const H = size(p.box)[1], end = p.ground(x) - 4, fall = Math.max(10, end - y);
    const v = (H * 1.04) / (16 + rnd() * 18);                    // the ambient pace: a box height in 16-34 s
    const sway = (18 + rnd() * 56) * (rnd() < 0.5 ? 1 : -1), spin = (rnd() < 0.5 ? 1 : -1) * (160 + rnd() * 380);
    s.style.setProperty("--size", `${(p.kind === "leaf" ? 11 + rnd() * 9 : 9 + rnd() * 8).toFixed(0)}px`);
    const k = (t: number, dx: number) => ({ transform: `translate3d(${(x + dx).toFixed(1)}px, ${(y + fall * t).toFixed(1)}px, 0) rotate(${(spin * t).toFixed(0)}deg)`, opacity: 1 });
    const a = s.animate([{ ...k(0, 0), opacity: 0 }, { ...k(0.04, sway * 0.15), offset: 0.04 }, k(0.25, sway), k(0.5, 0), k(0.75, -sway), k(1, 0)],
      { duration: (fall / v) * 1000, easing: "linear", fill: "forwards" });
    a.onfinish = () => { land(p, x); a.cancel(); };
  }

  // ---- the wind
  const pushes = new WeakMap<Element, Animation>();
  function wind(p: PageLife, cx: number, cy: number, dx: number, dy: number) {
    const R = 120, speed = Math.min(1, Math.hypot(dx, dy) / 40);
    for (const el of p.falling.children) {
      const b = el.getBoundingClientRect(), ex = b.left + b.width / 2, ey = b.top + b.height / 2, d = Math.hypot(ex - cx, ey - cy);
      if (d > R) continue;
      const f = (1 - d / R) ** 2 * 42 * (0.4 + 0.6 * speed), ux = (ex - cx) / (d || 1), uy = (ey - cy) / (d || 1);
      const cur = getComputedStyle(el).translate, [x0, y0] = cur === "none" ? [0, 0] : cur.split(" ").map((v) => parseFloat(v) || 0);
      pushes.get(el)?.cancel();
      pushes.set(el, el.animate([{ translate: `${x0}px ${y0 ?? 0}px` }, { translate: `${(x0 + ux * f).toFixed(1)}px ${((y0 ?? 0) + uy * f).toFixed(1)}px`, offset: 0.18 }, { translate: "0px 0px" }],
        { duration: 3200, easing: "cubic-bezier(.2, .7, .2, 1)" }));
    }
  }

  // the pointer: coalesced to one step per frame; a sprite every RELEASE_PX of travel, the wind at most
  // every 80 ms
  let px = -1, py = -1, lx = -1, ly = -1, lastWind = 0, queued = false, mx = 0, my = 0;
  function step() {
    queued = false;
    if (o.paused()) return;
    const hit = at(py);
    if (!hit) return;
    const { p, r } = hit;
    if (lx < 0 || Math.hypot(px - lx, py - ly) >= RELEASE_PX) {
      if (lx >= 0) release(p, px - r.left, py - r.top);
      lx = px; ly = py;
    }
    const now = performance.now();
    if (now - lastWind > 80) { lastWind = now; wind(p, px, py, mx, my); mx = my = 0; }
  }
  const move = (x: number, y: number) => { mx += x - (px < 0 ? x : px); my += y - (py < 0 ? y : py); px = x; py = y; if (!queued) { queued = true; requestAnimationFrame(step); } };
  window.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse" || e.pointerType === "pen") move(e.clientX, e.clientY); }, { passive: true });
  window.addEventListener("touchmove", (e) => { const t = e.touches[0]; if (t) move(t.clientX, t.clientY); }, { passive: true });
  window.addEventListener("touchend", () => { lx = ly = -1; }, { passive: true });

  // ---- the gusts
  function gust() {
    if (!document.hidden && !o.paused()) {
      const dir = rnd() < 0.5 ? 1 : -1, ms = 2400 + rnd() * 1200;
      for (const p of pages) {
        p.falling.animate([{ transform: "translate3d(0, 0, 0)" }, { transform: `translate3d(${dir * (50 + rnd() * 40)}px, 0, 0)`, offset: 0.45 }, { transform: "translate3d(0, 0, 0)" }],
          { duration: ms, easing: "ease-in-out" });
        const W = size(p.box)[0], n = Math.min(p.pieces.length, 4 + Math.floor(rnd() * 5)), lifted: Piece[] = [];
        for (let i = 0; i < n; i++) {
          const pc = p.pieces[Math.floor(rnd() * p.pieces.length)];
          if (lifted.includes(pc)) continue;
          const nx = Math.max(6, Math.min(W - 6, pc.x + dir * (40 + rnd() * 120))), nbin = Math.max(0, Math.floor(nx / BIN));
          if ((p.bins[nbin] ?? 0) >= p.cap(nx)) continue;
          p.bins[pc.bin] = Math.max(0, (p.bins[pc.bin] ?? 0) - 2.2);
          const ny = p.ground(nx) - (p.bins[nbin] ?? 0) - 3, nr = pc.r + dir * (180 + rnd() * 240);
          p.bins[nbin] = (p.bins[nbin] ?? 0) + 2.2;
          // the piece leaves the canvas and flies as a sprite (centred on the piece), then is drawn back in
          const el = sprite(p.kind, "sprite flying"); el.style.setProperty("--size", `${pc.s.toFixed(0)}px`);
          p.pool[0].parentElement!.appendChild(el);
          const T = (x: number, y: number, r: number) => `translate3d(${(x - pc.s / 2).toFixed(0)}px, ${(y - pc.s / 2).toFixed(0)}px, 0) rotate(${r.toFixed(0)}deg) scaleY(0.62)`;
          const lift = 24 + rnd() * 50, mid = pc.x + (nx - pc.x) * 0.5, from = { x: pc.x, y: pc.y, r: pc.r };
          const a = el.animate([{ transform: T(from.x, from.y, from.r), opacity: 1 }, { transform: T(mid, Math.min(from.y, ny) - lift, (from.r + nr) / 2), opacity: 1, offset: 0.45 }, { transform: T(nx, ny, nr), opacity: 1 }],
            { duration: ms * (0.7 + rnd() * 0.3), delay: rnd() * ms * 0.3, easing: "cubic-bezier(.3, .1, .3, 1)", fill: "both" });
          Object.assign(pc, { x: nx, y: ny, r: nr, bin: nbin });
          lifted.push(pc);
          a.onfinish = () => { el.remove(); p.pieces.push(pc); const ctx = p.pile.getContext("2d"); if (ctx) { const dpr = p.pile.width / Math.max(1, W); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); piece(ctx, p, pc); } };
        }
        if (lifted.length) { p.pieces = p.pieces.filter((pc) => !lifted.includes(pc)); draw(p); }
      }
    }
    window.setTimeout(gust, 30000 + rnd() * 30000);
  }
  window.setTimeout(gust, 30000 + rnd() * 30000);
}
