// The gate, from the page's side: a small typed API over the worker that owns Pyodide.
//   const gate = await loadGate();
//   const out = await gate.audit(inputs, { onSearch, onProgress });
// The page thread never runs Python.
//
// The full run: gate.inspect(panel, class) checks the visitor's files with the package's loaders
// before a key is used; gate.run(...) runs their model through the harness and audits the log;
// gate.cancel() ends a run by terminating the worker (a worker blocked in a synchronous request
// cannot be messaged), so a cancelled run leaves nothing behind; the next call starts a new worker.
import type { AuditInputs, AuditResult, FromWorker, InputsInfo, Progress, ReplicatePath, RunEvent, RunOptions, RunUsage, SearchTree, ToWorker } from "./types";

export type { AuditInputs, AuditResult, Progress, ReplicatePath, SearchTree } from "./types";

export type AuditOutcome =
  | { kind: "result"; result: AuditResult; replicatePaths: ReplicatePath[] | null; ms: number }
  | { kind: "refused"; message: string };

export type RunOutcome =
  | { kind: "done"; log: unknown; usage: RunUsage; result: AuditResult | null; refused?: string; tree: SearchTree | null; ms: number }
  | { kind: "stopped"; message: string; usage: RunUsage | null };

export interface RunInputs { panel: ArrayBuffer; cls: string; key: string; url: string; opts: RunOptions; B: number; seed: number }

export interface Gate {
  loadedMs: number;
  standins: Record<string, boolean>;
  wheel: string;
  audit(inputs: AuditInputs, on?: { onSearch?: (t: SearchTree) => void; onProgress?: (p: Progress) => void }): Promise<AuditOutcome>;
  inspect(panel: ArrayBuffer, cls: string): Promise<InputsInfo>;
  prompt(): Promise<{ system: string; schemas: Record<string, unknown> }>;
  run(inputs: RunInputs, on?: { onEvent?: (e: RunEvent) => void; onProgress?: (p: Progress) => void }): Promise<RunOutcome>;
}

let current: Worker | null = null, failAll: ((e: Error) => void) | null = null;

/** End whatever the worker is doing: a run in progress produces nothing. The next loadGate() starts afresh. */
export function cancelGate() {
  current?.terminate(); current = null; pending = null;
  failAll?.(new Error("cancelled")); failAll = null;
}

let pending: Promise<Gate> | null = null;

export function loadGate(): Promise<Gate> {
  pending ??= new Promise<Gate>((resolve, reject) => {
    const worker = new Worker(new URL("./gate.worker.ts", import.meta.url), { type: "module", name: "gate" });
    current = worker;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const jobs = new Map<number, { resolve: (o: any) => void; reject: (e: Error) => void;
      onSearch?: (t: SearchTree) => void; onProgress?: (p: Progress) => void; onEvent?: (e: RunEvent) => void }>();
    failAll = (e) => { for (const j of jobs.values()) j.reject(e); jobs.clear(); };
    let next = 1;
    const ask = <T,>(msg: ToWorker, extra: object = {}) => new Promise<T>((res, rej) => { jobs.set((msg as { id: number }).id, { resolve: res, reject: rej, ...extra }); worker.postMessage(msg); });
    worker.onmessage = (ev: MessageEvent<FromWorker>) => {
      const m = ev.data;
      if (m.type === "loaded") {
        resolve({
          loadedMs: m.ms, standins: m.standins, wheel: m.wheel,
          audit(inputs, on = {}) {
            const id = next++;
            return new Promise<AuditOutcome>((res, rej) => {
              jobs.set(id, { resolve: res, reject: rej, ...on });
              const msg: ToWorker = { type: "audit", id, ...inputs };
              worker.postMessage(msg);
            });
          },
          inspect: (panel, cls) => ask<InputsInfo>({ type: "inspect", id: next++, panel, cls }),
          prompt: () => ask({ type: "prompt", id: next++ }),
          run: (inputs, on = {}) => ask<RunOutcome>({ type: "run", id: next++, ...inputs }, on),
        });
        return;
      }
      if (m.type === "error" && m.id === undefined) { reject(new Error(m.message)); return; }
      const job = jobs.get(m.id!);
      if (!job) return;
      if (m.type === "inspected") { jobs.delete(m.id); job.resolve(m.info); return; }
      if (m.type === "prompt") { jobs.delete(m.id); job.resolve({ system: m.system, schemas: m.schemas }); return; }
      if (m.type === "run-event") { job.onEvent?.(m.event); return; }
      if (m.type === "run-done") { jobs.delete(m.id); job.resolve({ kind: "done", log: m.log, usage: m.usage, result: m.result, refused: m.refused, tree: m.tree, ms: m.ms }); return; }
      if (m.type === "run-stopped") { jobs.delete(m.id); job.resolve({ kind: "stopped", message: m.message, usage: m.usage }); return; }
      if (m.type === "search") job.onSearch?.(m.tree);
      else if (m.type === "progress") job.onProgress?.({ stage: m.stage, done: m.done, total: m.total });
      else if (m.type === "result") { jobs.delete(m.id); job.resolve({ kind: "result", result: m.result, replicatePaths: m.replicatePaths, ms: m.ms }); }
      else if (m.type === "refused") { jobs.delete(m.id); job.resolve({ kind: "refused", message: m.message }); }
      else if (m.type === "error") { jobs.delete(m.id!); job.reject(new Error(m.message)); }
    };
    worker.onerror = (e) => reject(new Error(e.message || "the gate's worker failed to start"));
    const msg: ToWorker = { type: "load" };
    worker.postMessage(msg);
  });
  return pending;
}
