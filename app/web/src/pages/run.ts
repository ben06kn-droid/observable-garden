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
import { drawRunTree } from "../runtree";
import type { GardenHandle } from "../garden";
import { Hourglass } from "../hourglass";
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

// ---- the scene (src/scene.ts): the run's tree alone, in this page's tokens
const scene = makeScene({ throttled: () => running });
const { two, svg, seed, bed, notes, idleBox, spot } = scene;
// the run's tree as a birch with the gate's numbers on a gauge beside it (src/runtree.ts); redrawn when
// the tree area changes size
let current: GardenHandle | null = null, lastDraw: { t: SearchTree; r: AuditResult | null; step: number } | null = null;
function draw(t: SearchTree, r: AuditResult | null, _runId: string, attempts = 4): GardenHandle {
  const gap = parseFloat(getComputedStyle(document.querySelector(".run-grid") ?? document.body).columnGap) || 24;
  const wordH = parseFloat(getComputedStyle($("verdict-word")).fontSize) * 0.92 || 90;
  current = drawRunTree(svg, spot, t, r, { gap, wordH, attempts });
  lastDraw = { t, r, step: 0 };
  relayout();
  return current;
}
let treeT = 0;
window.addEventListener("resize", () => { window.clearTimeout(treeT); treeT = window.setTimeout(() => {
  if (!lastDraw) return;
  const { t, r } = lastDraw, k = shownSteps;
  const g = draw(t, r, "", r ? 12 : 4); g.setStep(r ? Number.MAX_SAFE_INTEGER : k);
  notes.place();
}, 250); });
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
    const tick = (now: number) => { const k = Math.min(to, from + Math.ceil(((now - t0) / 40))); g.setStep(k); if (k < to && current === g) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    shownSteps = to;
  }
  notes.search(g, g.total, move, `${moves} moves · ${t.evaluations} evaluations`);
}

// ---- the hourglass (src/hourglass.ts): beside the form on a desktop, the headline passing behind the glass;
// under the headline on a phone. Turning it over inverts the page's palette, spreading from the neck.
// During a run it turns over by itself and the sand shows the share of the move budget spent.
const root = document.documentElement;
const phone = () => matchMedia("(max-width: 812px)").matches;
let hg: Hourglass | null = null, hgPhone: boolean | null = null;
function buildGlass() {
  if (hgPhone === phone() && hg) return;
  hg?.destroy(); hgPhone = phone();
  const head = parseFloat(getComputedStyle(root).getPropertyValue("--head")) || 76;
  // on a desktop it grows with the width, as the headline does, so the letters cross the same part of the bulb
  const height = hgPhone ? 340 : Math.round(Math.max(380, Math.min(innerWidth * 0.39, innerHeight - head - 120)));
  hg = new Hourglass($("hg-host"), { height, reduce: reduceMotion,
    behind: hgPhone || reduceMotion ? [] : [$("run-h")],
    onFlip: (flipped, neck) => {
      const swap = () => { root.dataset.hg = flipped ? "light" : "dark"; hg?.refreshPalette(); fan?.refreshPalette(); };
      const d = document as Document & { startViewTransition?: (f: () => void) => { finished: Promise<void> } };
      if (reduceMotion || !d.startViewTransition) { swap(); return; }
      root.style.setProperty("--vx", `${neck.x}px`); root.style.setProperty("--vy", `${neck.y}px`);
      root.dataset.hgSwap = "";
      d.startViewTransition(swap).finished.finally(() => { delete root.dataset.hgSwap; });
    } });
}
/** on a desktop, with the lens: the glass where the headline's letters pass through its upper bulb, at
 *  its widest, the last letters inside the glass and the rest clear of it; never over the form's
 *  columns, and, once it sticks, never under the header */
