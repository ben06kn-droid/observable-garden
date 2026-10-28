// The browser build against the command line, on every demo example.
//
// Browser side: Pyodide from public/pyodide/, the observable-garden wheel from public/py/, the
// worker's own Python (src/py/glue.py) with both stand-ins registered (it checks that they are),
// and the example copies the site serves: the code that ships. Command-line side: `quixote audit
// --json` with the real scipy and arch. Verdict, exit code, reasons and support must be identical;
// every number within 1e-9 (absolute). The largest difference is reported. Exit 1 on any failure.
// Each example runs at the B the demo runs it at (scripts/examples.mjs), unless --B overrides.
// The full run too, once per provider: a log written in the browser build by the harness with a
// model as its agent (the mock providers, scripts/mock_anthropic.mjs and scripts/mock_providers.mjs,
// each answering in its provider's shape; every request is checked for what the run page must
// send), audited in the browser build and by the CLI.
//   node scripts/equivalence.mjs [--B n] [--python python3]
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { DEMOS } from "./examples.mjs";
import { check as mockCheck, reply as mockReply } from "./mock_anthropic.mjs";
import { checkChat, checkResponses, replyChat, replyResponses } from "./mock_providers.mjs";

// errors raised inside Pyodide's minified module would otherwise print a whole source line
const fail = (e) => { console.error("equivalence: " + String(e?.message ?? e).slice(0, 4000)); process.exit(2); };
process.on("uncaughtException", fail);
process.on("unhandledRejection", fail);

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const B_OVERRIDE = arg("--B", null), SEED = 0, TOL = 1e-9;
const python = arg("--python", process.env.PYTHON ?? "python3");
const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(web, "..", "..");
const pub = join(web, "public");

const pyodideDir = join(pub, "pyodide", JSON.parse(readFileSync(join(pub, "pyodide", "MANIFEST.json"), "utf8")).pyodide);
const { loadPyodide } = await import(pathToFileURL(join(pyodideDir, "pyodide.mjs")).href);
const py = await loadPyodide({ indexURL: pyodideDir + "/", stdout: () => {}, stderr: () => {} });
await py.loadPackage(["numpy", "pandas"], { messageCallback: () => {} });
const wheel = JSON.parse(readFileSync(join(pub, "py", "MANIFEST.json"), "utf8")).wheel;
py.unpackArchive(new Uint8Array(readFileSync(join(pub, "py", wheel))), "wheel");
py.runPython(readFileSync(join(web, "src", "py", "glue.py"), "utf8"));
const standins = py.globals.get("STANDINS").toJs({ dict_converter: Object.fromEntries });
const blocked = py.runPython("import sys; json_ok = sys.modules['scipy'].__version__; json_ok");
if (!standins.arch || !standins.scipy || blocked !== "0+scipy_lite") throw new Error("the stand-ins are not what the browser build runs on: " + JSON.stringify(standins));

let worst = { diff: 0, where: "" };
const failures = [];
const report = [];
function compare(a, b, path) {
  if (typeof a === "number" && typeof b === "number") {
    const d = Math.abs(a - b);
    if (d > worst.diff) worst = { diff: d, where: path };
    if (!(d <= TOL)) failures.push(`${path}: browser ${a}, CLI ${b} (|diff| ${d})`);
  } else if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) failures.push(`${path}: lengths ${a.length} and ${b.length}`);
    a.forEach((x, i) => compare(x, b[i], `${path}[${i}]`));
  } else if (a && b && typeof a === "object") {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) compare(a[k], b[k], `${path}.${k}`);
  } else if (a !== b) failures.push(`${path}: browser ${JSON.stringify(a)}, CLI ${JSON.stringify(b)}`);
}

