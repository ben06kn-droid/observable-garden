"""Holdout: split it off before the search, grade once after.

`split` cuts a panel file at a row (an index, or a `row_labels` entry) into an in-sample file
and a holdout file, and writes the holdout's SHA-256 beside them. Search on the in-sample file
only. It prints no holdout value.

`grade` prices the submitted rule of a log on the holdout: its realised net Sharpe over the
holdout rows, with the books continuous across the boundary (the first holdout trade is costed
from the position carried out of the in-sample period). **It refuses to run twice on the same
holdout**: it writes `graded-<hash prefix>.json`, and refuses whenever such a file exists beside
the holdout or in the output directory. A holdout looked at twice is no longer a holdout.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class HoldoutRefused(RuntimeError):
    pass


def _cut_row(arrays: dict, at: str) -> int:
    labels = arrays["row_labels"]
    if at in labels:
        return labels.index(at)
    try:
        h = int(at)
    except ValueError:
        raise HoldoutRefused(f"{at!r} is neither a row index nor a row label") from None
    if not 0 < h < len(labels):
        raise HoldoutRefused(f"row {h} is outside 1..{len(labels) - 1}")
    return h


def split(panel_path, holdout_from: str, out_dir) -> dict:
    from quixote import panel as P
    a = P.read(panel_path)
    h = _cut_row(a, str(holdout_from))
    out = Path(out_dir)
    if (out / "holdout.npz").exists():
        raise HoldoutRefused(f"{out / 'holdout.npz'} exists; a holdout is split once")
    common = {k: a[k] for k in ("feature_names", "periods_per_year", "delay", "cost_bps", "borrow_bps_yr")}
    ins = P.save(out / "insample.npz", a["returns"][:h], a["features"][:h], row_labels=a["row_labels"][:h],
                 asset_names=a["asset_names"], **common)
    hol = P.save(out / "holdout.npz", a["returns"][h:], a["features"][h:], row_labels=a["row_labels"][h:],
                 asset_names=a["asset_names"], **common)
    rec = {"source": Path(panel_path).name, "source_sha256": P.sha256(panel_path), "insample_sha256": ins,
           "insample_rows": h, "holdout_sha256": hol, "holdout_rows": len(a["row_labels"]) - h,
           "holdout_first": a["row_labels"][h], "holdout_last": a["row_labels"][-1]}
    (out / "holdout.json").write_text(json.dumps(rec, indent=1))
    return rec


def _marker_name(sha: str) -> str:
    return f"graded-{sha[:16]}.json"


def grade(log_path, insample_path, holdout_path, class_path, out_dir) -> dict:
    from environments.class_table import streams_for
    from quixote import classes, panel as P
    log = json.loads(Path(log_path).read_text())
    hsha = P.sha256(holdout_path)
    out = Path(out_dir)
    for d in {Path(holdout_path).parent, out}:
        if (d / _marker_name(hsha)).exists():
            raise HoldoutRefused(f"this holdout ({hsha[:16]}) has been graded already "
                                 f"({d / _marker_name(hsha)}); a holdout is graded once")
    if log.get("panel_sha256") != P.sha256(insample_path):
        raise HoldoutRefused("the log was not searched on this in-sample file")
    if log.get("class_sha256") != classes.file_sha256(class_path):
        raise HoldoutRefused("the log's class hash is not this class file's")
    ins, hol = P.read(insample_path), P.read(holdout_path)
    if ins["feature_names"] != hol["feature_names"] or ins["returns"].shape[1] != hol["returns"].shape[1]:
        raise HoldoutRefused("the holdout's features or assets are not the in-sample's")
    lc = classes.load(class_path, ins, compute_bar=False)
    span = dict(ins)
    span["returns"] = np.vstack([ins["returns"], hol["returns"]])
    span["features"] = np.concatenate([ins["features"], hol["features"]], axis=0)
    span["row_labels"] = ins["row_labels"] + hol["row_labels"]
    panel = P.to_engine(span, features=lc.features)
    support = tuple((int(k), float(s)) for k, s in log["submitted"]["support"])
    stream = streams_for(panel, [support, support])[0]       # a book continuous across the boundary
    earned = panel.meta["earned_labels"]
    first = set(hol["row_labels"])
    rows = [i for i, lab in enumerate(earned) if lab in first]
    x = stream[rows]
    sd = float(x.std(ddof=1))
    sharpe = float(x.mean() / sd * np.sqrt(panel.periods_per_year)) if sd > 0 else 0.0
    rec = {"holdout_sha256": hsha, "graded_periods": len(rows), "first": earned[rows[0]] if rows else None,
           "last": earned[rows[-1]] if rows else None, "submitted_support": log["submitted"]["support"],
           "insample_sharpe": log["submitted"]["score"], "holdout_net_sharpe": sharpe,
           "holdout_net_return": float(np.prod(1 + x) - 1), "class_sha256": log["class_sha256"]}
    out.mkdir(parents=True, exist_ok=True)
    (out / _marker_name(hsha)).write_text(json.dumps(rec, indent=1))
    return rec
