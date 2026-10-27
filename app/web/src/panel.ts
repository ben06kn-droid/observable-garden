// The process panel: what one tree tried, move by move, and every rule each move scored. Opens
// beside the garden without a reload; Esc or the close button shuts it and returns focus.
import { h } from "./common";
import type { SearchTree } from "./types";

export interface PanelHandle { open(stem: number, move: number | null): void; close(): void; onClose(cb: () => void): void; onLight(cb: (move: number | null) => void): void }

export function makePanel(root: HTMLElement, tree: () => SearchTree | null): PanelHandle {
  root.className = "panel";
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "false");
  root.setAttribute("aria-labelledby", "panel-title");
  root.replaceChildren();
  const head = h("header", null, null, root);
  const title = h("h2", null, null, head); title.id = "panel-title"; title.tabIndex = -1;
  const close = h("button", "close", "Close", head) as HTMLButtonElement; close.type = "button";
  const list = h("ol", null, null, root);
  let closeCb: (() => void) | null = null, lightCb: ((m: number | null) => void) | null = null, returnTo: Element | null = null;

  const shut = () => {
    root.classList.remove("open");
    lightCb?.(null);
    closeCb?.();
    (returnTo as HTMLElement | null)?.focus?.();
  };
  close.addEventListener("click", shut);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && root.classList.contains("open")) shut(); });

  function open(stem: number, move: number | null) {
    const t = tree();
    if (!t) return;
    returnTo = document.activeElement;
    const moves = t.moves.map((m, i) => ({ m, i })).filter(({ m }) => m.stem === stem);
    const evals = moves.reduce((n, { m }) => n + m.candidates.length, 0);
    title.replaceChildren(`Tree ${stem + 1}`);
    h("span", "vh", ": ", title);
    h("small", null, `${moves.length} moves · ${evals} evaluations`, title);
    list.replaceChildren();
    for (const { m, i } of moves) {
      const li = h("li", null, null, list);
      const b = h("button", "mv", null, li) as HTMLButtonElement;
      b.type = "button";
      const ch = m.candidates[m.chosen];
      h("b", null, m.kind, b);
      h("span", null, `${m.candidates.length} scored · ${m.kept ? "kept" : "not kept"} ${ch.rule} ${ch.sharpe.toFixed(3)}`, b);
      const body = h("div", null, null, li); body.hidden = true;
      h("p", "logline", m.text, body);
      const tbl = h("table", null, null, body);
      m.candidates.map((c, ci) => ({ c, ci })).sort((a, z) => z.c.sharpe - a.c.sharpe).forEach(({ c, ci }) => {
        const tr = h("tr", ci === m.chosen ? "chosen" : null, null, tbl);
        h("td", null, c.rule, tr); h("td", "s", c.sharpe.toFixed(4), tr);
      });
      b.setAttribute("aria-expanded", "false");
      b.addEventListener("click", () => { const o = body.hidden; body.hidden = !o; b.setAttribute("aria-expanded", String(o)); lightCb?.(o ? i : null); });
      b.addEventListener("mouseenter", () => lightCb?.(i));
      b.addEventListener("focus", () => lightCb?.(i));
      if (move === i) { body.hidden = false; b.setAttribute("aria-expanded", "true"); }
    }
    root.classList.add("open");
    lightCb?.(move);
    title.focus();
  }
  return { open, close: shut, onClose: (cb) => { closeCb = cb; }, onLight: (cb) => { lightCb = cb; } };
}
