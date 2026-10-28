// The Sancho page: the lever editor. A form over sancho/config.json's levers (src/levers.ts); every
// change rewrites the config the page would download and its hash, the one `quixote sancho` records.
// It runs entirely in the page: nothing is sent or stored.
import { h } from "../common";
import { INSTALL } from "../install";
import { BLOCKS, configSha256, DEFAULT, fileText, firstScored, LEVERS, MEMORY_ROWS, numberList, problems, REGIMES, type Values } from "../levers";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const form = $<HTMLFormElement>("levers");
const clone = (v: Values): Values => JSON.parse(JSON.stringify(v));
const show = (x: unknown) => (Array.isArray(x) ? x.join(", ") : typeof x === "object" && x !== null ? JSON.stringify(x) : String(x));
const CONFIG_FILE = "sancho_config.json";

type Read = (v: Values, bad: string[]) => void;
const readers: Read[] = [];
let defaultHash = "";

/** one lever: its control, its default, what it may be, and what it does */
function lever(key: string, control: HTMLElement, read: Read, def: unknown) {
  const L = LEVERS.find((l) => l.key === key)!;
  const box = h("div", "lever", null, form);
  const lab = h("label", null, null, box);
  h("span", "lever-name", L.label, lab);
  lab.append(control);
  h("p", "fine", L.does, box);
  h("p", "fine smaller", `default ${show(def)} · ${L.allowed}`, box);
  readers.push(read);
}
const input = (type: string, value: string, attrs: Record<string, string> = {}) => {
  const e = document.createElement("input"); e.type = type; e.value = value;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  e.autocomplete = "off"; e.spellcheck = false; return e;
};
const select = (choices: readonly string[], value: string) => {
  const s = document.createElement("select");
  for (const c of choices) { const o = document.createElement("option"); o.value = o.textContent = c; s.append(o); }
  s.value = value; return s;
};
const whole = (key: string, min: number) => {
  const e = input("number", String(DEFAULT[key]), { min: String(min), step: "1" });
  lever(key, e, (v, bad) => { const x = Number(e.value); if (e.value.trim() === "" || !Number.isFinite(x)) bad.push(`${key} is not a number.`); v[key] = x; }, DEFAULT[key]);
  return e;
};
const checks = (names: readonly string[], on: (n: string) => boolean) => {
  const wrap = h("span", "checks", null);
  const boxes = names.map((n) => { const l = h("label", "check", null, wrap); const c = input("checkbox", n); c.checked = on(n); l.append(c, ` ${n}`); return c; });
  return { wrap, boxes };
};

