// The home page's scroll, modelled on lukres.dev.
//
// Within a page: Luka's ScrollPane. The wheel and the keys move a target offset and every frame the
// page eases toward it with a frame-rate-independent exponential, 1 - e^(-12 dt) (wheelEaseCoeff
// = 12, so about 0.38 s to settle), never overshooting. No browser smooth-scroll is in play.
//
// Between the pages: Luka's page transition. A move that leaves page one carries the visitor onto
// page two as one scripted transition: a transform on <main> (Web Animations, so it runs on the
// compositor, transform only, no layout or paint while it plays), 1.0 s on Luka's own curve,
// cubic-bezier(.35, 0, 0, 1). At its end, in one task, the native scroll position moves to page two
// and the transform is dropped, so there is no jump. Page two is fully drawn all along under an
// opaque paper cover; the switch to its look is that cover's opacity going to 0 at the end of the
// carry (a compositor change), so no frame shows both pages half-drawn. Input the other way during a
// carry reverses it in place; more input the same way is absorbed. Going up from the top of page two
// is the same carry backwards, with the cover put back at its start, but it takes a deliberate
// gesture: at the top of page two, one gesture that scrolls up by at least 40% of the viewport, or a
// nudge up, a pause, and another. Anything less leaves the page where it is.
//
// The page keeps its native scroll position (scrollbar, find-in-page, anchors, assistive tech);
// touch and scrollbar movement is followed, and a stop between the pages finishes as a carry.
// Reduced motion: the same moves, made at once.
export const CARRY_MS = 1000;
export const CARRY_EASE = "cubic-bezier(.35, 0, 0, 1)";

export interface CutOptions { main: HTMLElement; two: HTMLElement; night: (on: boolean) => void; reduce: boolean; paused: () => boolean;
  onCarry?: (phase: "start" | "end", dir: 1 | -1) => void }

