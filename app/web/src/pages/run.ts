// The full run: the visitor's panel, class, key and budget; their model as the agent through the
// harness, in their browser; the gate's price on the log it writes.
//
// The key lives in one variable (`key`) from Start to the run's end: it is sent to the worker with
// the run message, never written to storage or a URL, never put into the log, the result or an error
// message, and cleared (the variable and the field) when the run ends in any way or the page is left.
// The panel and the class are read by the package's own loaders in the worker (np.load with
// allow_pickle=False) and checked before the key is used; their errors are shown word for word.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/run.css";
import "../chain";
import { auditId, h, MEANING, reduceMotion, sha256Hex, word } from "../common";
import { cancelGate, loadGate, type RunOutcome } from "../gate";
import { makeScene } from "../scene";
import { drawRunScale } from "../runscale";
import type { GardenHandle } from "../garden";
import { Glass } from "../glass";
import { Hero } from "../hero";
import { Fan, type FanRect } from "../fan";
import { FALLBACK_MODELS, localEndpoint, NOT_SENT, OPENROUTER_MODELS, PROVIDERS, routerModels, type RouterModel } from "../providers";
import type { AuditResult, InputsInfo, ProviderId, RunEvent, RunUsage, SearchTree } from "../types";

/** members x rows the browser takes (scripts/measure_class_cap.mjs: a 25-million-cell class table
 *  is 200 MB, about 0.4 GB at peak, and about 16 s to build; at 85 million it is 1.9 GB and 3.5 minutes) */
export const CLASS_CAP = 25_000_000;
const SEED = 0;
// thinking plus one tool call, by effort: guesses, not measurements (a model's own default where no
// level is sent); the page labels the estimate rough and points to the running count, the real figure
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

// ---- the result (src/scene.ts for the notes, src/runscale.ts for the scale): no tree on this page. Before
// and during a run the result area is hidden; during a run a counter above the moves says how far the
// search has come; after it, the gate's numbers on a scale, drawn large.
const scene = makeScene({ throttled: () => running });
const { two, svg, bed, notes, idleBox, spot } = scene;
let shown: { t: SearchTree; r: AuditResult } | null = null;
function drawResult(t: SearchTree, r: AuditResult): GardenHandle {
  const wordH = parseFloat(getComputedStyle($("verdict-word")).fontSize) * 0.92 || 90;
  const g = drawRunScale(svg, spot, t, r, { wordH });
  shown = { t, r };
  relayout();
  return g;
}
let scaleT = 0;
window.addEventListener("resize", () => { window.clearTimeout(scaleT); scaleT = window.setTimeout(() => {
  if (!shown || two.hidden) return;
  drawResult(shown.t, shown.r); notes.place();
}, 250); });
notes.entered();                                             // no "click a tree" here: the record is below
const counter = $("move-count");

