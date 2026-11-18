// dev only (not in the build): the demo's search trees alone on the demo's backdrop, for review
import "../styles/base.css";
import { buildSearchTree, crossings } from "../searchtree";
import type { SearchTree } from "../types";
import "./tree-preview.css";

const SUBMITTED: Record<string, string> = { nothing: "-mom60_z +rev5_rank", planted: "+rev5_z -vol20_z", restart: "-mom60_z +rev5_rank" };
const host = document.getElementById("trees")!, info = document.getElementById("info")!;
const q = new URLSearchParams(location.search), only = q.get("t"), grow = q.get("grow");
for (const key of only ? [only] : ["nothing", "planted", "restart"]) {
  const tree = (await (await fetch(`/src/dev/trees/${key}.json`)).json()) as SearchTree;
  const H = Number(q.get("h") ?? 620);
  const t = buildSearchTree(tree, { height: H, seed: 3, submitted: SUBMITTED[key] });
  const w = t.r - t.l, h = -t.top + 6;
  const fig = document.createElement("figure");
  const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `${t.l} ${t.top} ${w} ${h}`); svg.setAttribute("width", String(Math.round(w))); svg.setAttribute("height", String(Math.round(h)));
  const upto = grow === null ? Infinity : Number(grow);
  for (const p of t.pieces) {
    if (p.step > upto) continue;
    const e = document.createElementNS(NS, "path"); e.setAttribute("d", p.d); e.setAttribute("class", `${p.kind}${p.pink ? " pink" : ""}`); svg.append(e);
  }
  fig.append(svg); const cap = document.createElement("figcaption"); cap.textContent = key; fig.append(cap); host.append(fig);
  info.textContent += `${key}: ${t.pieces.length} pieces, ${tree.moves.length} moves, ${tree.evaluations} rules, forced ${t.forced}, crossings ${crossings(t)}, submitted move ${t.submitted}\n`;
}