export function startScroll(o: CutOptions) {
  const K = 12, LEEWAY = 0.4, PAUSE = 250;
  let up = 0, lastUp = 0;   // the upward input at the top of page two in the current gesture, and when it came
  let target = window.scrollY, current = window.scrollY, last = performance.now(), running = false, lastSet = -1;
  let carry: { anim: Animation; dir: 1 | -1; started: 1 | -1 } | null = null;
  const put = (y: number) => { lastSet = Math.round(y); window.scrollTo(0, y); };
  const max = () => document.documentElement.scrollHeight - window.innerHeight;
  const twoTop = () => o.two.offsetTop;
  const oneEnd = () => Math.max(0, twoTop() - window.innerHeight);
  const clamp = (y: number) => Math.max(0, Math.min(max(), y));

  // at the top of page two: does this upward input go back to page one?
  function leave(delta: number) {
    const now = performance.now(), fresh = now - lastUp > PAUSE, nudged = up > 0;
    if (fresh) up = 0;
    lastUp = now; up += -delta;
    return (fresh && nudged) || up >= LEEWAY * window.innerHeight;
  }
  function land(dir: 1 | -1) {
    up = 0; lastUp = 0;
    const y = dir > 0 ? twoTop() : oneEnd();
    put(y); current = target = y;
    if (carry) { carry.anim.cancel(); carry = null; }
    o.night(dir > 0);
    o.onCarry?.("end", dir);
  }
  function startCarry(dir: 1 | -1) {
    if (carry) { if (carry.dir !== dir) { carry.dir = dir; carry.anim.reverse(); } return; }   // reverse in place, or absorb
    running = false;
    const from = window.scrollY, to = dir > 0 ? twoTop() : oneEnd();
    if (dir < 0) o.night(false);
    o.onCarry?.("start", dir);
    if (o.reduce) { land(dir); return; }
    // the native position stays put while the transform plays; it moves at the end, in one task
    const anim = o.main.animate([{ transform: "translate3d(0, 0, 0)" }, { transform: `translate3d(0, ${from - to}px, 0)` }],
                                { duration: CARRY_MS, easing: CARRY_EASE, fill: "both" });
    carry = { anim, dir, started: dir };
    anim.onfinish = () => {
      if (!carry) return;
      if (carry.dir === carry.started) land(carry.dir);                     // arrived
      else { anim.cancel(); carry = null; current = target = window.scrollY; o.night(window.scrollY >= twoTop() - 1.5); o.onCarry?.("end", dir === 1 ? -1 : 1); }  // reversed home
    };
  }

  function frame(now: number) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    const gap = target - current;
    if (Math.abs(gap) < 0.5) { current = target; running = false; }
    else current += gap * (1 - Math.exp(-K * dt));
    put(current);
    if (running) requestAnimationFrame(frame);
  }
  function go(delta: number) {
    if (carry) { startCarry(delta > 0 ? 1 : -1); return; }
    const top = twoTop(), end = oneEnd(), from = target, to = clamp(from + delta);
    if (delta > 0 && to > end + 1 && from < top - 1) {
      if (Math.abs(window.scrollY - end) > 1.5) { target = end; if (!running) { running = true; last = performance.now(); requestAnimationFrame(frame); } return; }  // finish page one first
      startCarry(1); return;
    }
    if (delta > 0) up = 0;
    if (delta < 0 && to < top - 1 && from >= top - 1) {
      if (Math.abs(window.scrollY - top) <= 2) { if (leave(delta)) startCarry(-1); return; }   // at the top: only a deliberate gesture leaves
      target = top; if (!running) { running = true; last = performance.now(); requestAnimationFrame(frame); } return;   // stop at the top first
    }
    target = to;
    if (o.reduce) { current = target; put(current); return; }
    if (!running) { running = true; last = performance.now(); requestAnimationFrame(frame); }
  }

  window.addEventListener("wheel", (e) => {
    if (o.paused() || e.ctrlKey) return;
    e.preventDefault();
    const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerHeight : 1;
    go(e.deltaY * unit);
  }, { passive: false });

  window.addEventListener("keydown", (e) => {
    if (o.paused() || e.altKey || e.metaKey || e.ctrlKey) return;
    const t = e.target as HTMLElement;
    if (t.closest("input, textarea, select, [contenteditable]") || (e.key === " " && t.closest("button, a, [role=button]"))) return;
    const page = window.innerHeight * 0.9;
    const d = { ArrowDown: 100, ArrowUp: -100, PageDown: page, PageUp: -page, " ": e.shiftKey ? -page : page }[e.key];
    if (d !== undefined) { e.preventDefault(); go(d); }
    else if (e.key === "Home") { e.preventDefault(); go(-target); }
    else if (e.key === "End") { e.preventDefault(); go(max() - target); }
  });

  let idle = 0;
  window.addEventListener("scroll", () => {
    if (carry || Math.abs(window.scrollY - lastSet) <= 1.5 || (running && Math.abs(window.scrollY - current) <= 1.5)) return;
    current = target = window.scrollY; running = false;
    if (current >= twoTop() - 1.5) o.night(true); else if (current <= oneEnd() + 1) o.night(false);   // between the pages, the page keeps its look
    const wasTwo = document.body.dataset.page === "two";
    window.clearTimeout(idle);
    idle = window.setTimeout(() => {
      const y = window.scrollY, end = oneEnd(), top = twoTop();
      if (y > end + 1 && y < top - 1) startCarry(wasTwo ? (top - y >= LEEWAY * window.innerHeight ? -1 : 1) : (y - end) > (top - y) ? 1 : -1);
    }, 140);
  }, { passive: true });

  o.night(window.scrollY >= twoTop() - 1.5);
  return { carrying: () => !!carry, toTwo: () => { if (window.scrollY < twoTop() - 1) { put(oneEnd()); current = target = oneEnd(); startCarry(1); } } };
}
