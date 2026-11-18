// The demo (demo.html; DESIGN.md 3, demo): three bundled searches, each run through the gate in the browser. One
// search is drawn as one tree (src/runtree.ts, src/demotree.ts) growing in search order, the repeated searches as a
// bed of small flowers (src/demobed.ts), the stages told in plain words in one fixed place, the verdict under them.
// After the verdict, the tree opens the run: a panel over the text column, beside the tree, telling every move in a
// sentence from the log. The cursor's tail (src/cursorwake.ts) acts on the tree, the bed and the backdrop, inside a
// run as outside it, under the text and never on the panel.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/demo-page.css";
import { auditId, h, MEANING, reduceMotion, sha256Hex, word } from "../common";
import { command, demos, loadDemo, type Demo } from "../demos";
import { loadGate } from "../gate";
import { buildRunTree, type RunTree } from "../runtree";
import { drawTree, treeFrame, type TreeView } from "../demotree";
import { makeBed } from "../demobed";
import { svgPart, WakeLayer } from "../cursorwake";
import type { AuditResult, Progress, SearchTree } from "../types";

const SEED = 0;
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const section = $("demo"), stage = $("stage"), svg = $("tree") as unknown as SVGSVGElement, bedCv = $("bed") as HTMLCanvasElement;
const rowsEl = $("rows"), startBtn = $<HTMLButtonElement>("start"), sayEl = $("say"), countEl = $("count");
const verdictEl = $("verdict"), panel = $("inside"), panelBody = $("in-body"), panelTitle = $("in-h");
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, reduceMotion ? Math.min(ms, 400) : ms));
const fmtB = (n: number) => n.toLocaleString("en");

// what each search is, and what to watch for
const ABOUT: Record<string, string> = {
  nothing: "Two moves on a panel with a weak edge. Does it stand out?",
  planted: "The same two moves, a strong rule planted. Watch it stand clear.",
  restart: "Swaps, flips, seven restarts. Watch luck reach higher too.",
};

interface Run { demo: Demo; tree: SearchTree | null; rt: RunTree | null; result: AuditResult | null; refused?: string; log: any; submitted: { rule: string; sharpe: number; text: string } | null }
const runs = new Map<string, Run>();
let list: Demo[] = [], chosen: Demo | null = null, shown: string | null = null, busy = false, growing = false;
let view: TreeView | null = null;

// ---- the status: one or two short lines in a fixed place
function say(text: string | (string | Node)[], count = "") {
  sayEl.replaceChildren(...(typeof text === "string" ? [text] : text));
  countEl.textContent = count;
}
const ruleSpan = (r: string, sub = true) => { const s = document.createElement("span"); s.className = sub ? "rule sub" : "rule"; s.textContent = r; return s; };

// ---- the bed, in the tree's frame
const bed = makeBed(bedCv, () => treeFrame(svg, stage), 64);
let half = 330;

// ---- the cursor's tail: the trail over the tree, the bed and the backdrop, under the text, never on the panel
const lightEl = section.querySelector<HTMLElement>(".dm-light")!;
const ground = (c: CanvasRenderingContext2D, w: number, hgt: number) => {
  c.fillStyle = getComputedStyle(document.body).backgroundColor || "#07060b"; c.fillRect(0, 0, w, hgt);
  const r = lightEl.getBoundingClientRect(), b = section.getBoundingClientRect();
  const cx = r.left - b.left + r.width / 2, cy = r.top - b.top + r.height / 2;
  c.save(); c.translate(cx, cy); c.scale(r.width / 2, r.height / 2);
  const g = c.createRadialGradient(0, 0, 0, 0, 0, 1);
  g.addColorStop(0, "rgba(68, 184, 255, 0.10)"); g.addColorStop(0.55, "rgba(68, 184, 255, 0.045)"); g.addColorStop(1, "rgba(68, 184, 255, 0)");
  c.fillStyle = g; c.fillRect(-1, -1, 2, 2); c.restore();
};
const box = (e: Element) => { const r = e.getBoundingClientRect(), b = section.getBoundingClientRect(); return { x: r.left - b.left, y: r.top - b.top, w: r.width, h: r.height }; };
const treePart = svgPart(section, () => [svg]);
const wake = new WakeLayer({ host: section, ground,
  mount: { parent: stage, before: null },
  parts: () => [treePart, bedCv],
  bends: () => false,
  keep: () => (panel.hidden ? [] : [box(panel)]),
  active: () => true,
  moving: () => growing,
  minRepaint: 250,
  // the trail's shape and life as before (2026-11-18): halfway between the narrow line and the docs tail, life x 0.65
  scale: { cell: 6.5, flow: 0.35625, curl: 41.6, force: 0.8, fade: 0.495 * 0.65,
           dye: 1.5, dyeWidth: 17.2 / 1.5, dyeGrow: 24 / 1.5, dyeFlow: 0.26625, dyeFade: 0.42 * 0.65 } });
