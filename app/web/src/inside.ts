// The view of the "inside a tree" layer: the selected tree, blue, grows from where it stood to fill
// the viewport and becomes the background, blue leaves falling over it; on top, the tree's process
// as raw run data (process.ts). Esc, the close control or a click on the background zooms back out.
// Reduced motion cuts instead of zooming.
import { h, reduceMotion } from "./common";
import { drawGarden } from "./garden";
import { leaves } from "./leaves";
import { processOf, treeOnly } from "./process";
import type { SearchTree } from "./types";

export interface InsideHandle { open(stem: number, move: number | null, from: DOMRect | null): void; close(): void; onClose(cb: () => void): void }

export function makeInside(root: HTMLElement, tree: () => SearchTree | null): InsideHandle {
  root.replaceChildren();
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-labelledby", "inside-title");
  const stage = h("div", "inside-stage", null, root);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "inside-tree");
  svg.setAttribute("aria-hidden", "true");
  stage.appendChild(svg);
  const fall = h("div", "leaves blue", null, root);
  const card = h("section", "process", null, root);
  const head = h("header", null, null, card);
  const title = h("h2", null, null, head); title.id = "inside-title"; title.tabIndex = -1;
  const close = h("button", "close", "Back to the garden", head) as HTMLButtonElement; close.type = "button";
  const list = h("ol", null, null, card);
  let closeCb: (() => void) | null = null, returnTo: Element | null = null, fromRect: DOMRect | null = null;

  function flipFrom(r: DOMRect | null) {
    if (!r || reduceMotion) return "none";
    const sx = r.width / innerWidth, sy = r.height / innerHeight;
    return `translate(${r.left}px, ${r.top}px) scale(${sx}, ${sy})`;
  }

  function open(stem: number, move: number | null, from: DOMRect | null) {
    const t = tree();
    if (!t) return;
    returnTo = document.activeElement; fromRect = from;
    drawGarden(svg, treeOnly(t, stem), { quiet: true, fill: true });
    const model = processOf(t, stem);
    title.replaceChildren(`Tree ${stem + 1}`);
    h("span", "vh", ": ", title);
    h("small", null, `${model.moves.length} moves · ${model.evaluations} evaluations`, title);
    list.replaceChildren();
    for (const m of model.moves) {
      const li = h("li", m.index === move ? "focus" : null, null, list);
      const top = h("p", "mv", null, li);
      h("b", null, m.kind, top);
      top.append(` · ${m.candidates.length} scored · ${m.kept ? "kept" : "not kept"} `);
      h("span", "rule", `${m.chosen.rule} ${m.chosen.sharpe.toFixed(4)}`, top);
      h("p", "logline", m.text, li);
      const tbl = h("table", null, null, li);
      for (const c of m.candidates) {
        const tr = h("tr", c.chosen ? "chosen" : null, null, tbl);
        h("td", null, c.rule, tr); h("td", "s", c.sharpe.toFixed(4), tr);
      }
    }
    leaves(fall, 16);
    root.hidden = false;
    stage.style.transform = flipFrom(from);
    root.classList.remove("open");
    void root.offsetWidth;                      // commit the starting frame, then grow to fill
    root.classList.add("open");
    stage.style.transform = "none";
    document.body.classList.add("inside-open");
    title.focus();
    if (move !== null) list.querySelector("li.focus")?.scrollIntoView({ block: "center" });
  }

  function shut() {
    if (root.hidden) return;
    root.classList.remove("open");
    stage.style.transform = flipFrom(fromRect);
    const done = () => { root.hidden = true; document.body.classList.remove("inside-open"); closeCb?.(); (returnTo as HTMLElement | null)?.focus?.(); };
    if (reduceMotion) done(); else window.setTimeout(done, 650);
  }
  close.addEventListener("click", shut);
  root.addEventListener("click", (e) => { if (!(e.target as Element).closest(".process")) shut(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !root.hidden) shut(); });
  root.hidden = true;
  return { open, close: shut, onClose: (cb) => { closeCb = cb; } };
}
