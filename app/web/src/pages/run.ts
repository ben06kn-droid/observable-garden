// The full run: the visitor's panel, class, key and budget; their model as the agent through the
// harness, in their browser; the gate's price on the log it writes.
//
// The key lives in one variable (`key`) from Start to the run's end: it is sent to the worker with
// the run message, never written to storage or a URL, never put into the log, the result or an error
// message, and cleared (the variable and the field) when the run ends in any way or the page is left.
// The panel and the class are read by the package's own loaders in the worker (np.load with
// allow_pickle=False) and checked before the key is used; their errors are shown word for word.
import { auditId, h, MEANING, reduceMotion, sha256Hex, word } from "../common";
import { cancelGate, loadGate, type RunOutcome } from "../gate";
import { makeScene } from "../scene";
import { FALLBACK_MODELS, localEndpoint, NOT_SENT, OPENROUTER_MODELS, PROVIDERS, routerModels, type RouterModel } from "../providers";
import type { AuditResult, InputsInfo, ProviderId, RunEvent, RunUsage, SearchTree } from "../types";

/** members x rows the browser takes (scripts/measure_class_cap.mjs: a 25-million-cell class table
 *  is 200 MB, about 0.4 GB at peak, and about 16 s to build; at 85 million it is 1.9 GB and 3.5 minutes) */
export const CLASS_CAP = 25_000_000;
const SEED = 0;
// thinking plus one tool call, by effort (rough: a model's own default where no level is sent)
const OUT_PER_TURN: Record<string, number> = { none: 150, minimal: 200, low: 250, medium: 600, high: 1500, xhigh: 3000, max: 6000, [NOT_SENT]: 600 };

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const form = $<HTMLFormElement>("run-form"), status = $("in-status"), capLine = $("in-cap"), errorBox = $("run-error");
const fPanel = $<HTMLInputElement>("f-panel"), fClass = $<HTMLInputElement>("f-class"), fKey = $<HTMLInputElement>("f-key");
const fModel = $<HTMLSelectElement>("f-model"), fEffort = $<HTMLSelectElement>("f-effort"), fMoves = $<HTMLInputElement>("f-moves");
const fProvider = $<HTMLSelectElement>("f-provider"), fModelId = $<HTMLInputElement>("f-model-id"), fLocal = $<HTMLInputElement>("f-local");
const fB = $<HTMLInputElement>("f-B"), fPrompt = $<HTMLTextAreaElement>("f-prompt"), startBtn = $<HTMLButtonElement>("start"), cancelBtn = $<HTMLButtonElement>("cancel");
const logList = $("run-log"), tokens = $("tokens");

let panel: ArrayBuffer | null = null, cls = "", panelName = "", className = "", info: InputsInfo | null = null;
let schemas: Record<string, unknown> = {}, defaultPrompt = "";
let key = "", running = false;