new MutationObserver(() => wake.invalidate()).observe(svg, { subtree: true, childList: true, attributes: true, attributeFilter: ["d", "class"] });

// ---- the searches: numbered rows, one Start
function markRows() {
  rowsEl.querySelectorAll<HTMLButtonElement>(".dm-row").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.key === chosen?.key));
    b.disabled = busy;
    const r = runs.get(b.dataset.key!), tag = b.querySelector(".r")!;
    tag.textContent = r?.result ? `${word(r.result.status)} · p ${r.result.p_replay?.toFixed(4) ?? "n/a"}` : r?.refused ? "Refused" : "";
  });
  const done = chosen && runs.get(chosen.key)?.result;
  startBtn.textContent = busy ? "Running" : done ? "Start again" : "Start";
  startBtn.disabled = busy || !chosen;
}
demos().then((ds) => {
  list = ds; chosen = ds[0];
  ds.forEach((d, i) => {
    const li = h("li", null, null, rowsEl);
    const b = h("button", "dm-row", null, li) as HTMLButtonElement;
    b.type = "button"; b.dataset.key = d.key;
    h("span", "n", String(i + 1).padStart(2, "0"), b); h("span", "t", d.title, b); h("span", "r", null, b); h("span", "a", ABOUT[d.key] ?? d.about, b);
    b.addEventListener("click", () => { if (busy) return; chosen = d; markRows(); showFinished(d.key); });
  });
  markRows();
});
startBtn.addEventListener("click", () => { if (!busy && chosen) void run(chosen); });

// ---- idle: the ground and the seed where the trunk will stand
function idle() {
  svg.replaceChildren(); view = null; shown = null;
  svg.setAttribute("viewBox", "-330 -745 660 790"); svg.setAttribute("preserveAspectRatio", "xMidYMax meet");
  const NS = "http://www.w3.org/2000/svg";
  const l = document.createElementNS(NS, "line"); l.setAttribute("class", "ground"); l.setAttribute("x1", "-330"); l.setAttribute("x2", "330"); l.setAttribute("y1", "0.3"); l.setAttribute("y2", "0.3"); svg.append(l);
  const c = document.createElementNS(NS, "circle"); c.setAttribute("class", "node"); c.setAttribute("cx", "0"); c.setAttribute("cy", "-2.4"); c.setAttribute("r", "2.2"); svg.append(c);
  svg.classList.remove("ready"); svg.removeAttribute("tabindex"); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "The run's tree. Choose a search and press Start.");
  bed.clear();
}
idle();

// the submitted rule, from the log's own submit call: its support named by the tree's features, its score as logged
function submittedOf(log: any, t: SearchTree): Run["submitted"] {
  const call = [...(log.calls ?? [])].reverse().find((c: any) => c.tool === "submit" && c.ok !== false);
  if (!call?.state?.support) return null;
  const rule = call.state.support.map(([k, s]: [number, number]) => (s > 0 ? "+" : "-") + t.feature_names[k]).join(" ");
  const m = /sharpe (-?[\d.]+)/.exec(call.text ?? "");
  return { rule, sharpe: call.state.score, text: m ? m[1] : String(call.state.score) };
}

