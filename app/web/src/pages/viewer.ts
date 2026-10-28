// The viewer: what quixote audit or quixote sancho wrote on the visitor's machine, drawn here without
// recomputing. A search: its log, its result (quixote audit --json, or the run page's result file),
// and the panel and class the log names; the package replays the log against them (the worker's
// search_tree, which refuses a log that does not re-execute) and the scene draws the tree with the
// verdict on it. Sancho: sancho.json (and its config, if given), drawn as the bonsai in its pot.
// Files are read in the page; the panel and the class go through the package's loaders in the worker.
import { h, MEANING, reduceMotion, sha256Hex, word } from "../common";
import { drawBonsai } from "../bonsai";
import { loadGate } from "../gate";
import { INSTALL } from "../install";
import { configSha256, DEFAULT, type Values } from "../levers";
import { makeScene } from "../scene";
import type { AuditResult, InputsInfo } from "../types";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const scene = makeScene();
scene.notes.entered();
const list = $("v-list"), errorBox = $("v-error");

type Kind = "log" | "result" | "browser-result" | "sancho" | "config" | "class" | "panel";
interface Dropped { name: string; kind: Kind; text?: string; json?: Values; bytes?: ArrayBuffer; sha256: string }
const files = new Map<Kind, Dropped>();
const KIND_NAME: Record<Kind, string> = { log: "log (quixote-log/1)", result: "result (quixote audit --json)", "browser-result": "result (from the run page)",
  sancho: "Sancho's output (sancho.json)", config: "a Sancho config", class: "class", panel: "panel" };

function kindOf(name: string, json: Values | null): Kind | null {
  if (json === null) return name.endsWith(".npz") ? "panel" : null;
  if (json.format === "quixote-log/1") return "log";
  if (json.format === "quixote-browser-result/1") return "browser-result";
  if ("config_sha256" in json && "net_sharpe_in_sample" in json) return "sancho";
  if ("status" in json && "class_bar" in json && "submitted_support" in json) return "result";
  if ("trees" in json && "ridge" in json && "version" in json) return "config";
  if ("kind" in json && "features" in json) return "class";
  return null;
}

async function take(fl: FileList | File[]) {
  errorBox.textContent = "";
  for (const f of [...fl]) {
    if (f.size > 512e6) { errorBox.textContent = `${f.name} is over 512 MB.`; continue; }
    const bytes = await f.arrayBuffer();
    let json: Values | null = null, text: string | undefined;
    if (!f.name.endsWith(".npz")) {
      text = new TextDecoder().decode(bytes);
      try { json = JSON.parse(text); } catch { errorBox.textContent = `${f.name} is not JSON, nor a panel (.npz).`; continue; }
    }
    const kind = kindOf(f.name, json);
    if (!kind) { errorBox.textContent = `${f.name}: not a log, a result, Sancho's output or config, a class or a panel.`; continue; }
    files.set(kind, { name: f.name, kind, text, json: json ?? undefined, bytes, sha256: await sha256Hex(bytes) });
  }
  listFiles();
  await show();
}

function listFiles() {
  list.replaceChildren();
  for (const d of files.values()) h("li", null, `${d.name}: ${KIND_NAME[d.kind]} · sha256 ${d.sha256.slice(0, 16)}…`, list);
}

const kv = $("v-kv");
function rows(r: [string, string][]) { kv.replaceChildren(); for (const [k, v] of r) { h("dt", null, k, kv); h("dd", null, v, kv); } }
function clearScene() {
  scene.svg.replaceChildren(); scene.idleBox(); scene.notes.clear(); scene.notes.entered(); scene.seed.classList.remove("spent");
}

let shown = "";
async function show() {
  const sig = [...files.values()].map((d) => d.sha256).join();
  if (sig === shown) return;
  shown = sig;
  if (files.has("sancho")) return showSancho();
  if (files.has("log")) return showSearch();
}