// ---- the scene: the demo's page two (src/scene.ts), the petals slowed while a run computes
const scene = makeScene(() => running);
const { two, svg, seed, bed, notes, idleBox, draw } = scene;
notes.entered();                                             // no "click a tree" here: the record is below
let shownSteps = 0;
/** the tree as the search so far, its new evaluations growing in one by one */
function grow(t: SearchTree, runId: string, move: string, moves: number) {
  const g = draw(t, null, runId);
  seed.classList.add("spent");
  if (reduceMotion) { g.setStep(g.total); shownSteps = g.total; }
  else {
    g.grow(); g.setStep(shownSteps);
    const from = shownSteps, to = g.total, t0 = performance.now();
    const tick = (now: number) => { const k = Math.min(to, from + Math.ceil(((now - t0) / 40))); g.setStep(k); if (k < to && scene.current() === g) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    shownSteps = to;
  }
  notes.search(g, g.total, move, `${moves} moves · ${t.evaluations} evaluations`);
}

// ---- inputs: the bundled pair to start, or the visitor's files; checked by the package's loaders
async function useBundled() {
  const [p, c] = await Promise.all([fetch("/examples/tiny_panel.npz").then((r) => r.arrayBuffer()), fetch("/examples/class.json").then((r) => r.text())]);
  panel = p; cls = c; panelName = "tiny_panel.npz"; className = "class.json";
  fPanel.value = ""; fClass.value = "";
  await check();
}
async function check() {
  info = null; refresh();
  if (!panel || !cls) return;
  status.textContent = `Reading ${panelName} and ${className}…`;
  try {
    const gate = await loadGate();
    info = await gate.inspect(panel.slice(0), cls);
  } catch (e) { info = { error: String((e as Error).message ?? e) }; }
  if (info.error) { status.textContent = info.error; status.classList.add("bad"); }
  else {
    status.classList.remove("bad");
    status.textContent = `${panelName}: ${info.rows!.toLocaleString("en")} rows, ${info.assets} assets, ${info.features} features. ${info.describe}`;
  }
  const cells = (info.size ?? 0) * (info.rows ?? 0);
  capLine.textContent = info.error ? "" : cells > CLASS_CAP
    ? `This class is too large for a browser: ${info.size!.toLocaleString("en")} members × ${info.rows!.toLocaleString("en")} rows is more than the ${(CLASS_CAP / 1e6).toFixed(0)} million cells this page takes (a class table of ${(CLASS_CAP * 8 / 1e6).toFixed(0)} MB). Run it locally: quixote run --agent examples.llm_agent:Agent --panel ${panelName} --class ${className} --out log.json`
    : `Class table: ${(cells * 8 / 1e6).toFixed(1)} MB (${info.size!.toLocaleString("en")} members × ${info.rows!.toLocaleString("en")} rows), within the ${(CLASS_CAP / 1e6).toFixed(0)} million cells a browser takes.`;
  refresh();
}
const readFile = (f: File) => new Promise<ArrayBuffer>((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result as ArrayBuffer); r.onerror = () => rej(r.error); r.readAsArrayBuffer(f); });
fPanel.addEventListener("change", async () => { const f = fPanel.files?.[0]; if (!f) return; if (f.size > 512e6) { status.textContent = "That panel is over 512 MB: run it locally with the CLI."; return; } panel = await readFile(f); panelName = f.name; await check(); });
fClass.addEventListener("change", async () => { const f = fClass.files?.[0]; if (!f) return; if (f.size > 4e6) { status.textContent = "That class file is over 4 MB, larger than any class file needs to be."; return; } cls = new TextDecoder().decode(await readFile(f)); className = f.name; await check(); });
$("f-bundled").addEventListener("click", () => void useBundled());

// ---- the provider: its models, its effort levels, where the key goes
const params = new URLSearchParams(location.search);
/** tests only: on 127.0.0.1 or localhost, ?provider=mock sends every call to the mock providers the
 *  test server mounts (scripts/mock_providers.mjs); a deploy never takes this branch */
const mock = (location.hostname === "127.0.0.1" || location.hostname === "localhost") && params.get("provider") === "mock";
const MOCK_URL: Record<ProviderId, string> = { anthropic: "/__mock/anthropic/v1/messages", openai: "/__mock/openai/v1/responses",
  openrouter: "/__mock/openrouter/api/v1/chat/completions", local: "" };
