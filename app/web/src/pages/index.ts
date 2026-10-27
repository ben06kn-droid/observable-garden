import { auditId, h, MEANING, reduceMotion, sha256Hex, word } from "../common";
import { makeBed } from "../bed";
import { makeCity } from "../city";
import { command, demos, loadDemo, type Demo } from "../demos";
import { Fx } from "../fx";
import { drawGarden, H as GH, SEED as SEED_AT, W as GW, type GardenHandle } from "../garden";
import { loadGate } from "../gate";
import { colourOf, kindOf } from "../heads";
import { SHAPES } from "../leaves";
import { Field, startLife } from "../particles";
import { makeRunView } from "../runView";
import { startScroll } from "../scroll";
import { makeSign } from "../sign";
import { branchSources, shakeable, shakeTree, woodOne, woodTwo } from "../woods";
import type { AuditResult, SearchTree } from "../types";

const SEED = 0;
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const two = $("demo"), one = $("overview"), body = document.body, main = document.querySelector("main") as HTMLElement, scene = $("scene");
const svg = $("garden") as unknown as SVGSVGElement, spot = $("spot"), seed = $("seed");

// ---- page two's effects canvas (fx.ts) and the run view (runView.ts)
const fx = new Fx($("fx") as HTMLCanvasElement, two);
const bed = makeBed($("bed") as unknown as SVGSVGElement, two);
let garden: GardenHandle | null = null;
const sparks = (): [number, number][] => {   // the heads the ring strikes lightning from: the bed's, and the blossoms on the run's tree
  const b = two.getBoundingClientRect();
  const blossoms = Array.from(svg.querySelectorAll(".blossom.open")).map((e) => { const r = e.getBoundingClientRect(); return [r.left + r.width / 2 - b.left, r.top + r.height / 2 - b.top] as [number, number]; });
  return [...bed.heads(), ...blossoms];
};
const inside = makeRunView({ two, scene, panel: $("inside"), fx, tree: () => garden?.treeRect() ?? null, sparks, reduce: reduceMotion });

// ---- the cut, and the scroll (scroll.ts)
const night = (on: boolean) => { body.dataset.page = on ? "two" : "one"; };
const scroll = startScroll({ main, two, night, reduce: reduceMotion, paused: () => inside.isOpen() });
document.querySelectorAll<HTMLAnchorElement>('a[href="#demo"]').forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); scroll.toTwo(); }));

// ---- leaves and petals (particles.ts): page one's ground is its foot, page two's is the bed's
// parabola (bed.ts); page one's pile stays below its text
const textBox = () => { const t = document.querySelector(".one .copy")?.getBoundingClientRect(), b = one.getBoundingClientRect(); return t ? { l: t.left - b.left, r: t.right - b.left, below: one.clientHeight - (t.bottom - b.top) - 10 } : null; };
let text = textBox();
const leaves = new Field({ box: one, air: $("air-one") as HTMLCanvasElement, pile: $("pile-one") as HTMLCanvasElement, kind: "leaf", count: 90, start: 46,
  ground: () => one.clientHeight - 4,
  cap: (x) => (text && x > text.l - 20 && x < text.r + 20 ? Math.max(0, Math.min(26, text.below)) : 26) });
const petals = new Field({ box: two, air: $("air-two") as HTMLCanvasElement, pile: $("pile-two") as HTMLCanvasElement, kind: "petal", count: 80, start: 36,
  ground: (x) => { const W = two.clientWidth, u = (x - W / 2) / (W / 2); return two.clientHeight * (0.93 - 0.11 * u * u); },
  cap: () => (innerWidth < 760 ? 0 : 12) });
let busy = false;
startLife({ fields: [leaves, petals], paused: () => inside.isOpen(), throttled: () => busy, reduce: reduceMotion });

// ---- the background trees (woods.ts): the restart example's search, from its log. Page one: eight
// tall and short trees in dark green. Page two: six at the edges as dim violet-pink neon. A click (or
// Enter) shakes one and sheds a burst from its branches.
const bgOne = $("bg-trees") as unknown as SVGSVGElement, bgTwo = $("wood2") as unknown as SVGSVGElement;
let backdrop: SearchTree | null = null;
const woods = () => {
  if (!backdrop) return;
  woodOne(bgOne, backdrop); woodTwo(bgTwo, backdrop);
  shakeable(bgOne, "Tree", (s) => leaves.burst(branchSources(bgOne, one, s), 16));
  shakeable(bgTwo, "Tree", (s) => petals.burst(branchSources(bgTwo, two, s), 16));
  leaves.setSources(branchSources(bgOne, one)); petals.setSources(branchSources(bgTwo, two));
};
fetch("/examples/overview-tree.json").then((r) => r.json()).then((tree: SearchTree) => { backdrop = tree; woods(); }).catch(() => {});

// ---- the city around page two (city.ts): cables, pylons, signs; a pulse now and then; a click strikes
const city = makeCity($("city") as unknown as SVGSVGElement, reduceMotion, fx);
city.draw();
city.start(() => body.dataset.page !== "two" || inside.isOpen() || document.hidden);
let resizeT = 0;
window.addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => { text = textBox(); woods(); city.draw(); placeSeed(); hangSign(); }, 200); });