// ---- a run
async function run(demo: Demo) {
  busy = true; shown = demo.key; closeInside(false);
  verdictEl.hidden = true; $("record").hidden = true;
  idle(); shown = demo.key; markRows();
  const B = demo.B;
  const r: Run = { demo, tree: null, rt: null, result: null, log: null, submitted: null };
  runs.set(demo.key, r);
  say("The gate is loading in your browser. The first time takes a few seconds.");
  try {
    const [gate, loaded] = await Promise.all([loadGate(), loadDemo(demo)]);
    r.log = loaded.logJson;
    const alpha = Number(loaded.logJson.alpha ?? 0.05);
    let gotTree: () => void = () => {};
    const treeIn = new Promise<void>((res) => { gotTree = res; });
    const prog: Partial<Record<Progress["stage"], Progress>> = {};
    let phase: "search" | "repeat" | "after" = "search";
    const repeatCount = () => {
      const p = prog.replay;
      countEl.textContent = p ? `Search ${fmtB(p.done)} of ${fmtB(p.total)}` : "Resampling the data";
    };
    say("The agent searches. Every rule it scores is recorded.");
    const outP = gate.audit({ ...loaded.inputs, B, seed: SEED }, {
      onSearch: (t) => { r.tree = t; r.submitted = submittedOf(loaded.logJson, t); r.rt = buildRunTree(t, { submitted: r.submitted }); gotTree(); },
      onProgress: (p) => { prog[p.stage] = p; if (phase === "repeat") repeatCount(); },
    });
    await Promise.race([treeIn, outP]);
    if (!r.rt || !r.tree) { const out = await outP; throw new Error(out.kind === "refused" ? out.message : "The gate returned no search."); }
    await grow(r.rt, r.tree);

    // what was submitted
    view!.showPink(true); view!.bloom("submitted");
    if (r.submitted) say(["The agent submits its best: ", ruleSpan(r.submitted.rule), `, in-sample Sharpe ${r.submitted.text}.`], `Search complete · ${r.tree.evaluations} rules scored`);
    await sleep(2200);

    // the search repeated on data with nothing in it
    phase = "repeat";
    say(`The gate now repeats the same search ${fmtB(B)} times, on resampled data where no rule has a real edge.`);
    repeatCount();
    bed.reset(demo.key, half);
    if (reduceMotion) bed.finish(); else bed.start();
    const [out] = await Promise.all([outP, sleep(3200)]);
    phase = "after";
    if (out.kind === "refused") { r.refused = out.message; finishRefused(r); return; }
    r.result = out.result;

    // the level a result must clear
    say(`To pass, the submitted Sharpe must beat what at least ${Math.round((1 - alpha) * 100)} in 100 of those searches reach.`, `α ${alpha}`);
    await sleep(2400);
    bed.finish();
    showVerdict(r);
    await record(r.result, demo, loaded.inputs.panel, loaded.inputs.cls, loaded.inputs.log, loaded.logJson, gate.wheel);
  } catch (e) {
    say(`The run stopped: ${String((e as Error).message ?? e)}`);
  } finally {
    busy = false; growing = false; markRows();
  }
}

// the tree grows rule by rule in the log's order; the count says how far the search has come
function grow(rt: RunTree, t: SearchTree): Promise<void> {
  view = drawTree(svg, rt);
  half = Math.max(160, Math.max(-rt.l, rt.r) + 24);
  bed.reset(shown ?? "", half);
  view.bloom("growing");
  const E = rt.evaluations, M = t.moves.length;
  const moveOf: number[] = []; t.moves.forEach((m, i) => m.candidates.forEach(() => moveOf.push(i)));
  const counter = (k: number) => { const i = Math.min(E, Math.max(0, Math.floor(k))); countEl.textContent = `Move ${Math.min(M, (moveOf[Math.min(i, E - 1)] ?? 0) + 1)} of ${M} · rule ${i} of ${E}`; };
  if (reduceMotion) { view.setAt(E + 1); counter(E); return Promise.resolve(); }
  const per = Math.max(12, Math.min(120, 5200 / E));
  growing = true;
  return new Promise((resolve) => {
    const t0 = performance.now();
    let last = -2;
    const frame = (now: number) => {
      const at = (now - t0) / per - 1;
      view!.setAt(Math.min(at, E + 1));
      if (Math.floor(at) !== last) { last = Math.floor(at); counter(at); }
      if (at < E + 1) requestAnimationFrame(frame); else { growing = false; counter(E); resolve(); }
    };
    requestAnimationFrame(frame);
  });
}

function showVerdict(r: Run) {
  const res = r.result!, w = word(res.status), alpha = res.alpha;
  const meaning = MEANING[w] ?? "";
  say(`${w}. ${meaning.replace(/^./, (x) => (x === "p" ? x : x.toUpperCase()))}`);
  $("v-word").textContent = w;
  $("v-nums").textContent = `p ${res.p_replay?.toFixed(4) ?? "n/a"} against α ${alpha}, over ${fmtB(res.B)} repeated searches`;
  verdictEl.hidden = false;
  view?.bloom("none");
  makeOpenable(r);
  $("rec-meaning").textContent = `${w}: ${meaning}`;
  const ul = $("rec-reasons"); ul.replaceChildren();
  for (const x of res.reasons) h("li", null, x, ul);
}
function finishRefused(r: Run) {
  say(`The gate refused this run: ${r.refused}`);
  $("v-word").textContent = "REFUSED"; $("v-nums").textContent = ""; verdictEl.hidden = false;
  makeOpenable(r);
}
function makeOpenable(r: Run) {
  svg.classList.add("ready"); svg.setAttribute("tabindex", "0"); svg.setAttribute("role", "button");
  svg.setAttribute("aria-label", `${r.demo.title}: the run's tree, ${r.tree?.moves.length ?? 0} moves and ${r.tree?.evaluations ?? 0} rules scored. Open the run.`);
}

