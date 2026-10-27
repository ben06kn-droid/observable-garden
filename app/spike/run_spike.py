"""Run the browser feasibility spike and print what it measured (app/BROWSER_FEASIBILITY.md).

    python app/spike/run_spike.py --pyodide <dir with pyodide-core and the package wheels> \
        --wheel <observable_garden-*.whl> [--B 2000,500] [--chrome PATH]

Builds a site directory in a temporary folder (Pyodide, the package wheel, the three example
inputs, this page), serves it from 127.0.0.1 with every request logged, opens it in headless
Chrome with an empty profile, waits for the page to post its timings, and prints one JSON report:
the page's timings, every file the first visit fetched with its raw, gzip and brotli sizes.
Nothing here is part of the site; it only measures.
"""
import argparse
import gzip
import http.server
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def brotli_size(data: bytes):
    try:
        import brotli
        return len(brotli.compress(data, quality=11))
    except ImportError:
        exe = shutil.which("brotli")
        if not exe:
            return None
        return len(subprocess.run([exe, "-c", "-q", "11"], input=data, capture_output=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pyodide", required=True)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--B", default="2000,500")
    ap.add_argument("--chrome", default=CHROME)
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()

    site = Path(tempfile.mkdtemp(prefix="og-spike-"))
    shutil.copytree(a.pyodide, site / "pyodide")
    shutil.copy(a.wheel, site / Path(a.wheel).name)
    (site / "examples").mkdir()
    for f in ("logs/scripted_session.json", "data/tiny_panel.npz", "class.json"):
        shutil.copy(REPO / "examples" / f, site / "examples" / Path(f).name)
    shutil.copy(HERE / "spike.mjs", site / "spike.mjs")
    (site / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>spike</title>'
                                     '<script type="module" src="spike.mjs"></script>running')

    served, result, done = [], {}, threading.Event()

    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                          ".mjs": "text/javascript", ".wasm": "application/wasm", ".whl": "application/zip"}

        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(site), **kw)

        def do_GET(self):
            path = self.path.split("?")[0].lstrip("/") or "index.html"
            if path != "favicon.ico":
                served.append(path)
            super().do_GET()

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            result.update(json.loads(body))
            self.send_response(204)
            self.end_headers()
            done.set()

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/index.html?wheel={Path(a.wheel).name}&B={a.B}"
    profile = tempfile.mkdtemp(prefix="og-spike-profile-")
    chrome = subprocess.Popen([a.chrome, "--headless=new", "--disable-gpu", "--no-first-run",
                               f"--user-data-dir={profile}", "--remote-debugging-port=0", url],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = done.wait(a.timeout)
    chrome.terminate()
    srv.shutdown()

    files = []
    for p in dict.fromkeys(served):              # first visit: each file once, in request order
        f = site / p
        if not f.is_file():
            continue
        data = f.read_bytes()
        spike_only = Path(p).name.startswith(("micropip-", "packaging-"))   # only for the arch check
        files.append({"file": p, "raw": len(data), "gzip": len(gzip.compress(data, 9)), "brotli": brotli_size(data),
                      "spike_only": spike_only})
    total = {k: sum((x[k] or 0) for x in files if not x["spike_only"]) for k in ("raw", "gzip", "brotli")}
    shutil.rmtree(site, ignore_errors=True)
    shutil.rmtree(profile, ignore_errors=True)
    print(json.dumps({"finished": ok, "page": result, "fetched": files, "fetched_total": total}, indent=1))


if __name__ == "__main__":
    main()