// ---- the glass (src/glass.ts) and the fan of paths (src/fan.ts): two independent elements
// The glass: a still hourglass in the right-hand columns from the opening screen down to the rule above
// 03 Key, scrolling with the page, an abstract flow pouring through it at one steady rate. A click on it
// inverts the page's palette, spreading from where it was clicked. The headline's last letters pass
// through its upper bulb, bent. On a phone it is a glass of its own size under the headline.
// The fan: random paths down the whole left of the page, from the top to above "Continue to docs",
// running right until the glass (beside it) or the page's right edge (below it); dimmed behind text,
// never under a field; its last paths come to rest at the foot. On a phone: a band between sections.
const root = document.documentElement;
const phone = () => matchMedia("(max-width: 812px)").matches;
const keySect = () => document.querySelectorAll<HTMLElement>(".run-form .sect")[2];
let glass: Glass | null = null, glassPhone: boolean | null = null, glassH = 0;
function invert(at: { x: number; y: number }) {
  const swap = () => { root.dataset.hg = root.dataset.hg === "light" ? "dark" : "light"; glass?.refreshPalette(); fan?.refreshPalette(); hero?.layout(); };
  const d = document as Document & { startViewTransition?: (f: () => void) => { finished: Promise<void> } };
  if (reduceMotion || !d.startViewTransition) { swap(); return; }
  root.style.setProperty("--vx", `${at.x}px`); root.style.setProperty("--vy", `${at.y}px`);
  root.dataset.hgSwap = "";
  d.startViewTransition(swap).finished.finally(() => { delete root.dataset.hgSwap; });
}
function buildGlass() {
  const ph = phone(), host = $("hg-host");
  // measured as if the disclosure above were closed, so opening it never resizes or rebuilds the glass
  const about = document.querySelector<HTMLDetailsElement>(".hero .about"), sum = about?.querySelector("summary");
  const opened = about?.open && sum ? about.getBoundingClientRect().height - sum.getBoundingClientRect().height : 0;
  const H = ph ? Math.round(Math.max(420, Math.min(640, innerHeight * 0.76)))
    : Math.round(keySect().getBoundingClientRect().top - host.getBoundingClientRect().top - opened);
  if (glass && glassPhone === ph && Math.abs(H - glassH) < 24) { placeGlass(); hero?.layout(); return; }
  glass?.destroy(); hero?.destroy(); hero = null; $("main").querySelector(".hero")!.classList.remove("painted");
  glassPhone = ph; glassH = H;
  // on a desktop with motion, the hero layer draws the glass and the opening text (the wake bends them)
  const layered = !ph && !reduceMotion;
  glass = new Glass(host, { height: H, reduce: reduceMotion, composited: layered, onClick: invert, onFrame: () => hero?.glassFrame() });
  placeGlass();
  if (layered) {
    const veil = $("main").querySelector<HTMLElement>(".hero")!;
    const h = new Hero({ host: $("main"), glass, veil, textBottom: () => document.querySelector(".run-form .sect")!.getBoundingClientRect().top + scrollY,
      text: () => [...veil.querySelectorAll<HTMLElement>(".label, h1, .lead, .about summary, .about[open] p, .to-demo a")] });
    if (h.ok) { hero = h; veil.classList.add("painted"); hero.layout(); }
    else { h.destroy(); glass.el.classList.remove("composited"); }
  }
}
let hero: Hero | null = null;
// the hero layer follows any change to the page's layout in the same frame, before it is painted (a
// ResizeObserver's callback runs after layout and before paint), so the drawn text never lags the page
new ResizeObserver(() => hero?.layout()).observe(document.querySelector(".hero")!);
/** across: on a desktop its bulbs clear the form's columns (and may be cropped by the page's right edge) */
function placeGlass() {
  if (!glass) return;
  const m = glass.measures(), host = $("hg-host").getBoundingClientRect();
  const cx = glassPhone ? host.left + host.width / 2 : Math.max($("run-form").getBoundingClientRect().right + m.R + 20, host.left + host.width / 2);
  glass.el.style.setProperty("--g-x", `${(cx - host.left - m.W / 2).toFixed(1)}px`);
}

let fan: Fan | null = null, fanPhone: boolean | null = null;
// the page's shape for the fan, taken once per layout (page px)
let geom = { bottom: 0, right: 0, glass: [0, 0, Infinity] as [number, number, number], masks: [] as FanRect[] };
const TEXT = ".hero .label, .hero h1, .hero .lead, .hero .about, .hero .to-demo, "
  + ".run-form .sect-h, .run-form .fine, .run-form label:not(.file), .run-form .status, .run-form .estimate, .run-form details, .run-go .run-error, "
  + ".move-count, #spot .note, #spot .note-word, .below h2, .below p, .run-log, #record .meaning, #record .reasons-d, #record h2, #record h3, #record .kv, #record pre, "
  + ".run-notes p, .carry-next .k, .carry-next .to";
