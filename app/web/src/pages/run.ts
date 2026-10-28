// The full run: the visitor's panel, class, key and budget; their model as the agent through the
// harness, in their browser; the gate's price on the log it writes.
//
// The key lives in one variable (`key`) from Start to the run's end: it is sent to the worker with
// the run message, never written to storage or a URL, never put into the log, the result or an error
// message, and cleared (the variable and the field) when the run ends in any way or the page is left.
// The panel and the class are read by the package's own loaders in the worker (np.load with
// allow_pickle=False) and checked before the key is used; their errors are shown word for word.
import { auditId, h, MEANING, reduceMotion, sha256Hex, word } from "../common";
import { makeBed } from "../bed";
import { makeCity } from "../city";
import { Fx } from "../fx";
import { drawGarden, H as GH, SEED as SEED_AT, W as GW, type GardenHandle } from "../garden";
import { cancelGate, loadGate, type RunOutcome } from "../gate";
import { colourOf, kindOf } from "../heads";
import { makeNotes } from "../notes";
import { Field, startLife } from "../particles";
import { branchSources, shakeable, woodTwo } from "../woods";
import type { AuditResult, InputsInfo, RunEvent, RunUsage, SearchTree } from "../types";

/** members x rows the browser takes (scripts/measure_class_cap.mjs: a 25-million-cell class table
 *  is 200 MB, about 0.4 GB at peak, and about 16 s to build; at 85 million it is 1.9 GB and 3.5 minutes) */
export const CLASS_CAP = 25_000_000;
const SEED = 0;
const PRICES: Record<string, [number, number, string]> = {   // list prices per million tokens, input and output
  "claude-opus-5-5": [4, 20, "Claude Opus 5.5"], "claude-sonnet-5-5": [2, 10, "Claude Sonnet 5.5"], "claude-haiku-5-5": [0.1, 0.5, "Claude Haiku 5.5"],
};
const OUT_PER_TURN: Record<string, number> = { low: 250, medium: 600, high: 1500 };   // thinking plus one tool call, by effort

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const form = $<HTMLFormElement>("run-form"), status = $("in-status"), capLine = $("in-cap"), errorBox = $("run-error");
const fPanel = $<HTMLInputElement>("f-panel"), fClass = $<HTMLInputElement>("f-class"), fKey = $<HTMLInputElement>("f-key");
const fModel = $<HTMLSelectElement>("f-model"), fEffort = $<HTMLSelectElement>("f-effort"), fMoves = $<HTMLInputElement>("f-moves");
const fB = $<HTMLInputElement>("f-B"), fPrompt = $<HTMLTextAreaElement>("f-prompt"), startBtn = $<HTMLButtonElement>("start"), cancelBtn = $<HTMLButtonElement>("cancel");
const two = $("demo"), svg = $("garden") as unknown as SVGSVGElement, spot = $("spot"), seed = $("seed"), logList = $("run-log"), tokens = $("tokens");

let panel: ArrayBuffer | null = null, cls = "", panelName = "", className = "", info: InputsInfo | null = null;
let schemas: Record<string, unknown> = {}, defaultPrompt = "";
let key = "", running = false;

// ---- the scene: the demo's page two (city, trees, petals, the bed, the run's tree, the annotation)
const fx = new Fx($("fx") as HTMLCanvasElement, two);
const bed = makeBed($("bed") as unknown as SVGSVGElement, two);
const notes = makeNotes(spot, two, () => bed.heads());
notes.entered();                                             // no "click a tree" here: the record is below
const city = makeCity($("city") as unknown as SVGSVGElement, reduceMotion, fx);
city.draw();
city.start(() => document.hidden);
const petals = new Field({ box: two, air: $("air-two") as HTMLCanvasElement, pile: $("pile-two") as HTMLCanvasElement, kind: "petal", count: 70, start: 30,
  ground: (x) => { const W = two.clientWidth, u = (x - W / 2) / (W / 2); return two.clientHeight * (0.93 - 0.11 * u * u); },
  cap: () => (innerWidth < 760 ? 0 : 12), avoid: () => notes.boxes() });
startLife({ fields: [petals], paused: () => false, throttled: () => running, reduce: reduceMotion });
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
window.addEventListener("resize", () => { city.draw(); placeSeed(); notes.place(); });