// a search already run: shown as it ended
function showFinished(key: string) {
  const r = runs.get(key);
  closeInside(false);
  if (!r?.rt || !r.tree || (!r.result && !r.refused)) { idle(); verdictEl.hidden = true; $("record").hidden = true; say("Choose a search and press Start."); return; }
  shown = key;
  view = drawTree(svg, r.rt); half = Math.max(160, Math.max(-r.rt.l, r.rt.r) + 24);
  view.setAt(r.rt.evaluations + 1); view.showPink(true);
  bed.reset(key, half); bed.finish();
  if (r.result) { showVerdict(r); $("record").hidden = false; } else finishRefused(r);
}

// ---- inside a run
function openInside() {
  const r = shown ? runs.get(shown) : null;
  if (busy || !r?.tree || (!r.result && !r.refused)) return;
  panelTitle.textContent = r.demo.title;
  fillInside(r);
  panel.hidden = false; section.classList.add("inside-open");
  panelTitle.focus();
  if (innerWidth <= 812) panel.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
  wake.invalidate();
}
function closeInside(refocus = true) {
  if (panel.hidden) return;
  panel.hidden = true; section.classList.remove("inside-open");
  if (refocus) svg.focus();
}
svg.addEventListener("click", () => { if (svg.classList.contains("ready")) (panel.hidden ? openInside() : closeInside()); });
svg.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && svg.classList.contains("ready")) { e.preventDefault(); panel.hidden ? openInside() : closeInside(); } });
$("in-close").addEventListener("click", () => closeInside());
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden && !document.querySelector(".top.open")) { e.preventDefault(); closeInside(); } });

