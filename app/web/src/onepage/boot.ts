// The one-page site: home, run, docs and Sancho as sections of one document, each built once behind
// the loading screen and kept alive. This module runs the document:
//
// - The work. Each page's script registers the real work it does before it can be shown (task(): data fetched,
//   a scene built and its first frame drawn); the files fetched before any script ran count as done. The loading
//   screen's box shows the share done. When all of it is done the screen goes (src/loader.ts), never before.
// - Addresses. Each section has its own address and title (data-path, data-title). As the reader scrolls, the
//   address, the title and the menu's current item follow the section under the middle of the screen
//   (history.replaceState: scrolling adds no history entries). A link to a section (the header's, a cue, a link in
//   the text) scrolls to it and adds an entry; Back and Forward scroll between them. A direct link to any address
//   opens on its section (data-start), behind the loading screen.
// - The scroll between sections is the browser's own. Where one section gives way to the next, the background
//   changes with the scroll position, as on lukres.dev (DESIGN.md section 1): one backdrop per section, each in its
//   theme's ground, the next fading in linearly while the next section's top rises from 65% to 27.6% of the
//   viewport's height (his 585 to 248 px at 900); the header's colours mix along with it, and it takes the new
//   section's theme (its type) half way.
// - Scenes pause while their section is off screen (inView, onView).
import { Loader } from "../loader";
import { reduceMotion } from "../common";
import "../styles/onepage.css";

const html = document.documentElement;
if ("scrollRestoration" in history) history.scrollRestoration = "manual";
const sections = [...document.querySelectorAll<HTMLElement>("[data-section]")];
const byName = new Map(sections.map((s) => [s.dataset.section!, s]));
const byPath = new Map(sections.map((s) => [s.dataset.path!, s]));
const backdrop = new Map([...document.querySelectorAll<HTMLElement>(".backdrop")].map((b) => [b.dataset.for!, b]));
const header = document.querySelector<HTMLElement>(".top")!, headerTheme = document.querySelector<HTMLElement>(".top-theme") ?? header;
const pathOf = (p: string) => (p === "/index.html" ? "/" : p);

/** a section's element, by name (home, run) */
export const section = (name: string) => byName.get(name)!;
const top = (s: HTMLElement) => s.getBoundingClientRect().top + window.scrollY;

// ---- the work, and the loading screen
const loader = new Loader(document.querySelector<HTMLElement>(".loader"), { formed: html.dataset.loader === "formed" });
let total = 0, done = 0, started = false, finishing = false;
const progress = () => loader.progress(total ? done / total : 0);
/** register a piece of work the site needs before it is shown; call the returned function when it is done */
export function task(_name: string): () => void {
  total++; let fired = false; progress();
  return () => { if (fired) return; fired = true; done++; progress(); if (started && done === total) { performance.mark("qx-work-done"); void reveal(); } };
}
// the files fetched before any script ran (the document, its styles and scripts): done already
{ const n = performance.getEntriesByType("resource").length + 1; total += n; done += n; }
// the fonts: requested by the first layout, done when all have arrived
{ const fonts = task("fonts"); requestAnimationFrame(() => { void document.fonts.ready.then(fonts); }); }

let revealedNow: () => void = () => {};
/** the site is shown: the loading screen has gone */
export const revealed = new Promise<void>((r) => { revealedNow = r; });
async function reveal() {
  if (finishing) return; finishing = true;
  snap(); goTo(startSection(), false); toAnchor(location.hash);   // the layout is final: open on the address's section (and anchor)
  for (const f of beforeReveal) f();   // a layer over the page that the address opens (the viewer at /viewer.html)
  scrub();
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));   // every scene's first frame is on screen beneath
  await loader.finish();
  performance.mark("qx-revealed");   // the screen has gone (for measurement: work done to revealed is the loader's own time)
  revealedNow();
}
const beforeReveal: (() => void)[] = [];
/** call once the layout is final and the address's section is in place, before the loading screen goes */
export function onBeforeReveal(f: () => void) { beforeReveal.push(f); }
/** all the page scripts have registered their work */
export function start() {
  // each section's colours, read now that every section's script has run: under the dev server a section's
  // stylesheet arrives with its script, after this module, and a read before then finds no colours at all (the
  // header's ink and ground mixed from transparent: it vanished)
  refreshThemes();
  started = true; snap(); goTo(startSection(), false); scrub(); if (done === total) { performance.mark("qx-work-done"); void reveal(); } }
/** an anchor inside a section (a docs heading): scroll to it, once its section is the current one */
function toAnchor(hash: string, smooth = false) {
  const el = hash.length > 1 ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
  if (!el) return false;
  target = Math.round(el.getBoundingClientRect().top + window.scrollY - (parseFloat(getComputedStyle(el).scrollMarginTop) || 0));
  window.scrollTo({ top: target, behavior: smooth && !reduceMotion ? "smooth" : "auto" });
  return true;
}
const startSection = () => byPath.get(pathOf(location.pathname)) ?? byName.get(html.dataset.start ?? "") ?? sections[0];

