// The verdict written onto the drawing. No container, no background, no rounded corner, no icon; each
// label is one word and a number, as wide as it needs.
//   The bar carries its value at its right end, in its amber: "bar 1.921".
//   The tree's height carries the submitted Sharpe: a hairline tick from the top of the trunk (the
//   highest kept branch) to the right margin, labelled "submitted 0.572" in the tree's colour. The gap
//   between the tick and the bar is the verdict, visible before any word is read.
//   The word is the only large text: PASS or FAIL right of the bar at its height, amber, counting in;
//   REFUSED the same in dim white. One small line under the bar: "p 0.9630 · B 2,000 · 30 evaluations
//   · seed 0".
//   During the search the same places carry the live numbers: the tick at the best kept Sharpe so far
//   ("best 0.341"), the line with the move and the count; the bar comes when the gate computes it.
// A label that would sit on a branch or a flower is nudged; the drawing never moves.
import { countUp, h, word } from "./common";
import type { GardenHandle } from "./garden";
import type { AuditResult } from "./types";

type Box = { x: number; y: number; w: number; h: number };

export function makeNotes(spot: HTMLElement, section: HTMLElement, flowers: () => [number, number][]) {
  const tick = h("div", "tick", null, spot); tick.setAttribute("aria-hidden", "true");
  const sub = h("p", "note note-sub", null, spot), bar = h("p", "note note-bar", null, spot), big = h("p", "note-word", null, spot);
  const line = h("p", "note note-line", null, spot);
  line.setAttribute("aria-live", "polite"); big.id = "verdict-word";
  for (const e of [tick, sub, bar, big, line]) { e.dataset.tide = ""; e.hidden = true; }
  let g: GardenHandle | null = null, mode: "off" | "search" | "verdict" | "refused" = "off", step = 0, barValue: number | null = null, subValue: number | null = null;
  let boxes: Box[] = [];

  const sp = () => spot.getBoundingClientRect();
  const at = (x: number, y: number) => { const p = g!.toScreen(x, y), r = sp(); return [p.x - r.left, p.y - r.top]; };
  const put = (e: HTMLElement, x: number, y: number) => { e.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`; };

  // what a label must not sit on: the run's branches and twigs, the flowers' heads, and the other labels
  function obstacles(): Box[] {
    const r = sp(), out: Box[] = [];
    for (const e of spot.querySelectorAll("#garden .real .twig, #garden .real .trunk, #garden .real .bud")) {
      const b = e.getBoundingClientRect(); out.push({ x: b.left - r.left, y: b.top - r.top, w: b.width, h: b.height });
    }
    const s = section.getBoundingClientRect();
    for (const [fx, fy] of flowers()) out.push({ x: fx + s.left - r.left - 8, y: fy + s.top - r.top - 8, w: 16, h: 16 });
    return out;
  }
  const hits = (a: Box, list: Box[]) => list.some((b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y);
  /** right-aligned at `xr`, its baseline about `y`; moved up or down in small steps until clear */
  function label(e: HTMLElement, xr: number, y: number, avoid: Box[], placed: Box[]) {
    const w = e.offsetWidth, hh = e.offsetHeight;
    for (const dy of [0, -6, 6, -12, 12, -18, 18, -24, 24, -32, 32]) {
      const b = { x: xr - w, y: y - hh + dy, w, h: hh };
      if (!hits(b, avoid) && !hits(b, placed) || dy === 32) { put(e, b.x, b.y); placed.push(b); return; }
    }
  }

  function place() {
    if (!g || mode === "off") return;
    const avoid = obstacles(), placed: Box[] = [], x1 = g.ends[1];
    const best = mode === "search" ? g.best(step) : g.best();
    const ys = subValue !== null ? g.ySharpe(subValue) : best?.y ?? null;
    if (ys !== null && best) {
      const [ax, ay] = at(best.x, ys), [bx] = at(x1, ys);
      tick.style.width = `${Math.max(0, bx - ax).toFixed(1)}px`; put(tick, ax, ay); tick.hidden = false;
      sub.hidden = false; label(sub, bx, ay - 4, avoid, placed);
    }
    if (barValue !== null) {
      const [bx, by] = at(x1, g.ySharpe(barValue));
      bar.hidden = false; label(bar, bx, by - 4, avoid, placed);
      line.hidden = false; label(line, bx, by + 6 + line.offsetHeight, avoid, placed);
      if (!big.hidden) { const b = { x: bx + 22, y: by - big.offsetHeight / 2, w: big.offsetWidth, h: big.offsetHeight }; put(big, b.x, b.y); placed.push(b); }
    } else if (ys !== null && best) {
      const [bx, ay] = at(x1, ys);
      line.hidden = false; label(line, bx, ay + 10 + line.offsetHeight, avoid, placed);
      if (!big.hidden) { put(big, bx + 22, ay - big.offsetHeight / 2); placed.push({ x: bx + 22, y: ay - big.offsetHeight / 2, w: big.offsetWidth, h: big.offsetHeight }); }
    }
    const s = section.getBoundingClientRect(), r = sp();
    boxes = placed.map((b) => ({ x: b.x + r.left - s.left, y: b.y + r.top - s.top, w: b.w, h: b.h }));
  }

  return {
    clear() { mode = "off"; g = null; barValue = subValue = null; for (const e of [tick, sub, bar, big, line]) e.hidden = true; big.className = "note-word"; boxes = []; },
    /** the replay's count on the line, the tick where the search left it */
    replay(text: string) { line.textContent = text; place(); },
    search(garden: GardenHandle, n: number, move: string, count: string) {
      g = garden; mode = "search"; step = n; barValue = subValue = null; bar.hidden = big.hidden = true;
      const best = garden.best(n);
      sub.textContent = best ? `best ${best.sharpe.toFixed(3)}` : "";
      sub.hidden = tick.hidden = !best;
      line.textContent = `${move} · ${count}`;
      place();
    },
    verdict(garden: GardenHandle, r: AuditResult, evaluations: number, seed: number) {
      g = garden; mode = "verdict"; barValue = r.class_bar; subValue = r.submitted_sharpe;
      sub.textContent = "submitted 0.000"; bar.textContent = "bar 0.000";
      line.textContent = `p ${r.p_replay === null ? "n/a" : r.p_replay.toFixed(4)} · B ${r.B.toLocaleString("en")} · ${evaluations} evaluations · seed ${seed}`;
      big.textContent = word(r.status); big.className = "note-word lit"; big.hidden = false;
      place();
      const sv = h("span", null, null), bv = h("span", null, null);
      sub.replaceChildren("submitted ", sv); bar.replaceChildren("bar ", bv);
      countUp(sv, r.submitted_sharpe, 3); countUp(bv, r.class_bar, 3);
    },
    refused(garden: GardenHandle | null, message: string, evaluations: number, what = "REFUSED") {
      g = garden; mode = "refused";
      big.textContent = what; big.className = "note-word dim"; big.hidden = false;
      line.textContent = `${what.toLowerCase()} · ${evaluations} evaluations`; line.title = message;
      place();
    },
    place,
    /** where the labels are, in the section's pixels, for the leaves and petals to keep clear of */
    boxes: () => boxes,
  };
}
