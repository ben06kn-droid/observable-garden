// Sancho's levers (sancho/config.json, documented in sancho/CONFIG.md), for the Sancho page's editor:
// each lever's default, what it may be, and one line on what it does, from CONFIG.md and the code
// that reads it (sancho/model.py, learner.py, views.py, states.py, cli.py). No lever is added here.
//
// The file the editor writes is JSON that `quixote sancho --config` reads (sancho.config.load), and
// its hash is the one the run records: SHA-256 of `json.dumps(values, sort_keys=True,
// separators=(",", ":"))`, Python's canonical form. So numbers are written as Python writes them: a
// float lever is always a float (3 is written 3.0, 1e-05 as Python spells it), so that Python's
// reading of the file hashes to exactly what this page shows. scripts/equivalence.mjs checks the
// page's hash against sancho.config.sha256_of for the default and for tailored configs.
// No DOM here: Node runs this file in that check.

export type Values = Record<string, unknown>;

export const BLOCKS = ["P", "X", "V", "F"] as const;
export const REGIMES = ["always", "vol_high", "vol_low", "mkt_up", "mkt_down", "disp_high", "disp_low"] as const;
export const MEMORY_ROWS: Record<string, number | null> = { roll252: 252, roll756: 756, expand: null };
export const RATE_GRIDS: Record<string, number[]> = { G1: [1.0, 0.3, 0.1], G2: [0.5, 0.2, 0.1], G3: [0.3, 0.1, 0.03] };
export const RIDGE_OFF = 1000000.0;

/** sancho/config.json, the registered version-2 values */
export const DEFAULT: Values = {
  version: 2,
  information: "all",
  horizon: 5,
  neutrality: "market",
  regime: "always",
  memories: { roll756: 756, expand: null },
  rates: [0.3, 0.1, 0.03],
  first_scored_row: 756,
  refit_every: 252,
  warmup_rows: 64,
  ridge: { grids: { L: [1.0, 3.0, 10.0, 30.0], Q: [0.3, 1.0, 3.0, 1000000.0], I: [1.0, 3.0, 10.0, 1000000.0], S: [1.0, 3.0, 10.0, 1000000.0] } },
  trees: {
    lightgbm: "4.7.0",
    rounds: 50,
    params: { objective: "regression", num_leaves: 4, max_depth: 2, learning_rate: 0.1, min_data_in_leaf: 200, max_bin: 63,
              num_threads: 1, deterministic: true, force_row_wise: true, verbose: -1, seed: 1 },
  },
};

