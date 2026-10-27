// The data layer of the "inside a tree" view: one tree's process as plain data, in search order.
// It holds the raw run data only (no summary, no interpretation), so a different presentation can
// replace inside.ts later without touching this.
import type { SearchTree } from "./types";

export interface ProcessCandidate { rule: string; sharpe: number; chosen: boolean }
export interface ProcessMove {
  index: number;            // the move's position in the whole search
  kind: string;             // init, extend_best, swap_worst, flip, refine, restart
  text: string;             // the harness's log line for the call
  kept: boolean;            // whether the chosen candidate was kept
  chosen: ProcessCandidate;
  candidates: ProcessCandidate[];   // every rule the move scored, highest Sharpe first
}
export interface ProcessModel { stem: number; evaluations: number; moves: ProcessMove[] }

export function processOf(tree: SearchTree, stem: number): ProcessModel {
  const moves: ProcessMove[] = [];
  tree.moves.forEach((m, index) => {
    if (m.stem !== stem) return;
    const candidates = m.candidates.map((c, i) => ({ rule: c.rule, sharpe: c.sharpe, chosen: i === m.chosen }))
      .sort((a, b) => b.sharpe - a.sharpe);
    moves.push({ index, kind: m.kind, text: m.text, kept: m.kept, chosen: candidates.find((c) => c.chosen)!, candidates });
  });
  return { stem, evaluations: moves.reduce((n, m) => n + m.candidates.length, 0), moves };
}

/** The tree with only one stem, renumbered as the first: for drawing that tree on its own. */
export function treeOnly(tree: SearchTree, stem: number): SearchTree {
  const moves = tree.moves.filter((m) => m.stem === stem).map((m) => ({ ...m, stem: 0 }));
  return { ...tree, moves, stems: 1, evaluations: moves.reduce((n, m) => n + m.candidates.length, 0) };
}
