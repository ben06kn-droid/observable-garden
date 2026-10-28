/// <reference lib="webworker" />
// The gate's worker: the only place Python runs. It loads Pyodide and the pinned packages from
// the site itself, installs the observable-garden wheel, and answers `audit` messages with the
// package's own audit. Messages are typed in types.ts.
//
// The full run (`run`): the harness runs here with the visitor's model as the agent. Each model call
// is a synchronous XMLHttpRequest made from this worker straight to the provider. A synchronous
// request is allowed in a worker, needs no shared memory, and lets the package's own run_session
// (synchronous Python) drive the agent unchanged. The alternative, an Atomics.wait bridge to an async
// fetch, needs SharedArrayBuffer and so cross-origin isolation (COOP and COEP headers the site does
// not set, and COEP would constrain every resource it loads). The key arrives with the run message,
// lives in one variable for the run's length, goes only into the request header, and is dropped when
// the run ends; no error message ever contains it.
import glue from "./py/glue.py?raw";
import type { FromWorker, RunEvent, ToWorker } from "./types";

declare const self: DedicatedWorkerGlobalScope;
const post = (m: FromWorker) => self.postMessage(m);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let py: any = null;
let loading: Promise<void> | null = null;

async function load(): Promise<void> {
  const t0 = performance.now();
  const base = new URL(`/pyodide/${__PYODIDE_VERSION__}/`, self.location.origin).href;
  const { loadPyodide } = await import(/* @vite-ignore */ base + "pyodide.mjs");
  py = await loadPyodide({ indexURL: base, fullStdLib: false });
  await py.loadPackage(["numpy", "pandas"], { messageCallback: () => {}, errorCallback: () => {} });
  const man = await (await fetch("/py/MANIFEST.json")).json();
  py.unpackArchive(await (await fetch("/py/" + man.wheel)).arrayBuffer(), "wheel");
  py.FS.mkdirTree("/work");
  py.FS.writeFile("/work/llm_agent.py", new Uint8Array(await (await fetch("/examples/llm_agent.py")).arrayBuffer()));   // the CLI adapter's prompt
  py.runPython(glue);
  const standins = py.globals.get("STANDINS").toJs({ dict_converter: Object.fromEntries });
  post({ type: "loaded", ms: Math.round(performance.now() - t0), standins, wheel: man.wheel });
}

const API_VERSION = "2026-10-21";

/** The provider's error, said plainly, with the provider's own message word for word (a 400 over the
 *  API version or the beta header must be readable as the provider put it); the key is never part
 *  of it. */
function providerError(status: number, text: string, key: string): string {
  let msg = "", type = "";
  try { const e = JSON.parse(text)?.error; msg = String(e?.message ?? ""); type = String(e?.type ?? ""); } catch { msg = text.trim(); }
  if (key) msg = msg.split(key).join("[key]");
  msg = msg.slice(0, 4000);                                    // a guard on size, never on what the provider said
  if (status === 401) return `The provider did not accept the API key (401)${msg ? `: ${msg}` : "."}`;
  if (status === 403) return `The API key is not allowed to do this (403)${msg ? `: ${msg}` : ""}.`;
  if (status === 429) return `Rate limited by the provider (429)${msg ? `: ${msg}` : ""}. Wait and try again.`;
  if (status === 400 && /credit/i.test(msg)) return `Insufficient credit: ${msg}`;
  if (status === 529 || status === 503) return `The provider is overloaded (${status}). Try again shortly.`;
  if (status >= 500) return `The provider failed (${status}). Try again shortly.`;
  return `The provider refused the request (${status}${type ? `, ${type}` : ""})${msg ? `: ${msg}` : "."}`;
}

/** One model call, synchronously, from the worker: the reply's JSON, or {"__error": message}. */
function callModel(url: string, key: string, body: string): string {
  const x = new XMLHttpRequest();
  x.open("POST", url, false);
  x.setRequestHeader("content-type", "application/json");
  x.setRequestHeader("x-api-key", key);
  x.setRequestHeader("anthropic-version", API_VERSION);
  x.setRequestHeader("anthropic-dangerous-direct-browser-access", "true");
  if (JSON.parse(body).fallbacks) x.setRequestHeader("anthropic-beta", "server-side-fallback-2026-07-01");
  try { x.send(body); } catch { return JSON.stringify({ __error: "Could not reach the provider (the network, or the request was blocked)." }); }
  if (x.status === 200) return x.responseText;
  return JSON.stringify({ __error: providerError(x.status, x.responseText, key) });
}

