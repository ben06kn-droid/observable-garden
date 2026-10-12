"""The recency flag's unweighted path, repeated on one committed log: the French in-sample
read (`runs/french_insample/2026-10-07/results.json`, read at fc92cdb). The same panel (the
pinned X), the same ridge_stack fit, block lengths and seeds, priced through
`estimator.recency` with h None. Every recorded number must be bit-identical.
Laptop (Darwin arm64); the outcome was read and committed before; nothing new is read.

    python -m experiments.recency_repeat_french --out runs/recency_repeat_french/2026-10-09
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

LOG = Path("runs/french_insample/2026-10-07/results.json")


def main(argv=None) -> int:
    import environments.planted_fast as pf
    from environments.class_table import members_in_order
    from environments.french_panel import build_french_panel
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import french_insample_read as FR
    from learn import inputs as I
    from learn import ridge_stack
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    ref = json.loads(LOG.read_text())
    panel = build_french_panel()
    res = ridge_stack.run(panel, "ridge_stack")
    rows = res["scored_rows"]
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    s = I.net_stream(res["positions"], panel, rows)
    L = int(select_block_length(bc[rows] - bc[rows].mean(axis=0)))
    r1 = ref["i_stream"]
    st = Rc.stream_test(s, L, panel.periods_per_year, r1["B"], r1["seed"])
    cache = pf.build(panel, members_in_order(CLS, panel.features.shape[2]), name="french49-signed-3")
    r2 = ref["ii_class"]
    cl = Rc.price_class(panel, cache, bc, r2["seed"], r2["B"], r2["alpha"], panel.feature_names)
    checks = {"stream block length": L == r1["block_length"], "stream S": st["S"] == r1["S"],
              "stream p": st["p"] == r1["p"], "stream L90": st["confidence"]["L"]["0.90"] == r1["L90"],
              "stream confidence curve": st["confidence"]["curve"] == r1["confidence"]["curve"],
              "class block length": cl["block_length"] == r2["block_length"], "class S": cl["S"] == r2["S"],
              "class p": cl["p"] == r2["p"], "class L90": cl["L90"] == r2["L90"],
              "class best member": cl["best_member"] == r2["best_member"]}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    text = "\n".join([f"Recency flag off, repeated on {LOG} (French in-sample read): every field bit-identical?"]
                     + [f"   {k}: {v}" for k, v in checks.items()]
                     + [f"ALL IDENTICAL: {all(checks.values())}"])
    (out / "repeat.txt").write_text(text + "\n")
    (out / "repeat.json").write_text(json.dumps(checks, indent=1))
    print(text)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
