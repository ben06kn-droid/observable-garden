// The demo's examples, served from /examples/ (copies of the repository's files; see
// scripts/copy_examples.mjs and the manifest beside them).
import type { AuditInputs } from "./types";

export interface Demo { key: string; title: string; log: string; panel: string; cls: string; B: number; truth?: string; about: string }

export async function demos(): Promise<Demo[]> {
  return (await (await fetch("/examples/demos.json")).json()).demos;
}

export interface LoadedDemo { demo: Demo; inputs: Omit<AuditInputs, "B" | "seed">; logJson: any; truth: any | null }

export async function loadDemo(demo: Demo): Promise<LoadedDemo> {
  const [log, panel, cls, truth] = await Promise.all([
    fetch("/examples/" + demo.log).then((r) => r.text()),
    fetch("/examples/" + demo.panel).then((r) => r.arrayBuffer()),
    fetch("/examples/" + demo.cls).then((r) => r.text()),
    demo.truth ? fetch("/examples/" + demo.truth).then((r) => r.json()) : Promise.resolve(null),
  ]);
  return { demo, inputs: { log, panel, cls }, logJson: JSON.parse(log), truth };
}

export const command = (d: Demo, B: number, seed: number) =>
  `quixote audit examples/logs/${d.log} --panel examples/data/${d.panel} --class examples/${d.cls} --B ${B} --seed ${seed} --json`;
