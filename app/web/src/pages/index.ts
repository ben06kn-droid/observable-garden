import { auditId, h, reduceMotion, sha256Hex, word } from "../common";
import { makeBed } from "../bed";
import { makeCity } from "../city";
import { command, demos, loadDemo, type Demo } from "../demos";
import { drawGarden, type GardenHandle } from "../garden";
import { loadGate } from "../gate";
import { colourOf, kindOf } from "../heads";
import { fall } from "../leaves";
import { makeRunInside } from "../runInside";
import { startScroll } from "../scroll";
import { woodOne, woodTwo } from "../woods";
import type { AuditResult, SearchTree } from "../types";
import { idleCard, verdictCard } from "../verdict";

const SEED = 0;
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const two = $("demo"), body = document.body, main = document.querySelector("main") as HTMLElement;

// ---- the cut, and the scroll (scroll.ts)
const night = (on: boolean) => { body.dataset.page = on ? "two" : "one"; };
const inside = makeRunInside($("inside"));
const scroll = startScroll({ main, two, night, reduce: reduceMotion, paused: () => inside.isOpen() });
document.querySelectorAll<HTMLAnchorElement>('a[href="#demo"]').forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); scroll.toTwo(); }));

// ---- the background trees (woods.ts): the restart example's search, from its log. Page one: eight
// tall and short trees in dark green. Page two: four of them at the edges as dim violet-pink neon.
// Leaves (page one) and petals (page two) are released from their buds.
const bgOne = $("bg-trees") as unknown as SVGSVGElement, bgTwo = $("wood2") as unknown as SVGSVGElement;
let backdrop: SearchTree | null = null;
const budsIn = (svg: SVGSVGElement, box: HTMLElement) => {
  const b = box.getBoundingClientRect();
  return Array.from(svg.querySelectorAll(".real .bud")).map((e) => e.getBoundingClientRect())
    .map((r) => ({ x: (r.left + r.width / 2 - b.left) / b.width, y: (r.top + r.height / 2 - b.top) / b.height }))
    .filter((p) => p.x > 0 && p.x < 1 && p.y > 0 && p.y < 0.97);
};
const drop = () => {
  fall($("leaves"), { n: 120, kind: "leaf", seed: 4, sources: budsIn(bgOne, $("overview")) });
  fall($("petals"), { n: 110, kind: "petal", seed: 8, sources: budsIn(bgTwo, two) });
};
const woods = () => { if (backdrop) { woodOne(bgOne, backdrop); woodTwo(bgTwo, backdrop); } };
fetch("/examples/overview-tree.json").then((r) => r.json()).then((tree: SearchTree) => {
  backdrop = tree;
  woods();
  requestAnimationFrame(drop);
}).catch(() => {});

// ---- the city around page two (city.ts): cables, pylons, signs; a pulse now and then
const city = makeCity($("city") as unknown as SVGSVGElement, reduceMotion);
city.draw();
city.start(() => body.dataset.page !== "two" || inside.isOpen() || document.hidden);
let resizeT = 0;
window.addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => { woods(); city.draw(); drop(); }, 200); });

// ---- page two: the run's tree in the spot, the bed along the bottom
const svg = $("garden") as unknown as SVGSVGElement;
const bed = makeBed($("bed") as unknown as SVGSVGElement, two);
const phase = $("phase"), big = $("big"), line = $("line"), runBtn = $<HTMLButtonElement>("run"), enterBtn = $<HTMLButtonElement>("enter");
const verdictBox = $("verdict");
idleCard(verdictBox, "Run an example to see its verdict here.");
const setState = (p: string, b: string, l: string) => { phase.textContent = p; big.textContent = b; line.textContent = l; };

const runs = new Map<string, { tree: SearchTree | null; result: AuditResult | null; refused?: string }>();
let shown: string | null = null, garden: GardenHandle | null = null, chosen: Demo, list: Demo[] = [], busy = false;

function enter() {
  if (!shown) return;
  const r = runs.get(shown), d = list.find((x) => x.key === shown)!;
  if (!r?.tree) return;
  inside.open({ id: d.key, title: d.title, tree: r.tree, result: r.result, refused: r.refused }, backdrop, garden?.treeRect() ?? null);
}
$("bed").addEventListener("click", enter);
enterBtn.addEventListener("click", enter);

function drawRun(d: Demo, t: SearchTree, r: AuditResult | null) {
  garden = drawGarden(svg, t, { interactive: true, halo: true, neon: true, canopy: false, bar: r?.class_bar,
    blossom: { kind: kindOf(d.key), colour: colourOf(d.key) },
    submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
  garden.onPick(() => enter());
  svg.setAttribute("aria-label", `${d.title}: the run's tree, ${t.moves.length} moves and ${t.evaluations} evaluations. Choose a tree to go inside the run.`);
  return garden;
}

demos().then((ds) => {
  list = ds; chosen = ds[0];
  const chips = $("chips");
  for (const d of ds) {
    const li = h("li", null, null, chips);
    const b = h("button", "chip", null, li) as HTMLButtonElement;
    b.type = "button"; b.dataset.key = d.key;
    b.append(d.title); h("small", null, d.about, b);
    b.addEventListener("click", () => {
      chosen = d; markChip();
      const r = runs.get(d.key);
      if (r?.tree && !busy) {                         // a run already made: show it as it ended
        shown = d.key; bed.reset(d.key); bed.grow(1); drawRun(d, r.tree, r.result).bloom(r.refused ? 0 : 1);
        if (r.result) verdictCard(verdictBox, r.result); enterBtn.hidden = false;
      }
    });
  }
  const li = h("li", null, null, chips);
  const rp = h("button", "chip", "82,240-member ETF class", li) as HTMLButtonElement;
  rp.type = "button"; rp.disabled = true;
  rp.title = "Too large for a browser: it will be a recorded replay of a local run. The format is in Docs; no recording yet.";
  h("small", null, "recorded replay · not yet", rp);
  markChip();
});
function markChip() { $("chips").querySelectorAll<HTMLButtonElement>(".chip[data-key]").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.key === chosen.key))); }

