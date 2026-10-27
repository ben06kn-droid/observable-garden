import { h, headerOverPaper, reduceMotion, sha256Hex, word } from "../common";
import { command, demos, loadDemo, type Demo } from "../demos";
import { drawGarden, scaleFor, type GardenHandle } from "../garden";
import { loadGate } from "../gate";
import { makePanel } from "../panel";
import { drawStreaks } from "../streaks";
import type { AuditResult, Progress, ReplicatePath, SearchTree } from "../types";
import { idleCard, verdictCard } from "../verdict";

const SEED = 0, PATHS = 48;
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const one = $("overview"), two = $("demo");
headerOverPaper(one);

// ---- the hard cut: scrolling down from the overview settles on the demo; scrolling up from the
// demo's top settles back on the overview. Below the demo, scrolling is free.
let settling = false;
const go = (y: number) => {
  settling = true;
  window.scrollTo({ top: y, behavior: reduceMotion ? "auto" : "smooth" });
  window.setTimeout(() => { settling = false; }, reduceMotion ? 50 : 700);
};
let lastY = window.scrollY;
window.addEventListener("scroll", () => {
  const y = window.scrollY, top = two.offsetTop, dir = y - lastY;
  lastY = y;
  if (settling) return;
  if (y > 4 && y < top - 4) go(dir > 0 ? top : 0);
}, { passive: true });

// ---- page one: the restart example's trees, dark green, behind the overview
fetch("/examples/overview-tree.json").then((r) => r.json()).then((tree: SearchTree) => {
  drawGarden($<SVGSVGElement & HTMLElement>("bg-trees") as unknown as SVGSVGElement, tree, { quiet: true });
}).catch(() => {});

// ---- page two
const svg = $("garden") as unknown as SVGSVGElement;
const phase = $("phase"), big = $("big"), line = $("line"), stateWord = $("state-word"), runBtn = $<HTMLButtonElement>("run");
const verdictBox = $("verdict");
idleCard(verdictBox, "Run an example to see its verdict here.");
let tree: SearchTree | null = null;
let garden: GardenHandle | null = null;
const panel = makePanel($("panel"), () => tree);
panel.onClose(() => garden?.select(null));
panel.onLight((m) => garden?.light(m));

let chosen: Demo;
const chips = $("chips");
demos().then((list) => {
  chosen = list[0];
  for (const d of list) {
    const li = h("li", null, null, chips);
    const b = h("button", "chip", null, li) as HTMLButtonElement;
    b.type = "button";
    b.setAttribute("aria-pressed", String(d === chosen));
    b.append(d.title);
    h("small", null, d.about, b);
    b.addEventListener("click", () => {
      chosen = d;
      chips.querySelectorAll(".chip:not([disabled])").forEach((c) => c.setAttribute("aria-pressed", String(c === b)));
    });
  }
  const li = h("li", null, null, chips);
  const r = h("button", "chip", "82,240-member ETF class", li) as HTMLButtonElement;
  r.type = "button"; r.disabled = true;
  r.title = "Too large for a browser: it will be a recorded replay of a local run. The format is defined in Docs; no recording yet.";
  h("small", null, "recorded replay · not yet", r);
});

function setState(p: string, b: string, l: string) { phase.textContent = p; big.textContent = b; line.textContent = l; }

runBtn.addEventListener("click", () => { void run(chosen); });

async function run(demo: Demo) {
  runBtn.disabled = true;
  stateWord.hidden = true;
  idleCard(verdictBox, "Waiting for the verdict.");
  $("record").hidden = true;
  const streakBox = $("streaks") as unknown as SVGSVGElement;
  streakBox.replaceChildren();
  try {
    setState("Loading", "the gate", "Python and the package, into your browser; once per visit.");
    const [gate, loaded] = await Promise.all([loadGate(), loadDemo(demo)]);
    const log = loaded.logJson;
    let searchDone: () => void = () => {};
    const searchShown = new Promise<void>((r) => { searchDone = r; });
    let latest: Progress | null = null;
    const B0 = demo.B;
    let nullShown = false;
    const showNull = () => {
      if (!latest || latest.stage !== "replay") { setState("The null", "re-growing", `on ${B0.toLocaleString("en")} resampled copies of the data`); return; }
      setState("The null", `${latest.done.toLocaleString("en")}`, `of ${latest.total.toLocaleString("en")} replicates`);
    };
    setState("The search", "0", "evaluations");
    const B = demo.B;
    const out = await gate.audit({ ...loaded.inputs, B, seed: SEED, replicatePaths: PATHS }, {
      onSearch: (t) => { tree = t; void animateSearch(t, log, demo).then(() => { nullShown = true; showNull(); searchDone(); }); },
      onProgress: (p) => { latest = p; if (nullShown) showNull(); },
    });
    await searchShown;
    if (out.kind === "refused") {
      setState("Refused", "—", out.message);
      return;
    }
    await land(out.result, out.replicatePaths, demo, loaded.inputs.panel, loaded.inputs.cls, loaded.inputs.log, log, gate.wheel);
  } catch (e) {
    setState("Error", "—", String((e as Error).message ?? e));
  } finally {
    runBtn.disabled = false;
  }
}