let garden: GardenHandle | null = null, shownSteps = 0;
function draw(t: SearchTree, r: AuditResult | null, runId: string) {
  garden = drawGarden(svg, t, { interactive: false, halo: true, neon: true, canopy: false, twigs: true, bar: r?.class_bar,
    blossom: { kind: kindOf(runId), colour: colourOf(runId) },
    submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
  return garden;
}
/** the tree as the search so far, its new evaluations growing in one by one */
function grow(t: SearchTree, runId: string, move: string, moves: number) {
  const g = draw(t, null, runId);
  seed.classList.add("spent");
  if (reduceMotion) { g.setStep(g.total); shownSteps = g.total; }
  else {
    g.grow(); g.setStep(shownSteps);
    const from = shownSteps, to = g.total, t0 = performance.now();
    const tick = (now: number) => { const k = Math.min(to, from + Math.ceil(((now - t0) / 40))); g.setStep(k); if (k < to && garden === g) requestAnimationFrame(tick); };
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

// ---- the estimate: tokens before the run, from the prompt, the tools and the budget
function estimate() {
  const n = Math.max(1, Math.min(60, Number(fMoves.value) || 20)) + 3;   // the budget plus declare, predict and submit
  const base = Math.ceil((fPrompt.value.length + JSON.stringify(schemas).length * 1.6) / 4) + 200;   // system, tool definitions
  const obs = 420, reply = 140, out = OUT_PER_TURN[fEffort.value] ?? 600;
  const input = n * (base + obs) + ((obs + reply) * n * (n - 1)) / 2;   // each turn resends the history so far
  const output = n * out;
  const [pi, po, name] = PRICES[fModel.value];
  const dollars = (input * pi + output * po) / 1e6;
  $("estimate").textContent = `Estimate for up to ${n - 3} moves: about ${Math.round(input / 1000)}k input and ${Math.round(output / 1000)}k output tokens, `
    + `at most about $${dollars < 0.1 ? dollars.toFixed(3) : dollars.toFixed(2)} at ${name}'s list prices (less where the provider's prompt cache applies). A model that stops early costs less.`;
}
for (const el of [fMoves, fModel, fEffort, fPrompt]) el.addEventListener("input", estimate);

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
  key = fKey.value.trim();
  if (!key) { errorBox.textContent = "Enter your API key to start."; fKey.focus(); return; }
  running = true; refresh();
  $("record").hidden = true; logList.replaceChildren(); tokens.textContent = "Starting…";
  runId = `run-${Date.now().toString(36)}`; shownSteps = 0; garden = null;
  svg.replaceChildren(); idleBox(); notes.clear(); notes.entered(); seed.classList.remove("spent");
  bed.reset(runId); bed.start();
  two.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  const model = fModel.value, moves = Math.max(1, Math.min(60, Math.round(Number(fMoves.value) || 20)));
  const B = Math.max(100, Math.min(10000, Math.round(Number(fB.value) || 2000)));
  const local = location.hostname === "127.0.0.1" || location.hostname === "localhost";
  const url = local && new URLSearchParams(location.search).get("provider") === "mock" ? "/__mock/anthropic/v1/messages" : "https://api.anthropic.com/v1/messages";
  const opts = { model, effort: fEffort.value, max_moves: moves, fallbacks: model !== "claude-haiku-5-5", seed: SEED,
                 system: fPrompt.value.trim() && fPrompt.value !== defaultPrompt ? fPrompt.value : undefined };
  let lastMove = "", nMoves = 0, served = model, out: RunOutcome;
  try {
    const gate = await loadGate();
    const runKey = key;
    out = await gate.run({ panel: panel.slice(0), cls, key: runKey, url, opts, B, seed: SEED }, {
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
  if (t) { draw(t, r, runId).setStep(Number.MAX_SAFE_INTEGER); notes.verdict(garden!, r, t.evaluations, SEED); }
  // the prompt actually sent: the adapter's own, or the visitor's edit (a different search)
  const prompt = { edited: opts.system !== undefined, sha256: await sha256Hex(opts.system ?? defaultPrompt) };
  await showRecord(r, out.log as Record<string, unknown>, model, served, moves, prompt);
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
async function showRecord(r: AuditResult, log: Record<string, unknown>, model: string, served: string, moves: number, prompt: { edited: boolean; sha256: string }) {
  const gate = await loadGate();
  lastLog = JSON.stringify(log, null, 1);
  const logSha = await sha256Hex(lastLog);
  const id = await auditId({ alpha: r.alpha, B: r.B, class_sha256: info!.class_sha256!, log_sha256: logSha, panel_sha256: info!.panel_sha256!, seed: SEED, wheel: gate.wheel });
  const record = { panel_file: panelName, panel_sha256: info!.panel_sha256!, class_file: className, class_sha256: info!.class_sha256!,
    log_sha256: logSha, model, served_by: served, budget_moves: moves, prompt: prompt.edited ? "edited" : "default", prompt_sha256: prompt.sha256,
    B: r.B, seed: SEED, audit_id: id, package: gate.wheel };
  lastResult = JSON.stringify({ format: "quixote-browser-result/1", result: r, record }, null, 1);
  $("rec-meaning").textContent = `${word(r.status)}: ${MEANING[word(r.status)] ?? ""}`;
  const ul = $("rec-reasons"); ul.replaceChildren(); for (const x of r.reasons) h("li", null, x, ul);
  const kv = $("rec-kv"); kv.replaceChildren();
  const rows: [string, string][] = [["Panel", `${panelName} · ${record.panel_sha256}`], ["Class", `${className} · ${record.class_sha256}`],
    ["Model", served !== model ? `${model} (served by ${served})` : model], ["Budget", `${moves} moves`],
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
  estimate();
  await useBundled();
})();
