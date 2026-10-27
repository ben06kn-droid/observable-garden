// The gate, from the page's side: a small typed API over the worker that owns Pyodide.
//   const gate = await loadGate();
//   const out = await gate.audit(inputs, { onSearch, onProgress });
// The page thread never runs Python.
import type { AuditInputs, AuditResult, FromWorker, Progress, ReplicatePath, SearchTree, ToWorker } from "./types";

export type { AuditInputs, AuditResult, Progress, ReplicatePath, SearchTree } from "./types";

export type AuditOutcome =
  | { kind: "result"; result: AuditResult; replicatePaths: ReplicatePath[] | null; ms: number }
  | { kind: "refused"; message: string };

export interface Gate {
  loadedMs: number;
  standins: Record<string, boolean>;
  wheel: string;
  audit(inputs: AuditInputs, on?: { onSearch?: (t: SearchTree) => void; onProgress?: (p: Progress) => void }): Promise<AuditOutcome>;
}

let pending: Promise<Gate> | null = null;

export function loadGate(): Promise<Gate> {
  pending ??= new Promise<Gate>((resolve, reject) => {
    const worker = new Worker(new URL("./gate.worker.ts", import.meta.url), { type: "module", name: "gate" });
    const jobs = new Map<number, { resolve: (o: AuditOutcome) => void; reject: (e: Error) => void;
      onSearch?: (t: SearchTree) => void; onProgress?: (p: Progress) => void }>();
    let next = 1;
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
        });
        return;
      }
      if (m.type === "error" && m.id === undefined) { reject(new Error(m.message)); return; }
      const job = jobs.get(m.id!);
      if (!job) return;
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
