# Browser feasibility: the gate's audit under Pyodide

Measured 2026-10-26 on an Apple M3 (8 GB), macOS 14.5, Google Chrome 156.0.8078.48 (headless,
empty profile), from branch `app-browser` (based on `app-design` at f752524) with the two package
changes of step 2 in the working tree. Every number below was measured; none is estimated. The
harness is `app/spike/` (`run_spike.py` serves one local directory and logs every byte; `spike.mjs`
times each phase in the page and posts the results back).

**Result: one gate fails.** The demo runs well inside the time gate (7.5 s at the default B), but the
first visit downloads **28.4 MB gzip / 27.4 MB brotli**, over the 25 MB gate. Per the work order this
report stops here; the proposal is at the end.

## a. Pyodide, and what the audit path imports

- **Pinned release: Pyodide 314.0.7** (2026-09-14; Python 3.14.2, ABI `2026_0`, emscripten 5.0.3),
  the newest stable release. `pyodide-core-314.0.7.tar.bz2` sha256
  `2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95`.
- **numpy 2.4.6, scipy 1.18.0, pandas 3.0.2 load** (with python-dateutil 2.9.0.post0, pytz
  2026.1.post1, six 1.17.0). Every wheel's sha256 matched `pyodide-lock.json`.
- **`arch` does not load.** It is not among the 357 packages in the lock file, and
  `micropip.install("arch")` in the page fails: micropip finds no pure-Python wheel (arch ships
  compiled extensions only).
- **The audit path's third-party imports on the desktop**, traced with an import hook during
  `audit_log` on the example: every one except numpy comes in through `arch`.

  | import | first imported by | needed without arch? |
  |---|---|---|
  | `arch` | `estimator/bootstrap.py:23` (`optimal_block_length`, its only use) | no: the vendored port stands in, step 2a (below) |
  | `scipy` | `arch.univariate.recursions_python` | **yes**: `quixote/confidence.py` (`scipy.stats.norm`) and `garden/power.py` (`brentq`, `trapezoid`, `log_ndtr`, `ndtri`, `norm`) import it directly |
  | `pandas` | `arch._typing` | **yes**: `environments/sandbox.py` and `garden/transcript.py` import it directly |
  | `statsmodels` (+ `patsy`, `formulaic`) | `arch.univariate.mean` | no |
  | `matplotlib` (+ `PIL`, `fontTools`, `kiwisolver`, `cycler`) | `arch.univariate.base:52` | no |
  | `lightgbm`, `sklearn` | never | no |

  So **the audit path imports matplotlib only through arch** (`arch/univariate/base.py`), and never
  imports lightgbm. With arch absent, the audit loads exactly numpy, scipy, pandas (with dateutil,
  pytz, six) and the repository's own packages; this was confirmed in the page, where
  `sys.modules` held no arch, matplotlib, statsmodels, lightgbm or sklearn.
- **What scipy is used for in an audit:** one call. Wrapping every scipy function the audit path
  imports and running all three committed example logs, the only call made was `norm.cdf`, once
  per audit (`quixote/confidence.py:65`). `garden.power` is imported (by `garden.audit` and
  `garden.preflight`) but none of its functions ran.

**How the port is wired.** The work order asked for `estimator/bootstrap.py` to import from arch
when it is installed and from the vendored module otherwise. That file cannot change:
`research/tests/test_pins_after_cleanup.py` holds every moved engine file to its pre-cleanup
text, allowing only data-path and package-rename lines, and `research/` is not to change. So
`bootstrap.py` is untouched and still says `from arch.bootstrap import optimal_block_length`;
`estimator/block_length.py` has `install_as_arch()`, which, only when `arch` cannot be imported,
registers the port in `sys.modules` as `arch.bootstrap`. The browser calls it before importing the
package. On the desktop it does nothing and arch itself runs. A test runs `quixote example --json`
in a fresh interpreter with arch blocked and the port installed, and gets the same bytes as with
arch.

## b. The example in Chrome

The package went in as a pure-Python wheel built from the working tree with the
`garden/data/*.npz` package data left out: the audit path opens only its three inputs (traced with an
`open` hook: the log, the panel, the class), never anything under `garden/data`. The wheel is
`observable_garden-0.1.0-py3-none-any.whl`, 290,871 bytes, 94 files, no `.npz`. It was unpacked
into the page's site-packages with `pyodide.unpackArchive`, so micropip is not part of the demo.

**Timings** (two runs, first / second; milliseconds in the page). A third run, after the port was
rewired as above, gave the same verdicts and p values and 8,342 ms at B = 2000, slower because the
full test suite was running on the same machine at the time.