let routed: RouterModel[] = [], routedState: "none" | "loading" | "loaded" | "failed" = "none";
const provider = () => PROVIDERS[fProvider.value as ProviderId];
const modelId = () => fModelId.value.trim() || (provider().id === "local" ? "" : fModel.value);
function options(sel: HTMLSelectElement, items: [string, string][], keep?: string) {
  sel.replaceChildren(...items.map(([v, t]) => { const o = document.createElement("option"); o.value = v; o.textContent = t; return o; }));
  if (keep && items.some(([v]) => v === keep)) sel.value = keep;
}
function fillModels() {
  const p = provider();
  if (p.id === "openrouter") {
    options(fModel, routed.length ? routed.map((m) => [m.id, m.name]) : [["", routedState === "loading" ? "loading the list…" : routedState === "failed" ? "the list did not load: type an id" : "enter a key to load the list"]], fModel.value);
  } else options(fModel, p.models.map((m) => [m.id, m.name]), p.id === "anthropic" ? "claude-opus-5-5" : undefined);
}
function onProvider() {
  const p = provider();
  fillModels();
  options(fEffort, p.efforts.map((e) => [e, e]), p.defaultEffort);
  $("l-model").hidden = p.id === "local";
  $("l-local").hidden = $("local-note").hidden = p.id !== "local";
  $("l-model-id").textContent = p.id === "local" ? "Model id (as the server names it)" : "Or any model id";
  fModelId.placeholder = p.id === "local" ? "e.g. qwen3:32b" : "as the provider names it";
  fKey.placeholder = p.keyPlaceholder;
  $("provider-note").textContent = `Sent to the ${p.shape} as ${p.effortParam}${p.id === "local" ? " (only if a level is chosen)" : ""}. `
    + "Every level the provider documents is offered for every model; a model that refuses one answers with the provider's error, shown word for word."
    + (p.id === "openrouter" ? " The list is OpenRouter's models that take tools." : "");
  $("key-host").textContent = endpoint().host;
  void loadRouted();
  estimate();
}
/** where this run's requests go; the host is what the record and the verification sentence name */
function endpoint(): { url: string; host: string; error?: string } {
  const p = provider();
  if (p.id === "local") {
    const e = localEndpoint(fLocal.value);
    return "error" in e ? { url: "", host: "a server on localhost", error: e.error } : e;
  }
  return { url: mock ? MOCK_URL[p.id] : p.url, host: mock ? `${location.host} (the mock ${p.label} API)` : new URL(p.url).host };
}
/** OpenRouter's model list, once a key is present: a public endpoint, so the key is not sent with it */
async function loadRouted() {
  if (provider().id !== "openrouter" || !fKey.value.trim() || routedState === "loading" || routedState === "loaded") return;
  routedState = "loading"; fillModels();
  try {
    const r = await fetch(mock ? "/__mock/openrouter/api/v1/models" : OPENROUTER_MODELS, { credentials: "omit", referrerPolicy: "no-referrer" });
    if (!r.ok) throw new Error(String(r.status));
    routed = routerModels(await r.json());
    routedState = routed.length ? "loaded" : "failed";
  } catch { routedState = "failed"; }
  if (provider().id === "openrouter") { fillModels(); estimate(); }
}
fProvider.addEventListener("change", onProvider);
fKey.addEventListener("input", () => void loadRouted());
fLocal.addEventListener("input", () => { $("key-host").textContent = endpoint().host; });

/** list prices for the chosen model, per million tokens, if the provider publishes them */
function price(): [number, number] | null {
  const p = provider(), id = modelId();
  if (p.id === "openrouter") return routed.find((m) => m.id === id)?.price ?? null;
  return p.models.find((m) => m.id === id)?.price ?? null;
}

// ---- the estimate: tokens before the run, from the prompt, the tools and the budget
function estimate() {
  const n = Math.max(1, Math.min(60, Number(fMoves.value) || 20)) + 3;   // the budget plus declare, predict and submit
  const base = Math.ceil((fPrompt.value.length + JSON.stringify(schemas).length * 1.6) / 4) + 200;   // system, tool definitions
  const obs = 420, reply = 140, out = OUT_PER_TURN[fEffort.value] ?? 600;
  const input = n * (base + obs) + ((obs + reply) * n * (n - 1)) / 2;   // each turn resends the history so far
  const output = n * out;
  const pr = price(), id = modelId() || "the model";
  const tokensLine = `Estimate for up to ${n - 3} moves: about ${Math.round(input / 1000)}k input and ${Math.round(output / 1000)}k output tokens`;
  if (!pr) { $("estimate").textContent = `${tokensLine}; cost unknown (${provider().id === "local" ? "a local server has no list price" : `no list price known for ${id}`}).`; return; }
  const dollars = (input * pr[0] + output * pr[1]) / 1e6;
  $("estimate").textContent = `${tokensLine}, at most about $${dollars < 0.1 ? dollars.toFixed(3) : dollars.toFixed(2)} at ${provider().label}'s list prices for ${id} `
    + "(less where the provider's prompt cache applies). A model that stops early costs less.";
}
for (const el of [fMoves, fModel, fModelId, fEffort, fPrompt]) el.addEventListener("input", estimate);

function refresh() {
  const ok = !!info && !info.error && (info.size ?? 0) * (info.rows ?? 0) <= CLASS_CAP;
  startBtn.disabled = running || !ok;
  cancelBtn.hidden = !running;
  for (const el of form.querySelectorAll<HTMLInputElement>("input, select, textarea, button.link")) el.disabled = running;
}

// ---- the run
const logLine = (cls: string, parts: (string | Node)[]) => { const li = h("li", cls, null, logList); li.append(...parts); li.scrollIntoView?.({ block: "nearest" }); return li; };
const fmtUsage = (u: RunUsage) => `${u.requests} model calls · ${u.input_tokens.toLocaleString("en")} input tokens (${u.cache_read_input_tokens.toLocaleString("en")} from cache) · ${u.output_tokens.toLocaleString("en")} output tokens`;
function endKey() { key = ""; fKey.value = ""; }
window.addEventListener("pagehide", () => { endKey(); if (running) cancelGate(); });