const FIELDS = ".run-form input:not([type=file]), .run-form select, .run-form textarea, .run-form label.file, .run-form button, #record button";
function measure() {
  const y = scrollY, rect = (e: Element) => e.getBoundingClientRect(), next = document.querySelector(".carry-next .k");
  geom.bottom = (next ? rect(next).top : document.documentElement.scrollHeight - y) + y - 32;
  geom.right = innerWidth - parseFloat(getComputedStyle($("main").querySelector(".run-grid")!).paddingRight || "72");
  if (glass && !glassPhone) { const g = rect(glass.el), m = glass.measures(); geom.glass = [g.top + y, g.bottom + y, g.left + g.width / 2 - m.R - 28]; }
  else geom.glass = [0, 0, Infinity];
  const list: FanRect[] = [], range = document.createRange(), pad = 6;
  // behind text: the text's own extent (a grid cell may stretch an element far past its words). At 6% of
  // the lines' strength, every text tone keeps 7.8:1 or more over a gold path, in both palettes
  for (const e of document.querySelectorAll(TEXT)) {
    range.selectNodeContents(e); const r = range.getBoundingClientRect();
    if (r.width && r.height) list.push({ x: r.left - pad, y: r.top + y - pad, w: r.width + 2 * pad, h: r.height + 2 * pad, keep: 0.06 });
  }
  const tree = svg.querySelector(".real"); if (tree) { const r = rect(tree); if (r.width) list.push({ x: r.left - 10, y: r.top + y - 10, w: r.width + 20, h: r.height + 20, keep: 0.15 }); }
  for (const e of document.querySelectorAll(FIELDS)) { const r = rect(e); if (r.width && r.height) list.push({ x: r.left - 6, y: r.top + y - 6, w: r.width + 12, h: r.height + 12, keep: 0 }); }
  geom.masks = list;
}
function buildFan() {
  const ph = phone();
  if (fan && fanPhone === ph) { measure(); fan.layout(); return; }
  fan?.destroy(); fan = null; fanPhone = ph;
  if (ph) {
    const band = $("fan-band");
    fan = new Fan(document.body, { reduce: reduceMotion, seed: 7,
      region: () => { const r = band.getBoundingClientRect(); return { top: r.top + scrollY + 1, bottom: r.bottom + scrollY }; },
      reach: () => innerWidth - 12 });
    return;
  }
  measure();
  fan = new Fan(document.body, { reduce: reduceMotion, foot: 280, seed: 5, wake: true,
    region: () => ({ top: 0, bottom: geom.bottom }),
    reach: (y) => (y >= geom.glass[0] && y <= geom.glass[1] ? geom.glass[2] : geom.right),
    masks: () => geom.masks });
}
let relayT = 0;
const relayout = () => { window.clearTimeout(relayT); relayT = window.setTimeout(() => { buildGlass(); buildFan(); }, 150); };
new ResizeObserver(relayout).observe($("main"));
void document.fonts.ready.then(() => { buildGlass(); buildFan(); });

// ---- inputs: the bundled pair to start, or the visitor's files; checked by the package's loaders
async function useBundled() {
  const [p, c] = await Promise.all([fetch("/examples/tiny_panel.npz").then((r) => r.arrayBuffer()), fetch("/examples/class.json").then((r) => r.text())]);
  panel = p; cls = c; panelName = "tiny_panel.npz"; className = "class.json";
  fPanel.value = ""; fClass.value = "";
  await check();
}
async function check() {
  info = null; refresh();
  $("f-panel-name").textContent = panelName || "none"; $("f-class-name").textContent = className || "none";
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
  const tokensLine = `Rough estimate for up to ${n - 3} moves: about ${Math.round(input / 1000)}k input and ${Math.round(output / 1000)}k output tokens`;
  const real = " The output figure is a guess by effort level, not a measurement: once the run starts, the token count under “The model's moves” is the real figure, from the provider's own usage.";
  if (!pr) { $("estimate").textContent = `${tokensLine}; cost unknown (${provider().id === "local" ? "a local server has no list price" : `no list price known for ${id}`}).${real}`; return; }
  const dollars = (input * pr[0] + output * pr[1]) / 1e6;
  $("estimate").textContent = `${tokensLine}, at most about $${dollars < 0.1 ? dollars.toFixed(3) : dollars.toFixed(2)} at ${provider().label}'s list prices for ${id} `
    + `(less where the provider's prompt cache applies; a model that stops early costs less).${real}`;
}
for (const el of [fMoves, fModel, fModelId, fEffort, fPrompt]) el.addEventListener("input", estimate);