// ---- the sign (sign.ts): the run state, then the verdict, hung level with the bar at the bed's right
const enterBtn = h("button", "enter", "Enter the run") as HTMLButtonElement; enterBtn.type = "button"; enterBtn.id = "enter"; enterBtn.hidden = true;
const sign = makeSign($("sign"), enterBtn);
function hangSign() {
  const b = two.getBoundingClientRect(), bar = svg.querySelector(".bar line");
  const y = bar ? bar.getBoundingClientRect().top - b.top : b.height * 0.46;
  const x = b.width * 0.77, W = b.width, u = (x - W / 2) / (W / 2);
  sign.hang(y, b.height * (0.93 - 0.11 * u * u));
}
sign.state("ready", "Ready", [["Choose", "an example by the seed, then run the gate"]]);
requestAnimationFrame(hangSign);

// ---- page two: the run's tree in the spot, the bed along the bottom
const runBtn = $<HTMLButtonElement>("run");
const runs = new Map<string, { tree: SearchTree | null; result: AuditResult | null; refused?: string }>();
let shown: string | null = null, chosen: Demo, list: Demo[] = [];

function enter() {
  if (!shown || busy) return;
  const r = runs.get(shown), d = list.find((x) => x.key === shown)!;
  if (!r?.tree || (!r.result && !r.refused)) return;      // only once the verdict is in
  inside.open({ id: d.key, title: d.title, tree: r.tree, result: r.result, refused: r.refused });
}
$("bed").addEventListener("click", enter);
enterBtn.addEventListener("click", enter);

