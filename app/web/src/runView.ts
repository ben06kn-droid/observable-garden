// Entering a run, after its verdict, is one motion: on the click, page two's scene starts to zoom about
// the run's tree (1.0 s on cubic-bezier(.35, 0, 0, 1), transform only) and an invisible front spreads
// out from the tree on the same curve, reaching the screen's corners exactly as the zoom completes.
// Each element changes to the run view's colours as the front passes it, with a soft 320 ms falloff,
// so the change reads as a wave and never as an edge: the run's tree and the background trees blue,
// the ground, the gradient, the bar and the text blue, the power lines pink. The flowers keep their
// colours; as the front crosses a petal it glows with blue lightning for a moment (fx.ts). runView
// times each [data-tide] element by inverting the curve at its distance from the tree. The run's
// process (its moves and every rule scored) comes in over the garden. Closing is the same motion
// reversed: zoom out while the colour drains from the corners back to the tree. Reduced motion: a
// cross-fade into the same end state, no travel.
//
// Esc, the close control, a click outside the process, or Back closes it; the URL changes without a
// reload (#run-<id>), so Back works.
import { h, word } from "./common";
import type { Fx } from "./fx";
import { processOfRun } from "./process";
import type { AuditResult, SearchTree } from "./types";

export const ZOOM_MS = 1000;
export const ZOOM_EASE = "cubic-bezier(.35, 0, 0, 1)";
const K = 1.3;
// the curve's progress y at time x is a cubic bezier with control points (.35, 0) and (0, 1); its
// inverse (the time at which progress reaches y), by bisection on the curve's parameter
const bez = (a: number, b: number, t: number) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
function timeAt(y: number): number {
  let lo = 0, hi = 1;
  for (let i = 0; i < 40; i++) { const m = (lo + hi) / 2; if (bez(0, 1, m) < y) lo = m; else hi = m; }
  return bez(0.35, 0, (lo + hi) / 2);
}
type Pt = [number, number];

export interface RunView { id: string; title: string; tree: SearchTree; result: AuditResult | null; refused?: string }
export interface RunViewOptions { two: HTMLElement; scene: HTMLElement; panel: HTMLElement; fx: Fx; tree: () => DOMRect | null; sparks: () => Pt[]; reduce: boolean }

