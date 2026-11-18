// The viewer's way in, through and out (DESIGN.md section 3, viewer; the reference is lukres.dev's project page,
// section 1). A layer over the one page, opened only by "Open the viewer" in the Sancho section.
//
// - Opening: Sancho's content rises and fades, a white ground covers the dusk, the viewer's first panel rises in (1 s,
//   the site's travel curve). The page beneath stops scrolling and everything on it is inert; once covered, its scenes
//   pause (setCovered). The address becomes /viewer.html (one history entry).
// - Browsing: full-window panels left to right. The wheel (vertical or sideways) moves the strip 1:1 in pixels through
//   lukres.dev's eased follow (each frame `remaining × (1 − e^(−12·dt))`); 150 ms after the last wheel event the strip
//   eases to the nearest panel. ← and → move a panel, Home and End to the ends; Tab brings the focused panel into view.
//   A small mark shows which panel is current.
// - Leaving: scrolling back (up or left) from the first panel leaves at once; so do Escape, Close and the browser's
//   Back. The page returns exactly where the reader left it, and focus to the control that opened it.
// - A direct link to /viewer.html opens it behind the loading screen, over the Sancho section at that control.
// - Phone, a short window, a touch screen or reduced motion: the same panels as a plain vertical list in the same layer,
//   scrolled natively; no sideways movement. Reduced motion: no animation in or out.
import { reduceMotion } from "./common";
import { onBeforeReveal, onPopFirst, setCovered } from "./onepage/boot";

const PATH = "/viewer.html", TITLE = "Quixote · viewer";
const EASE = "cubic-bezier(.35, 0, 0, 1)";
const html = document.documentElement;

