// A run's tree in a section, for pages that draw one (the run page, the viewer). The page supplies the
// markup (a #demo section holding #spot and #garden) and gets back what it draws with.
//
// The decorative layers are optional. With `decor` (the demo's look): the city, the background trees,
// the petals, the flower bed, the seed, neon tubing with blossoms; the markup must then also hold
// #city, #wood2, #air-two, #pile-two, #bed, #fx and #seed. Without it (the default, every page but the
// demo): the tree alone, drawn flat in the page's own tokens (`--tree`, `--tree-path`, `--tree-bar`),
// with its bar and the verdict written on it. The gate's numbers are drawn the same either way.
import { reduceMotion } from "./common";
import { makeBed } from "./bed";
import { makeCity } from "./city";
import { Fx } from "./fx";
import { drawGarden, H as GH, SEED as SEED_AT, W as GW, type GardenHandle } from "./garden";
import { colourOf, kindOf } from "./heads";
import { makeNotes } from "./notes";
import { Field, startLife } from "./particles";
import { branchSources, woodTwo } from "./woods";
import type { AuditResult, SearchTree } from "./types";

export interface SceneOptions { decor?: boolean; throttled?: () => boolean }

/** what the page calls on the bed; without decor there is no bed and these do nothing */
interface BedLike { reset(key: string): void; start(): void; finish(): void; heads(): [number, number][] }

export function makeScene(o: SceneOptions = {}) {
  const decor = !!o.decor, throttled = o.throttled ?? (() => false);
  const $ = (id: string) => document.getElementById(id) as HTMLElement;
  const two = $("demo"), svg = $("garden") as unknown as SVGSVGElement, spot = $("spot");
  const seed = $("seed") ?? document.createElement("div");   // without decor: a detached stand-in, never shown
  let bed: BedLike = { reset() {}, start() {}, finish() {}, heads: () => [] };
  const resized: (() => void)[] = [];
  const notes = makeNotes(spot, two, () => bed.heads());

  if (decor) {
    const fx = new Fx($("fx") as HTMLCanvasElement, two);
    bed = makeBed($("bed") as unknown as SVGSVGElement, two);
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
      petals.setSources(branchSources(bgTwo, two));
    }).catch(() => {});
    resized.push(() => city.draw());
  }

  function idleBox() { svg.setAttribute("viewBox", `0 0 ${GW} ${GH}`); svg.setAttribute("preserveAspectRatio", "xMidYMax meet"); svg.classList.add("garden"); }
  function placeSeed() {
    if (!decor) return;
    const m = svg.getScreenCTM(), sr = spot.getBoundingClientRect();
    if (!m) return;
    const p = svg.createSVGPoint(); p.x = SEED_AT[0]; p.y = SEED_AT[1];
    const q = p.matrixTransform(m);
    seed.style.transform = `translate3d(${(q.x - sr.left).toFixed(1)}px, ${(q.y - sr.top).toFixed(1)}px, 0)`;
  }
  idleBox(); placeSeed(); bed.reset("idle");
  window.addEventListener("resize", () => { placeSeed(); notes.place(); for (const f of resized) f(); });

  let garden: GardenHandle | null = null;
  function draw(t: SearchTree, r: AuditResult | null, runId: string) {
    garden = drawGarden(svg, t, { interactive: false, halo: decor, neon: decor, canopy: false, twigs: true, bar: r?.class_bar,
      blossom: decor ? { kind: kindOf(runId), colour: colourOf(runId) } : undefined,
      submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
    return garden;
  }
  return { two, svg, spot, seed, bed, notes, idleBox, placeSeed, draw, decor,
           /** the tree drawn last, if any */
           current: () => garden,
           /** called after the scene's own work on every resize */
           onResize: (f: () => void) => { resized.push(f); } };
}
