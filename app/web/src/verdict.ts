// The verdict card: the status in amber with its one-line meaning, the four numbers (counting up
// once when the verdict lands), and the way back to the CLI.
import { MEANING, countUp, h, lowerBound, word } from "./common";
import type { AuditResult } from "./types";

export function idleCard(box: HTMLElement, text: string) {
  box.className = "verdict idle";
  box.replaceChildren();
  h("p", "k", "Verdict", box);
  h("p", "word", "—", box);
  h("p", "meaning", text, box);
}

export function verdictCard(box: HTMLElement, r: AuditResult, extra?: (box: HTMLElement) => void) {
  const w = word(r.status);
  box.className = "verdict";
  box.replaceChildren();
  h("p", "k", "Verdict", box);
  h("p", "word", w, box);
  h("p", "meaning", MEANING[w] ?? "", box);
  const dl = h("dl", null, null, box);
  const L = lowerBound(r.reasons);
  const rows: [string, number | null, number, string, boolean][] = [
    ["In-sample Sharpe", r.submitted_sharpe, 3, r.submitted_feature_names.join(" "), false],
    ["The bar", r.class_bar, 3, `class tier, ${r.class_size.toLocaleString("en")} members`, false],
    ["p", r.p_replay, 4, `replay tier · α ${r.alpha} · B ${r.B}`, false],
    ["L 0.90", L, 3, "lower bound after the search", true],
  ];
  for (const [k, v, dec, note, sign] of rows) {
    const d = h("div", null, null, dl);
    h("dt", null, k, d);
    const dd = h("dd", null, null, d);
    const num = h("span", "num", v === null ? "n/a" : (0).toFixed(dec), dd);
    h("small", null, note, dd);
    if (v !== null) countUp(num, v, dec, sign);
  }
  extra?.(box);
}