form.addEventListener("submit", (e) => { e.preventDefault(); void start(); });
cancelBtn.addEventListener("click", () => {
  if (!running) return;
  cancelGate();                                              // the worker ends; nothing it held survives
  finish("Cancelled. A cancelled run produces no result.");
});

let runId = "";
async function start() {
  errorBox.textContent = "";
  if (running || !panel || !info || info.error) return;
  const p = provider(), model = modelId(), where = endpoint();
  if (where.error) { errorBox.textContent = where.error; fLocal.focus(); return; }
  if (!model) { errorBox.textContent = p.id === "local" ? "Enter the model id, as the server names it." : "Choose a model, or type its id."; fModelId.focus(); return; }
  key = fKey.value.trim();
  if (!key && p.keyRequired) { errorBox.textContent = "Enter your API key to start."; fKey.focus(); return; }
  running = true; refresh();
  $("record").hidden = true; logList.replaceChildren(); tokens.textContent = "Starting…";
  runId = `run-${Date.now().toString(36)}`; shownSteps = 0;
  svg.replaceChildren(); idleBox(); notes.clear(); notes.entered(); seed.classList.remove("spent");
  bed.reset(runId); bed.start();
  two.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  const moves = Math.max(1, Math.min(60, Math.round(Number(fMoves.value) || 20)));
  const B = Math.max(100, Math.min(10000, Math.round(Number(fB.value) || 2000)));
  const effort = fEffort.value === NOT_SENT ? undefined : fEffort.value;
  const maxOut = p.id === "openrouter" ? routed.find((m) => m.id === model)?.maxOut : undefined;
  const opts = { provider: p.id, model, effort, max_moves: moves, fallbacks: p.id === "anthropic" && FALLBACK_MODELS.has(model), seed: SEED,
                 system: fPrompt.value.trim() && fPrompt.value !== defaultPrompt ? fPrompt.value : undefined,
                 max_tokens: maxOut ? Math.min(16000, maxOut) : undefined };
  const run = { provider: p.id, label: p.label, effort: effort ?? NOT_SENT, host: where.host };
  let lastMove = "", nMoves = 0, served = model, out: RunOutcome;
  try {
    const gate = await loadGate();
    const runKey = key;
    out = await gate.run({ panel: panel.slice(0), cls, key: runKey, provider: p.id, url: where.url, opts, B, seed: SEED }, {
      onEvent: (ev: RunEvent) => {
        if (ev.type === "move") {
          if (ev.tool) { lastMove = ev.tool; nMoves++; }
          logLine("move", [h("b", null, ev.tool ?? "(no move)"), " ", Object.keys(ev.args).length ? JSON.stringify(ev.args) : "", ev.text ? h("span", "say", ` ${ev.text}`) : ""]);
        } else if (ev.type === "result") {
          logLine(ev.last.refused ? "refused" : "result", [ev.last.refused ? `refused: ${ev.last.refused}` : (ev.last.text ?? "")]);
        } else if (ev.type === "usage") {
          if (ev.model) served = ev.model;
          tokens.textContent = fmtUsage(ev.usage);
        } else if (ev.type === "tree") grow(ev.tree, runId, lastMove, nMoves);
      },
      onProgress: (p) => { if (p.stage === "replay") notes.replay(`replay · ${p.done.toLocaleString("en")} of ${p.total.toLocaleString("en")}`); },
    });
  } catch (e) {
    const msg = String((e as Error).message ?? e);
    if (msg === "cancelled") return;
    finish(`The run failed: ${msg.split(key || "\u0000").join("[key]")}`);
    return;
  }
  endKey();
  if (out.kind === "stopped") { finish(out.message, out.usage); return; }
  if (out.usage) tokens.textContent = fmtUsage(out.usage);
  running = false; refresh();
  if (!out.result) { finish(`The gate refused the log: ${out.refused ?? "no reason given"}`); return; }
  const r = out.result, t = out.tree;
  bed.finish();
  if (t) { draw(t, r, runId).setStep(Number.MAX_SAFE_INTEGER); notes.verdict(scene.current()!, r, t.evaluations, SEED); }
  // the prompt actually sent: the adapter's own, or the visitor's edit (a different search)
  const prompt = { edited: opts.system !== undefined, sha256: await sha256Hex(opts.system ?? defaultPrompt) };
  await showRecord(r, out.log as Record<string, unknown>, model, served, moves, prompt, run);
}

