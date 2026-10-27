import { auditId, h, reduceMotion, sha256Hex, word } from "../common";
import { makeBed } from "../bed";
import { makeCity } from "../city";
import { command, demos, loadDemo, type Demo } from "../demos";
import { drawGarden, H as GH, SEED as SEED_AT, W as GW, type GardenHandle } from "../garden";
import { loadGate } from "../gate";
import { colourOf, kindOf } from "../heads";
import { fall, SHAPES } from "../leaves";
import { startLife } from "../life";
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
  requestAnimationFrame(placeChoice);
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
        shown = d.key; bed.reset(d.key); bed.grow(1); drawRun(d, r.tree, r.result).bloom(r.refused ? 0 : 1); seed.classList.add("spent");
        if (r.result) verdictCard(verdictBox, r.result); enterBtn.hidden = false;
      }
    });
  }
  markChip();
  placeSeed();
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
  svg.replaceChildren(); idleBox(); placeChoice();
  seed.classList.remove("spent");
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

// ---- the seed: before a run, a bright point in the ground where the trunk will stand (the garden's
// own trunk position, garden.ts SEED), breathing, with one swaying sprout, and the three examples
// beside it as the choice. Run grows the trunk out of it (the trunk scales up from its foot), so the
// idle is the run's first frame. For an example with restarts, the first tree stands here.
const spot = $("spot"), seed = $("seed");
function idleBox() { svg.setAttribute("viewBox", `0 0 ${GW} ${GH}`); svg.setAttribute("preserveAspectRatio", "xMidYMax meet"); svg.classList.add("garden"); }
function placeSeed() {
  if (!svg.getAttribute("viewBox")) idleBox();
  const m = svg.getScreenCTM(), sr = spot.getBoundingClientRect();
  if (!m) return;
  const p = svg.createSVGPoint(); p.x = SEED_AT[0]; p.y = SEED_AT[1];
  const q = p.matrixTransform(m), x = q.x - sr.left, y = q.y - sr.top;
  seed.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
  seedAt = [q.x, q.y];
  placeChoice();
}
// the choice sits in the section, over the bed: beside the seed, and once a tree stands there, just
// past the tree's right edge so no branch crosses a name
let seedAt: [number, number] = [0, 0];
function placeChoice() {
  const list = $("chips"), tr = two.getBoundingClientRect(), tree = svg.querySelector(".real") ? garden?.treeRect() : null;
  const x = tree && tree.width ? Math.max(seedAt[0] + 34, tree.right + 28) : seedAt[0] + 34;
  list.style.transform = `translate3d(${(x - tr.left).toFixed(1)}px, ${(seedAt[1] - tr.top - list.offsetHeight - 18).toFixed(1)}px, 0)`;
}
idleBox(); placeSeed();
window.addEventListener("resize", () => requestAnimationFrame(placeSeed));

// ---- a petal now and then lands on the bar (once a run has drawn it), rests, slides off an end and
// falls. Decoration on the gate's bar: it reads where the bar is, nothing else.
const barPetal = document.createElementNS("http://www.w3.org/2000/svg", "svg");
barPetal.setAttribute("viewBox", "-10 -10 20 20"); barPetal.setAttribute("class", "sprite p bar-petal"); barPetal.setAttribute("aria-hidden", "true");
barPetal.innerHTML = `<path d="${SHAPES.petal}"></path>`;
spot.appendChild(barPetal);
function petalOnBar() {
  const line = svg.querySelector(".bar line");
  if (!reduceMotion && line && body.dataset.page === "two" && !inside.isOpen() && !document.hidden) {
    const lr = line.getBoundingClientRect(), sr = spot.getBoundingClientRect(), s = 12;
    const x = lr.left - sr.left + lr.width * (0.2 + Math.random() * 0.6), y = lr.top - sr.top - s * 0.75, dir = Math.random() < 0.5 ? -1 : 1;
    const end = dir > 0 ? lr.right - sr.left : lr.left - sr.left - s, r0 = Math.random() * 90;
    const T = (px: number, py: number, r: number) => `translate3d(${px.toFixed(1)}px, ${py.toFixed(1)}px, 0) rotate(${r.toFixed(0)}deg)`;
    barPetal.animate([
      { transform: T(x - dir * 40, y - 160, r0), opacity: 0 },
      { transform: T(x, y, r0 + 140), opacity: 1, offset: 0.32, easing: "cubic-bezier(.3, .6, .4, 1)" },
      { transform: T(x, y, r0 + 140), opacity: 1, offset: 0.5, easing: "cubic-bezier(.5, 0, .9, .6)" },
      { transform: T(end, y + 2, r0 + 140 + dir * 25), opacity: 1, offset: 0.82 },
      { transform: T(end + dir * 24, y + 150, r0 + 330), opacity: 0 },
    ], { duration: 7200, easing: "linear" });
  }
  window.setTimeout(petalOnBar, 9000 + Math.random() * 7000);
}
window.setTimeout(petalOnBar, 6000);

// ---- life before anything is clicked (life.ts): the cursor's trail, its wind, the piles, the gusts
startLife({ one: $("overview"), two, leaves: $("leaves"), petals: $("petals"),
  textOne: () => document.querySelector(".one .copy")?.getBoundingClientRect() ?? null,
  paused: () => inside.isOpen() || scroll.carrying() });

// the run's tree grows evaluation by evaluation in the log's order; the bed's first half follows it
function grow(d: Demo, t: SearchTree, maxMoves: number): Promise<void> {
  const g = drawRun(d, t, null);
  const finish = () => setState("The search", String(t.evaluations), `evaluations in ${t.moves.length} moves`);
  if (reduceMotion) { g.setStep(g.total); bed.grow(0.5); seed.classList.add("spent"); finish(); return Promise.resolve(); }
  g.grow(); g.setStep(0);
  const per = Math.min(70, 4200 / t.evaluations);
  return new Promise((resolve) => {
    let k = 0, mi = 0, inMove = 0;
    const tick = () => {
      if (mi >= t.moves.length) { finish(); resolve(); return; }
      k++; inMove++; g.setStep(k); bed.grow(0.5 * k / t.evaluations);
      if (k === 1) seed.classList.add("spent");                // the trunk has grown out of the seed
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
