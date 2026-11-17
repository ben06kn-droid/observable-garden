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
// Never mid-read. A carry only arms once the page is already at its end AND the wheel has gone
// quiet there (so the momentum of the scroll that reached the end never counts). Then it takes one
// gesture of at least 40% of the viewport, or a nudge, a pause and another. The end of each page
// carries a visible cue ("Continue to docs ↓") whose hairline fills with the push; it is also a plain
// link, the keyboard's way on. Going up from the top is the same rule, and lands at the previous
// page's end. Touch: a pull of 30% of the viewport, started at the end (or the top), carries on release.
import { reduceMotion } from "./common";
import "./styles/chain.css";

export interface ChainPage { path: string; name: string; ground: string }
/** The chain, in order. `ground` must equal each theme's --ground (the browser check holds them equal). */
export const CHAIN: ChainPage[] = [
  { path: "/", name: "home", ground: "#efe6d2" },
  { path: "/run.html", name: "run", ground: "#121416" },
  { path: "/docs.html", name: "docs", ground: "#d4e9f8" },
  { path: "/sancho.html", name: "Sancho", ground: "#ece2cf" },
];
export const CARRY_MS = 1000;
export const CARRY_EASE = "cubic-bezier(.35, 0, 0, 1)";
const LEEWAY = 0.4, TOUCH = 0.3, QUIET = 220, PAUSE = 250, EDGE = 2;

const here = location.pathname === "/index.html" ? "/" : location.pathname;
const at = CHAIN.findIndex((p) => p.path === here);
const next = at >= 0 ? CHAIN[at + 1] : undefined, prev = at > 0 ? CHAIN[at - 1] : undefined;
const html = document.documentElement;
// cross-document view transitions: the pageswap event and the @view-transition rule
const crossDoc = "onpageswap" in window && typeof CSSRule !== "undefined" && "CSSViewTransitionRule" in window
  && new URLSearchParams(location.search).get("carry") !== "fallback";   // ?carry=fallback forces the fallback path, for testing

let carrying = false, covered = false;   // covered: this carry used the fallback's cover

/** carry to `to`, going down (to the next page) or up (to the previous one) */
export function carry(to: ChainPage, dir: "down" | "up") {
  if (carrying) return;
  carrying = true;
  const url = to.path + (new URLSearchParams(location.search).get("carry") === "fallback" ? "?carry=fallback" : "");
  const note = (cover: boolean) => { try { sessionStorage.setItem("qx-carry", JSON.stringify({ to: to.path, dir, cover, t: Date.now() })); } catch { /* private mode: the carry still navigates */ } };
  if (reduceMotion || crossDoc) { note(false); location.assign(url); return; }
  // the fallback: the next page's ground slides over this one, then the navigation
  note(true); covered = true;
  const cover = document.createElement("div");
  cover.className = "carry-cover"; cover.setAttribute("aria-hidden", "true");
  cover.style.setProperty("--carry-ground", to.ground);
  document.body.append(cover);
  const from = dir === "down" ? "translate3d(0, 100%, 0)" : "translate3d(0, -100%, 0)";
  const a = cover.animate([{ transform: from }, { transform: "translate3d(0, 0, 0)" }], { duration: CARRY_MS * 0.6, easing: CARRY_EASE, fill: "forwards" });
  a.finished.then(() => location.assign(url), () => location.assign(url));
}

// a navigation that is not a carry (a header link, Back) plays no transition; nor does a fallback carry, whose cover already played
window.addEventListener("pageswap", (e: Event) => { const vt = (e as Event & { viewTransition?: { skipTransition(): void } | null }).viewTransition; if (vt && (!carrying || covered)) vt.skipTransition(); });
// coming back to this page from the cache (Back after a carry): ready to carry again
window.addEventListener("pageshow", (e) => { if ((e as PageTransitionEvent).persisted) { carrying = false; covered = false; document.querySelectorAll(".carry-cover").forEach((c) => c.remove()); reset(); } });

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

// ---- arming and the push
const max = () => html.scrollHeight - window.innerHeight;
const atEnd = () => window.scrollY >= max() - EDGE;
const atTop = () => window.scrollY <= EDGE;
let lastWheel = 0;               // when the last wheel event came, anywhere
let armed: "down" | "up" | null = null;
let push = 0, gestures = 0, gestureAt = 0;

