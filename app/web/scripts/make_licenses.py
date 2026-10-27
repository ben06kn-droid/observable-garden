"""Write public/licenses.txt: the licence of every third-party component the site serves, taken
from the components themselves (each wheel's dist-info, each font package, Pyodide's package), plus
the notices of the two ports inside the observable-garden wheel.

    python3 app/web/scripts/make_licenses.py
"""
import json
import zipfile
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
PUB = WEB / "public"
parts = ["Third-party software served by this site, and the notices it requires.",
         "The site's own code and the observable-garden package: MIT (see the repository's LICENSE).", ""]


def section(title, text):
    parts.extend(["=" * 78, title, "=" * 78, text.strip(), ""])


nm = WEB / "node_modules"
section("Pyodide 314.0.7 (pyodide.mjs, pyodide.asm.mjs, pyodide.asm.wasm, python_stdlib.zip): MPL-2.0. "
        "Served unmodified; source at https://github.com/pyodide/pyodide/tree/314.0.7. The Python standard "
        "library inside it is under the Python Software Foundation License.",
        (WEB / "scripts" / "third_party" / "pyodide-LICENSE").read_text())
man = json.loads((PUB / "pyodide" / "MANIFEST.json").read_text())
for f in man["files"]:
    if not f.get("package"):
        continue
    z = zipfile.ZipFile(PUB / "pyodide" / man["pyodide"] / f["file"])
    lic = [n for n in z.namelist() if ".dist-info/" in n and ("LICEN" in n.upper() or "COPYING" in n.upper())]
    text = "\n\n".join(f"--- {n.split('.dist-info/')[-1]} ---\n" + z.read(n).decode("utf-8", "replace") for n in lic)
    section(f"{f['package']} {f['version']} ({f['file']})", text)
for pkg, name in [("@fontsource-variable/bricolage-grotesque", "Bricolage Grotesque"),
                  ("@fontsource/ibm-plex-mono", "IBM Plex Mono"), ("@fontsource/ibm-plex-sans", "IBM Plex Sans")]:
    version = json.loads((nm / pkg / "package.json").read_text())["version"]
    section(f"{name} (font files, via {pkg} {version}): SIL Open Font License 1.1", (nm / pkg / "LICENSE").read_text())
src = WEB.parents[1] / "quixote" / "engine" / "estimator"
for mod, what in [("block_length.py", "estimator/block_length.py: a port of arch's optimal block length (Kevin Sheppard), NCSA"),
                  ("scipy_lite.py", "estimator/scipy_lite.py: erf/erfc/ndtr ported from scipy's xsf (Cephes), BSD-3")]:
    doc = (src / mod).read_text().split('"""')[1]
    section(what, doc)
(PUB / "licenses.txt").write_text("\n".join(parts))
print(f"wrote public/licenses.txt ({(PUB / 'licenses.txt').stat().st_size:,} bytes)")