// ---- a search: the log, its result, the panel and the class --------------------------------------
async function showSearch() {
  const log = files.get("log")!, lj = log.json!;
  const res = files.get("result") ?? files.get("browser-result");
  const r = (res?.kind === "browser-result" ? res.json!.result : res?.json) as AuditResult | undefined;
  const rec = res?.kind === "browser-result" ? res.json!.record as Values : null;
  const panel = files.get("panel"), cls = files.get("class");
  const notes: string[] = [];
  if (r) {   // the result must be this log's: the same submitted rule, class and number of moves
    const sameRule = JSON.stringify(r.submitted_support) === JSON.stringify((lj.submitted as Values)?.support);
    if (!sameRule || r.class_size !== lj.class_size || r.n_moves !== lj.n_moves)
      errorBox.textContent = `${res!.name} is not the result of ${log.name}: the submitted rule, the class size or the number of moves differ.`;
  } else notes.push("No result dropped: the search is drawn without a verdict. Audit it with the command below.");
  let info: InputsInfo | null = null;
  clearScene();
  if (panel && cls) {
    const gate = await loadGate();
    info = await gate.inspect(panel.bytes!.slice(0), cls.text!);
    if (info.error) { errorBox.textContent = `${panel.name} and ${cls.name}: ${info.error}`; info = null; }
    else if (info.panel_sha256 !== lj.panel_sha256 || info.class_sha256 !== lj.class_sha256)
      errorBox.textContent = `The log was written on another ${info.panel_sha256 !== lj.panel_sha256 ? "panel" : "class"} (its hash differs from ${info.panel_sha256 !== lj.panel_sha256 ? panel.name : cls.name}).`;
    else {
      const out = await gate.tree(log.text!, panel.bytes!.slice(0), cls.text!);
      if (out.kind === "refused") errorBox.textContent = `The package refused the log: ${out.message}`;
      else {
        const g = scene.draw(out.tree, r && !errorBox.textContent ? r : null, `view-${log.sha256.slice(0, 8)}`);
        scene.seed.classList.add("spent");
        g.setStep(Number.MAX_SAFE_INTEGER);
        if (r && !errorBox.textContent) scene.notes.verdict(g, r, out.tree.evaluations, rec ? Number(rec.seed) : null);
      }
    }
  } else notes.push(`To draw the search, add the panel and the class the log names: ${lj.panel_file} and ${lj.class_file}.`);

  $("v-rec-h").textContent = "The verdict";
  $("v-meaning").textContent = r ? `${word(r.status)}: ${MEANING[word(r.status)] ?? ""}` : notes.join(" ");
  $("v-reasons-h").hidden = !r;
  const ul = $("v-reasons"); ul.replaceChildren(); for (const x of r?.reasons ?? []) h("li", null, x, ul);
  if (r) for (const n of notes) h("li", null, n, ul);
  const out: [string, string][] = [
    ["Log", `${log.name} · sha256 ${log.sha256}`], ["Agent", String(lj.agent)], ["Moves", `${lj.n_moves} of ${lj.max_moves}`],
    ["Panel", `${lj.panel_file} · ${lj.panel_sha256}${info ? " (matches the panel given)" : ""}`],
    ["Class", `${lj.class_file} · ${lj.class_sha256}${info ? " (matches the class given)" : ""}`],
  ];
  if (r) out.push(["Submitted", `${r.submitted_feature_names.join(" ")} · in-sample Sharpe ${r.submitted_sharpe.toFixed(3)}`],
    ["Bar", r.class_bar.toFixed(3)], ["p", r.p_replay === null ? "n/a" : r.p_replay.toFixed(4)], ["B", r.B.toLocaleString("en")], ["α", String(r.alpha)],
    ["Seed", rec ? String(rec.seed) : "not recorded in the result (quixote audit's default is 0)"]);
  if (rec) for (const k of ["provider", "endpoint_host", "model", "effort", "audit_id", "package"]) if (rec[k] !== undefined) out.push([k.replace("_", " "), String(rec[k])]);
  rows(out);
  const seed = rec ? Number(rec.seed) : 0;
  $("v-cmd").textContent = `quixote audit ${log.name} --panel ${lj.panel_file} --class ${lj.class_file} --B ${r?.B ?? 2000} --seed ${seed} --json > result.json`;
  $("v-record").hidden = false;
  scene.two.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
}