function refresh() {
  const ok = !!info && !info.error && (info.size ?? 0) * (info.rows ?? 0) <= CLASS_CAP;
  startBtn.disabled = running || !ok;
  cancelBtn.hidden = !running;
  for (const el of form.querySelectorAll<HTMLInputElement>("input, select, textarea, button.link")) el.disabled = running;
}

// ---- the run
// the list follows its newest line by scrolling itself only, so the page stays where the visitor put it
const logLine = (cls: string, parts: (string | Node)[]) => { const li = h("li", cls, null, logList); li.append(...parts); logList.scrollTop = logList.scrollHeight; return li; };
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
  runId = `run-${Date.now().toString(36)}`;
  two.hidden = true; svg.replaceChildren(); idleBox(); shown = null; notes.clear(); notes.entered();
  bed.reset(runId); bed.start();
  const moves = Math.max(1, Math.min(60, Math.round(Number(fMoves.value) || 20)));
  counter.textContent = `move 0 of ${moves}`; counter.hidden = false;
  $("log-h").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  const B = Math.max(100, Math.min(10000, Math.round(Number(fB.value) || 2000)));
  const effort = fEffort.value === NOT_SENT ? undefined : fEffort.value;
  const maxOut = p.id === "openrouter" ? routed.find((m) => m.id === model)?.maxOut : undefined;
  const opts = { provider: p.id, model, effort, max_moves: moves, fallbacks: p.id === "anthropic" && FALLBACK_MODELS.has(model), seed: SEED,
                 system: fPrompt.value.trim() && fPrompt.value !== defaultPrompt ? fPrompt.value : undefined,
                 max_tokens: maxOut ? Math.min(16000, maxOut) : undefined };
  const run = { provider: p.id, label: p.label, effort: effort ?? NOT_SENT, host: where.host };
  let nMoves = 0, served = model, out: RunOutcome;
  try {
    const gate = await loadGate();
    const runKey = key;
    out = await gate.run({ panel: panel.slice(0), cls, key: runKey, provider: p.id, url: where.url, opts, B, seed: SEED }, {
      onEvent: (ev: RunEvent) => {
        if (ev.type === "move") {
          if (ev.tool) { nMoves++; counter.textContent = `move ${nMoves} of ${moves}`; }
          logLine("move", [h("b", null, ev.tool ?? "(no move)"), " ", Object.keys(ev.args).length ? JSON.stringify(ev.args) : "", ev.text ? h("span", "say", ` ${ev.text}`) : ""]);
        } else if (ev.type === "result") {
          logLine(ev.last.refused ? "refused" : "result", ev.last.refused ? [h("span", "tag", "refused"), ev.last.refused] : [ev.last.text ?? ""]);
        } else if (ev.type === "usage") {
          if (ev.model) served = ev.model;
          tokens.textContent = fmtUsage(ev.usage);
        }
      },
      onProgress: (p) => { if (p.stage === "replay") counter.textContent = `replay · ${p.done.toLocaleString("en")} of ${p.total.toLocaleString("en")}`; },
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
  counter.hidden = true;
  if (t) { two.hidden = false; const g = drawResult(t, r); notes.verdict(g, r, t.evaluations, SEED); }
  // the prompt actually sent: the adapter's own, or the visitor's edit (a different search)
  const prompt = { edited: opts.system !== undefined, sha256: await sha256Hex(opts.system ?? defaultPrompt) };
  await showRecord(r, out.log as Record<string, unknown>, model, served, moves, prompt, run);
}

function finish(message: string, usage?: RunUsage | null) {
  endKey();
  running = false; refresh();
  if (usage) tokens.textContent = fmtUsage(usage);
  errorBox.textContent = message;
  logLine("refused", [h("span", "tag", "stopped"), message]);
  bed.finish(); counter.hidden = true;
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
  ($("rec-reasons-d") as HTMLDetailsElement).open = !phone();          // open on a desktop, closed on a phone
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