export function makeRunView(o: RunViewOptions) {
  const root = o.panel;
  root.replaceChildren();
  root.setAttribute("role", "dialog"); root.setAttribute("aria-modal", "true"); root.setAttribute("aria-labelledby", "run-title");
  const head = h("header", null, null, root);
  const title = h("h2", null, null, head); title.id = "run-title"; title.tabIndex = -1;
  const closeBtn = h("button", "close", "Back to the garden", head) as HTMLButtonElement; closeBtn.type = "button";
  const body = h("div", "process-body", null, root);
  root.hidden = true;

  let open = false, busy = false, pushed = false, centre: Pt = [0, 0], returnTo: Element | null = null;
  const zoomT = () => `translate3d(${(centre[0] * (1 - K)).toFixed(1)}px, ${(centre[1] * (1 - K)).toFixed(1)}px, 0) scale(${K})`;

  /** the front out (dir 1) or back in (dir -1), on the zoom's own curve and duration */
  function tide(dir: 1 | -1): number {
    const b = o.two.getBoundingClientRect();
    const corners: Pt[] = [[0, 0], [b.width, 0], [0, b.height], [b.width, b.height]];
    const max = Math.max(...corners.map(([x, y]) => Math.hypot(x - centre[0], y - centre[1])));
    // every read first, then every write, so the layout is computed once
    const sparks = o.sparks(), els = Array.from(o.two.querySelectorAll<HTMLElement | SVGElement>("[data-tide]"));
    const ds = els.map((el) => { const r = el.getBoundingClientRect(); return Math.hypot(r.left + r.width / 2 - b.left - centre[0], r.top + r.height / 2 - b.top - centre[1]); });
    const when = (d: number) => ZOOM_MS * timeAt(Math.min(1, dir > 0 ? d / max : 1 - d / max));
    els.forEach((el, i) => el.style.setProperty("--d", `${when(ds[i]).toFixed(0)}ms`));
    o.two.style.setProperty("--T", `${ZOOM_MS}ms`);
    o.two.classList.add("tiding");
    o.two.classList.toggle("in-run", dir > 0);
    o.fx.sparks(sparks.map((p) => ({ p, t: when(Math.hypot(p[0] - centre[0], p[1] - centre[1])) / 1000 })));
    return ZOOM_MS / 1000;
  }

  function zoom(forward: boolean): Promise<void> {
    o.scene.style.willChange = "transform";
    o.two.classList.toggle("zoomed", forward);   // the page's own text steps back while the process is open
    const a = o.scene.animate([{ transform: forward ? "none" : zoomT() }, { transform: forward ? zoomT() : "none" }], { duration: ZOOM_MS, easing: ZOOM_EASE, fill: "forwards" });
    const p = forward
      ? root.animate([{ opacity: 0, transform: "translate3d(40px, 0, 0)" }, { opacity: 1, transform: "none" }], { duration: ZOOM_MS * 0.75, delay: ZOOM_MS * 0.25, easing: ZOOM_EASE, fill: "both" })
      : root.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 300, fill: "forwards" });
    return Promise.all([a.finished, p.finished]).then(() => {
      o.scene.style.transform = forward ? zoomT() : "";
      a.cancel(); p.cancel();
      o.scene.style.willChange = "";      // re-rastered sharp at its new scale
      if (!forward) root.hidden = true;
    });
  }

  function fill(run: RunView) {
    const r = run.result;
    title.replaceChildren(run.title);
    h("span", "vh", ": ", title);
    h("small", null, `${run.refused ? "refused" : r ? word(r.status) : "running"}${r?.p_replay != null ? ` · p ${r.p_replay.toFixed(4)}` : ""}${r ? ` · B ${r.B.toLocaleString("en")}` : ""} · ${run.tree.moves.length} moves · ${run.tree.evaluations} evaluations`, title);
    body.replaceChildren();
    for (const stem of processOfRun(run.tree)) {
      if (run.tree.stems > 1) h("h3", null, `Tree ${stem.stem + 1} · ${stem.moves.length} moves · ${stem.evaluations} evaluations`, body);
      const list = h("ol", null, null, body);
      for (const m of stem.moves) {
        const li = h("li", null, null, list);
        const top = h("p", "mv", null, li);
        h("b", null, m.kind, top);
        top.append(` · ${m.candidates.length} scored · ${m.kept ? "kept" : "not kept"} `);
        h("span", "rule", `${m.chosen.rule} ${m.chosen.sharpe.toFixed(4)}`, top);
        h("p", "logline", m.text, li);
        const tbl = h("table", null, null, li);
        for (const c of m.candidates) { const tr = h("tr", c.chosen ? "chosen" : null, null, tbl); h("td", null, c.rule, tr); h("td", "s", c.sharpe.toFixed(4), tr); }
      }
    }
  }

  const outside = (e: Event) => { if (!busy && !root.contains(e.target as Node)) shut(); };

  function show(run: RunView) {
    if (open) return;
    const t = o.tree(), b = o.two.getBoundingClientRect();
    if (!t) return;
    open = true; busy = true; returnTo = document.activeElement;
    centre = [t.left + t.width / 2 - b.left, t.top + t.height / 2 - b.top];
    fill(run);
    document.body.classList.add("inside-open");
    if (!pushed) { history.pushState({ run: run.id }, "", `#run-${run.id}`); pushed = true; }
    const done = () => { busy = false; title.focus({ preventScroll: true }); window.setTimeout(() => document.addEventListener("click", outside), 0); };
    if (o.reduce) {
      o.scene.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: "forwards" }).finished.then((a) => {
        o.two.classList.add("in-run", "zoomed"); o.scene.style.transform = zoomT(); root.hidden = false;
        a.cancel(); o.scene.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160 }); done();
      });
      return;
    }
    const T = tide(1);                                         // the front and the zoom together
    root.hidden = false;
    void zoom(true).then(done);
    window.setTimeout(() => o.two.classList.remove("tiding"), T * 1000 + 400);
  }

  function shut(fromHistory = false) {
    if (!open || busy) return;
    if (pushed && !fromHistory) { pushed = false; history.back(); return; }   // popstate comes back here
    pushed = false; busy = true;
    document.removeEventListener("click", outside);
    const end = () => { open = false; busy = false; document.body.classList.remove("inside-open"); (returnTo as HTMLElement | null)?.focus?.({ preventScroll: true }); };
    if (o.reduce) {
      o.scene.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: "forwards" }).finished.then((a) => {
        o.two.classList.remove("in-run", "zoomed"); o.scene.style.transform = ""; root.hidden = true;
        a.cancel(); o.scene.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160 }); end();
      });
      return;
    }
    tide(-1);                                                  // zoom out while the colour drains, one motion
    void zoom(false).then(() => window.setTimeout(() => { o.two.classList.remove("tiding"); end(); }, 400));
  }

  window.addEventListener("popstate", () => { if (open) shut(true); });
  closeBtn.addEventListener("click", () => shut());
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && open) shut(); });
  return { open: show, close: () => shut(), isOpen: () => open };
}
