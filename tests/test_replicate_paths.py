"""The optional export of the certifying null's replicates (`audit_log(..., replicate_paths=n)`).

The site draws the search re-grown on noise from these, so they must be the null's own draws, and
asking for them must change nothing else; a default audit must not carry them at all.
"""
import json
from pathlib import Path

import numpy as np

from quixote import audit as A
from quixote import classes, panel as P
from quixote.certify import three_nulls
from quixote.run import replay

EX = Path(__file__).resolve().parents[1] / "examples"
ARGS = (EX / "logs" / "restart_session.json", EX / "data" / "tiny_panel.npz", EX / "class.json")


def test_default_has_no_paths_and_the_same_dict():
    plain = A.audit_log(*ARGS, B=120, seed=0)
    assert plain.replicate_paths is None and "replicate_paths" not in plain.to_dict()
    json.dumps(plain.to_dict())


def test_paths_are_the_nulls_own_replicates_and_change_nothing():
    n, B = 12, 120
    plain = A.audit_log(*ARGS, B=B, seed=0)
    with_paths = A.audit_log(*ARGS, B=B, seed=0, replicate_paths=n)
    d = with_paths.to_dict()
    paths = d.pop("replicate_paths")
    assert d == plain.to_dict()
    assert len(paths) == n
    json.dumps(paths)

    # the same draws three_nulls makes for the verdict: each path's score is the trigger null's
    log = json.loads(ARGS[0].read_text())
    arrays = P.read(str(ARGS[1]))
    lc = classes.load(str(ARGS[2]), arrays, compute_bar=False)
    h = replay(log, arrays, lc)
    base = h.sandbox.base_feature_columns()
    nulls, _ = three_nulls(h.tools.session.log, lc.spec_class, base, float(np.sqrt(h.panel.periods_per_year)),
                           B, seed=0, table=h.table)
    assert [p["score"] for p in paths] == list(nulls.trigger[:n])
    for p in paths:
        assert p["steps"] and all(s["action"] in ("continue", "restart", "stop") for s in p["steps"])
        assert all(isinstance(s["sharpe"], float) for s in p["steps"])
        assert any(s["action"] == "restart" for s in p["steps"])      # this searcher restarts on noise too
