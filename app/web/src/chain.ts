// The scroll chain: home → run → docs → Sancho, each its own HTML document and URL. Reading scroll
// is the browser's own; nothing is intercepted within a page. Only at a page's end (or its top)
// does a deliberate push carry the visitor to the next page (or back to the previous one), as one
// scripted transition on lukres.dev's curve, cubic-bezier(.35, 0, 0, 1), 1.0 s:
//
// - Where the browser has cross-document view transitions, the carry is a plain navigation that
//   opts in (chain.css's @view-transition); the old page's snapshot slides off as the new one slides
//   on (transform only, on the compositor) while the header stays put. public/carry.js, on the page
//   arriving, reads the direction this page wrote to sessionStorage before its first frame.
// - Elsewhere (the fallback): a cover in the next page's ground slides over this page, then the
//   browser navigates; the next page starts under its own ground and uncovers. No white flash.
// - Reduced motion: the same gesture, then an immediate navigation.
//
// Never mid-read, and little effort. A push counts only at the very end of a page (or its very top,
// going back), and only from a gesture that began there: the scroll that arrives at the end, momentum
// and all, never counts. A trackpad's momentum only ever falls, so a gesture ends at a pause over 100 ms,
// a reversal, or the wheel speeding up again after it had begun to fall (a new swipe). One short scroll
// past the end, 15% of the viewport's height in all, carries; the end's cue ("Continue to docs ↓") fills
// its hairline with the push and is also a plain link, the keyboard's way on. Keys: one press of Space,
// Page Down, Arrow Down or End at the end (the press that reached the end does not count). Touch: a pull of
// 15% that starts at the end, carried on release. Going up from the top is the same rule, and lands at
// the previous page's end. Nothing arms until the page has arrived (`settled`).
import { reduceMotion } from "./common";
import "./styles/chain.css";

export interface ChainPage { path: string; name: string; ground: string; top: string; foot: string }
/** The chain, in order. `ground` must equal each theme's --ground (the browser check holds them equal). `top` and
 *  `foot`: the colour just under the header on the page's first screen and at the bottom of its last (measured
 *  from screenshots at 1440x900), shown where a push opens a gap onto the page next to it. */
export const CHAIN: ChainPage[] = [
  { path: "/", name: "home", ground: "#efe6d2", top: "#ede6d4", foot: "#ede6d4" },
  { path: "/run.html", name: "run", ground: "#121416", top: "#121416", foot: "#121416" },
  { path: "/docs.html", name: "docs", ground: "#255ea4", top: "#406ba6", foot: "#d7efdf" },
  { path: "/sancho.html", name: "Sancho", ground: "#ece2cf", top: "#2c0e0d", foot: "#e2d8c8" },
];
const THRESHOLD = 0.15, EDGE = 2, GAP = 100, RELAX = 600;

const here = location.pathname === "/index.html" ? "/" : location.pathname;
const at = CHAIN.findIndex((p) => p.path === here);
const next = at >= 0 ? CHAIN[at + 1] : undefined, prev = at > 0 ? CHAIN[at - 1] : undefined;
const html = document.documentElement;
// cross-document view transitions: the pageswap event and the @view-transition rule
const crossDoc = "onpageswap" in window && typeof CSSRule !== "undefined" && "CSSViewTransitionRule" in window
  && new URLSearchParams(location.search).get("carry") !== "fallback";   // ?carry=fallback forces the fallback path, for testing

/** Resolves once this page has arrived: shown (not a prerender), the carry that brought it here over
 *  (public/carry.js: its view transition finished or its cover lifted), and two frames drawn. Each page
 *  starts its heavy work (WebGL scenes, Pyodide) after this, and no carry arms before it. */
export const settled: Promise<void> = new Promise((resolve) => {
  const go = () => {
    const done = (window as Window & { __carry?: { done?: Promise<void> } }).__carry?.done ?? Promise.resolve();
    void done.then(() => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  };
  if ((document as Document & { prerendering?: boolean }).prerendering) document.addEventListener("prerenderingchange", go, { once: true });
  else go();
});
/** A page's graphics, started after it has arrived, come in over its CSS stand-in: 450 ms, linear (a change
 *  of colour, as the site's colour changes are). Under reduced motion they are simply there. */
export function fadeIn(...els: (Element | null | undefined)[]): Promise<void> {
  const list = els.filter((e): e is Element => !!e);
  if (reduceMotion || !list.length) return Promise.resolve();
  return Promise.all(list.map((e) => e.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 450, easing: "linear" }).finished.catch(() => {}))).then(() => {});
}
/** idle time after `settled`, for work nobody is waiting on (the run page's Pyodide) */
export const idle = (timeout = 1500) => new Promise<void>((r) => {
  const w = window as Window & { requestIdleCallback?: (f: () => void, o?: { timeout: number }) => number };
  if (w.requestIdleCallback) w.requestIdleCallback(() => r(), { timeout }); else window.setTimeout(r, 300);
});
let ready = false;
void settled.then(() => { ready = true; });