function placeGlass() {
  const el = hg?.el; if (!el || !hg) return;
  el.style.setProperty("--hg-dx", "0px"); el.style.setProperty("--hg-dy", "0px");
  if (hgPhone || reduceMotion) { hg.paintText(); return; }
  const range = document.createRange(); range.selectNodeContents($("run-h"));
  const m = hg.measures(), h1 = range.getBoundingClientRect(), box = el.getBoundingClientRect();   // the text's extent, not its box
  const form = $("run-form").getBoundingClientRect(), stick = $("hg-host").getBoundingClientRect();
  // from the column it is centred in (the glass itself may be mid-arrival, offset by its animation)
  const cx0 = stick.left + stick.width / 2, cy0 = stick.top + stick.height / 2; void box;
  const cx = Math.max(form.right + m.R + 15 + 12, h1.right - m.R * 0.55);
  let dy = h1.top + h1.height * 0.5 + 0.76 * m.gy - cy0;                // the letters in the bulb's empty upper part
  dy = Math.max(m.H / 2 - stick.height / 2 + 4, Math.min(stick.height / 2 - m.H / 2 - 4, dy));
  el.style.setProperty("--hg-dx", `${(cx - cx0).toFixed(1)}px`); el.style.setProperty("--hg-dy", `${dy.toFixed(1)}px`);
  hg.paintText();
}
// ---- the glass's travel, and the fan of paths (src/fan.ts) that takes over below it
// On a desktop the glass rides with the scroll from the opening screen down to the rule above 03 Key and
// comes to rest with its base on it: its column ends there (by the glass's own offset in its sticky box).
// As it arrives, a thin stream of sand leaves its base, runs along that rule to the left edge and becomes
// the first sand-toned path of the fan, which fills the left of the page from that rule down to above
// "Continue to docs", fading before the fields and the tree, dimmed behind text, its last paths resting.
// On a phone the fan is its own band between the form and the tree, with no lens.
const keySect = () => document.querySelectorAll<HTMLElement>(".run-form .sect")[2];
function travel() {
  const col = document.querySelector<HTMLElement>(".glass-col")!;
  if (hgPhone || !hg) { col.style.removeProperty("--glass-h"); return; }
  const m = hg.measures(), stick = $("hg-host").getBoundingClientRect();
  const dy = parseFloat(hg.el.style.getPropertyValue("--hg-dy")) || 0;
  const below = stick.height / 2 - dy - m.H / 2;                 // the sticky box's bottom, below the glass's base
  col.style.setProperty("--glass-h", `${Math.round(keySect().getBoundingClientRect().top - col.getBoundingClientRect().top + below)}px`);
}
let fan: Fan | null = null, fanPhone: boolean | null = null, handed = false;
// the page's shape for the fan, taken once per layout (page px)
let geom = { top: 0, bottom: 0, col3: 300, stage: [0, 0], tree: Infinity, masks: [] as FanRect[] };
const TEXT = ".run-form .sect-h, .run-form .fine, .run-form label:not(.file), .run-form .status, .run-form .estimate, .run-form details, .run-go .run-error, "
  + ".stage-empty, #spot .note, #spot .note-word, .below h2, .below p, .run-log, #record .meaning, #record .reasons-d, #record h2, #record h3, #record .kv, #record pre, "
  + ".run-notes p, .carry-next .k, .carry-next .to";