export interface Lever { key: string; label: string; allowed: string; does: string }
/** In the file's order. `allowed` is what the code accepts and acts on, said plainly. */
export const LEVERS: Lever[] = [
  { key: "version", label: "version", allowed: "2 (fixed)", does: "The model version these levers belong to." },
  { key: "information", label: "information", allowed: "\"all\", or any of P, X, V, F",
    does: "The input blocks the base view uses: all available, or a list from P (the 40 registered features), X (return structure), V (volume), F (funding). quixote sancho supplies X, and P when the panel has exactly 40 features; it has no V or F, so naming them stops the run." },
  { key: "horizon", label: "horizon", allowed: "a whole number of rows, 1 or more (the registered menu: 1, 5, 20)",
    does: "Rows ahead the target sums over; the embargo between training and scoring is h + 1 + d rows." },
  { key: "neutrality", label: "neutrality", allowed: "market or group",
    does: "Market: positions demeaned across all assets. Group: within asset groups, which the panel format does not carry, so under quixote sancho no refit is fitted and the book stays empty." },
  { key: "regime", label: "regime", allowed: REGIMES.join(", "),
    does: "The regime gate: the book is held only while the regime is on (always: never gated); each gated regime is off until its market state is warm." },
  { key: "memories", label: "memories", allowed: "one or more of roll252, roll756, expand",
    does: "M2: the training windows averaged, rolling 252 rows, rolling 756 rows, or expanding." },
  { key: "rates", label: "rates", allowed: "one or more numbers above 0 and at most 1 (registered grids G1 1, 0.3, 0.1; G2 0.5, 0.2, 0.1; G3 0.3, 0.1, 0.03)",
    does: "G3: the trading rates averaged; at rate a the book moves each row a fraction a of the way to the target." },
  { key: "first_scored_row", label: "first_scored_row", allowed: "a whole number of rows, 1 or more",
    does: "The first refit row, before the embargo h + 1 + d is added: nothing is scored before it." },
  { key: "refit_every", label: "refit_every", allowed: "a whole number of rows, 1 or more", does: "Rows between refits." },
  { key: "warmup_rows", label: "warmup_rows", allowed: "a whole number of rows, 0 or more", does: "Rows dropped from the start of every training set." },
  { key: "ridge.grids", label: "ridge.grids", allowed: "for each of L, Q, I, S, one or more penalties above 0 (1000000.0 = off)",
    does: "Penalty grids per ridge block, each chosen by out-of-fold error over 3 blocked folds: L linear over the active columns; with P active also Q (14 family squares), I (91 family products) and S (14 families × 3 states)." },
  { key: "trees.lightgbm", label: "trees.lightgbm", allowed: "a LightGBM version; the run stops unless exactly that version is installed",
    does: "The LightGBM version required (the optional extra sancho installs 4.7.0)." },
  { key: "trees.rounds", label: "trees.rounds", allowed: "a whole number, 1 or more", does: "Boosting rounds." },
  { key: "trees.params", label: "trees.params", allowed: "a JSON object of LightGBM parameters, passed to LightGBM as given",
    does: "LightGBM parameters (as registered: depth-2 trees, deterministic, one thread)." },
];

// ---- Python's JSON: floats as repr writes them, ASCII only, keys sorted for the canonical form -------

/** repr(float(x)) in Python: the shortest digits that round-trip (as JavaScript finds them), written
 *  in fixed notation for exponents -4 to 15 and in scientific notation otherwise ("1e-05", "1e+16"). */
export function pyFloat(x: number): string {
  if (!Number.isFinite(x)) throw new Error(`${x} cannot be written in JSON`);
  if (x === 0) return Object.is(x, -0) ? "-0.0" : "0.0";
  const sign = x < 0 ? "-" : "";
  const [mant, ex] = Math.abs(x).toExponential().split("e");
  const digits = mant.replace(".", ""), e = Number(ex);
  if (e >= -4 && e < 16) {
    if (e >= digits.length - 1) return sign + digits + "0".repeat(e - digits.length + 1) + ".0";
    if (e >= 0) return sign + digits.slice(0, e + 1) + "." + digits.slice(e + 1);
    return sign + "0." + "0".repeat(-e - 1) + digits;
  }
  return sign + digits[0] + (digits.length > 1 ? "." + digits.slice(1) : "") + "e" + (e < 0 ? "-" : "+") + String(Math.abs(e)).padStart(2, "0");
}

const pyString = (s: string) => JSON.stringify(s).replace(/[\u007f-￿]/g, (c) => c.charCodeAt(0) > 0x7f ? "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0") : c);

/** whether a number at this path is a float in the file (the registered file's own types) */
function isFloatPath(path: string[], x: number): boolean {
  const p = path.join(".");
  if (p.startsWith("rates.") || p.startsWith("ridge.grids.")) return true;
  if (p.startsWith("trees.params.")) return !Number.isInteger(x);   // free-form: as typed
  return false;
}

