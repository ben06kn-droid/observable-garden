// Inside a run: clicking the run enlarges its tree and pulls the visitor into it, the way lukres.dev
// goes from a project card to its page: a shared-element zoom from where the tree stood to the full
// view, mapped tree onto tree (the drawn tree's own box on page two onto its box inside, about one
// origin), so it grows in place,
// 1.0 s on Luka's curve cubic-bezier(.35, 0, 0, 1), transform and opacity only. Everything is drawn
// first while the layer is invisible, and the zoom starts two frames later, so no frame of the
// transition does layout or paint. The URL changes without a reload, so Back also zooms out.
//
// Inside, everything is blue (the run's tree with its blossoms open, the background trees, the panel
// chrome) except the falling petals, which stay pink. Over it sits the run's process as raw data from
// process.ts. Esc, the close control, a click outside the process, or Back zooms out to page two as it
// was. Reduced motion cuts instead of zooming.
import { h, reduceMotion, word } from "./common";
import { drawGarden } from "./garden";
import { woodTwo } from "./woods";
import { colourOf, kindOf } from "./heads";
import { fall } from "./leaves";
import { processOfRun } from "./process";
import type { AuditResult, SearchTree } from "./types";

const NS = "http://www.w3.org/2000/svg";
export const ZOOM_MS = 1000;
export const ZOOM_EASE = "cubic-bezier(.35, 0, 0, 1)";

export interface RunView { id: string; title: string; tree: SearchTree; result: AuditResult | null; refused?: string }
export interface RunInside { open(run: RunView, backdrop: SearchTree | null, from: DOMRect | null): void; close(): void; onClose(cb: () => void): void; isOpen(): boolean }

export function makeRunInside(root: HTMLElement): RunInside {
  root.replaceChildren();
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-labelledby", "run-title");
  const veil = h("div", "veil", null, root);
  const woods = document.createElementNS(NS, "svg"); woods.setAttribute("class", "inside-wood"); woods.setAttribute("aria-hidden", "true");
  veil.appendChild(woods);
  const petals = h("div", "falling petals", null, veil);
  const stage = h("div", "inside-stage", null, root);
  const big = document.createElementNS(NS, "svg"); big.setAttribute("class", "inside-tree"); big.setAttribute("aria-hidden", "true");
  stage.appendChild(big);
  const card = h("section", "process", null, root);
  const head = h("header", null, null, card);
  const title = h("h2", null, null, head); title.id = "run-title"; title.tabIndex = -1;
  const close = h("button", "close", "Back to the garden", head) as HTMLButtonElement; close.type = "button";
  const body = h("div", "process-body", null, card);
  let closeCb: (() => void) | null = null, returnTo: Element | null = null, fromRect: DOMRect | null = null, toRect: DOMRect | null = null, pushed = false, anims: Animation[] = [];

  // the stage's transform (origin at its top left) that puts the tree drawn inside (toRect) exactly
  // over the tree on page two (fromRect): same centre, same height
  const flip = (r: DOMRect | null) => {
    const t = toRect;
    if (!r || !r.width || !t || !t.height) return "translate3d(0, 0, 0) scale(1)";
    const s = Math.max(0.05, r.height / t.height);
    const tx = r.left + r.width / 2 - s * (t.left + t.width / 2), ty = r.top + r.height / 2 - s * (t.top + t.height / 2);
    return `translate3d(${tx.toFixed(1)}px, ${ty.toFixed(1)}px, 0) scale(${s.toFixed(4)})`;
  };
  const play = (forward: boolean) => {
    anims.forEach((a) => a.cancel());
    const o = { duration: ZOOM_MS, easing: ZOOM_EASE, fill: "both" as FillMode };
    const k = forward ? [0, 1] : [1, 0];
    anims = [
      stage.animate([{ transform: forward ? flip(fromRect) : "translate3d(0, 0, 0) scale(1)" }, { transform: forward ? "translate3d(0, 0, 0) scale(1)" : flip(fromRect) }], o),
      veil.animate([{ opacity: k[0] }, { opacity: k[1] }], o),
      card.animate([{ opacity: k[0], transform: `translate3d(${forward ? 40 : 0}px, 0, 0)` }, { opacity: k[1], transform: `translate3d(${forward ? 0 : 40}px, 0, 0)` }], { ...o, delay: forward ? ZOOM_MS * 0.25 : 0, duration: ZOOM_MS * 0.75 }),
    ];
    return anims[0].finished;
  };

  function open(run: RunView, backdrop: SearchTree | null, from: DOMRect | null) {
    returnTo = document.activeElement; fromRect = from;
    // draw everything first, while the layer is invisible
    root.classList.add("preparing");
    root.hidden = false;
    if (backdrop) woodTwo(woods, backdrop);
    const r = run.result;
    const g = drawGarden(big, run.tree, { quiet: true, halo: true, neon: true, canopy: false, blossom: { kind: kindOf(run.id), colour: colourOf(run.id) },
      submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
    g.bloom(run.refused ? 0 : 1);
    toRect = g.treeRect();
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
    const box = petals;
    const sources = backdrop ? Array.from(woods.querySelectorAll(".real .bud")).slice(0, 300).map((b) => {
      const rr = b.getBoundingClientRect(); return { x: (rr.left + rr.width / 2) / innerWidth, y: (rr.top + rr.height / 2) / innerHeight };
    }).filter((p) => p.x > 0 && p.x < 1 && p.y > 0 && p.y < 0.98) : undefined;
    fall(box, { n: 90, kind: "petal", seed: 5, sources });
    document.body.classList.add("inside-open");
    if (!pushed) { history.pushState({ run: run.id }, "", `#run-${run.id}`); pushed = true; }
    const go = () => {
      root.classList.remove("preparing");
      root.classList.add("open");
      title.focus({ preventScroll: true });
      if (!reduceMotion) void play(true);
    };
    if (reduceMotion) go(); else requestAnimationFrame(() => requestAnimationFrame(go));   // let it paint, then move
  }

  function shut(fromHistory = false) {
    if (root.hidden) return;
    if (pushed && !fromHistory) { pushed = false; history.back(); return; }   // popstate comes back here
    pushed = false;
    const done = () => { anims.forEach((a) => a.cancel()); anims = []; root.classList.remove("open"); root.hidden = true; document.body.classList.remove("inside-open"); closeCb?.(); (returnTo as HTMLElement | null)?.focus?.({ preventScroll: true }); };
    if (reduceMotion) done(); else void play(false).then(done, done);
  }
  window.addEventListener("popstate", () => { if (!root.hidden) shut(true); });
  close.addEventListener("click", () => shut());
  root.addEventListener("click", (e) => { if (!(e.target as Element).closest(".process")) shut(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !root.hidden) shut(); });
  root.hidden = true;
  return { open, close: () => shut(), onClose: (cb) => { closeCb = cb; }, isOpen: () => !root.hidden };
}
