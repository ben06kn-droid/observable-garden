// The demo's page two as a scene for other pages (the run page, the viewer): the city, the background
// trees, the petals, the flower bed, the run's tree with its seed, the annotation. The page supplies
// the markup (run.html's #demo section) and gets back what it draws with.
import { reduceMotion } from "./common";
import { makeBed } from "./bed";
import { makeCity } from "./city";
import { Fx } from "./fx";
import { drawGarden, H as GH, SEED as SEED_AT, W as GW, type GardenHandle } from "./garden";
import { colourOf, kindOf } from "./heads";
import { makeNotes } from "./notes";
import { Field, startLife } from "./particles";
import { branchSources, shakeable, woodTwo } from "./woods";
import type { AuditResult, SearchTree } from "./types";

export function makeScene(throttled: () => boolean = () => false) {
  const $ = (id: string) => document.getElementById(id) as HTMLElement;
  const two = $("demo"), svg = $("garden") as unknown as SVGSVGElement, spot = $("spot"), seed = $("seed");
  const fx = new Fx($("fx") as HTMLCanvasElement, two);
  const bed = makeBed($("bed") as unknown as SVGSVGElement, two);
  const notes = makeNotes(spot, two, () => bed.heads());
  const city = makeCity($("city") as unknown as SVGSVGElement, reduceMotion, fx);
  city.draw();
  city.start(() => document.hidden);
  const petals = new Field({ box: two, air: $("air-two") as HTMLCanvasElement, pile: $("pile-two") as HTMLCanvasElement, kind: "petal", count: 70, start: 30,
    ground: (x) => { const W = two.clientWidth, u = (x - W / 2) / (W / 2); return two.clientHeight * (0.93 - 0.11 * u * u); },
    cap: () => (innerWidth < 760 ? 0 : 12), avoid: () => notes.boxes() });
  startLife({ fields: [petals], paused: () => false, throttled, reduce: reduceMotion });
  const bgTwo = $("wood2") as unknown as SVGSVGElement;
  fetch("/examples/overview-tree.json").then((r) => r.json()).then((tree: SearchTree) => {
    woodTwo(bgTwo, tree);
    shakeable(bgTwo, "Tree", (s) => petals.burst(branchSources(bgTwo, two, s), 16));
    petals.setSources(branchSources(bgTwo, two));
  }).catch(() => {});
  function idleBox() { svg.setAttribute("viewBox", `0 0 ${GW} ${GH}`); svg.setAttribute("preserveAspectRatio", "xMidYMax meet"); svg.classList.add("garden"); }
  function placeSeed() {
    const m = svg.getScreenCTM(), sr = spot.getBoundingClientRect();
    if (!m) return;
    const p = svg.createSVGPoint(); p.x = SEED_AT[0]; p.y = SEED_AT[1];
    const q = p.matrixTransform(m);
    seed.style.transform = `translate3d(${(q.x - sr.left).toFixed(1)}px, ${(q.y - sr.top).toFixed(1)}px, 0)`;
  }
  idleBox(); placeSeed(); bed.reset("idle");
  const resized: (() => void)[] = [];
  window.addEventListener("resize", () => { city.draw(); placeSeed(); notes.place(); for (const f of resized) f(); });

  let garden: GardenHandle | null = null;
  function draw(t: SearchTree, r: AuditResult | null, runId: string) {
    garden = drawGarden(svg, t, { interactive: false, halo: true, neon: true, canopy: false, twigs: true, bar: r?.class_bar,
      blossom: { kind: kindOf(runId), colour: colourOf(runId) },
      submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
    return garden;
  }
  return { two, svg, spot, seed, bed, notes, petals, idleBox, placeSeed, draw,
           /** the tree drawn last, if any */
           current: () => garden,
           /** called after the scene's own work on every resize */
           onResize: (f: () => void) => { resized.push(f); } };
}
