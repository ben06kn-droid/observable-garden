# Third-party components

Everything below is served by the site itself (nothing is loaded from another origin). The full
licence texts, taken from each component, are in `public/licenses.txt` (served at `/licenses.txt`,
written by `scripts/make_licenses.py`).

## Ported into the observable-garden package

Both ports live in the package and are used only where the original library cannot be imported
(the browser). Each file carries the original copyright and licence text at the top of its module
docstring.

| file | ported from | authors | licence | where the text is |
|---|---|---|---|---|
| `quixote/engine/estimator/block_length.py` | `arch` 8.0.0, `arch.bootstrap.base._single_optimal_block` and `optimal_block_length` (Politis and White 2004, Patton, Politis and White 2009) | Kevin Sheppard | University of Illinois/NCSA Open Source Licence | lines 27-59: copyright and the full licence |
| `quixote/engine/estimator/scipy_lite.py` (erf, erfc, ndtr) | Cephes Math Library 2.2, as carried in SciPy's xsf (`include/xsf/cephes/ndtr.h`) | Stephen L. Moshier (Cephes); the SciPy developers (xsf) | BSD 3-Clause (xsf, Copyright (c) 2024, SciPy), with the Cephes copyright notice | lines 31-50: both notices and the full BSD-3 text |

The rest of `scipy_lite.py` is written from published algorithms, not copied code: Wichura's AS 241
for the inverse normal (coefficients as published, Applied Statistics 37(3), 1988), Brent's method
following the structure of SciPy's `brentq`, and numpy's trapezoidal rule.

## Served as they are

| component | version | licence | notes |
|---|---|---|---|
| Pyodide (`pyodide.mjs`, `pyodide.asm.mjs`, `pyodide.asm.wasm`) | 314.0.7 | MPL-2.0 | unmodified; source at github.com/pyodide/pyodide, tag 314.0.7 |
| CPython standard library (`python_stdlib.zip`, inside Pyodide) | 3.14.2 | Python Software Foundation License | unmodified |
| numpy | 2.4.6 (Pyodide build) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (bundled components) | unmodified wheel |
| pandas | 3.0.2 (Pyodide build) | BSD 3-Clause | unmodified wheel |
| python-dateutil | 2.9.0.post0 | dual: Apache-2.0 and BSD 3-Clause | unmodified wheel |
| pytz | 2026.1.post1 | MIT | unmodified wheel |
| six | 1.17.0 | MIT | unmodified wheel |
| Bricolage Grotesque (variable) | via @fontsource-variable/bricolage-grotesque 5.3.0 | SIL Open Font License 1.1 | Copyright 2022 The Bricolage Grotesque Project Authors |
| IBM Plex Mono | via @fontsource/ibm-plex-mono 5.3.0 | SIL Open Font License 1.1 | Copyright 2017 IBM Corp. |
| IBM Plex Sans | via @fontsource/ibm-plex-sans 5.3.0 | SIL Open Font License 1.1 | Copyright 2017 IBM Corp. |

## Used to build, not served

Vite 8.3.4 (MIT), TypeScript 6.0.3 (Apache-2.0), and the `pyodide` npm package 314.0.7 (MPL-2.0, for
its type definitions). Exact versions and integrity hashes are in `package-lock.json`.

The site's own code and the observable-garden package are MIT; the paper is CC BY.