function reset() { push = 0; gestures = 0; show(cue, 0); show(hint, 0); hint?.classList.remove("pulling"); }
function arm() {
  const was = armed;
  armed = next && atEnd() ? "down" : prev && atTop() ? "up" : null;
  if (armed !== was) reset();
}

window.addEventListener("wheel", (e) => {
  if (carrying || e.ctrlKey || at < 0) { lastWheel = performance.now(); return; }
  const now = performance.now(), quiet = now - lastWheel > QUIET;
  lastWheel = now;
  const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerHeight : 1, dy = e.deltaY * unit;
  // arm only from a standstill at the edge: the scroll that reached the edge never counts
  if (quiet) arm();
  else if (armed && !((armed === "down" && atEnd()) || (armed === "up" && atTop()))) { armed = null; reset(); }
  if (!armed) return;
  if ((armed === "down" && dy <= 0) || (armed === "up" && dy >= 0)) { if (Math.abs(dy) > 4) reset(); return; }
  if (quiet || now - gestureAt > PAUSE) { gestures++; push = 0; }
  gestureAt = now;
  push += Math.abs(dy);
  const v = push / (LEEWAY * window.innerHeight);
  if (armed === "down") show(cue, Math.max(v, gestures > 1 ? 1 : 0)); else { show(hint, Math.max(v, gestures > 1 ? 1 : 0)); hint?.classList.add("pulling"); }
  if (v >= 1 || gestures >= 2) { const to = armed === "down" ? next : prev; if (to) carry(to, armed); }
}, { passive: true });
// a plain scroll away from the edge disarms (scrollbar, keys, find-in-page)
window.addEventListener("scroll", () => { if (armed && !((armed === "down" && atEnd()) || (armed === "up" && atTop()))) { armed = null; reset(); } }, { passive: true });
// relax the meter when the push stops short
let relaxT = 0;
window.addEventListener("wheel", () => { window.clearTimeout(relaxT); relaxT = window.setTimeout(() => { if (!carrying && gestures < 2) { push = 0; show(cue, 0); show(hint, 0); hint?.classList.remove("pulling"); } }, 900); }, { passive: true });

// keys at the edge: Space, Page Down, Arrow Down and End count as nudges (two, with a pause, carry)
window.addEventListener("keydown", (e) => {
  if (carrying || e.altKey || e.metaKey || e.ctrlKey) return;
  const t = e.target as HTMLElement;
  if (t.closest?.("input, textarea, select, [contenteditable], button")) return;
  const down = ["PageDown", "ArrowDown", "End"].includes(e.key) || (e.key === " " && !e.shiftKey);
  const up = ["PageUp", "ArrowUp", "Home"].includes(e.key) || (e.key === " " && e.shiftKey);
  if (!down && !up) return;
  const dir = down ? "down" : "up", to = down ? next : prev;
  if (!to || !(down ? atEnd() : atTop())) { gestures = 0; return; }
  if (e.repeat) return;
  const now = performance.now();
  if (armed !== dir) { armed = dir; reset(); gestureAt = now; gestures = 1; show(down ? cue : hint, 0.5); if (up) hint?.classList.add("pulling"); return; }
  if (now - gestureAt > PAUSE) carry(to, dir);
});

// touch: a pull that starts at the edge and passes 30% of the viewport carries on release
let touchY: number | null = null, touchDir: "down" | "up" | null = null;
window.addEventListener("touchstart", (e) => {
  if (carrying || e.touches.length !== 1) return;
  touchDir = next && atEnd() ? "down" : prev && atTop() ? "up" : null;
  touchY = touchDir ? e.touches[0].clientY : null;
}, { passive: true });
window.addEventListener("touchmove", (e) => {
  if (touchY === null || !touchDir) return;
  const d = touchY - e.touches[0].clientY, v = (touchDir === "down" ? d : -d) / (TOUCH * window.innerHeight);
  if (touchDir === "down") show(cue, v); else { show(hint, v); hint?.classList.toggle("pulling", v > 0); }
}, { passive: true });
window.addEventListener("touchend", (e) => {
  if (touchY === null || !touchDir) return;
  const d = touchY - e.changedTouches[0].clientY, v = (touchDir === "down" ? d : -d) / (TOUCH * window.innerHeight);
  const to = touchDir === "down" ? next : prev;
  if (v >= 1 && to) carry(to, touchDir); else reset();
  touchY = null; touchDir = null;
}, { passive: true });