const FIELDS = ".run-form input:not([type=file]), .run-form select, .run-form textarea, .run-form label.file, .run-form button, #record button";
function measure() {
  const y = scrollY, rect = (e: Element) => e.getBoundingClientRect();
  const key = rect(keySect()), next = document.querySelector(".carry-next .k"), stage = rect($("demo"));
  geom.top = key.top + y - 3; geom.bottom = (next ? rect(next).top : document.documentElement.scrollHeight - y) + y - 32;
  geom.col3 = rect(keySect().querySelector(".sect-b")!).left - 18;
  geom.stage = [stage.top + y, stage.bottom + y];
  const real = svg.querySelector(".real"), tr = real ? rect(real) : null;
  geom.tree = tr && tr.width > 0 ? tr.left - 16 : Infinity;
  const pad = 6, list: FanRect[] = [];
  // behind text: the text's own extent (a grid cell may stretch an element far past its words)
  const range = document.createRange();
  for (const e of document.querySelectorAll(TEXT)) {
    range.selectNodeContents(e); const r = range.getBoundingClientRect();
    if (r.width && r.height && r.left < geom.col3 + 40) list.push({ x: r.left - pad, y: r.top + y - pad, w: r.width + 2 * pad, h: r.height + 2 * pad, keep: 0.28 });
  }
  for (const e of document.querySelectorAll(FIELDS)) { const r = rect(e); if (r.width && r.height && r.left < geom.col3 + 40) list.push({ x: r.left - 4, y: r.top + y - 4, w: r.width + 8, h: r.height + 8, keep: 0 }); }
  geom.masks = list;
}
function buildFan() {
  const ph = phone();
  if (fan && fanPhone === ph) { measure(); fan.layout(); checkHand(); return; }
  fan?.destroy(); fan = null; fanPhone = ph; handed = false;
  if (ph) {
    const band = $("fan-band");
    fan = new Fan(document.body, { reduce: reduceMotion, lens: false, seed: 7,
      region: () => { const r = band.getBoundingClientRect(); return { top: r.top + scrollY + 1, bottom: r.bottom + scrollY }; },
      reach: () => innerWidth - 12 });
    return;
  }
  measure();
  fan = new Fan(document.body, { reduce: reduceMotion, awaitHandover: !reduceMotion, foot: 280, seed: 5,
    region: () => ({ top: geom.top, bottom: geom.bottom }),
    reach: (y) => (y >= geom.stage[0] && y <= geom.stage[1] ? Math.max(48, Math.min(geom.col3, geom.tree)) : geom.col3),
    masks: () => geom.masks });
  checkHand();
}
/** the glass has come to rest on the rule: the stream sets off (and is taken back if the visitor scrolls up) */
function checkHand() {
  if (!fan || fanPhone || !hg || reduceMotion) return;
  const m = hg.measures(), b = hg.el.getBoundingClientRect(), base = b.top + b.height / 2 + m.H / 2, rule = keySect().getBoundingClientRect().top;
  if (!handed && base >= rule - 2) { handed = true; void fan.handover({ x: b.left + b.width / 2, y: rule + scrollY }); }
  else if (handed && base < rule - 60) { handed = false; fan.resetHandover(); }
}
addEventListener("scroll", checkHand, { passive: true });
let relayT = 0;
const relayout = () => { window.clearTimeout(relayT); relayT = window.setTimeout(() => { travel(); buildFan(); }, 150); };
new ResizeObserver(relayout).observe($("main"));
void document.fonts.ready.then(() => { buildGlass(); placeGlass(); travel(); buildFan(); });
let glassT = 0;
let glassW = innerWidth;
window.addEventListener("resize", () => { window.clearTimeout(glassT); glassT = window.setTimeout(() => {
  if (hgPhone !== phone() || (!hgPhone && Math.abs(innerWidth - glassW) > 40)) { glassW = innerWidth; hgPhone = null; buildGlass(); }
  placeGlass(); travel(); buildFan();
}, 200); });

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
  two.classList.add("has-run");
  hg?.beginRun();
  $("record").hidden = true; logList.replaceChildren(); tokens.textContent = "Starting…";
  runId = `run-${Date.now().toString(36)}`; shownSteps = 0;
  svg.replaceChildren(); idleBox(); lastDraw = null; current = null; notes.clear(); notes.entered(); seed.classList.remove("spent");
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
          if (ev.tool) { lastMove = ev.tool; nMoves++; hg?.setShare(0.8 * Math.min(1, nMoves / moves)); }
          logLine("move", [h("b", null, ev.tool ?? "(no move)"), " ", Object.keys(ev.args).length ? JSON.stringify(ev.args) : "", ev.text ? h("span", "say", ` ${ev.text}`) : ""]);
        } else if (ev.type === "result") {
          logLine(ev.last.refused ? "refused" : "result", ev.last.refused ? [h("span", "tag", "refused"), ev.last.refused] : [ev.last.text ?? ""]);
        } else if (ev.type === "usage") {
          if (ev.model) served = ev.model;
          tokens.textContent = fmtUsage(ev.usage);
        } else if (ev.type === "tree") grow(ev.tree, runId, lastMove, nMoves);
      },
      onProgress: (p) => {
        if (p.stage !== "replay") return;
        notes.replay(`replay · ${p.done.toLocaleString("en")} of ${p.total.toLocaleString("en")}`);
        hg?.setShare(0.8 + 0.2 * (p.total ? p.done / p.total : 0));          // the last fifth of the sand runs with the replay
      },
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
  await hg?.finish();                                         // the verdict appears as the last grain lands
  bed.finish();
  if (t) { const g = draw(t, r, runId, 12); g.setStep(Number.MAX_SAFE_INTEGER); notes.verdict(g, r, t.evaluations, SEED); }
  // the prompt actually sent: the adapter's own, or the visitor's edit (a different search)
  const prompt = { edited: opts.system !== undefined, sha256: await sha256Hex(opts.system ?? defaultPrompt) };
  await showRecord(r, out.log as Record<string, unknown>, model, served, moves, prompt, run);
}

function finish(message: string, usage?: RunUsage | null) {
  endKey();
  void hg?.finish();
  running = false; refresh();
  if (usage) tokens.textContent = fmtUsage(usage);
  errorBox.textContent = message;
  logLine("refused", [h("span", "tag", "stopped"), message]);
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
