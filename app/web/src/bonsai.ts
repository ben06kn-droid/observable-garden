// Sancho in the garden: a bonsai in its pot, where a run's tree would stand. One fixed model, one
// fixed shape: it does not grow with a search, because Sancho does not search. Drawn into the scene's
// garden SVG in its coordinates (W x H, the ground at the seed), in the neon style of the run's tree:
// a filled, tapering trunk; foliage pads as tube outlines with a faint fill; a pot in the dim tube.
import { SEED, W } from "./garden";

const NS = "http://www.w3.org/2000/svg";
const el = (name: string, attrs: Record<string, string | number>, parent: Element) => {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent.append(e); return e;
};

/** A tapering band around a centre line (points from the base up), half-width w0 at the base to w1. */
function limb(pts: [number, number][], w0: number, w1: number): string {
  const n = pts.length, left: string[] = [], right: string[] = [];
  for (let i = 0; i < n; i++) {
    const [x, y] = pts[i], [ax, ay] = pts[Math.max(0, i - 1)], [bx, by] = pts[Math.min(n - 1, i + 1)];
    const dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy) || 1, w = w0 + (w1 - w0) * (i / (n - 1));
    left.push(`${(x - (dy / len) * w).toFixed(1)},${(y + (dx / len) * w).toFixed(1)}`);
    right.unshift(`${(x + (dy / len) * w).toFixed(1)},${(y - (dx / len) * w).toFixed(1)}`);
  }
  return `M${left.join(" L")} L${right.join(" L")} Z`;
}

export function drawBonsai(svg: SVGSVGElement, label: string): SVGGElement {
  const cx = SEED[0], ground = SEED[1] - 30;   // the seed sits a little under the visible curve of the bed: the pot stands on it
  const g = el("g", { class: "bonsai", "aria-hidden": "true" }, svg) as SVGGElement;
  const at = (dx: number, dy: number): [number, number] => [cx + dx, ground + dy];
  // the pot: a lip and a shallow, tapered body standing on the ground
  el("rect", { class: "pot", x: cx - 82, y: ground - 42, width: 164, height: 9, rx: 1.5 }, g);
  el("path", { class: "pot", d: `M${cx - 74} ${ground - 33} L${cx + 74} ${ground - 33} L${cx + 60} ${ground} L${cx - 60} ${ground} Z` }, g);
  el("line", { class: "pot-foot", x1: cx - 48, y1: ground, x2: cx - 40, y2: ground + 5 }, g);
  el("line", { class: "pot-foot", x1: cx + 48, y1: ground, x2: cx + 40, y2: ground + 5 }, g);
  // the trunk, an S, and three branches; the pads at their ends and at the crown
  const trunk: [number, number][] = [at(0, -42), at(-14, -92), at(10, -140), at(22, -176), at(-4, -214), at(6, -246)];
  const branches: [number, number][][] = [
    [at(-12, -96), at(-42, -112), at(-78, -118)],
    [at(14, -146), at(46, -156), at(82, -170)],
    [at(0, -206), at(-30, -222), at(-56, -236)],
  ];
  for (const b of branches) el("path", { class: "bark", d: limb(b, 4.2, 1.4) }, g);
  el("path", { class: "bark", d: limb(trunk, 11, 3) }, g);
  const pads: [number, number, number, number][] = [[-84, -126, 44, 17], [88, -178, 48, 18], [-60, -244, 38, 15], [8, -262, 56, 21]];
  for (const [dx, dy, rx, ry] of pads) {
    const [x, y] = at(dx, dy);
    el("ellipse", { class: "pad", cx: x, cy: y, rx, ry }, g);
    for (let k = -2; k <= 2; k++) el("circle", { class: "dot", cx: x + k * rx * 0.36, cy: y - ry * 0.25 * (1 - Math.abs(k) / 3), r: 1.6 }, g);
  }
  const t = el("text", { class: "bonsai-label", x: Math.min(W - 10, cx + 150), y: ground - 150 }, g);
  t.textContent = label;
  return g;
}
