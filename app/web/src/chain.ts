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

export interface ChainPage { path: string; name: string; ground: string }
/** The chain, in order. `ground` must equal each theme's --ground (the browser check holds them equal). */
export const CHAIN: ChainPage[] = [
  { path: "/", name: "home", ground: "#efe6d2" },
  { path: "/run.html", name: "run", ground: "#121416" },
  { path: "/docs.html", name: "docs", ground: "#255ea4" },
  { path: "/sancho.html", name: "Sancho", ground: "#ece2cf" },
];
export const CARRY_MS = 1000;
export const CARRY_EASE = "cubic-bezier(.35, 0, 0, 1)";
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
let ready = false;
void settled.then(() => { ready = true; });

let carrying = false, covered = false;   // covered: this carry used the fallback's cover
let lastWheelEpoch = 0, lastWheelAbs = 0;  // handed to the arriving page, which swallows the rest of this gesture

const note = (to: ChainPage, dir: "down" | "up", cover: boolean) => {
  try { sessionStorage.setItem("qx-carry", JSON.stringify({ to: to.path, dir, cover, t: Date.now(), w: lastWheelEpoch, a: lastWheelAbs })); } catch { /* private mode: the carry still navigates */ }
};
let pending: { to: ChainPage; dir: "down" | "up"; cover: boolean } | null = null;

/** carry to `to`, going down (to the next page) or up (to the previous one) */
export function carry(to: ChainPage, dir: "down" | "up") {
  if (carrying) return;
  carrying = true;
  const url = to.path + (new URLSearchParams(location.search).get("carry") === "fallback" ? "?carry=fallback" : "");
  if (reduceMotion || crossDoc) { pending = { to, dir, cover: false }; note(to, dir, false); location.assign(url); return; }
  // the fallback: the next page's ground slides over this one, then the navigation
  pending = { to, dir, cover: true }; note(to, dir, true); covered = true;
  const cover = document.createElement("div");
  cover.className = "carry-cover"; cover.setAttribute("aria-hidden", "true");
  cover.style.setProperty("--carry-ground", to.ground);
  document.body.append(cover);
  const from = dir === "down" ? "translate3d(0, 100%, 0)" : "translate3d(0, -100%, 0)";
  const a = cover.animate([{ transform: from }, { transform: "translate3d(0, 0, 0)" }], { duration: CARRY_MS * 0.6, easing: CARRY_EASE, fill: "forwards" });
  a.finished.then(() => location.assign(url), () => location.assign(url));
}

// a navigation that is not a carry (a header link, Back) plays no transition; nor does a fallback carry, whose cover already played
window.addEventListener("pageswap", (e: Event) => {
  const vt = (e as Event & { viewTransition?: { skipTransition(): void } | null }).viewTransition;
  if (vt && (!carrying || covered)) vt.skipTransition();
  if (pending) note(pending.to, pending.dir, pending.cover);   // the last word on the gesture, as the page is left
});
// coming back to this page from the cache (Back after a carry): ready to carry again
window.addEventListener("pageshow", (e) => { if ((e as PageTransitionEvent).persisted) { carrying = false; covered = false; pending = null; document.querySelectorAll(".carry-cover").forEach((c) => c.remove()); reset(); } });

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

// ---- gestures: a trackpad swipe and its momentum are one gesture; a pause, a reversal or a new rise starts another
let gLast = -1e9, gLow = 0, gPeak = 0, gSign = 0, gRise = 0;
/** a wheel event's strength as px per 60 Hz frame: when the main thread is busy the browser merges events
 *  (twice the delta, twice the interval), and a merged event must not look like a new swipe */
const rate = (a: number, dt: number) => (a * 16.7) / Math.max(8, Math.min(60, dt));
let gDir: "down" | "up" | null = null;   // the gesture under way counts toward a carry in this direction (it began at that edge)
let push = 0, relaxT = 0, lastPushDir: "down" | "up" = "down";

function reset() { push = 0; show(cue, 0); show(hint, 0); hint?.classList.remove("pulling"); }

window.addEventListener("wheel", (e) => {
  const now = e.timeStamp || performance.now();
  const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerHeight : 1, dy = e.deltaY * unit, a = Math.abs(dy), s = Math.sign(dy);
  const r = rate(a, now - gLast);
  // a new swipe during momentum: the rate rises again, after it had begun to fall, for two events running
  gRise = gLow < gPeak * 0.8 && r > Math.max(gLow * 1.6, gLow + 4) && r >= 6 ? gRise + 1 : 0;
  const fresh = now - gLast > GAP || (s !== 0 && gSign !== 0 && s !== gSign) || gRise >= 2;
  gLast = now; lastWheelEpoch = Date.now(); lastWheelAbs = r;
  if (fresh) { gLow = r; gPeak = r; gRise = 0; gSign = s || gSign; } else { gLow = Math.min(gLow, r); gPeak = Math.max(gPeak, r); }
  if (carrying) return;
  if (e.ctrlKey || at < 0 || e.defaultPrevented || !ready) { gDir = null; return; }   // a pinch; the landing gesture (carry.js); before arriving
  if (fresh) {
    // a gesture counts only if it begins at an edge, pushing past it
    gDir = s > 0 && atEdge("down") ? "down" : s < 0 && atEdge("up") ? "up" : null;
    if (gDir && gDir !== lastPushDir) reset();   // a push the other way starts from nothing
  }
  if (!gDir) return;
  if (!atEdge(gDir) || (gDir === "down" ? dy <= 0 : dy >= 0)) { gDir = null; reset(); return; }
  lastPushDir = gDir;
  push += a;
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
  if (touchDir === "down") show(cue, v); else { show(hint, v); hint?.classList.toggle("pulling", v > 0); }
}, { passive: true });
window.addEventListener("touchend", (e) => {
  if (touchY === null || !touchDir) return;
  const d = touchY - e.changedTouches[0].clientY, v = (touchDir === "down" ? d : -d) / (THRESHOLD * window.innerHeight);
  const to = touchDir === "down" ? next : prev;
  if (v >= 1 && to) carry(to, touchDir); else reset();
  touchY = null; touchDir = null;
}, { passive: true });