export function makeStrip(layer: HTMLElement, o: { onResize?: () => void } = {}) {
  const strip = layer.querySelector<HTMLElement>(".v-strip")!, ground = layer.querySelector<HTMLElement>(".v-ground")!;
  const chrome = [layer.querySelector<HTMLElement>(".v-bar")!, strip, layer.querySelector<HTMLElement>(".v-progress")!];
  const count = layer.querySelector<HTMLElement>("#v-count")!, name = layer.querySelector<HTMLElement>("#v-name")!;
  const thumb = layer.querySelector<HTMLElement>("#v-thumb")!, progress = layer.querySelector<HTMLElement>(".v-progress")!;
  const main = document.getElementById("main")!;
  const listMQ = matchMedia("(max-width: 812px), (max-height: 639px), (pointer: coarse)");
  const isList = () => reduceMotion || listMQ.matches;

  let open = false, busy = false, opener: HTMLElement | null = null, titleBefore = "";
  let panels: HTMLElement[] = [], vw = 1, x = 0, target = 0, raf = 0, last = 0, settleT = 0, shownIndex = -1;

  // ---- the panels and the mark
  function refresh() {
    panels = [...strip.querySelectorAll<HTMLElement>(".v-panel")].filter((p) => !p.hidden);
    progress.style.setProperty("--n", String(panels.length));
    progress.hidden = panels.length < 2;
    measure();
    target = Math.min(target, max()); x = Math.min(x, max());
    write(); mark(true);
  }
  const max = () => Math.max(0, (panels.length - 1) * vw);
  const index = () => Math.max(0, Math.min(panels.length - 1, Math.round(target / vw)));
  function measure() {
    const old = vw; vw = layer.clientWidth || 1;
    if (old !== vw) { const i = Math.round(target / old); target = x = i * vw; }
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  function mark(force = false) {
    const i = Math.max(0, Math.min(panels.length - 1, Math.round(x / vw)));
    if (i === shownIndex && !force) return;
    shownIndex = i;
    count.textContent = `${pad(i + 1)} / ${pad(panels.length)}`;
    name.textContent = panels[i]?.dataset.name ?? "";
  }
  function write() {
    if (isList()) { strip.style.removeProperty("transform"); return; }
    strip.style.setProperty("transform", `translate3d(${(-x).toFixed(2)}px, 0, 0)`);
    thumb.style.setProperty("transform", `translate3d(${((x / vw) * 100).toFixed(3)}%, 0, 0)`);
  }

  // ---- the eased follow (lukres.dev's ScrollPane: frame-rate independent, never overshoots)
  function frame(t: number) {
    const dt = last ? Math.min(0.1, (t - last) / 1000) : 1 / 60; last = t;
    const rem = target - x;
    x = Math.abs(rem) < 0.1 ? target : x + rem * (1 - Math.exp(-12 * dt));
    write(); mark();
    raf = x === target ? 0 : requestAnimationFrame(frame);
    if (!raf) last = 0;
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(frame); };
  function go(i: number) {
    if (isList()) { panels[i]?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" }); return; }
    target = Math.max(0, Math.min(panels.length - 1, i)) * vw; kick();
  }
  const settle = () => { settleT = 0; target = index() * vw; kick(); };

  // ---- the wheel: down (or right) moves on, up (or left) moves back; from the first panel, back leaves
  const px = (d: number, mode: number) => (mode === 1 ? d * 16 : mode === 2 ? d * innerHeight : d);
  layer.addEventListener("wheel", (e) => {
    if (!open || busy || isList()) return;
    const d = Math.max(-200, Math.min(200, px(e.deltaY, e.deltaMode) + px(e.deltaX, e.deltaMode)));
    if (d === 0) return;
    if (d < 0 && target <= 0.5) { requestClose(); return; }
    target = Math.max(0, Math.min(max(), target + d)); kick();
    window.clearTimeout(settleT); settleT = window.setTimeout(settle, 150);
  }, { passive: true });

  // ---- the keyboard: arrows, Home and End move between panels; Escape leaves; Tab brings its panel into view
  const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.matches("input:not([type=file]), textarea, select") || t.isContentEditable);
  document.addEventListener("keydown", (e) => {
    if (!open || busy) return;
    if (e.key === "Escape") { e.preventDefault(); requestClose(); return; }
    if (e.key === "Tab") { trap(e); return; }
    if (isList() || typing(e.target) || e.altKey || e.metaKey || e.ctrlKey) return;
    const i = index();
    const to = e.key === "ArrowRight" || e.key === "PageDown" ? i + 1 : e.key === "ArrowLeft" || e.key === "PageUp" ? i - 1
      : e.key === "Home" ? 0 : e.key === "End" ? panels.length - 1 : null;
    if (to === null) return;
    e.preventDefault(); go(to);
  });
  // focus stays inside: from the last stop Tab goes to the first, from the first Shift+Tab to the last (everything else
  // is inert, so the browser's own order inside is the reading order: Close, then each panel and what is in it)
  function trap(e: KeyboardEvent) {
    const stops = [...layer.querySelectorAll<HTMLElement>("button, input, a[href], [tabindex='0']")]
      .filter((el) => !el.closest("[hidden]") && !(el as HTMLButtonElement).disabled);
    if (!stops.length) { e.preventDefault(); return; }
    const first = stops[0], lastStop = stops[stops.length - 1], at = document.activeElement;
    if (e.shiftKey && (at === first || at === layer || !layer.contains(at))) { e.preventDefault(); lastStop.focus(); }
    else if (!e.shiftKey && (at === lastStop || !layer.contains(at))) { e.preventDefault(); first.focus(); }
  }
  layer.addEventListener("focusin", (e) => {
    if (isList()) return;
    const p = (e.target as Element).closest?.(".v-panel") as HTMLElement | null;
    const i = p ? panels.indexOf(p) : -1;
    if (i >= 0 && i !== index()) go(i);
  });

  // ---- open and close
  const others = () => [...document.body.children].filter((c) => c !== layer && !c.classList.contains("loader")) as HTMLElement[];
  const anim = (el: HTMLElement, frames: Keyframe[], delay: number, duration: number) =>
    el.animate(frames, { delay, duration, easing: EASE, fill: "both" });
  const done = (as: Animation[]) => Promise.all(as.map((a) => a.finished.catch(() => {})));
  let pageAnims: Animation[] = [], layerAnims: Animation[] = [];
  const clearAnims = (as: Animation[]) => { for (const a of as) a.cancel(); return [] as Animation[]; };

  async function show(how: "click" | "direct" | "pop") {
    if (open) return;
    open = true; busy = true;
    opener = document.querySelector<HTMLElement>("[data-open-viewer]");
    titleBefore = document.title;
    if (how === "click") history.pushState({ viewer: 1 }, "", PATH);
    document.title = TITLE;
    layer.hidden = false;
    layer.classList.toggle("list", isList());
    html.classList.add("viewer-open");
    for (const c of others()) c.inert = true;
    target = x = 0; layer.scrollTop = 0; refresh();
    const instant = how === "direct" || reduceMotion;
    pageAnims = clearAnims(pageAnims); layerAnims = clearAnims(layerAnims);
    if (!instant) {
      pageAnims = [anim(main, [{ opacity: 1, transform: "translate3d(0, 0, 0)" }, { opacity: 0, transform: "translate3d(0, -6vh, 0)" }], 0, 600)];
      layerAnims = [anim(ground, [{ opacity: 0 }, { opacity: 1 }], 100, 600),
        // the separate translate property, not transform: the strip's own transform is its position
        ...chrome.map((c) => anim(c, [{ opacity: 0, translate: "0 3vh" }, { opacity: 1, translate: "0 0" }], 400, 600))];
      await done([...pageAnims, ...layerAnims]);
      layerAnims = clearAnims(layerAnims);   // their end is the layer's own state
    } else pageAnims = [anim(main, [{ opacity: 0 }, { opacity: 0 }], 0, 1)];
    setCovered(true);   // the page beneath is hidden: its scenes pause
    layer.focus({ preventScroll: true });
    busy = false;
  }

  async function hide(how: "ui" | "pop", instant = false) {
    if (!open) return;
    busy = true;
    window.clearTimeout(settleT); cancelAnimationFrame(raf); raf = 0; last = 0;
    if (how === "ui" && history.state?.viewer !== 1) history.replaceState({ section: "sancho" }, "", "/sancho.html");
    setCovered(false);   // the scenes beneath draw again before they show
    document.title = titleBefore && titleBefore !== TITLE ? titleBefore : "Quixote · Sancho";
    if (!(instant || reduceMotion)) {
      layerAnims = clearAnims(layerAnims); const back = pageAnims; pageAnims = [];
      const out = [...chrome.map((c) => anim(c, [{ opacity: 1, translate: "0 0" }, { opacity: 0, translate: "0 2vh" }], 0, 400)),
        anim(ground, [{ opacity: 1 }, { opacity: 0 }], 200, 500),
        anim(main, [{ opacity: 0, transform: "translate3d(0, -6vh, 0)" }, { opacity: 1, transform: "translate3d(0, 0, 0)" }], 300, 500)];
      clearAnims(back);
      await done(out);
      clearAnims(out);
    } else { clearAnims(layerAnims); clearAnims(pageAnims); layerAnims = pageAnims = []; }
    layer.hidden = true;
    html.classList.remove("viewer-open");
    for (const c of others()) c.inert = false;
    open = false; busy = false;
    opener?.focus({ preventScroll: true });
  }
  /** Close, Escape or scrolling back from the first panel: back through history if the viewer added the entry */
  function requestClose() {
    if (!open || busy) return;
    if (history.state?.viewer === 1) history.back();   // popstate closes it
    else void hide("ui");
  }

  layer.querySelector("#v-close")!.addEventListener("click", requestClose);
  for (const a of document.querySelectorAll<HTMLAnchorElement>("[data-open-viewer]")) a.addEventListener("click", (e) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;   // a new tab loads /viewer.html itself
    e.preventDefault(); void show("click");
  });
  onPopFirst(() => {
    const at = location.pathname === PATH;
    if (at && !open) { void show("pop"); return true; }
    if (!at && open) {
      if (location.pathname === "/sancho.html") { void hide("pop"); return true; }
      void hide("pop", true); return false;   // Back to another section: the page goes there
    }
    return at;
  });
  // a direct link: open over the Sancho section, at the control, before the loading screen goes
  onBeforeReveal(() => {
    if (location.pathname !== PATH) return;
    document.querySelector("[data-open-viewer]")?.scrollIntoView({ block: "center" });
    void show("direct");
  });
  addEventListener("resize", () => {
    if (!open) return;
    layer.classList.toggle("list", isList());
    measure(); write(); mark(true); o.onResize?.();
  }, { passive: true });
  listMQ.addEventListener("change", () => { if (open) { layer.classList.toggle("list", isList()); target = x = 0; refresh(); } });

  return { refresh, go, isOpen: () => open };
}
