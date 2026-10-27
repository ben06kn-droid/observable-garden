/// <reference lib="webworker" />
// The gate's worker: the only place Python runs. It loads Pyodide and the pinned packages from
// the site itself, installs the observable-garden wheel, and answers `audit` messages with the
// package's own audit. Messages are typed in types.ts.
import glue from "./py/glue.py?raw";
import type { FromWorker, ToWorker } from "./types";

declare const self: DedicatedWorkerGlobalScope;
const post = (m: FromWorker) => self.postMessage(m);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let py: any = null;
let loading: Promise<void> | null = null;

async function load(): Promise<void> {
  const t0 = performance.now();
  const base = new URL("/pyodide/", self.location.origin).href;
  const { loadPyodide } = await import(/* @vite-ignore */ base + "pyodide.mjs");
  py = await loadPyodide({ indexURL: base, fullStdLib: false });
  await py.loadPackage(["numpy", "pandas"], { messageCallback: () => {}, errorCallback: () => {} });
  const man = await (await fetch("/py/MANIFEST.json")).json();
  py.unpackArchive(await (await fetch("/py/" + man.wheel)).arrayBuffer(), "wheel");
  py.FS.mkdirTree("/work");
  py.runPython(glue);
  const standins = py.globals.get("STANDINS").toJs({ dict_converter: Object.fromEntries });
  post({ type: "loaded", ms: Math.round(performance.now() - t0), standins, wheel: man.wheel });
}

self.onmessage = async (ev: MessageEvent<ToWorker>) => {
  const m = ev.data;
  try {
    loading ??= load();
    await loading;
    if (m.type === "load") return;
    const dir = `/work/${m.id}`;
    py.FS.mkdirTree(dir);
    const enc = new TextEncoder();
    py.FS.writeFile(`${dir}/log.json`, enc.encode(m.log));
    py.FS.writeFile(`${dir}/panel.npz`, new Uint8Array(m.panel));
    py.FS.writeFile(`${dir}/class.json`, enc.encode(m.cls));
    const t0 = performance.now();
    try {
      const tree = JSON.parse(py.globals.get("search_tree")(`${dir}/log.json`, `${dir}/panel.npz`, `${dir}/class.json`));
      post({ type: "search", id: m.id, tree });
    } catch (e) {
      const msg = String((e as Error).message ?? e);
      if (msg.includes("AuditRefused")) return post({ type: "refused", id: m.id, message: msg.split("AuditRefused:").pop()!.trim() });
      throw e;
    }
    const out = JSON.parse(py.globals.get("run_audit")(`${dir}/log.json`, `${dir}/panel.npz`, `${dir}/class.json`,
      m.B, m.seed, m.replicatePaths ?? 0,
      (stage: "class" | "replay", done: number, total: number) => post({ type: "progress", id: m.id, stage, done, total })));
    if (out.refused) post({ type: "refused", id: m.id, message: out.refused });
    else post({ type: "result", id: m.id, result: out.result, replicatePaths: out.replicate_paths, ms: Math.round(performance.now() - t0) });
  } catch (e) {
    post({ type: "error", id: m.type === "audit" ? m.id : undefined, message: String((e as Error).message ?? e) });
  }
};