async function runAgent(m: Extract<ToWorker, { type: "run" }>) {
  let key = m.key;
  m.key = "";                                                  // not kept in the message either
  const dir = `/work/run-${m.id}`, enc = new TextEncoder();
  py.FS.mkdirTree(dir);
  py.FS.writeFile(`${dir}/panel.npz`, new Uint8Array(m.panel));
  py.FS.writeFile(`${dir}/class.json`, enc.encode(m.cls));
  const t0 = performance.now();
  let stopped: string | null = null;
  const call = (body: string) => {
    const out = callModel(m.url, key, body);
    if (out.startsWith('{"__error"')) stopped = JSON.parse(out).__error;
    return out;
  };
  const event = (json: string) => post({ type: "run-event", id: m.id, event: JSON.parse(json) as RunEvent });
  try {
    py.globals.set("_call_model", (body: string) => {
      const out = call(body);
      if (stopped) throw new Error("stopped");                 // ends the run inside Python
      return out;
    });
    let out: { log?: unknown; usage?: never; stopped?: string };
    try {
      out = JSON.parse(py.globals.get("run_agent")("/work/llm_agent.py", `${dir}/panel.npz`, `${dir}/class.json`, `${dir}/log.json`,
        JSON.stringify(m.opts), py.globals.get("_call_model"), event));
    } catch (e) {
      if (stopped) return post({ type: "run-stopped", id: m.id, message: stopped, usage: null });
      throw e;
    }
    if (out.stopped) return post({ type: "run-stopped", id: m.id, message: out.stopped, usage: out.usage ?? null });
    key = "";                                                  // the model is done: the key is dropped before the audit
    // the gate prices the log the run wrote: the same calls as the demo's audit
    const logPath = `${dir}/log.json`;
    let tree = null;
    try { tree = JSON.parse(py.globals.get("search_tree")(logPath, `${dir}/panel.npz`, `${dir}/class.json`)); } catch { /* drawn as it grew */ }
    const audit = JSON.parse(py.globals.get("run_audit")(logPath, `${dir}/panel.npz`, `${dir}/class.json`, m.B, m.seed, 0,
      (stage: "class" | "replay", done: number, total: number) => post({ type: "progress", id: m.id, stage, done, total })));
    post({ type: "run-done", id: m.id, log: out.log, usage: out.usage as never, result: audit.result ?? null, refused: audit.refused, tree,
           ms: Math.round(performance.now() - t0) });
  } finally {
    key = "";
    py.globals.delete?.("_call_model");
  }
}

self.onmessage = async (ev: MessageEvent<ToWorker>) => {
  const m = ev.data;
  try {
    loading ??= load();
    await loading;
    if (m.type === "load") return;
    if (m.type === "prompt") {
      const p = JSON.parse(py.globals.get("agent_prompt")("/work/llm_agent.py"));
      return post({ type: "prompt", id: m.id, system: p.system, schemas: p.schemas });
    }
    if (m.type === "inspect") {
      const dir = `/work/in-${m.id}`;
      py.FS.mkdirTree(dir);
      py.FS.writeFile(`${dir}/panel.npz`, new Uint8Array(m.panel));
      py.FS.writeFile(`${dir}/class.json`, new TextEncoder().encode(m.cls));
      return post({ type: "inspected", id: m.id, info: JSON.parse(py.globals.get("inspect_inputs")(`${dir}/panel.npz`, `${dir}/class.json`)) });
    }
    if (m.type === "run") return await runAgent(m);
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
    const msg = String((e as Error).message ?? e);
    post({ type: "error", id: m.type === "load" ? undefined : m.id, message: m.type === "run" && m.key ? msg.split(m.key).join("[key]") : msg });
  }
};