// ---- Sancho: sancho.json, drawn as the bonsai in its pot -------------------------------------------
async function showSancho() {
  const s = files.get("sancho")!, j = s.json!, cfg = files.get("config");
  const defaultHash = await configSha256(DEFAULT);
  const hash = String(j.config_sha256), registered = hash === defaultHash && j.is_default === true;
  const sharpe = Number(j.net_sharpe_in_sample), stream = (j.stream as number[] | undefined) ?? [];
  clearScene();
  scene.seed.classList.add("spent");
  drawBonsai(scene.svg, `Sancho · in-sample net Sharpe ${sharpe >= 0 ? "+" : ""}${sharpe.toFixed(3)}`);
  let cfgLine = "";
  if (cfg) {
    const ch = await configSha256(cfg.json!);
    cfgLine = ch === hash ? `${cfg.name} hashes to the same config` : `${cfg.name} hashes to ${ch}, not this run's config`;
    if (ch !== hash) errorBox.textContent = `${cfg.name} is not the config this output was run with.`;
  }
  $("v-rec-h").textContent = registered ? "Sancho, the registered model" : "Sancho, tailored";
  $("v-meaning").textContent = "Sharpe and config hash, not a verdict: Sancho is a fixed model, not a search, so it gets no search verdict. "
    + "There is no search for the gate to replay; what quixote sancho writes is Sancho's stream and its in-sample Sharpe, and that is all there is to show. "
    + (registered ? "This is the registered Sancho (the default levers); its registered tests, priced as one declared strategy, are on the Sancho page."
                  : "This config is not the registered one: a different model from the registered Sancho, labelled by its config hash.");
  $("v-reasons-h").hidden = true; $("v-reasons").replaceChildren();
  const about = (j.panel_about ?? {}) as Values, turn = (j.turnover ?? {}) as Values;
  const out: [string, string][] = [
    ["Output", `${s.name} · sha256 ${s.sha256}`],
    ["Config hash", `${hash} (${registered ? "default: the registered Sancho" : "non-default: tailored"})`],
    ...(cfgLine ? [["Config file", cfgLine] as [string, string]] : []),
    ["View", Array.isArray(j.view) ? `information ${(j.view[0] as string[]).join("")} · horizon ${j.view[1]} · ${j.view[2]} · ${j.view[3]}` : "n/a"],
    ["Panel", `${j.panel} · ${about.rows} rows, ${about.assets} assets, ${about.features} features (P ${about.P_used ? "used" : "not used"}) · delay ${about.delay} · cost ${about.cost_bps} bps · borrow ${about.borrow_bps_yr} bps a year`],
    ["Scored", `${stream.length.toLocaleString("en")} rows from row ${j.first_scored_row}`],
    ["In-sample net Sharpe", `${sharpe >= 0 ? "+" : ""}${sharpe.toFixed(3)}`],
    ["Turnover", `${Number(turn.turnover_per_row).toFixed(4)} a row · cost ${Number(turn.cost_per_year).toFixed(4)} a year`],
  ];
  rows(out);
  $("v-cmd").textContent = `${INSTALL}\nquixote sancho --panel ${j.panel}${cfg ? ` --config ${cfg.name}` : registered ? "" : " --config <the config with this hash>"} --out sancho_out/`;
  $("v-record").hidden = false;
  scene.two.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
}

const input = $<HTMLInputElement>("v-files"), drop = $("v-drop");
input.addEventListener("change", () => { if (input.files) void take(input.files); });
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer?.files) void take(e.dataTransfer.files); });