// hovering the run's tree shakes it (its click enters the run), at most every 1.5 s, shedding petals
let lastShake = 0;
function drawRun(d: Demo, t: SearchTree, r: AuditResult | null) {
  garden = drawGarden(svg, t, { interactive: true, halo: true, neon: true, canopy: false, bar: r?.class_bar,
    blossom: { kind: kindOf(d.key), colour: colourOf(d.key) },
    submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
  garden.onPick(() => enter());
  svg.querySelectorAll<SVGGElement>(".real .stem").forEach((g) => g.addEventListener("pointerenter", () => {
    const now = performance.now();
    if (now - lastShake < 1500 || reduceMotion) return;
    lastShake = now;
    const s = Number(g.dataset.stem);
    shakeTree(svg, s); petals.burst(branchSources(svg, two, s), 10);
  }));
  requestAnimationFrame(() => { placeChoice(); hangSign(); });
  svg.setAttribute("aria-label", `${d.title}: the run's tree, ${t.moves.length} moves and ${t.evaluations} evaluations. Choose it to go inside the run once the verdict is in.`);
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
        if (r.result) { sign.verdict(r.result); below(r.result); } enterBtn.hidden = !(r.result || r.refused);
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
  $("record").hidden = true;
  const key = demo.key, B = demo.B;
  runs.set(key, { tree: null, result: null });
  shown = key; bed.reset(key); bed.grow(0);
  svg.replaceChildren(); idleBox(); garden = null; placeChoice(); hangSign();
  seed.classList.remove("spent");
  try {
    sign.state("loading", "Loading", [["Gate", "Python and the package, into your browser; once per visit"]]);
    const [gate, loaded] = await Promise.all([loadGate(), loadDemo(demo)]);
    let searched: () => void = () => {};
    const searchShown = new Promise<void>((r) => { searched = r; });
    let replay = 0, searchDone = false;
    const showNull = () => {
      garden?.bloom(replay); bed.grow(0.5 + 0.5 * replay);
      sign.state("null", "Null", [["Replicates", `${Math.round(replay * B).toLocaleString("en")} of ${B.toLocaleString("en")}`], ["Search", "re-run on noise, move for move"]]);
    };
    sign.state("search", "Search", [["Evaluated", "0"]]);
    const out = await gate.audit({ ...loaded.inputs, B, seed: SEED }, {
      onSearch: (t) => { runs.get(key)!.tree = t; void grow(demo, t, loaded.logJson.max_moves).then(() => { searchDone = true; showNull(); searched(); }); },
      onProgress: (p) => { if (p.stage === "replay") replay = p.done / p.total; if (searchDone) showNull(); },
    });
    await searchShown;
    if (out.kind === "refused") {
      runs.get(key)!.refused = out.message;
      (garden as GardenHandle | null)?.bloom(0);
      sign.state("refused", "Refused", [["Reason", out.message]]);
      enterBtn.hidden = false;
      return;
    }
    const r = out.result;
    runs.get(key)!.result = r;
    drawRun(demo, runs.get(key)!.tree!, r).bloom(1);     // the submitted branch and the bar, now known
    bed.grow(1);
    const tr = garden!.treeRect(), cr = ($("city") as HTMLElement).getBoundingClientRect();   // the verdict's pulse arrives at the tree's top
    city.pulseTo(tr.left + tr.width / 2 - cr.left, tr.top - cr.top);
    sign.verdict(r);
    requestAnimationFrame(hangSign);
    enterBtn.hidden = false;
    below(r);
    await record(r, demo, loaded.inputs.panel, loaded.inputs.cls, loaded.inputs.log, loaded.logJson, gate.wheel);
  } catch (e) {
    sign.state("error", "Error", [["Reason", String((e as Error).message ?? e)]]);
  } finally {
    busy = false; runBtn.disabled = false;
  }
}

// the verdict's meaning and its reasons, below the fold, as plain type
function below(r: AuditResult) {
  $("rec-meaning").textContent = `${word(r.status)}: ${MEANING[word(r.status)] ?? ""}`;
  const ul = $("rec-reasons"); ul.replaceChildren();
  for (const x of r.reasons) h("li", null, x, ul);
}

// ---- the seed: before a run, a bright point in the ground where the trunk will stand (the garden's
// own trunk position, garden.ts SEED), breathing, with one swaying sprout, and the three examples
// beside it as the choice. Run grows the trunk out of it (the trunk scales up from its foot), so the
// idle is the run's first frame. For an example with restarts, the first tree stands here.
function idleBox() { svg.setAttribute("viewBox", `0 0 ${GW} ${GH}`); svg.setAttribute("preserveAspectRatio", "xMidYMax meet"); svg.classList.add("garden"); }
let seedAt: [number, number] = [0, 0];
function placeSeed() {
  if (!svg.getAttribute("viewBox")) idleBox();
  const m = svg.getScreenCTM(), sr = spot.getBoundingClientRect();
  if (!m) return;
  const p = svg.createSVGPoint(); p.x = SEED_AT[0]; p.y = SEED_AT[1];
  const q = p.matrixTransform(m), tr = two.getBoundingClientRect();
  seed.style.transform = `translate3d(${(q.x - sr.left).toFixed(1)}px, ${(q.y - sr.top).toFixed(1)}px, 0)`;
  seedAt = [q.x - tr.left, q.y - tr.top];                    // in the section's pixels
  placeChoice();
}
// the choice sits beside the seed; once a tree stands there it moves to the dark upper left, level with
// the sign across the page, where no branch, flower or petal pile sits behind the names
function placeChoice() {
  const box = $("choice"), tr = two.getBoundingClientRect(), tree = svg.querySelector(".real") ? garden?.treeRect() : null;
  const [x, y] = tree && tree.width && innerWidth >= 760 ? [tr.width * 0.06, tr.height * 0.34] : [seedAt[0] + 34, seedAt[1] - box.offsetHeight - 64];   // clear of the pile on the ground
  box.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
}
idleBox(); placeSeed();
bed.reset("idle"); bed.grow(0);   // the ground and its line from the start; the flowers come with a run

// ---- a petal now and then lands on the bar (once a run has drawn it), rests, slides off an end and
// falls. Decoration on the gate's bar: it reads where the bar is, nothing else.
const barPetal = document.createElementNS("http://www.w3.org/2000/svg", "svg");
barPetal.setAttribute("viewBox", "-10 -10 20 20"); barPetal.setAttribute("class", "bar-petal"); barPetal.setAttribute("aria-hidden", "true");
barPetal.innerHTML = `<path d="${SHAPES.petal}"></path>`;
spot.appendChild(barPetal);
function petalOnBar() {
  const lines = Array.from(svg.querySelectorAll(".bar line"));
  if (!reduceMotion && lines.length && body.dataset.page === "two" && !inside.isOpen() && !document.hidden) {
    const l0 = lines[0].getBoundingClientRect(), l1 = lines[lines.length - 1].getBoundingClientRect(), sr = spot.getBoundingClientRect(), s = 12;
    const left = l0.left - sr.left, right = l1.right - sr.left, y = l0.top - sr.top - s * 0.75, dir = Math.random() < 0.5 ? -1 : 1;
    const x = left + (right - left) * (0.2 + Math.random() * 0.6), end = dir > 0 ? right : left - s, r0 = Math.random() * 90;
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

// the run's tree grows evaluation by evaluation in the log's order; the bed's first half follows it
function grow(d: Demo, t: SearchTree, maxMoves: number): Promise<void> {
  const g = drawRun(d, t, null);
  const finish = () => sign.state("search", "Search", [["Evaluated", String(t.evaluations)], ["Moves", String(t.moves.length)]]);
  if (reduceMotion) { g.setStep(g.total); bed.grow(0.5); seed.classList.add("spent"); finish(); return Promise.resolve(); }
  g.grow(); g.setStep(0);
  const per = Math.min(70, 4200 / t.evaluations);
  return new Promise((resolve) => {
    let k = 0, mi = 0, inMove = 0;
    const tick = () => {
      if (mi >= t.moves.length) { finish(); resolve(); return; }
      k++; inMove++; g.setStep(k); bed.grow(0.5 * k / t.evaluations);
      if (k === 1) seed.classList.add("spent");                // the trunk has grown out of the seed
      sign.state("search", "Search", [["Move", t.moves[mi].kind], ["Evaluated", `${k} of ${t.evaluations}`], ["Moves", `${mi + 1} of ${maxMoves}`]]);
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