function animateSearch(t: SearchTree, log: any, _demo: Demo): Promise<void> {
  garden = drawGarden(svg, t, { interactive: true });
  svg.setAttribute("aria-label", `The search drawn as ${t.stems} tree${t.stems > 1 ? "s" : ""}: ${t.moves.length} moves, ${t.evaluations} evaluations. Select a tree to see what it tried.`);
  garden.onPick((stem, move) => { garden!.select(stem); panel.open(stem, move); });
  if (reduceMotion) { garden.setStep(garden.total); setState("The search", String(t.evaluations), `evaluations in ${t.moves.length} moves`); return Promise.resolve(); }
  garden.grow(); garden.setStep(0);
  const per = Math.min(90, 5000 / t.evaluations);
  return new Promise((resolve) => {
    let k = 0, mi = 0, inMove = 0;
    const tick = () => {
      if (mi >= t.moves.length) { resolve(); return; }
      k++; inMove++; garden!.setStep(k);
      setState("The search", String(k), `evaluations · move ${mi + 1} of ${log.max_moves}`);
      if (inMove >= t.moves[mi].candidates.length) { mi++; inMove = 0; }
      window.setTimeout(tick, per);
    };
    tick();
  });
}

async function land(r: AuditResult, paths: ReplicatePath[] | null, demo: Demo, panelBytes: ArrayBuffer, cls: string,
                    logText: string, log: any, wheel: string) {
  if (paths?.length) {
    const vals = paths.flatMap((p) => p.steps.map((s) => s.sharpe));
    const sc = scaleFor(vals, r.class_bar);
    const st = drawStreaks($("streaks") as unknown as SVGSVGElement, paths, sc.lo, sc.hi);
    if (reduceMotion) st.reveal(1);
    else await new Promise<void>((res) => { let i = 0; const n = 24; const t = () => { st.reveal(++i / n); if (i < n) window.setTimeout(t, 45); else res(); }; t(); });
  }
  const w = word(r.status);
  garden?.verdict(w);
  if (tree) {   // redraw with the submitted branch marked, now that it is known
    const sel = drawGarden(svg, tree, { interactive: true, bar: r.class_bar,
      submitted: { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } });
    sel.onPick((stem, move) => { sel.select(stem); panel.open(stem, move); });
    garden = sel;
  }
  setState("The verdict", w, `p ${r.p_replay === null ? "n/a" : r.p_replay.toFixed(4)} · B ${r.B.toLocaleString("en")}`);
  big.textContent = w;
  verdictCard(verdictBox, r, (box) => {
    const p = h("p", "fine", null, box);
    const a = h("a", null, "Its own page, the log and the record", p) as HTMLAnchorElement;
    a.href = `/result.html?ex=${demo.key}`;
  });
  await record(r, demo, panelBytes, cls, logText, log, wheel);
}

async function record(r: AuditResult, demo: Demo, panelBytes: ArrayBuffer, cls: string, logText: string, log: any, wheel: string) {
  const [panelSha, classSha, logSha] = await Promise.all([sha256Hex(panelBytes), sha256Hex(cls), sha256Hex(logText)]);
  const config = { alpha: r.alpha, B: r.B, class_sha256: classSha, log_sha256: logSha, panel_sha256: panelSha, seed: SEED, wheel };
  const configHash = await sha256Hex(JSON.stringify(config));
  const kv = $("rec-kv"); kv.replaceChildren();
  const rows: [string, string][] = [
    ["Class", `${log.class_name} · ${r.class_size} members`],
    ["Class hash", `${classSha}${classSha === log.class_sha256 ? "" : " (differs from the log's!)"}`],
    ["Panel hash", `${panelSha}${panelSha === log.panel_sha256 ? "" : " (differs from the log's!)"}`],
    ["Seeds", `search ${log.seed} · audit ${SEED}`],
    ["B", r.B.toLocaleString("en")],
    ["Config hash", configHash],
    ["Package", wheel],
  ];
  for (const [k, v] of rows) { h("dt", null, k, kv); h("dd", null, v, kv); }
  $("rec-cmd").textContent = command(demo, r.B, SEED);
  ($("rec-link") as HTMLAnchorElement).href = `/result.html?ex=${demo.key}`;
  const logBox = $("rec-log"); logBox.replaceChildren();
  for (const c of log.calls) {
    const p = h("p", null, null, logBox);
    h("b", null, c.tool, p);
    p.append(" ", c.refused ? `refused: ${c.refused}` : (c.text ?? "").replace(new RegExp("^" + c.tool + "(?=[\\s:])"), "").trim());
  }
  $("record").hidden = false;
}