let carrying = false, covered = false;   // covered: this carry used the fallback's cover
let lastWheelEpoch = 0, lastWheelAbs = 0;  // handed to the arriving page, which swallows the rest of this gesture

const note = (to: ChainPage, dir: "down" | "up", cover: boolean) => {
  try { sessionStorage.setItem("qx-carry", JSON.stringify({ to: to.path, dir, cover, t: Date.now(), w: lastWheelEpoch, a: lastWheelAbs, o: offset, vh: window.innerHeight, col: dir === "down" ? to.top : to.foot })); } catch { /* private mode: the carry still navigates */ }
};
let pending: { to: ChainPage; dir: "down" | "up"; cover: boolean; url?: string } | null = null;

// ---- the motion. While a push builds, the page (everything but the header) slides by the push, following the
// wheel through lukres.dev's eased scroll (each frame closes 1 - e^(-12 dt) of the gap), and the next page's
// colour opens up behind it. When the push carries, the same motion simply continues toward a full screen; the
// page being left is captured mid-move and the arriving page (public/carry.js, chain.css) carries on from
// exactly there, as one scroll. Short of a carry, it eases back.
const K = 12;
let offset = 0, target = 0, raf = 0, lastT = 0, frozen = false, moveDir: "down" | "up" = "down";
let movers: HTMLElement[] = [];
const strip = document.createElement("div"); strip.className = "carry-strip"; strip.setAttribute("aria-hidden", "true");
function paint() {
  const y = (moveDir === "down" ? -offset : offset).toFixed(2);
  for (const m of movers) m.style.translate = `0 ${y}px`;
  strip.style.transform = `translate3d(0, ${y}px, 0)`;
}
function tick(t: number) {
  raf = 0;
  const dt = Math.min(0.05, Math.max(0, (t - lastT) / 1000)); lastT = t;
  offset += (target - offset) * (1 - Math.exp(-K * dt));
  if (Math.abs(target - offset) < 0.25) offset = target;
  paint();
  if (covered && carrying && offset >= window.innerHeight - 0.5 && pending?.url) { const u = pending.url; pending.url = undefined; location.assign(u); }
  if (offset === 0 && target === 0) { stopMoving(); return; }
  if (offset !== target) raf = requestAnimationFrame(tick);
}
function stopMoving() {
  for (const m of movers) m.style.translate = "";
  movers = []; strip.remove(); html.removeAttribute("data-pushing"); offset = 0; target = 0;
}
function moveTo(px: number, dir: "down" | "up") {
  if (frozen || reduceMotion) return;
  if (!movers.length) {
    const to = dir === "down" ? next : prev; if (!to) return;
    moveDir = dir; html.setAttribute("data-pushing", dir);
    strip.style.setProperty("--carry-strip", dir === "down" ? to.top : to.foot);
    movers = [...document.body.children].filter((e): e is HTMLElement => e instanceof HTMLElement && !e.matches(".top, .carry-strip, .carry-prev, .skip, script"));
    document.body.append(strip);
  }
  target = Math.max(0, Math.min(window.innerHeight, px));
  if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(tick); }
}

/** carry to `to`, going down (to the next page) or up (to the previous one) */
export function carry(to: ChainPage, dir: "down" | "up") {
  if (carrying) return;
  carrying = true;
  const fallback = new URLSearchParams(location.search).get("carry") === "fallback";
  if (reduceMotion || crossDoc) { pending = { to, dir, cover: false }; note(to, dir, false); moveTo(window.innerHeight, dir); location.assign(to.path + (fallback ? "?carry=fallback" : "")); return; }
  // the fallback (no cross-document view transitions): the same motion runs on until the next page's colour fills
  // the screen, then the browser navigates (tick) and the next page uncovers
  pending = { to, dir, cover: true, url: to.path + (fallback ? "?carry=fallback" : "") }; note(to, dir, true); covered = true;
  moveTo(window.innerHeight, dir);
}

// a navigation that is not a carry (a header link, Back) plays no transition; nor does a fallback carry, whose cover already played
window.addEventListener("pageswap", (e: Event) => {
  const vt = (e as Event & { viewTransition?: { skipTransition(): void } | null }).viewTransition;
  if (vt && (!carrying || covered)) vt.skipTransition();
  // the page is captured as it stands: the motion stops here, and the arriving page is told where it was
  frozen = true; if (raf) { cancelAnimationFrame(raf); raf = 0; }
  if (pending) note(pending.to, pending.dir, pending.cover);
});
// coming back to this page from the cache (Back after a carry): ready to carry again, as it was before the push
window.addEventListener("pageshow", (e) => { if ((e as PageTransitionEvent).persisted) { carrying = false; covered = false; pending = null; frozen = false; stopMoving(); reset(); } });