/** idle time, for work nobody is waiting on (the run page's Pyodide) */
export const idle = (timeout = 1500) => new Promise<void>((r) => {
  const w = window as Window & { requestIdleCallback?: (f: () => void, o?: { timeout: number }) => number };
  if (w.requestIdleCallback) w.requestIdleCallback(() => r(), { timeout }); else window.setTimeout(r, 300);
});

// ---- each section starts on a whole pixel: the sections above it need not end on one, and a section a fraction of
// a pixel off would render every glyph and line a little differently from its page (under 1 px of space is added)
function snap() {
  let shift = 0;
  for (const s of sections.slice(1)) {
    s.style.removeProperty("margin-top");
    const t = s.getBoundingClientRect().top + window.scrollY, f = t - Math.floor(t);
    if (f > 0.001) { s.style.setProperty("margin-top", `${(1 - f).toFixed(3)}px`); shift++; }
  }
  return shift;
}
new ResizeObserver(() => { snap(); }).observe(sections[0]);

// ---- addresses
let current: HTMLElement | null = null, steering = 0;   // steering: a scroll to a section is under way (no address updates)
function mark(s: HTMLElement, how: "replace" | "push" | "none") {
  const path = s.dataset.path!;
  if (how === "push" && pathOf(location.pathname) !== path) history.pushState({ section: s.dataset.section }, "", path);
  else if (how === "replace" && pathOf(location.pathname) !== path) history.replaceState({ section: s.dataset.section }, "", path);
  document.title = s.dataset.title ?? document.title;
  for (const a of header.querySelectorAll<HTMLAnchorElement>("nav a")) {
    if (pathOf(new URL(a.href).pathname) === path) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  current = s;
}
/** scroll to a section: instantly (opening, Back), or as a smooth scroll (a link), adding a history entry if asked */
let target = -1;   // where a scroll to a section is going: the address is left alone until it gets there
function goTo(s: HTMLElement, smooth: boolean, push = false) {
  mark(s, push ? "push" : "none");
  target = Math.round(top(s));
  window.clearTimeout(steering);
  steering = window.setTimeout(() => { steering = 0; target = -1; }, smooth ? 2500 : 300);   // a backstop
  const from = window.scrollY, behavior: ScrollBehavior = smooth && !reduceMotion ? "smooth" : "auto";
  window.scrollTo({ top: target, behavior });
  // a smooth scroll asked for in the same frame as another scroll ends can be dropped (seen in Chrome straight after
  // Back): if it has not moved at all, ask again
  if (behavior === "smooth") window.setTimeout(() => { if (target >= 0 && Math.abs(window.scrollY - from) < 1 && Math.abs(window.scrollY - target) > 2) window.scrollTo({ top: target, behavior }); }, 120);
}
addEventListener("scrollend", () => { if (steering && Math.abs(window.scrollY - target) < 2) { window.clearTimeout(steering); steering = 0; target = -1; } });
document.addEventListener("click", (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a || (a.target && a.target !== "_self") || a.hasAttribute("download")) return;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin) return;
  const s = byPath.get(pathOf(url.pathname)); if (!s) return;
  e.preventDefault();
  if (url.hash) {   // an anchor in a section: the section's address with the anchor, and a scroll to it
    mark(s, "none"); history.pushState({ section: s.dataset.section }, "", s.dataset.path + url.hash);
    window.clearTimeout(steering); steering = window.setTimeout(() => { steering = 0; target = -1; }, 2500);
    toAnchor(url.hash, true);
    const el = document.getElementById(decodeURIComponent(url.hash.slice(1)));
    if (el) { if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1"); el.focus({ preventScroll: true }); }
    return;
  }
  goTo(s, true, true);
  // focus moves with the reader, as it does for an in-page link: the next Tab continues from the section
  if (!s.hasAttribute("tabindex")) s.setAttribute("tabindex", "-1");
  s.focus({ preventScroll: true });
});
// a layer over the page (the viewer) handles the entries that open and close it, leaving the scroll where it was
let popFirst: (() => boolean) | null = null;
/** f runs first on Back and Forward; when it returns true the page itself does nothing */
export function onPopFirst(f: () => boolean) { popFirst = f; }
addEventListener("popstate", () => { if (popFirst?.()) return; const s = byPath.get(pathOf(location.pathname)); if (!s) return; goTo(s, false); toAnchor(location.hash); });

