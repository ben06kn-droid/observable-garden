// The verdict as a sign in the garden: one hairline neon rule hung level with the Sharpe bar at the
// right of the bed, on a thin post down to the ground; the word above it in the display face, the four
// numbers below in monospace with one-word labels. No border, no background, no rounded corner: a soft
// dark vignette sits behind it only to keep the type legible over the scene. While a run computes the
// same sign is dimmer and shows the phase, the move and the counts; when the verdict lands the word
// and the rule light amber and the numbers count up. Its text is read from the gate's numbers only.
import { countUp, h, lowerBound, word } from "./common";
import type { AuditResult } from "./types";

export type Phase = "ready" | "loading" | "search" | "null" | "verdict" | "refused" | "error";

export interface Sign {
  state(phase: Phase, title: string, rows: [string, string][]): void;
  verdict(r: AuditResult): void;
  /** hang the rule at `y` (the section's pixels); the post runs down to `ground` */
  hang(y: number, ground: number): void;
  el: HTMLElement;
}

export function makeSign(box: HTMLElement, extra?: HTMLElement): Sign {
  box.replaceChildren();
  const wordEl = h("p", "sign-word", null, box); wordEl.id = "sign-word";
  const rule = h("div", "sign-rule", null, box); rule.setAttribute("aria-hidden", "true");
  const nums = h("dl", "sign-nums", null, box);
  if (extra) box.appendChild(extra);
  const post = h("div", "sign-post", null, box); post.setAttribute("aria-hidden", "true");
  let y = 0, groundY = 0;

  const rows = (list: [string, string][], count?: ([number, number, boolean] | null)[]) => {
    nums.replaceChildren();
    list.forEach(([k, v], i) => {
      const d = h("div", null, null, nums);
      h("dt", null, k, d);
      const dd = h("dd", null, v, d);
      const c = count?.[i];
      if (c) countUp(dd, c[0], c[1], c[2]);
    });
  };
  const place = () => {
    const top = y - rule.offsetTop;
    box.style.transform = `translate3d(0, ${top.toFixed(1)}px, 0)`;
    post.style.top = `${rule.offsetTop}px`;
    post.style.setProperty("--post", `${Math.max(0, groundY - y).toFixed(0)}px`);
  };
  return {
    el: box,
    state(phase, title, list) {
      box.dataset.phase = phase;
      wordEl.textContent = title;
      rows(list);
      place();
    },
    verdict(r) {
      box.dataset.phase = "verdict";
      wordEl.textContent = word(r.status);
      const L = lowerBound(r.reasons);
      const list: [string, string][] = [["Sharpe", "0.000"], ["Bar", "0.000"], ["p", r.p_replay === null ? "n/a" : "0.0000"], ["Bound", L === null ? "n/a" : "0.000"]];
      rows(list, [[r.submitted_sharpe, 3, false], [r.class_bar, 3, false], r.p_replay === null ? null : [r.p_replay, 4, false], L === null ? null : [L, 3, true]]);
      place();
    },
    hang(ny, ground) { y = ny; groundY = ground; place(); },
  };
}