function finish(message: string, usage?: RunUsage | null) {
  endKey();
  running = false; refresh();
  if (usage) tokens.textContent = fmtUsage(usage);
  errorBox.textContent = message;
  logLine("refused", [message]);
  bed.finish();
}

// ---- the result: the record, the CLI command, the downloads, the share link
let lastLog = "", lastResult = "", lastShare = "";
async function showRecord(r: AuditResult, log: Record<string, unknown>, model: string, served: string, moves: number, prompt: { edited: boolean; sha256: string },
                          run: { provider: ProviderId; label: string; effort: string; host: string }) {
  const gate = await loadGate();
  lastLog = JSON.stringify(log, null, 1);
  const logSha = await sha256Hex(lastLog);
  const id = await auditId({ alpha: r.alpha, B: r.B, class_sha256: info!.class_sha256!, log_sha256: logSha, panel_sha256: info!.panel_sha256!, seed: SEED, wheel: gate.wheel });
  const record = { panel_file: panelName, panel_sha256: info!.panel_sha256!, class_file: className, class_sha256: info!.class_sha256!,
    log_sha256: logSha, provider: run.provider, endpoint_host: run.host, model, served_by: served, effort: run.effort, budget_moves: moves, prompt: prompt.edited ? "edited" : "default", prompt_sha256: prompt.sha256,
    B: r.B, seed: SEED, audit_id: id, package: gate.wheel };
  lastResult = JSON.stringify({ format: "quixote-browser-result/1", result: r, record }, null, 1);
  $("rec-meaning").textContent = `${word(r.status)}: ${MEANING[word(r.status)] ?? ""}`;
  const ul = $("rec-reasons"); ul.replaceChildren(); for (const x of r.reasons) h("li", null, x, ul);
  const kv = $("rec-kv"); kv.replaceChildren();
  const rows: [string, string][] = [["Panel", `${panelName} · ${record.panel_sha256}`], ["Class", `${className} · ${record.class_sha256}`],
    ["Provider", `${run.label} · ${run.host}`],
    ["Model", served && served !== model ? `${model} (served by ${served})` : model], ["Effort", run.effort], ["Budget", `${moves} moves`],
    ["Prompt", prompt.edited ? `edited, not the adapter's own: a different search · ${prompt.sha256}` : `default (examples/llm_agent.py's) · ${prompt.sha256}`],
    ["B", r.B.toLocaleString("en")],
    ["Seed", String(SEED)], ["Audit id", id], ["Package", gate.wheel]];
  for (const [k, v] of rows) { h("dt", null, k, kv); h("dd", null, v, kv); }
  $("rec-cmd").textContent = `quixote audit log.json --panel ${panelName} --class ${className} --B ${r.B} --seed ${SEED}`;
  lastShare = await shareLink(r, record);
  $("share-out").textContent = "";
  $("record").hidden = false;
}

function download(name: string, text: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
  window.setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
$("dl-log").addEventListener("click", () => download("log.json", lastLog));
$("dl-result").addEventListener("click", () => download("result.json", lastResult));
$("share").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(lastShare); $("share-out").textContent = "Copied. The link carries the verdict and the hashes in its fragment, which is never sent to any server; no key, panel, class or log is in it."; }
  catch { $("share-out").textContent = lastShare; }
});

/** The verdict and the hashes, deflated into the URL's fragment (never sent to a server). */
async function shareLink(r: AuditResult, record: Record<string, unknown>): Promise<string> {
  const payload = { v: 1, result: { status: r.status, p_replay: r.p_replay, class_bar: r.class_bar, submitted_sharpe: r.submitted_sharpe,
    submitted_feature_names: r.submitted_feature_names, class_size: r.class_size, B: r.B, alpha: r.alpha, reasons: r.reasons }, record };
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  const z = await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"))).arrayBuffer();
  let bin = ""; for (const b of new Uint8Array(z)) bin += String.fromCharCode(b);
  return `${location.origin}/share.html#r=${btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")}`;
}

// ---- start: the prompt from the CLI adapter, the bundled inputs
(async () => {
  try {
    const gate = await loadGate();
    const p = await gate.prompt();
    defaultPrompt = p.system; schemas = p.schemas;
    fPrompt.value = p.system; $("f-tools").textContent = JSON.stringify(p.schemas, null, 1);
  } catch (e) { errorBox.textContent = `The gate did not load: ${String((e as Error).message ?? e)}`; }
  onProvider();
  await useBundled();
})();
