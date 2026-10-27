"""Write public/examples/overview-tree.json: the restart example's search, for the trees drawn
behind the overview page. It is the output of the worker's own `search_tree` (src/py/glue.py) on the
committed log, so page one shows real evaluations without loading Python first.

    python3 app/web/scripts/make_overview_tree.py           # write
    python3 app/web/scripts/make_overview_tree.py --check   # fail if the committed file is stale
"""
import json
import runpy
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
REPO = WEB.parents[1]
OUT = WEB / "public" / "examples" / "overview-tree.json"

glue = runpy.run_path(str(WEB / "src" / "py" / "glue.py"))
tree = json.loads(glue["search_tree"](str(REPO / "examples/logs/restart_session.json"),
                                      str(REPO / "examples/data/tiny_panel.npz"), str(REPO / "examples/class.json")))
text = json.dumps(tree, separators=(",", ":")) + "\n"
if "--check" in sys.argv:
    if OUT.read_text() != text:
        sys.exit("public/examples/overview-tree.json is stale: run app/web/scripts/make_overview_tree.py")
    print("overview-tree.json is current")
else:
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)}: {tree['evaluations']} evaluations on {tree['stems']} stems")