| phase | run 1 | run 2 |
|---|---|---|
| load Pyodide | 907 | 899 |
| load numpy, scipy, pandas | 863 | 878 |
| install the wheel and the three inputs | 12 | 11 |
| `import quixote.audit` | 2,911 | 2,860 |
| **audit at B = 2000** (the audit's default) | **7,582** | **7,523** |
| audit at B = 500 (`quixote example`'s default) | 2,073 | 2,024 |
| page open to the second verdict | 14,348 | 14,196 |

The desktop CLI on the same machine: `quixote example --B 2000` 3.9 s, `quixote example` (B 500)
1.9 s wall, each including interpreter start. The browser is about 2x slower on the audit itself.
**Gate: under 60 s at the default B. Passes**: about 12 s from page open to a B = 2000 verdict.

**Agreement with the CLI.** Same verdict and identical p values: B = 2000 gives replay p
0.9630184907546226 and class p 0.9695152423788106 in both; B = 500 gives 0.9720558882235529 and
0.9800399201596807 in both. The class tier's bar differs in the last bit: at B = 500 it is
1.8882606322704842 in the browser and 1.8882606322704845 on the desktop (numpy 2.4.6 in Pyodide,
2.5.3 on the desktop; the class table's matrix products round differently). The step-3
equivalence test should therefore compare status, p values and integers exactly and the Sharpe
quantities to about 1e-12, not byte for byte.

**First-visit download** (every file the page fetched once, from an empty profile; gzip at level 9;
brotli at quality 11, the best a static host would serve):

| file | raw | gzip | brotli |
|---|---:|---:|---:|
| `pyodide.asm.wasm` | 9,598,218 | 3,528,803 | 2,741,061 |
| `python_stdlib.zip` | 2,545,637 | 2,503,129 | 2,487,479 |
| `pyodide.asm.mjs` | 1,250,344 | 259,957 | 207,390 |
| `pyodide.mjs`, `pyodide-lock.json`, page | 140,886 | 35,363 | 29,681 |
| **scipy** 1.18.0 wheel | 14,029,750 | **13,812,133** | **13,776,475** |
| pandas 3.0.2 wheel | 4,177,749 | 4,141,942 | 4,136,251 |
| numpy 2.4.6 wheel | 2,960,568 | 2,924,334 | 2,913,946 |
| pytz, python-dateutil, six wheels | 751,431 | 616,253 | 525,500 |
| the package wheel | 290,871 | 285,320 | 282,604 |
| the three example inputs | 536,057 | 294,693 | 274,075 |
| **total** | **36,281,511** | **28,401,927** | **27,374,462** |

Wheels and `python_stdlib.zip` are already zip-compressed, so a host's compression barely touches
them; brotli saves 1.0 MB over gzip, nearly all of it on the wasm. **Gate: under 25 MB compressed.
Fails, at 27.4 MB with brotli** (28.4 MB gzip). scipy is 13.8 MB of it, half the download.

## c. The panel from bytes

In the page: `np.load(io.BytesIO(raw), allow_pickle=False)` reads `tiny_panel.npz` from its bytes
(all nine arrays), and the repository's own loader `quixote.panel.read` reads the same bytes written
to Pyodide's in-memory filesystem (it already calls `np.load(path, allow_pickle=False)`); `returns`
is 600 x 12. An `.npz` holding an object array is refused from bytes: `ValueError: Object arrays
cannot be loaded when allow_pickle=False`. A visitor's upload can go through the same loader
unchanged.

## d. Phase 4, checked only (nothing implemented)

Read from the SDKs' source on their main branches today:

- **Anthropic TypeScript SDK** (`@anthropic-ai/sdk`, `src/client.ts`): the client refuses to
  construct in a browser unless `dangerouslyAllowBrowser: true` is passed
  (`new Anthropic({ apiKey, dangerouslyAllowBrowser: true })`). With it set, every request carries
  the header **`anthropic-dangerous-direct-browser-access: true`**, which is what lets the API
  accept a cross-origin browser request. Default base URL `https://api.anthropic.com`.
- **OpenAI** (`openai-node`, `src/client.ts`): the same option name, `dangerouslyAllowBrowser:
  true`, with the same refusal otherwise; default base URL `https://api.openai.com/v1`.
- **CSP `connect-src`** will need `'self'` (the site's own wheels and data) plus
  `https://api.anthropic.com` and `https://api.openai.com`, and nothing else. Pyodide itself will
  need `script-src 'self' 'wasm-unsafe-eval'` for WebAssembly compilation (to be confirmed when the
  CSP is written; not tested here).

## Proposal (the download gate)

The time gate has room to spare, so lowering B or shrinking the bootstrap loop would not help:
neither changes what is downloaded. The download is the problem, and half of it is scipy, which
an audit uses for a single `norm.cdf`.

1. **Recommended: stop loading scipy for an audit.** Make the scipy imports in
   `quixote/confidence.py` and `garden/power.py` lazy (inside the functions that use them), and give
   `confidence.py` a `norm.cdf` that uses scipy when it is installed and the standard library's
   `statistics.NormalDist().cdf` otherwise, the same pattern as the block length. Effect, computed
   from the measured file sizes above (not yet run, since it needs the change): scipy is never
   fetched, and the first visit falls to **14.6 MB gzip / 13.6 MB brotli**, comfortably under the
   gate. The desktop path still uses scipy, so no registered number
   moves; `NormalDist().cdf` affects only `P_H` (a confidence floor printed beside a certificate),
   and a test would hold it to scipy's within 1e-12 the way `tests/test_block_length.py` does. This
   is a third package change, outside the two this work order allows, so it needs your approval.
   If a later page (Sancho, power) does call `garden.power`, that page loads scipy then.
2. **If the package must not change further:** lazy-load in the page. Load Pyodide, numpy and pandas
   (14.6 MB) to run the demo, and fetch scipy in the background after first paint, before the
   audit needs it. That passes the gate only if "first visit" means what blocks the first verdict;
   the full 27.4 MB is still fetched, so I would not count it as passing.
3. Not worth pursuing: shrinking `python_stdlib.zip` (2.5 MB) or dropping pandas (4.1 MB, used by
   `environments/sandbox.py`). The first is fiddly and the second is a larger change to the engine.
   Neither is needed once scipy is out.

## Reproduce

    # Pyodide core and the package wheels, checked against pyodide-lock.json
    curl -LO https://github.com/pyodide/pyodide/releases/download/314.0.7/pyodide-core-314.0.7.tar.bz2
    # (numpy, scipy, pandas, python-dateutil, pytz, six, micropip, packaging: from the 314.0.7 distribution)
    # the package wheel, without garden/data: remove the [tool.setuptools.package-data] lines, then
    pip wheel . --no-deps -w wheels/
    python app/spike/run_spike.py --pyodide <pyodide dir> --wheel wheels/observable_garden-0.1.0-py3-none-any.whl
