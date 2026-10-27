// What every page shares: the fonts and styles, the header's colour over paper or night, and the
// two sentences on result pages.
import "./styles.css";

export const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function headerOverPaper(paper: Element | null) {
  const top = document.querySelector(".top");
  if (!top || !paper) return;
  const io = new IntersectionObserver(([e]) => top.classList.toggle("on-paper", e.isIntersecting && e.intersectionRatio > 0.06),
                                      { threshold: [0, 0.06, 0.5, 1] });
  io.observe(paper);
}

export const WORD: Record<string, string> = { CERTIFIED: "PASS" };
export const MEANING: Record<string, string> = {
  PASS: "p is below α: the submitted rule beats what the search would find on noise.",
  FAIL: "p is at or above α, and the test had the power to tell: the result is what this search finds by luck.",
  INADMISSIBLE: "p is at or above α, and the search was too wide to certify anything: the test's power against the reference Sharpe (1.0 by default) is below the power floor (0.20).",
  UNDECIDABLE: "the record alone cannot license a correction, for example returns logged without the search that chose them.",
  DEGENERATE: "the test statistic broke on this menu. Do not read its p.",
  DEPENDS_ON_JUDGMENT: "the search changed a declared rule mid-run; the decision after the change cannot be priced.",
};
export const word = (status: string) => WORD[status] ?? status;

/** L_0.90, which the audit reports only inside its confidence reason line. */
export function lowerBound(reasons: string[]): number | null {
  const m = /L_0\.90 ([+-]?\d+\.\d+)/.exec(reasons.join(" "));
  return m ? Number(m[1]) : null;
}

export function countUp(node: HTMLElement, to: number, decimals: number, sign = false) {
  const fmt = (x: number) => (sign && x > 0 ? "+" : "") + x.toFixed(decimals);
  if (reduceMotion) { node.textContent = fmt(to); return; }
  let t0: number | null = null;
  const frame = (t: number) => {
    t0 ??= t;
    const k = Math.min(1, (t - t0) / 1400), e = 1 - Math.pow(1 - k, 3);
    node.textContent = fmt(to * e);
    if (k < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

export async function sha256Hex(data: ArrayBuffer | string): Promise<string> {
  const buf = typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data);
  const h = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function h<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string | null, text?: string | null, parent?: Element): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
