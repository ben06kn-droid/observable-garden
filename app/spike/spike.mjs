// Feasibility spike (app/BROWSER_FEASIBILITY.md): the gate's audit under Pyodide, timed in the page.
// Served by run_spike.py from one local directory; nothing is fetched from anywhere else except
// the final, separate check that `arch` cannot be installed (which asks PyPI through micropip).
import { loadPyodide } from "./pyodide/pyodide.mjs";

const q = new URLSearchParams(location.search);
const WHEEL = q.get("wheel");
const BS = (q.get("B") || "2000,500").split(",").map(Number);
const out = { timings_ms: {}, audits: [], checks: {} };
const t0 = performance.now();
const lap = (k, t) => {
  out.timings_ms[k] = Math.round(performance.now() - t);
  document.body.textContent = "running… " + Object.keys(out.timings_ms).join(", ") + " done";
};
const post = () => fetch("/result", { method: "POST", body: JSON.stringify(out) });

try {
  let t = performance.now();
  const py = await loadPyodide({ indexURL: "./pyodide/" });
  lap("load_pyodide", t);

  t = performance.now();
  await py.loadPackage(["numpy", "scipy", "pandas"]);
  lap("load_numpy_scipy_pandas", t);

  t = performance.now();
  py.unpackArchive(await (await fetch("./" + WHEEL)).arrayBuffer(), "wheel");
  for (const f of ["scripted_session.json", "tiny_panel.npz", "class.json"]) {
    const b = new Uint8Array(await (await fetch("./examples/" + f)).arrayBuffer());
    py.FS.writeFile("/home/pyodide/" + f, b);
  }
  lap("install_wheel_and_inputs", t);

  t = performance.now();
  out.checks.imports = JSON.parse(py.runPython(`
import sys, json
import estimator.block_length as bl
installed = bl.install_as_arch()          # no arch here: the port goes in under arch's name
import quixote.audit as A
import estimator.bootstrap as eb
mods = sorted({m.split('.')[0] for m in sys.modules if not m.startswith('_')} - set(sys.stdlib_module_names))
json.dumps({"python": sys.version.split()[0], "port_installed": installed,
            "block_length_from": eb.optimal_block_length.__module__,
            "third_party_loaded": mods,
            "arch_is_the_port": getattr(sys.modules.get("arch"), "__doc__", "").startswith("Stand-in"),
            "forbidden_loaded": [m for m in ("matplotlib", "statsmodels", "lightgbm", "sklearn") if m in sys.modules]})
`));
  lap("import_quixote_audit", t);

  for (const B of BS) {
    t = performance.now();
    const r = py.runPython(`
import json
calls = []
r = A.audit_log("/home/pyodide/scripted_session.json", "/home/pyodide/tiny_panel.npz", "/home/pyodide/class.json",
                B=${B}, seed=0, progress=lambda *c: calls.append(list(c)))
d = r.to_dict(); d["progress_calls"] = calls
json.dumps(d)
`);
    out.audits.push({ B, ms: Math.round(performance.now() - t), result: JSON.parse(r) });
  }
  out.timings_ms.page_open_to_last_verdict = Math.round(performance.now() - t0);

  // 1c: the panel from bytes, pickle refused
  out.checks.panel_from_bytes = JSON.parse(py.runPython(`
import io, json, numpy as np
from quixote import panel as P
raw = open("/home/pyodide/tiny_panel.npz", "rb").read()
with np.load(io.BytesIO(raw), allow_pickle=False) as z:
    from_bytes = {k: z[k].shape for k in z.files}
d = P.read("/home/pyodide/tiny_panel.npz")          # the repo's loader, on bytes written to the in-memory FS
buf = io.BytesIO(); np.savez(buf, returns=np.array([{"a": 1}], dtype=object))
try:
    np.load(io.BytesIO(buf.getvalue()), allow_pickle=False)["returns"]
    refused = False
except ValueError as e:
    refused = str(e)
json.dumps({"keys_from_bytes": sorted(from_bytes), "returns_shape": list(d["returns"].shape),
            "object_array_refused": refused})
`));

  // 1a: arch has no Pyodide build and no pure-Python wheel
  t = performance.now();
  await py.loadPackage("micropip");
  try {
    await py.runPythonAsync(`import micropip\nawait micropip.install("arch")`);
    out.checks.arch_install = "INSTALLED (unexpected)";
  } catch (e) {
    out.checks.arch_install = String(e.message || e).split("\n").filter(l => l.trim()).slice(-2).join(" | ");
  }
  lap("arch_check", t);
} catch (e) {
  out.error = String(e && e.stack || e);
}
await post().catch(() => {});        // run_spike.py collects this; a plain static server ignores it
const pre = document.createElement("pre");
pre.textContent = JSON.stringify(out, (k, v) => (k === "reasons" ? undefined : v), 1);
document.body.replaceChildren(pre);
