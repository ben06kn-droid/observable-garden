// The background trees: decoration, drawn from the restart example's logged search (its eight
// restarts are eight trees). Each is a tall or a short tree: a bare trunk and one crown at its own
// top. Page one shows all eight, tall and short alternating, reaching high into the page. Page two
// (and the inside of a run) shows four, pushed to the edges and smaller than the run's tree, so none
// can be mistaken for it and none crosses the animation spot.
import { drawGarden, type GardenHandle } from "./garden";
import type { SearchTree } from "./types";

const H = 600;

/** The search restricted to some of its stems, renumbered 0..n-1. */
export function subTree(tree: SearchTree, stems: number[]): SearchTree {
  const moves = tree.moves.filter((m) => stems.includes(m.stem)).map((m) => ({ ...m, stem: stems.indexOf(m.stem) }));
  return { ...tree, moves, stems: stems.length, evaluations: moves.reduce((n, m) => n + m.candidates.length, 0) };
}

const aspect = (svg: SVGSVGElement) => { const r = svg.getBoundingClientRect(); return r.width && r.height ? r.width / r.height : 1.6; };

export function woodOne(svg: SVGSVGElement, tree: SearchTree): GardenHandle {
  return drawGarden(svg, tree, { quiet: true, fill: true, halo: false, canopy: false, crown: { heights: [0.96, 0.5, 0.9, 0.46, 0.98, 0.52, 0.92, 0.48], fan: 115 } });
}

export function woodTwo(svg: SVGSVGElement, tree: SearchTree): GardenHandle {
  const width = H * aspect(svg);
  const t = subTree(tree, [1, 3, 5, 7]);
  return drawGarden(svg, t, { quiet: true, halo: true, neon: true, canopy: false, width,
    crown: { heights: [0.58, 0.3, 0.32, 0.56], xs: [0.07, 0.175, 0.825, 0.93], fan: width * 0.08 } });
}
