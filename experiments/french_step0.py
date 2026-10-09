"""French holdout grading, step 0: the platform feasibility check (draft
`prereg/french-holdout-grading.md`, section 4; approved in design, QUEUED; this script is
written and tested, NOT run).

Two modes, both in-sample only. They read no holdout row: the loader refuses any row dated
on or after 2020-01-01 and any quarantined path, and the panel is checked to end before
2020.
- `reference` (the laptop, Darwin arm64, macOS LightGBM pin): ridge_stack on the pinned-X
  panel; writes its per-refit penalties and stack weights, its positions, and member 2937's
  positions, as the reference.
- `compare` (the Linux box, Linux LightGBM pin): rebuilds X from the in-sample CSV and
  compares it with the pinned arm64 X (the largest z-feature difference, and the number of
  rank entries that differ); recomputes member 2937's and ridge_stack's in-sample net
  Sharpe on the rebuilt panel (both already read at fc92cdb: 0.679 and 0.547); counts the
  refits whose penalties or stack weights differ from the reference; reports the
  correlation of ridge_stack's positions with the reference's. It then checks the draft's
  Option A tolerances, printing PASS or FAIL for each.

    laptop:  python -m experiments.french_step0 reference --out runs/french_step0/2026-10-xx
    box:     python -m experiments.french_step0 compare --out runs/french_step0/2026-10-xx \
                 --reference runs/french_step0/2026-10-xx/reference.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
from pathlib import Path

import numpy as np

MEMBER_2937 = ((28, 1.0), (29, -1.0))
READ_SHARPE = {"member_2937": 0.679, "ridge_stack": 0.547}     # fc92cdb, as printed
TOL = {"z_max_abs": 1e-9, "rank_differing_per": 1e-4, "sharpe_decimals": 3}
STACK_TOL = 1e-9


def feature_diffs(X_a: np.ndarray, X_b: np.ndarray, names) -> dict:
    z = [i for i, n in enumerate(names) if n.endswith("_z")]
    r = [i for i, n in enumerate(names) if n.endswith("_rank")]
    dz = float(np.abs(X_a[:, :, z] - X_b[:, :, z]).max()) if z else 0.0
    nr = int((X_a[:, :, r] != X_b[:, :, r]).sum()) if r else 0
    return {"z_max_abs": dz, "rank_differing": nr, "rank_total": int(X_a[:, :, r].size)}


def refit_diffs(ref: list[dict], new: list[dict]) -> dict:
    """Refits (matched by year) whose chosen penalties differ, or whose stack weights differ
    by more than STACK_TOL."""
    by = {d["year"]: d for d in ref}
    pen = stk = 0
    for d in new:
        r = by.get(d["year"])
        if r is None:
            pen += 1
            continue
        pen += list(map(float, r["penalties"])) != list(map(float, d["penalties"]))
        stk += float(np.abs(np.asarray(r["stack_weights"]) - np.asarray(d["stack_weights"])).max()) > STACK_TOL
    return {"refits": len(new), "penalties_differ": int(pen), "stack_weights_differ": int(stk)}


def tolerances(fd: dict, sharpes: dict) -> dict:
    out = {"z_max_abs": fd["z_max_abs"] <= TOL["z_max_abs"],
           "rank_entries": fd["rank_differing"] <= TOL["rank_differing_per"] * fd["rank_total"]}
    for k, v in sharpes.items():
        out[f"sharpe_{k}"] = round(v, TOL["sharpe_decimals"]) == READ_SHARPE[k]
    return out


def _guard(panel) -> None:
    last = max(panel.meta["earned_dates"])
    if last >= dt.date(2020, 1, 1):
        raise SystemExit(f"the panel reaches {last}: a holdout row; refused")


def _member_sharpe(panel) -> float:
    from environments.class_table import streams_for
    s = streams_for(panel, [MEMBER_2937])[0]
    sd = s.std(ddof=1)
    return float(s.mean() / sd * np.sqrt(panel.periods_per_year)) if sd > 0 else 0.0


def _ridge(panel):
    from learn import inputs as I
    from learn import ridge_stack
    res = ridge_stack.run(panel, "ridge_stack")
    s = I.net_stream(res["positions"], panel, res["scored_rows"])
    sd = s.std(ddof=1)
    return res, (float(s.mean() / sd * np.sqrt(panel.periods_per_year)) if sd > 0 else 0.0)


def main(argv=None) -> int:
    from environments import french_panel as fp
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("reference", "compare"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--reference", default=None)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    plat = f"{platform.system()} {platform.machine()}"
    if a.mode == "reference":
        if plat != "Darwin arm64":
            raise SystemExit("the reference is made on the laptop (Darwin arm64)")
        panel = fp.build_french_panel()
        _guard(panel)
        res, _ = _ridge(panel)
        np.save(out / "ref_positions.npy", res["positions"])
        (out / "reference.json").write_text(json.dumps(
            {"platform": plat, "diagnostics": res["diagnostics"]}, indent=1, default=float))
        print(f"reference written to {out}")
        return 0
    if plat != "Linux x86_64":
        raise SystemExit("the comparison runs on the Linux box")
    ref = json.loads(Path(a.reference).read_text())
    rebuilt = fp.build_french_panel(pinned=False)
    _guard(rebuilt)
    X_pin = fp.pinned_features()
    fd = feature_diffs(rebuilt.features, X_pin, rebuilt.feature_names)
    sh = {"member_2937": _member_sharpe(rebuilt)}
    res, sh["ridge_stack"] = _ridge(rebuilt)
    rd = refit_diffs(ref["diagnostics"], res["diagnostics"])
    p_ref = np.load(Path(a.reference).parent / "ref_positions.npy")
    rows = res["scored_rows"]
    corr = float(np.corrcoef(p_ref[rows].ravel(), res["positions"][rows].ravel())[0, 1])
    tol = tolerances(fd, sh)
    L = [f"French step 0 on {plat}: in-sample only (holdout refused by the loader)",
         f"   z-features: largest |difference| {fd['z_max_abs']:.3e} (tolerance 1e-9) -> {'PASS' if tol['z_max_abs'] else 'FAIL'}",
         f"   rank entries differing: {fd['rank_differing']} of {fd['rank_total']} (tolerance 1 in 10,000) -> "
         f"{'PASS' if tol['rank_entries'] else 'FAIL'}",
         f"   member 2937 in-sample net Sharpe (already read: 0.679): {sh['member_2937']:.3f} -> "
         f"{'PASS' if tol['sharpe_member_2937'] else 'FAIL'}",
         f"   ridge_stack in-sample net Sharpe (already read: 0.547): {sh['ridge_stack']:.3f} -> "
         f"{'PASS' if tol['sharpe_ridge_stack'] else 'FAIL'}",
         f"   ridge_stack refits: {rd['refits']}; penalties differ {rd['penalties_differ']}; stack weights differ "
         f"(> {STACK_TOL:g}) {rd['stack_weights_differ']}",
         f"   ridge_stack positions: correlation with the laptop's over the scored rows {corr:.6f}"]
    (out / "step0.txt").write_text("\n".join(L) + "\n")
    (out / "step0.json").write_text(json.dumps({"features": fd, "sharpes": sh, "refits": rd,
                                                "position_corr": corr, "tolerances": tol}, indent=1))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