for (const d of DEMOS) {
  const B = B_OVERRIDE ? Number(B_OVERRIDE) : d.B;
  py.FS.mkdirTree(`/eq/${d.key}`);
  for (const f of [d.log, d.panel, d.cls]) py.FS.writeFile(`/eq/${d.key}/${f}`, new Uint8Array(readFileSync(join(pub, "examples", f))));
  const t0 = Date.now();
  const out = JSON.parse(py.globals.get("run_audit")(`/eq/${d.key}/${d.log}`, `/eq/${d.key}/${d.panel}`, `/eq/${d.key}/${d.cls}`, B, SEED, 48, () => {}));
  const browserMs = Date.now() - t0;
  if (out.refused) { failures.push(`${d.key}: the browser build refused: ${out.refused}`); continue; }
  let cli;
  const t1 = Date.now();
  try {
    cli = execFileSync(python, ["-m", "quixote.cli", "audit", `examples/logs/${d.log}`, "--panel", `examples/data/${d.panel}`,
      "--class", `examples/${d.cls}`, "--B", String(B), "--seed", String(SEED), "--json"], { cwd: repo, encoding: "utf8" });
  } catch (e) { cli = e.stdout; }     // the CLI exits 1 on FAIL; its JSON is still on stdout
  const cliMs = Date.now() - t1;
  const want = JSON.parse(cli);
  const before = failures.length, w0 = worst.diff;
  worst = { diff: 0, where: "" };
  compare(out.result, want, d.key);
  report.push({ example: d.key, status: out.result.status, p_replay: out.result.p_replay, B, browser_ms: browserMs, cli_ms: cliMs,
                largest_difference: worst.diff, at: worst.where, ok: failures.length === before });
  worst = worst.diff > w0 ? worst : { diff: w0, where: "" };
}
// the full run, once per provider: each mock answers in its provider's shape and checks every request
const RUNS = [
  { name: "anthropic", opts: { provider: "anthropic", model: "claude-opus-5-5", effort: "medium", fallbacks: true }, check: mockCheck, reply: mockReply },
  { name: "openai", opts: { provider: "openai", model: "gpt-6.1-sol", effort: "high", fallbacks: false }, check: checkResponses, reply: replyResponses },
  { name: "openrouter", opts: { provider: "openrouter", model: "qwen/qwen3-235b-a22b", effort: "medium", fallbacks: false, max_tokens: 8192 }, check: checkChat, reply: replyChat },
  { name: "local", opts: { provider: "local", model: "qwen3:32b", fallbacks: false },
    check: (b) => checkChat(b, null, { local: true }), reply: (b) => replyChat(b, { local: true }) },
];
for (const run of RUNS) {
  const B = B_OVERRIDE ? Number(B_OVERRIDE) : 2000;
  const dir = `/eq/run-${run.name}`;
  py.FS.mkdirTree(dir);
  for (const f of ["tiny_panel.npz", "class.json", "llm_agent.py"]) py.FS.writeFile(`${dir}/${f}`, new Uint8Array(readFileSync(join(pub, "examples", f))));
  const problems = [];
  const callModel = (s) => { const body = JSON.parse(s); const p = run.check(body); if (p) problems.push(p); return JSON.stringify(run.reply(body)); };
  const opts = { ...run.opts, max_moves: 12, seed: SEED };
  const ran = JSON.parse(py.globals.get("run_agent")(`${dir}/llm_agent.py`, `${dir}/tiny_panel.npz`, `${dir}/class.json`, `${dir}/log.json`,
    JSON.stringify(opts), callModel, () => {}));
  const tag = `full run (${run.name})`;
  if (!ran.log) failures.push(`${tag}: the browser build did not finish: ${JSON.stringify(ran).slice(0, 300)}`);
  for (const p of new Set(problems)) failures.push(`${tag}: a request the provider would refuse: ${p}`);
  if (ran.log) {
    const t0 = Date.now();
    const out = JSON.parse(py.globals.get("run_audit")(`${dir}/log.json`, `${dir}/tiny_panel.npz`, `${dir}/class.json`, B, SEED, 0, () => {}));
    const browserMs = Date.now() - t0;
    const logFile = join(mkdtempSync(join(tmpdir(), "qx-eq-")), `browser_run_${run.name}.json`);
    writeFileSync(logFile, JSON.stringify(ran.log, null, 1));
    let cli;
    const t1 = Date.now();
    try {
      cli = execFileSync(python, ["-m", "quixote.cli", "audit", logFile, "--panel", "examples/data/tiny_panel.npz",
        "--class", "examples/class.json", "--B", String(B), "--seed", String(SEED), "--json"], { cwd: repo, encoding: "utf8" });
    } catch (e) { cli = e.stdout; }
    const cliMs = Date.now() - t1;
    if (out.refused) failures.push(`${tag}: the browser build refused its own log: ${out.refused}`);
    else {
      const before = failures.length;
      worst = { diff: 0, where: "" };
      compare(out.result, JSON.parse(cli), tag);
      report.push({ example: `${tag}: a browser-written log, mock model`, calls: ran.log.calls.length, requests: ran.usage.requests, format: ran.log.format,
                    agent: ran.log.agent, submitted: ran.log.submitted?.support, status: out.result.status,
                    p_replay: out.result.p_replay, B, browser_ms: browserMs, cli_ms: cliMs, largest_difference: worst.diff, at: worst.where, ok: failures.length === before });
    }
  }
}
// Sancho's config hash: the Sancho page's (src/levers.ts) against sancho.config.sha256_of, on the
// default and on tailored configs written as the page writes them; and the page's Python float form
// against repr() on awkward values
{
  const L = await import("../src/levers.ts");
  const T = L.DEFAULT.trees, G = L.DEFAULT.ridge.grids;
  const configs = { default: L.DEFAULT,
    tailored: { ...L.DEFAULT, information: ["P", "X"], horizon: 20, regime: "vol_high", memories: { roll252: 252, expand: null }, rates: [1, 0.5, 0.2, 0.1] },
    grids: { ...L.DEFAULT, ridge: { grids: { ...G, L: [3], Q: [0.00001, 1e6], S: [2.5e-7, 1e16] } },
             trees: { ...T, rounds: 80, params: { ...T.params, learning_rate: 0.05, objective: "huber é" } } } };
  const hashes = {};
  for (const [name, v] of Object.entries(configs)) {
    const py = execFileSync(python, ["-c", "import json,sys; from sancho.config import sha256_of; print(sha256_of(json.loads(sys.stdin.read())))"],
      { input: L.fileText(v), encoding: "utf8", cwd: repo }).trim();
    const page = await L.configSha256(v);
    hashes[name] = page.slice(0, 16);
    if (page !== py) failures.push(`Sancho config ${name}: the page's hash ${page}, sancho.config's ${py}`);
  }
  const xs = [0.1, 0.3, 0.03, 1e-4, 1e-5, 2.5e-7, 5e-324, 1e15, 1e16, 1.5e16, 9999999999999998, 123.456, 1e22, -0.0, 1000000.0, 0.1 + 0.2];
  const reprs = JSON.parse(execFileSync(python, ["-c", "import json,sys; print(json.dumps([repr(float(x)) for x in json.load(sys.stdin)]))"], { input: JSON.stringify(xs), encoding: "utf8" }));
  xs.forEach((x, i) => { if (L.pyFloat(x) !== reprs[i] && !Object.is(x, -0)) failures.push(`float ${x}: the page writes ${L.pyFloat(x)}, Python ${reprs[i]}`); });
  report.push({ example: "Sancho config hash (page vs sancho.config)", configs: hashes, floats: xs.length, largest_difference: 0, ok: !failures.some((f) => f.startsWith("Sancho") || f.startsWith("float")) });
}
const largest = Math.max(...report.map((r) => r.largest_difference));
console.log(JSON.stringify({ wheel, standins, tolerance: TOL, largest_difference: largest, examples: report, failures }, null, 1));
process.exit(failures.length ? 1 : 0);