// the run told move by move, from the log's own words and numbers
const SEARCH = new Set(["init", "extend_best", "swap_worst", "flip", "restart"]);
const TRIES: Record<string, string> = {
  init: "Scored every one-feature rule",
  extend_best: "Tried adding one more feature to its rule",
  swap_worst: "Tried swapping out each feature of its rule",
  restart: "Started again from the ground, as its declared rule says",
};
function fillInside(r: Run) {
  const t = r.tree!, log = r.log, names = t.feature_names;
  const named = (idx: string) => idx.split(",").map((x) => x.trim()).filter(Boolean).map((x) => (x.endsWith("+") ? "+" : "-") + names[Number(x.slice(0, -1))]).join(" ");
  panelBody.replaceChildren();
  const calls: any[] = log?.calls ?? [];
  let k = 0, moves = 0, best: string | null = null, lastRefused: any = null, pred: any = null;
  const items: { p: (string | Node)[]; tool: string; refused?: string }[] = [];
  for (const c of calls) {
    const text: string = c.text ?? "";
    if (c.ok === false) {
      items.push({ p: [`Tried to ${c.tool === "restart" ? "start again" : c.tool.replace(/_/g, " ")}; refused: ${text}.`], tool: c.tool, refused: text });
      if (SEARCH.has(c.tool)) lastRefused = c;
      continue;
    }
    if (c.tool === "declare_triggers") {
      const tr = (c.args?.triggers ?? []).map((x: any) => {
        // the gate's own definitions (quixote/session.py): a move's gain is its score less the best before it; failures
        // count the moves in a row that do not beat the best (an improvement or a restart starts the count again)
        const cond = x.trigger === "last_gain_at_most" ? (Number(x.param) === 0 ? "once a move does not beat its best" : `once a move beats its best by ${x.param} or less`)
          : x.trigger === "failures_at_least" ? `after ${x.param} moves in a row that do not beat its best` : `${x.trigger} ${x.param}`;
        return `${x.action} ${cond}`;
      }).join("; ");
      items.push({ p: [`Declared its rule before searching: ${tr}.`], tool: c.tool });
      continue;
    }
    if (c.tool === "predict") {
      const m = /prediction (-?[\d.]+) \(sd ([\d.]+)\)/.exec(text);
      pred = m ? { mean: m[1], sd: m[2] } : { mean: c.args?.mean, sd: c.args?.sd };
      items.push({ p: [`Recorded a prediction for its rule: ${pred.mean} (sd ${pred.sd}).`], tool: c.tool }); continue;
    }
    if (c.tool === "submit") {
      const m = /submitted \[([^\]]*)\] sharpe (-?[\d.]+)/.exec(text);
      items.push({ p: ["Submitted ", ruleSpan(m ? named(m[1]) : r.submitted?.rule ?? ""), ` at in-sample Sharpe ${m ? m[2] : ""}.`], tool: c.tool });
      continue;
    }
    // a search move: what it tried, how many rules it scored (the gate's re-execution of the log), what it kept
    const tm = t.moves[k];
    const n = tm && tm.kind === c.tool ? tm.candidates.length : null;
    if (SEARCH.has(c.tool) || /kept:/.test(text)) { k++; moves++; }
    let m = /kept: \[([^\]]*)\] sharpe (-?[\d.]+) \(best (-?[\d.]+)/.exec(text);
    const rs = /restarted on (.+?): \[([^\]]*)\] sharpe (-?[\d.]+) \(best (-?[\d.]+)\)/.exec(text);
    const tries = c.tool === "flip" ? `Flipped the sign of ${names[c.args?.feature] ?? "a feature"}` : TRIES[c.tool] ?? c.tool.replace(/_/g, " ");
    const scored = n !== null ? ` (${n} rule${n === 1 ? "" : "s"})` : "";
    if (rs) m = [rs[0], rs[2], rs[3], rs[4]] as unknown as RegExpExecArray;
    if (m) {
      const sub = r.submitted && named(m[1]) === r.submitted.rule && m[2] === r.submitted.text;
      const stays = m[3] !== m[2] ? ` Its best stays ${m[3]}.` : "";
      best = best === null || Number(m[3]) > Number(best) ? m[3] : best;
      // a restart: the rule it starts again from, chosen among the one-feature rules it scored
      if (c.tool === "restart") items.push({ p: [`Started again from the ground, as its declared rule says: it scored ${n ?? "the"} one-feature rules and began again from `, ruleSpan(named(m[1]), !!sub), ` at Sharpe ${m[2]}.${stays}`], tool: c.tool });
      else items.push({ p: [`${tries}${scored} and kept `, ruleSpan(named(m[1]), !!sub), ` at Sharpe ${m[2]}.${stays}`], tool: c.tool });
    } else items.push({ p: [`${tries}: ${text.split(" | ")[0]}`], tool: c.tool });
  }
  const sumP = h("p", "sum", null, panelBody);
  sumP.append(`${moves} moves, ${t.evaluations} rules scored. Best in-sample Sharpe ${best ?? "n/a"}. Submitted `);
  if (r.submitted) sumP.append(ruleSpan(r.submitted.rule), ` at ${r.submitted.text}.`);
  const ol = h("ol", null, null, panelBody);
  items.forEach((it, i) => {
    const li = h("li", it.refused ? "refused" : null, null, ol);
    h("span", "i", String(i + 1).padStart(2, "0"), li);
    const p = h("p", null, null, li);
    if (it.refused) h("span", "tag", "refused", p);
    p.append(...it.p);
    h("span", "tool", it.tool, p);
  });
  const end = h("div", "end", null, panelBody);
  h("h3", null, "How the search ended", end);
  const pe = h("p", null, null, end);
  pe.append(lastRefused ? `It ended when it tried to start again and was refused: ${lastRefused.text}. ` : `It ended after ${moves} moves. `);
  if (pred) pe.append(`It recorded a prediction of ${pred.mean} (sd ${pred.sd}) and submitted `); else pe.append("It submitted ");
  if (r.submitted) pe.append(ruleSpan(r.submitted.rule), ` at in-sample Sharpe ${r.submitted.text}.`);
  h("h3", null, "What the gate decided", end);
  if (r.result) {
    const res = r.result, w = word(res.status);
    h("p", null, `It repeated the search ${fmtB(res.B)} times on resampled data where no rule has a real edge. Its verdict is ${w}: ${MEANING[w] ?? ""}`, end);
    h("p", "nums", `p ${res.p_replay?.toFixed(4) ?? "n/a"} against α ${res.alpha}, over ${fmtB(res.B)} repeated searches.`, end);
    h("p", "nums", `Class tier, beside it: p ${res.p_class.toFixed(4)}; the class's bar ${res.class_bar.toFixed(3)} over all ${fmtB(res.class_size)} rules.`, end);
  } else h("p", null, `The gate refused the run: ${r.refused}`, end);
  panelBody.tabIndex = 0;
  panelBody.scrollTop = 0;
}

// ---- the record, below the first screen
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

// a resize redraws the bed in the tree's new frame
let rz = 0;
window.addEventListener("resize", () => { clearTimeout(rz); rz = window.setTimeout(() => { bed.paint(); wake.invalidate(); }, 150); });
void list;