function build() {
  const d = DEFAULT, trees = d.trees as Values, grids = (d.ridge as Values).grids as Values;
  const version = input("text", String(d.version), { readonly: "" });
  lever("version", version, (v) => { v.version = d.version; }, d.version);

  const info = h("span", "checks", null);
  const allSel = select(["all", "chosen blocks"], "all");
  const blocks = checks(BLOCKS, () => true);
  info.append(allSel, blocks.wrap);
  const sync = () => { for (const b of blocks.boxes) b.disabled = allSel.value === "all"; };
  allSel.addEventListener("change", sync); sync();
  lever("information", info, (v) => { v.information = allSel.value === "all" ? "all" : blocks.boxes.filter((b) => b.checked).map((b) => b.value); }, d.information);

  whole("horizon", 1);
  const neu = select(["market", "group"], String(d.neutrality));
  lever("neutrality", neu, (v) => { v.neutrality = neu.value; }, d.neutrality);
  const reg = select(REGIMES, String(d.regime));
  lever("regime", reg, (v) => { v.regime = reg.value; }, d.regime);

  const mem = checks(Object.keys(MEMORY_ROWS), (n) => n in (d.memories as Values));
  lever("memories", mem.wrap, (v) => { v.memories = Object.fromEntries(mem.boxes.filter((b) => b.checked).map((b) => [b.value, MEMORY_ROWS[b.value]])); }, Object.keys(d.memories as Values));

  const rates = input("text", (d.rates as number[]).join(", "));
  lever("rates", rates, (v, bad) => { const xs = numberList(rates.value); if (!xs) bad.push("rates: a list of numbers, separated by commas."); v.rates = xs ?? []; }, d.rates);

  whole("first_scored_row", 1); whole("refit_every", 1); whole("warmup_rows", 0);

  const gridBox = h("span", "grids", null);
  const gridInputs = Object.keys(grids).map((b) => { const l = h("label", "grid", null, gridBox); const e = input("text", (grids[b] as number[]).join(", ")); l.append(`${b} `, e); return [b, e] as const; });
  lever("ridge.grids", gridBox, (v, bad) => {
    const g: Values = {};
    for (const [b, e] of gridInputs) { const xs = numberList(e.value); if (!xs) bad.push(`ridge.grids.${b}: a list of numbers, separated by commas.`); g[b] = xs ?? []; }
    v.ridge = { grids: g };
  }, "as registered");

  const lgb = input("text", String(trees.lightgbm));
  const rounds = input("number", String(trees.rounds), { min: "1", step: "1" });
  const params = document.createElement("textarea"); params.rows = 8; params.spellcheck = false;
  params.value = JSON.stringify(trees.params, null, 1);
  lever("trees.lightgbm", lgb, () => {}, trees.lightgbm);
  lever("trees.rounds", rounds, () => {}, trees.rounds);
  lever("trees.params", params, (v, bad) => {
    let p: unknown = null;
    try { p = JSON.parse(params.value); } catch { bad.push("trees.params is not valid JSON."); }
    v.trees = { lightgbm: lgb.value.trim(), rounds: Number(rounds.value), params: p };
  }, "as registered");
}

let current: Values = clone(DEFAULT), ready = false;
async function update() {
  const v: Values = {}, bad: string[] = [];
  for (const r of readers) r(v, bad);
  // the file's key order is the registered file's
  current = Object.fromEntries(Object.keys(DEFAULT).map((k) => [k, v[k]]));
  const all = [...bad, ...(bad.length ? [] : problems(current))];
  $("lever-problems").textContent = all.join(" ");
  $<HTMLButtonElement>("cfg-download").disabled = all.length > 0;
  ready = all.length === 0;
  if (!ready) { $("cfg-hash").textContent = "(fix the levers above)"; return; }
  const sha = await configSha256(current), registered = sha === defaultHash;
  $("cfg-hash").textContent = sha;
  $("cfg-kind").textContent = registered ? "The registered Sancho (the default levers)." : "A tailored Sancho: not the registered one.";
  $("cfg-cmd").textContent = `${INSTALL}\nquixote sancho --panel my_panel.npz --config ${CONFIG_FILE} --out sancho_out/`;
  const first = firstScored(current);
  $("cfg-rows").replaceChildren(registered
    ? `Sancho's first scored row is ${first} after the embargo, so it needs about three years of daily rows and refuses the 600-row bundled panel by design; the `
    : `With these levers Sancho's first scored row is ${first} after the embargo (for a panel whose delay is 1), so the panel needs more rows than that; the `,
    Object.assign(h("a", null, "Docs page"), { href: "/docs.html#panel" }), " shows the panel format.");
}

$("cfg-download").addEventListener("click", () => {
  if (!ready) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([fileText(current)], { type: "application/json" }));
  a.download = CONFIG_FILE; document.body.appendChild(a); a.click(); a.remove();
  window.setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});
$("cfg-reset").addEventListener("click", () => { form.replaceChildren(); readers.length = 0; build(); void update(); });
form.addEventListener("input", () => void update());
form.addEventListener("change", () => void update());
form.addEventListener("submit", (e) => e.preventDefault());

(async () => {
  defaultHash = await configSha256(DEFAULT);
  $("default-hash").textContent = defaultHash;
  build();
  await update();
})();
