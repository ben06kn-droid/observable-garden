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
import { makeNotes } from "../notes";
import { branchSources, shakeable, woodOne, woodTwo } from "../woods";
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
// inside a run with several trees, the one being read is lit and the others dim
const litTree = (stem: number | null) => svg.querySelectorAll<SVGGElement>("[data-stem]").forEach((g) => g.classList.toggle("dimmed", stem !== null && Number(g.dataset.stem) !== stem));
const inside = makeRunView({ two, scene, panel: $("inside"), fx, tree: () => garden?.treeRect() ?? null, sparks, reduce: reduceMotion,
  onTree: litTree, isTree: (t) => !!t.closest?.("#garden .real .stem") });

// ---- the cut, and the scroll (scroll.ts)
const night = (on: boolean) => { body.dataset.page = on ? "two" : "one"; };
const scroll = startScroll({ main, two, night, reduce: reduceMotion, paused: () => inside.isOpen() });
document.querySelectorAll<HTMLAnchorElement>('a[href="#demo"]').forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); scroll.toTwo(); }));
// the header's name on this page: home without a reload (a carry back from page two); a modified click
// (a new tab or window) is left to the browser; inside a run, it closes the run first
document.querySelector<HTMLAnchorElement>(".top .brand")?.addEventListener("click", (e) => {
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  if (inside.isOpen()) { inside.close(); return; }
  scroll.home();
});

// ---- leaves and petals (particles.ts): page one's ground is its foot, page two's is the bed's
// parabola (bed.ts); page one's pile stays below its text
const textBox = () => { const t = document.querySelector(".one .copy")?.getBoundingClientRect(), b = one.getBoundingClientRect(); return t ? { l: t.left - b.left, r: t.right - b.left, below: one.clientHeight - (t.bottom - b.top) - 10 } : null; };
let text = textBox();
const leaves = new Field({ box: one, air: $("air-one") as HTMLCanvasElement, pile: $("pile-one") as HTMLCanvasElement, kind: "leaf", count: 90, start: 46,
  ground: () => one.clientHeight - 4,
  cap: (x) => (text && x > text.l - 20 && x < text.r + 20 ? Math.max(0, Math.min(26, text.below)) : 26) });
// the verdict written onto the drawing (notes.ts); the petals fade behind its labels and the choice
const notes = makeNotes(spot, two, () => bed.heads());
let choiceBox = { x: 0, y: 0, w: 0, h: 0 };
const petals = new Field({ box: two, air: $("air-two") as HTMLCanvasElement, pile: $("pile-two") as HTMLCanvasElement, kind: "petal", count: 80, start: 36,
  ground: (x) => { const W = two.clientWidth, u = (x - W / 2) / (W / 2); return two.clientHeight * (0.93 - 0.11 * u * u); },
  cap: () => (innerWidth < 760 ? 0 : 12), avoid: () => [...notes.boxes(), choiceBox] });
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
window.addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => { text = textBox(); woods(); city.draw(); placeSeed(); notes.place(); }, 200); });

// ---- page two: the run's tree in the spot, the bed along the bottom
const runBtn = $<HTMLButtonElement>("run");
const runs = new Map<string, { tree: SearchTree | null; result: AuditResult | null; refused?: string }>();
let shown: string | null = null, chosen: Demo, list: Demo[] = [];

function enter() {
  if (!shown || busy) return;
  const r = runs.get(shown), d = list.find((x) => x.key === shown)!;
  if (!r?.tree || (!r.result && !r.refused)) return;      // only once the verdict is in
  inside.open({ id: d.key, title: d.title, tree: r.tree, result: r.result, refused: r.refused });
  notes.entered();
}
$("bed").addEventListener("click", enter);

// the run's tree: every evaluation of the search a twig (garden.ts `twigs`); hovering only brightens
// it, a click (or Enter) goes inside once the verdict is in
function drawRun(d: Demo, t: SearchTree, r: AuditResult | null) {
  garden = drawGarden(svg, t, { interactive: true, halo: true, neon: true, canopy: false, twigs: true, bar: r?.class_bar,
    blossom: { kind: kindOf(d.key), colour: colourOf(d.key) },
    submitted: r ? { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } : undefined });
  garden.onPick((stem) => (inside.isOpen() ? inside.choose(stem) : enter()));   // inside, a click picks that tree
  requestAnimationFrame(placeChoice);
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
        shown = d.key; bed.reset(d.key); bed.finish(); settle(drawRun(d, r.tree, r.result)).bloom(r.refused ? 0 : 1); seed.classList.add("spent");
        if (r.result) { notes.verdict(garden!, r.result, r.tree.evaluations, SEED); below(r.result); } else if (r.refused) notes.refused(garden, r.refused, r.tree.evaluations);
      }
    });
  }
  markChip();
  placeSeed();
});
function markChip() { $("chips").querySelectorAll<HTMLButtonElement>(".chip[data-key]").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.key === chosen.key))); }

