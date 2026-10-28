// How large a class the browser build can take: the peak WebAssembly memory of Pyodide (the build
// the site ships, stand-ins registered) while it loads a class, computes its bar and builds its class
// table, at growing members x rows, each size in a fresh interpreter (the heap never shrinks). Also
// the most the heap will grow to. The run page's cap comes from these numbers.
//   node scripts/measure_class_cap.mjs
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const pub = join(web, "public");
const pyodideDir = join(pub, "pyodide", JSON.parse(readFileSync(join(pub, "pyodide", "MANIFEST.json"), "utf8")).pyodide);
const { loadPyodide } = await import(pathToFileURL(join(pyodideDir, "pyodide.mjs")).href);
const wheel = JSON.parse(readFileSync(join(pub, "py", "MANIFEST.json"), "utf8")).wheel;
const glue = readFileSync(join(web, "src", "py", "glue.py"), "utf8");

async function fresh() {
  const py = await loadPyodide({ indexURL: pyodideDir + "/", stdout: () => {}, stderr: () => {} });
  await py.loadPackage(["numpy", "pandas"], { messageCallback: () => {} });
  py.unpackArchive(new Uint8Array(readFileSync(join(pub, "py", wheel))), "wheel");
  py.runPython(glue);
  return py;
}
const heap = (py) => py._module.HEAPU8.length;

// a synthetic panel: T rows, 30 assets, K features; a signed subsets class of up to `m` features
const rows = [];
for (const [T, K, m] of [[1000, 12, 2], [1000, 20, 3], [2500, 20, 3], [2500, 30, 3], [5000, 30, 3], [2500, 40, 3]]) {
  const py = await fresh();
  const base = heap(py);
  try {
    const out = py.runPython(`
import json, time, numpy as np
from quixote import classes, panel as P
rng = np.random.default_rng(0)
T, M, K, m = ${T}, 30, ${K}, ${m}
np.savez("/p.npz", returns=rng.normal(0, 0.01, (T, M)), features=rng.normal(0, 1, (T, M, K)),
         feature_names=np.array([f"f{i}" for i in range(K)]), periods_per_year=252)
open("/c.json", "w").write(json.dumps({"kind": "subsets", "max_size": m, "signed": True, "features": "all"}))
t0 = time.time()
arrays = P.read("/p.npz")
lc = classes.load("/c.json", arrays, B=500)
panel, table = classes.table_for(lc, arrays)
json.dumps({"members": int(lc.size), "rows": T, "table_mb": table.streams.nbytes / 1e6, "s": round(time.time() - t0, 1)})`);
    rows.push({ ...JSON.parse(out), peak_mb: Math.round(heap(py) / 1e6), grew_mb: Math.round((heap(py) - base) / 1e6) });
  } catch (e) {
    rows.push({ T, K, m, failed: String(e.message ?? e).split("\n").filter(Boolean).pop() });
  }
  console.error(JSON.stringify(rows[rows.length - 1]));
}
// the most the heap grows to before an allocation fails
const py = await fresh();
let ceiling = 0;
try { py.runPython(`
blocks = []
import numpy as np
while True:
    blocks.append(np.ones(64 * 2**20 // 8))`); } catch { ceiling = heap(py); }
console.log(JSON.stringify({ rows, heap_ceiling_mb: Math.round(ceiling / 1e6) }, null, 1));