function write(v: unknown, path: string[], sortKeys: boolean, indent: string | null, depth: number): string {
  if (v === null) return "null";
  if (v === true) return "true";
  if (v === false) return "false";
  if (typeof v === "number") return isFloatPath(path, v) || !Number.isInteger(v) ? pyFloat(v) : String(v);
  if (typeof v === "string") return pyString(v);
  const nl = indent === null ? "" : "\n" + indent.repeat(depth + 1), end = indent === null ? "" : "\n" + indent.repeat(depth);
  const sep = indent === null ? "," : ",", colon = indent === null ? ":" : ": ";
  if (Array.isArray(v)) {
    const items = v.map((x, i) => write(x, [...path, String(i)], sortKeys, null, depth + 1));
    return "[" + items.join(indent === null ? "," : ", ") + "]";      // lists on one line, as in sancho/config.json
  }
  const keys = Object.keys(v as object);
  if (sortKeys) keys.sort();
  if (!keys.length) return "{}";
  return "{" + keys.map((k) => nl + pyString(k) + colon + write((v as Values)[k], [...path, k], sortKeys, indent, depth + 1)).join(sep) + end + "}";
}

/** Python's json.dumps(values, sort_keys=True, separators=(",", ":")) */
export const canonical = (values: Values) => write(values, [], true, null, 0);
/** the file to download: the levers in the registered file's order, two-space indented */
export const fileText = (values: Values) => write(values, [], false, "  ", 0) + "\n";

export async function configSha256(values: Values): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(values)));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** The levers checked against what the code accepts; returns the problems, worded for the form. */
export function problems(v: Values): string[] {
  const out: string[] = [];
  const whole = (k: string, min: number) => { const x = v[k]; if (typeof x !== "number" || !Number.isInteger(x) || x < min) out.push(`${k} must be a whole number, ${min} or more.`); };
  const info = v.information;
  if (info !== "all" && !(Array.isArray(info) && info.length && info.every((b) => (BLOCKS as readonly string[]).includes(b)))) out.push("information must be \"all\" or at least one of P, X, V, F.");
  whole("horizon", 1); whole("first_scored_row", 1); whole("refit_every", 1); whole("warmup_rows", 0);
  if (!["market", "group"].includes(String(v.neutrality))) out.push("neutrality must be market or group.");
  if (!(REGIMES as readonly string[]).includes(String(v.regime))) out.push(`regime must be one of ${REGIMES.join(", ")}.`);
  const mem = v.memories as Values;
  if (!mem || !Object.keys(mem).length || Object.keys(mem).some((k) => !(k in MEMORY_ROWS))) out.push("memories must name one or more of roll252, roll756, expand.");
  const rates = v.rates;
  if (!Array.isArray(rates) || !rates.length || rates.some((a) => typeof a !== "number" || !(a > 0 && a <= 1))) out.push("rates must be one or more numbers above 0 and at most 1.");
  const grids = ((v.ridge as Values)?.grids ?? {}) as Values;
  for (const b of ["L", "Q", "I", "S"]) {
    const g = grids[b];
    if (!Array.isArray(g) || !g.length || g.some((a) => typeof a !== "number" || !(a > 0) || !Number.isFinite(a))) out.push(`ridge.grids.${b} must be one or more penalties above 0.`);
  }
  const trees = (v.trees ?? {}) as Values;
  if (typeof trees.lightgbm !== "string" || !/^\d+(\.\d+)*$/.test(trees.lightgbm)) out.push("trees.lightgbm must be a version such as 4.7.0.");
  if (typeof trees.rounds !== "number" || !Number.isInteger(trees.rounds) || trees.rounds < 1) out.push("trees.rounds must be a whole number, 1 or more.");
  if (!trees.params || typeof trees.params !== "object" || Array.isArray(trees.params)) out.push("trees.params must be a JSON object.");
  return out;
}

/** a parsed list of numbers ("0.3, 0.1, 0.03"), or null if any item is not a number */
export function numberList(text: string): number[] | null {
  const parts = text.split(/[\s,]+/).filter(Boolean);
  const xs = parts.map(Number);
  return parts.length && xs.every(Number.isFinite) ? xs : null;
}

/** the first row Sancho scores, after the embargo h + 1 + d (d the panel's delay, 1 by default) */
export const firstScored = (v: Values, d = 1) => Number(v.first_scored_row) + Number(v.horizon) + 1 + d;