runBtn.addEventListener("click", () => { if (!busy) void run(chosen); });

async function run(demo: Demo) {
  busy = true; runBtn.disabled = true;
  $("record").hidden = true;
  const key = demo.key, B = demo.B;
  runs.set(key, { tree: null, result: null });
  shown = key; bed.reset(key); bed.start();     // the bed blooms on its own clock from the click
  svg.replaceChildren(); idleBox(); garden = null; notes.clear(); placeChoice();
  seed.classList.remove("spent");
  try {
    const [gate, loaded] = await Promise.all([loadGate(), loadDemo(demo)]);
    let searched: () => void = () => {};
    const searchShown = new Promise<void>((r) => { searched = r; });
    let replay = 0, searchDone = false;
    const showNull = () => notes.replay(`replay · ${Math.round(replay * B).toLocaleString("en")} of ${B.toLocaleString("en")}`);
    const out = await gate.audit({ ...loaded.inputs, B, seed: SEED }, {
      onSearch: (t) => { runs.get(key)!.tree = t; void grow(demo, t).then(() => { searchDone = true; garden?.bloomAll(2600); showNull(); searched(); }); },
      onProgress: (p) => { if (p.stage === "replay") replay = p.done / p.total; if (searchDone) showNull(); },
    });
    await searchShown;
    if (out.kind === "refused") {
      runs.get(key)!.refused = out.message;
      (garden as GardenHandle | null)?.bloom(0);
      notes.refused(garden, out.message, runs.get(key)!.tree?.evaluations ?? 0);
      return;
    }
    const r = out.result;
    runs.get(key)!.result = r;
    settle(drawRun(demo, runs.get(key)!.tree!, r)).bloom(1);     // the submitted branch and the bar, now known
    const tr = garden!.treeRect(), cr = ($("city") as HTMLElement).getBoundingClientRect();   // the verdict's pulse arrives at the tree's top
    city.pulseTo(tr.left + tr.width / 2 - cr.left, tr.top - cr.top);
    notes.verdict(garden!, r, runs.get(key)!.tree!.evaluations, SEED);
    below(r);
    await record(r, demo, loaded.inputs.panel, loaded.inputs.cls, loaded.inputs.log, loaded.logJson, gate.wheel);
  } catch (e) {
    notes.refused(garden, String((e as Error).message ?? e), 0, "ERROR");
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
  const [x, y] = tree && tree.width && innerWidth >= 760 ? freeSpot(box.offsetWidth, box.offsetHeight, tr) : [seedAt[0] + 34, seedAt[1] - box.offsetHeight - 64];   // clear of the pile on the ground
  box.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
  choiceBox = { x: x - 12, y: y - 8, w: box.offsetWidth + 24, h: box.offsetHeight + 16 };
}
// the first place in the upper left, scanning down then right, where the names touch no frond of a
// background tree and no cable (14 px clear): the text moves, never the drawing
function freeSpot(w: number, hgt: number, tr: DOMRect): [number, number] {
  const pts = [...branchSources(bgTwo, two), ...city.points()], pad = 14, W = tr.width, H = tr.height;
  const clear = (x: number, y: number) => pts.every((p) => !("x" in p ? p.x > x - pad && p.x < x + w + pad && p.y > y - pad && p.y < y + hgt + pad : p[0] > x - pad && p[0] < x + w + pad && p[1] > y - pad && p[1] < y + hgt + pad));
  for (let x = W * 0.045; x < W * 0.24 - w; x += 12) for (let y = 70; y < H * 0.6 - hgt; y += 8) if (clear(x, y)) return [x, y];
  return [W * 0.06, H * 0.34];
}
// a redrawn tree shows its blossoms as they were, without opening them again
function settle(g: GardenHandle) { svg.classList.add("settled"); requestAnimationFrame(() => requestAnimationFrame(() => svg.classList.remove("settled"))); return g; }
idleBox(); placeSeed();
bed.reset("idle");   // the ground and its line from the start; the flowers come with a run

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
function grow(d: Demo, t: SearchTree): Promise<void> {
  const g = drawRun(d, t, null);
  const finish = () => notes.search(g, g.total, "search", `${t.evaluations} evaluations`);
  if (reduceMotion) { g.setStep(g.total); seed.classList.add("spent"); finish(); return Promise.resolve(); }
  g.grow(); g.setStep(0);
  const per = Math.min(70, 4200 / t.evaluations);
  return new Promise((resolve) => {
    let k = 0, mi = 0, inMove = 0;
    const tick = () => {
      if (mi >= t.moves.length) { finish(); resolve(); return; }
      k++; inMove++; g.setStep(k);
      if (k === 1) seed.classList.add("spent");                // the trunk has grown out of the seed
      notes.search(g, k, t.moves[mi].kind, `${k} of ${t.evaluations}`);
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