// ---- the cue at the end, and the hint at the top
const cue = document.querySelector<HTMLAnchorElement>("a.carry-next");
const hint = document.querySelector<HTMLAnchorElement>("a.carry-prev");
const show = (el: HTMLElement | null, v: number) => el?.style.setProperty("--push", Math.max(0, Math.min(1, v)).toFixed(3));
for (const [el, to, dir] of [[cue, next, "down"], [hint, prev, "up"]] as const) {
  el?.addEventListener("click", (e) => {
    if (!to || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;   // a new tab or window is the browser's
    e.preventDefault(); carry(to, dir);
  });
}

// ---- the edges
const max = () => html.scrollHeight - window.innerHeight;
const atEnd = () => window.scrollY >= max() - EDGE;
const atTop = () => window.scrollY <= EDGE;
const atEdge = (dir: "down" | "up") => (dir === "down" ? !!next && atEnd() : !!prev && atTop());

// ---- preparing the page a carry will show, before it is needed: the next one once the reader is within 1.5
// viewports of the end, the previous one when they head back up within 1.5 viewports of the top. Chrome
// prerenders it (the Speculation-Rules header names public/speculation-rules.json, whose rule prerenders any
// link marked data-prepare), so the carry shows a page that is already loaded, laid out and painted; a
// prerendered page starts no graphics until it is shown (settled). Where there is no prerendering (Safari),
// its scripts and stylesheets are fetched ahead (they are cached for a year), leaving only its HTML to load.
const canPrerender = !!(HTMLScriptElement as typeof HTMLScriptElement & { supports?: (t: string) => boolean }).supports?.("speculationrules") && "prerendering" in document;
const prepared = new Set<string>();
function prepare(el: HTMLAnchorElement | null, to: ChainPage | undefined) {
  if (!el || !to || prepared.has(to.path)) return;
  prepared.add(to.path);
  el.dataset.prepare = "";
  if (!canPrerender) void warm(to.path);
}
async function warm(path: string) {
  try {
    const doc = new DOMParser().parseFromString(await (await fetch(path, { credentials: "same-origin" })).text(), "text/html");
    for (const l of doc.querySelectorAll("link[rel=modulepreload], script[type=module][src], link[rel=stylesheet]")) {
      const href = l.getAttribute("href") ?? l.getAttribute("src");
      if (!href || !href.startsWith("/assets/") || document.querySelector(`link[href="${href}"], script[src="${href}"]`)) continue;
      const k = document.createElement("link");
      if (l.getAttribute("rel") === "stylesheet") { k.rel = "preload"; k.as = "style"; } else k.rel = "modulepreload";
      k.crossOrigin = "anonymous"; k.href = href; document.head.append(k);
    }
  } catch { /* the carry still navigates */ }
}
let lastY = window.scrollY;
const near = () => {
  if (!ready) return;
  const y = window.scrollY, vh = window.innerHeight;
  if (next && max() - y < 1.5 * vh) prepare(cue, next);
  if (prev && y < 1.5 * vh && y < lastY) prepare(hint, prev);
  lastY = y;
};
window.addEventListener("scroll", near, { passive: true });
void settled.then(near);

// ---- gestures: a trackpad swipe and its momentum are one gesture; a pause, a reversal or a new rise starts another
let gLast = -1e9, gStart = 0, gLow = 0, gPeak = 0, gSign = 0, gRise = 0;
/** the wheel's strength as px per 60 Hz frame, over the last 50 ms: a busy main thread delivers wheel events in
 *  bursts or merges them (twice the delta, twice the interval), and neither must look like a new swipe */
const WIN = 50, recent: [number, number][] = [];
function rate(now: number, a: number, start: number) {
  recent.push([now, a]); while (recent.length && recent[0][0] < now - WIN) recent.shift();
  let sum = 0; for (const [, x] of recent) sum += x;
  return (sum * 16.7) / Math.min(WIN, now - start + 16.7);
}
let gDir: "down" | "up" | null = null;   // the gesture under way counts toward a carry in this direction (it began at that edge)
let push = 0, relaxT = 0, lastPushDir: "down" | "up" = "down";

function reset() { push = 0; show(cue, 0); show(hint, 0); hint?.classList.remove("pulling"); if (!carrying && movers.length) moveTo(0, moveDir); }

window.addEventListener("wheel", (e) => {
  const now = e.timeStamp || performance.now();
  const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerHeight : 1, dy = e.deltaY * unit, a = Math.abs(dy), s = Math.sign(dy);
  const paused = now - gLast > GAP || (s !== 0 && gSign !== 0 && s !== gSign);
  if (paused) { recent.length = 0; gStart = now; }
  const r = rate(now, a, gStart);
  // a new swipe during momentum: the rate rises again, after it had begun to fall, for two events running
  gRise = !paused && gLow < gPeak * 0.8 && r > Math.max(gLow * 1.6, gLow + 4) && r >= 6 ? gRise + 1 : 0;
  const fresh = paused || gRise >= 2;
  gLast = now; lastWheelEpoch = Date.now(); lastWheelAbs = r;
  if (fresh) { if (!paused) { recent.length = 0; recent.push([now, a]); gStart = now; } gLow = r; gPeak = r; gRise = 0; gSign = s || gSign; }
  // gLow is the lowest point since the peak: the swipe "has begun to fall" once it is under 80% of the peak, and a
  // rise is measured from there (so a swipe's own ramp to its peak never reads as a new one)
  else if (r >= gPeak) { gPeak = r; gLow = r; } else gLow = Math.min(gLow, r);
  if (carrying) return;
  if (e.ctrlKey || at < 0 || e.defaultPrevented || !ready) { gDir = null; return; }   // a pinch; the landing gesture (carry.js); before arriving
  if (fresh) {
    // a gesture counts only if it begins at an edge, pushing past it
    gDir = s > 0 && atEdge("down") ? "down" : s < 0 && atEdge("up") ? "up" : null;
    if (gDir === "up") prepare(hint, prev);
    if (gDir && gDir !== lastPushDir) reset();   // a push the other way starts from nothing
  }
  if (!gDir) return;
  if (!atEdge(gDir) || (gDir === "down" ? dy <= 0 : dy >= 0)) { gDir = null; reset(); return; }
  lastPushDir = gDir;
  push += a;
  moveTo(push, gDir);
  const v = push / (THRESHOLD * window.innerHeight);
  if (gDir === "down") show(cue, v); else { show(hint, v); hint?.classList.add("pulling"); }
  window.clearTimeout(relaxT);
  relaxT = window.setTimeout(() => { if (!carrying) reset(); }, RELAX);   // a push that stops short relaxes
  if (v >= 1) { const to = gDir === "down" ? next : prev; if (to) carry(to, gDir); }
}, { passive: true });
// a plain scroll away from the edge disarms (scrollbar, keys, find-in-page)
window.addEventListener("scroll", () => { if (gDir && !atEdge(gDir)) { gDir = null; reset(); } }, { passive: true });

// keys at the edge: one press of Space, Page Down, Arrow Down or End carries (Shift+Space, Page Up, Arrow Up
// and Home at the top). The press that reached the edge was made before it, so it never counts.
window.addEventListener("keydown", (e) => {
  if (carrying || !ready || e.altKey || e.metaKey || e.ctrlKey || e.repeat) return;
  const t = e.target as HTMLElement;
  if (t.closest?.("input, textarea, select, [contenteditable], button")) return;
  const down = ["PageDown", "ArrowDown", "End"].includes(e.key) || (e.key === " " && !e.shiftKey);
  const up = ["PageUp", "ArrowUp", "Home"].includes(e.key) || (e.key === " " && e.shiftKey);
  if (!down && !up) return;
  const dir = down ? "down" : "up", to = down ? next : prev;
  if (!to || !atEdge(dir)) return;
  e.preventDefault(); carry(to, dir);
});

// touch: a pull that starts at the edge and passes 15% of the viewport carries on release
let touchY: number | null = null, touchDir: "down" | "up" | null = null;
window.addEventListener("touchstart", (e) => {
  if (carrying || !ready || e.touches.length !== 1) return;
  touchDir = atEdge("down") ? "down" : atEdge("up") ? "up" : null;
  touchY = touchDir ? e.touches[0].clientY : null;
}, { passive: true });
window.addEventListener("touchmove", (e) => {
  if (touchY === null || !touchDir) return;
  const d = touchY - e.touches[0].clientY, v = (touchDir === "down" ? d : -d) / (THRESHOLD * window.innerHeight);
  moveTo(Math.max(0, touchDir === "down" ? d : -d), touchDir);
  if (touchDir === "down") show(cue, v); else { show(hint, v); hint?.classList.toggle("pulling", v > 0); }
}, { passive: true });
window.addEventListener("touchend", (e) => {
  if (touchY === null || !touchDir) return;
  const d = touchY - e.changedTouches[0].clientY, v = (touchDir === "down" ? d : -d) / (THRESHOLD * window.innerHeight);
  const to = touchDir === "down" ? next : prev;
  if (v >= 1 && to) carry(to, touchDir); else reset();
  touchY = null; touchDir = null;
}, { passive: true });
