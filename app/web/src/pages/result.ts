import { auditId, h, reduceMotion, sha256Hex, word } from "../common";
import { command, demos, loadDemo } from "../demos";
import { drawGarden } from "../garden";
import { loadGate } from "../gate";
import { makeInside } from "../inside";
import { makeNotes } from "../notes";
import type { SearchTree } from "../types";

const SEED = 0;
const $ = (id: string) => document.getElementById(id) as HTMLElement;
const q = new URLSearchParams(location.search);
const status = $("r-status");
// the verdict written on the drawing, as on the demo (notes.ts)
const notes = makeNotes($("r-spot"), $("r-spot"), () => []);
let tree: SearchTree | null = null;
const inside = makeInside($("inside"), () => tree);

(async () => {
  const list = await demos();
  const demo = list.find((d) => d.key === q.get("ex")) ?? list[0];
  const B = q.has("B") ? Math.max(100, Math.min(10000, Number(q.get("B")) || demo.B)) : demo.B;
  $("r-label").textContent = `Result · ${demo.title}`;
  const [gate, loaded] = await Promise.all([loadGate(), loadDemo(demo)]);
  const out = await gate.audit({ ...loaded.inputs, B, seed: SEED }, {
    onSearch: (t) => { tree = t; },
    onProgress: (p) => { status.textContent = p.stage === "replay" ? `The null: ${p.done} of ${p.total} replicates` : "The class tier"; },
  });
  if (out.kind === "refused") { status.textContent = "Refused: " + out.message; return; }
  const r = out.result, log = loaded.logJson, w = word(r.status);
  status.textContent = `${w} · p ${r.p_replay?.toFixed(4) ?? "n/a"} · computed in ${(out.ms / 1000).toFixed(1)} s`;
  if (tree) {
    const g = drawGarden($("garden") as unknown as SVGSVGElement, tree, { interactive: true, neon: true, halo: true, canopy: false, twigs: true, bar: r.class_bar,
      submitted: { rule: r.submitted_feature_names.join(" "), sharpe: r.submitted_sharpe } });
    g.verdict(w);
    g.onPick((stem, move) => { notes.entered(); g.select(stem); window.setTimeout(() => inside.open(stem, move, g.rectOf(stem)), reduceMotion ? 0 : 450); });
    inside.onClose(() => g.select(null));
    requestAnimationFrame(() => notes.verdict(g, r, tree!.evaluations, SEED));
    window.addEventListener("resize", () => notes.place());
  }
  if (loaded.truth) {                                       // the planted example's truth, as plain type
    const t = loaded.truth, p = $("r-truth");
    p.textContent = `The planted truth: ${t.planted_rule.join(" ")} · population Sharpe ${Number(t.population_sharpe).toFixed(2)} (target ${Number(t.population_sharpe_target).toFixed(1)}), net of costs; submitted ${r.submitted_feature_names.join(" ")}`;
    p.hidden = false;
  }
  const [panelSha, classSha, logSha] = await Promise.all([sha256Hex(loaded.inputs.panel), sha256Hex(loaded.inputs.cls), sha256Hex(loaded.inputs.log)]);
  const id = await auditId({ alpha: r.alpha, B: r.B, class_sha256: classSha, log_sha256: logSha, panel_sha256: panelSha, seed: SEED, wheel: gate.wheel });
  const kv = $("rec-kv");
  for (const [k, v] of [["Class", `${log.class_name} · ${r.class_size} members`], ["Class hash", classSha], ["Panel hash", panelSha],
                        ["Seeds", `search ${log.seed} · audit ${SEED}`], ["B", r.B.toLocaleString("en")], ["Audit id", id],
                        ["Package", gate.wheel], ["Exit code", String(r.exit_code)]] as [string, string][]) {
    h("dt", null, k, kv); h("dd", null, v, kv);
  }
  $("rec-cmd").textContent = command(demo, r.B, SEED);
  const rs = $("reasons");
  for (const x of r.reasons) h("li", null, x, rs);
  const lb = $("rec-log");
  for (const c of log.calls) { const p = h("p", null, null, lb); h("b", null, c.tool, p); p.append(" ", c.refused ? `refused: ${c.refused}` : (c.text ?? "").replace(new RegExp("^" + c.tool + "(?=[\\s:])"), "").trim()); }
})().catch((e) => { status.textContent = "Error: " + String((e as Error).message ?? e); });