// ---- the scrub: backdrops and the header, by scroll position; which section is current; which are in view
const BAND: [number, number] = [0.65, 0.276];   // the next section's top, as a share of the viewport's height: fade starts, ends
type RGBA = [number, number, number, number];
const probe = document.createElement("i");
function rgba(c: string): RGBA {
  probe.style.color = ""; probe.style.color = c; document.body.append(probe);
  const m = getComputedStyle(probe).color.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0, 1]; probe.remove();
  return [m[0], m[1], m[2], m[3] ?? 1];
}
const HEADER_VARS = ["--header-bg", "--ink", "--muted", "--rule"];
let themes = new Map<string, RGBA[]>();
/** read each section's header colours again (after the run page inverts its palette) */
export function refreshThemes() {
  themes = new Map(sections.map((s) => { const cs = getComputedStyle(backdrop.get(s.dataset.section!) ?? s); return [s.dataset.section!, HEADER_VARS.map((k) => rgba(cs.getPropertyValue(k).trim() || "transparent"))]; }));
  scrub();
}
const visible = new Map<string, boolean>(), watchers = new Map<string, ((v: boolean) => void)[]>();
/** whether a section is on screen now */
export const inView = (name: string) => visible.get(name) ?? false;
/** call back when a section comes on screen or leaves it */
export function onView(name: string, f: (v: boolean) => void) { watchers.set(name, [...(watchers.get(name) ?? []), f]); f(inView(name)); }

const seen = new Map<string, boolean>(), backdropWatchers = new Map<string, ((v: boolean) => void)[]>();
/** call back when a section's backdrop comes into sight or goes (its scene draws only while it can be seen) */
export function onBackdrop(name: string, f: (v: boolean) => void) { backdropWatchers.set(name, [...(backdropWatchers.get(name) ?? []), f]); f(seen.get(name) ?? false); }

// while a layer covers the whole window (the viewer), nothing on the page counts as seen: every scene pauses
let covered = false;
/** the page is (or is no longer) covered by a layer over the whole window */
export function setCovered(c: boolean) { covered = c; scrub(); }
let raf = 0;
function scrub() {
  raf = 0;
  const vh = window.innerHeight;
  // each section's share of the backdrop: the first is always there, each next one fades in over the band
  let k = 0, p = 1;
  sections.forEach((s, i) => {
    const r = s.getBoundingClientRect();
    const v = !covered && r.bottom > 0 && r.top < vh;
    if (visible.get(s.dataset.section!) !== v) { visible.set(s.dataset.section!, v); for (const f of watchers.get(s.dataset.section!) ?? []) f(v); }
    if (i === 0) return;
    const q = Math.max(0, Math.min(1, (BAND[0] - r.top / vh) / (BAND[0] - BAND[1])));
    backdrop.get(s.dataset.section!)?.style.setProperty("opacity", q.toFixed(4));
    if (q > 0) { k = i; p = q; }
  });
  // which backdrops can be seen: each from when it starts to fade in until the next has fully covered it
  const share = sections.map((s, i) => i === 0 ? 1 : parseFloat(backdrop.get(s.dataset.section!)?.style.opacity || "0"));
  sections.forEach((s, i) => {
    const v = !covered && share[i] > 0 && (i === sections.length - 1 || share[i + 1] < 1), n = s.dataset.section!;
    if (seen.get(n) !== v) { seen.set(n, v); for (const f of backdropWatchers.get(n) ?? []) f(v); }
  });
  // the header: the two sections' colours mixed by the same share; their theme (type) from half way
  const a = themes.get(sections[Math.max(0, k - 1)].dataset.section!), b = themes.get(sections[k].dataset.section!);
  if (a && b) HEADER_VARS.forEach((name, j) => {
    const m = (x: number, y: number) => x + (y - x) * (k === 0 ? 1 : p);
    const c = [0, 1, 2].map((n) => Math.round(m(a[j][n], b[j][n]))), al = m(a[j][3], b[j][3]);
    header.style.setProperty(name, `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${al.toFixed(3)})`);
  });
  const lead = sections[k === 0 || p >= 0.5 ? k : k - 1];
  headerTheme.dataset.theme = lead.dataset.theme ?? lead.dataset.section!;
  if (lead.dataset.page) headerTheme.dataset.page = lead.dataset.page; else delete headerTheme.dataset.page;
  // the current section: the one under the middle of the screen; the address follows it
  const mid = sections.find((s) => { const r = s.getBoundingClientRect(); return r.top <= vh / 2 && r.bottom > vh / 2; });
  if (mid && mid !== current && !steering && finishing && !covered) mark(mid, "replace");
}
const ask = () => { if (!raf) raf = requestAnimationFrame(scrub); };
addEventListener("scroll", ask, { passive: true });
addEventListener("resize", ask, { passive: true });
refreshThemes();