runBtn.addEventListener("click", () => { if (!busy) void run(chosen); });

async function run(demo: Demo) {
  busy = true; runBtn.disabled = true; enterBtn.hidden = true;
  idleCard(verdictBox, "Waiting for the verdict.");
  $("record").hidden = true;
  const key = demo.key, B = demo.B;
  runs.set(key, { tree: null, result: null });
  shown = key; bed.reset(key); bed.grow(0);
  svg.replaceChildren();
  try {
    setState("Loading", "the gate", "Python and the package, into your browser; once per visit.");
    const [gate, loaded] = await Promise.all([loadGate(), loadDemo(demo)]);
    let searched: () => void = () => {};
    const searchShown = new Promise<void>((r) => { searched = r; });
    let replay = 0, searchDone = false;
    const showNull = () => {
      garden?.bloom(replay); bed.grow(0.5 + 0.5 * replay);
      setState("The null", replay > 0 ? `${Math.round(replay * B).toLocaleString("en")}` : "re-running", `of ${B.toLocaleString("en")} replicates`);
    };
    setState("The search", "0", "evaluations");
    const out = await gate.audit({ ...loaded.inputs, B, seed: SEED }, {
      onSearch: (t) => { runs.get(key)!.tree = t; void grow(demo, t, loaded.logJson.max_moves).then(() => { searchDone = true; showNull(); searched(); }); },
      onProgress: (p) => { if (p.stage === "replay") replay = p.done / p.total; if (searchDone) showNull(); },
    });
    await searchShown;
    if (out.kind === "refused") {
      runs.get(key)!.refused = out.message;
      garden?.bloom(0);
      setState("Refused", "—", out.message);
      enterBtn.hidden = false;
      return;
    }
    const r = out.result;
    runs.get(key)!.result = r;
    drawRun(demo, runs.get(key)!.tree!, r).bloom(1);     // the submitted branch and the bar, now known
    bed.grow(1);
    const tr = garden!.treeRect(), cr = ($("city") as HTMLElement).getBoundingClientRect();   // the verdict's pulse arrives at the tree's top
    city.pulseTo(tr.left + tr.width / 2 - cr.left, tr.top - cr.top);
    const w = word(r.status);
    setState("The verdict", w, `p ${r.p_replay === null ? "n/a" : r.p_replay.toFixed(4)} · B ${r.B.toLocaleString("en")}`);
    verdictCard(verdictBox, r, (box) => {
      const p = h("p", "fine", null, box);
      const a = h("a", null, "Its own page, the log and the record", p) as HTMLAnchorElement;
      a.href = `/result.html?ex=${demo.key}`;
    });
    enterBtn.hidden = false;
    await record(r, demo, loaded.inputs.panel, loaded.inputs.cls, loaded.inputs.log, loaded.logJson, gate.wheel);
  } catch (e) {
    setState("Error", "—", String((e as Error).message ?? e));
  } finally {
    busy = false; runBtn.disabled = false;
  }
}

// the run's tree grows evaluation by evaluation in the log's order; the bed's first half follows it
function grow(d: Demo, t: SearchTree, maxMoves: number): Promise<void> {
  const g = drawRun(d, t, null);
  const finish = () => setState("The search", String(t.evaluations), `evaluations in ${t.moves.length} moves`);
  if (reduceMotion) { g.setStep(g.total); bed.grow(0.5); finish(); return Promise.resolve(); }
  g.grow(); g.setStep(0);
  const per = Math.min(70, 4200 / t.evaluations);
  return new Promise((resolve) => {
    let k = 0, mi = 0, inMove = 0;
    const tick = () => {
      if (mi >= t.moves.length) { finish(); resolve(); return; }
      k++; inMove++; g.setStep(k); bed.grow(0.5 * k / t.evaluations);
      setState("The search", String(k), `evaluations · move ${mi + 1} of ${maxMoves}`);
      if (inMove >= t.moves[mi].candidates.length) { mi++; inMove = 0; }
      window.setTimeout(tick, per);
    };
    tick();
  });
}

async function record(r: AuditResult, demo: Demo, panelBytes: ArrayBuffer, cls: string, logText: string, log: any, wheel: string) {
  const [panelSha, classSha, logSha] = await Promise.all([sha256Hex(panelBytes), sha256Hex(cls), sha256Hex(logText)]);
  const id = await auditId({ alpha: r.alpha, B: r.B, class_sha256: classSha, log_sha256: logSha, panel_sha256: panelSha, seed: SEED, wheel });
  const kv = $("rec-kv"); kv.replaceChildren();
  const rows: [string, string][] = [
    ["Class", `${log.class_name} · ${r.class_size} members`],
    ["Class hash", `${classSha}${classSha === log.class_sha256 ? "" : " (differs from the log's!)"}`],
    ["Panel hash", `${panelSha}${panelSha === log.panel_sha256 ? "" : " (differs from the log's!)"}`],
    ["Seeds", `search ${log.seed} · audit ${SEED}`],
    ["B", r.B.toLocaleString("en")],
    ["Audit id", id],
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
