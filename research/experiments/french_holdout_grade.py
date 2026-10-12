"""French holdout grading, the grader (`prereg/french-holdout-grading.md`, live at
4f11f952092831d77c4d8287f083bda12b425f22; checklist step 10). Runs on the holdout host
(Option A).

In this order, refusing on any failure before any holdout value is computed:
  1. start-up refusals: the registration is an ancestor of HEAD; HEAD equals --expect-head;
     no tracked changes; Linux x86_64; LightGBM 4.7.0 with the Linux library's SHA-256; the
     pinned French X and the in-sample CSV have their registered SHA-256;
  2. section 4's Option A tolerances, on the host's own in-sample build against the pinned
     X and the in-sample read;
  3. section 3's no-restart checks: the spanning panel's features on the in-sample rows
     equal the in-sample-only build's, bit for bit; each object's positions on the
     in-sample rows equal the in-sample-only run's, bit for bit; the first holdout period's
     cost is the cost of trading from the carried in-sample position; and no restart
     signature at the boundary (no unwarmed all-zero feature row in the first 253 holdout
     rows, ridge_stack holds a position at the first holdout row, the market states are
     live there).
Then section 5's quantities, written to grades.json with the holdout's last date. **No
value is printed.** The reader is `experiments/read_french_holdout.py`.

    python -m experiments.french_holdout_grade --holdout ~/french_holdout/holdout.csv \\
        --out runs/french_holdout/<date> --expect-head <G>
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import platform
from pathlib import Path

import numpy as np

LIVE = "4f11f952092831d77c4d8287f083bda12b425f22"
MEMBER = ((28, 1.0), (29, -1.0))
INSAMPLE_RESULTS = Path("runs/french_insample/2026-10-07/results.json")
INSAMPLE_CSV_SHA256 = "1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e"
LIB_SHA256 = "573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a"
HOLDOUT_START = dt.date(2020, 1, 1)
B = 10_000
SEED = 694000
RIDGE_FIRST_ROW = 756


class GradingRefused(RuntimeError):
    pass


# -- data ---------------------------------------------------------------------------------

def load_holdout(path) -> tuple[list, list, np.ndarray]:
    """The holdout CSV (the grading flag): every row must be dated on or after 2020-01-01."""
    dates, rows = [], []
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        cols = next(rd)[1:]
        for row in rd:
            d = dt.date.fromisoformat(row[0])
            if d < HOLDOUT_START:
                raise GradingRefused(f"{d} in the holdout file is before 2020-01-01")
            dates.append(d)
            rows.append([float(x) for x in row[1:]])
    R = np.asarray(rows, float) / 100.0
    if np.isnan(R).any() or (R <= -0.9999).any():
        raise GradingRefused("a missing or invalid holdout value")
    return dates, cols, R


def build(dates_in, names, R_in, dates_ho, R_ho):
    """(in-sample-only panel, spanning panel, index of the first holdout feature row)."""
    from environments.french_panel import panel_from_returns
    p_in = panel_from_returns(dates_in, names, R_in)
    p_sp = panel_from_returns(list(dates_in) + list(dates_ho), names, np.vstack([R_in, R_ho]))
    return p_in, p_sp, p_in.features.shape[0]


# -- objects ------------------------------------------------------------------------------

def member_positions(panel) -> np.ndarray:
    import environments.planted_panel as pp
    return pp.member_weights(panel, MEMBER)


def ridge_positions(panel) -> np.ndarray:
    from learn import ridge_stack
    return ridge_stack.run(panel, "ridge_stack")["positions"]


def net(panel, w, start: int) -> np.ndarray:
    """Net return of positions w on rows start.., one continuous book from zero at `start`."""
    from learn import inputs as I
    rows = np.arange(start, panel.features.shape[0])
    return I.net_stream(w, panel, rows)


def sharpe(x, ppy=252.0) -> float:
    sd = np.std(x, ddof=1)
    return float(np.mean(x) / sd * np.sqrt(ppy)) if sd > 0 else 0.0


# -- checks -------------------------------------------------------------------------------

def check_tolerances(p_in, X_pin, refs: dict) -> dict:
    """Section 4's Option A tolerances on the host's own in-sample build."""
    from experiments import french_step0 as S0
    fd = S0.feature_diffs(p_in.features, X_pin, p_in.feature_names)
    sh = {"member_2937": sharpe(net(p_in, member_positions(p_in), 0)),
          "ridge_stack": sharpe(net(p_in, ridge_positions(p_in), RIDGE_FIRST_ROW))}
    ok = {"z_max_abs": fd["z_max_abs"] <= 1e-9,
          "rank_entries": fd["rank_differing"] <= 1e-4 * fd["rank_total"],
          "sharpe_member_2937": round(sh["member_2937"], 3) == refs["member_2937"],
          "sharpe_ridge_stack": round(sh["ridge_stack"], 3) == refs["ridge_stack"]}
    return {"features": fd, "sharpes": sh, "pass": ok}


def check_no_restart(p_in, p_sp, h0: int, pos_in: dict, pos_sp: dict, net_fn=None) -> dict:
    """Section 3: identical features and positions on the in-sample rows; the first holdout
    trade costed from the carried position. `net_fn` is the stream function the grader uses
    (injectable so a restarted book can be shown to fail)."""
    net_fn = net_fn or net
    from learn import inputs as I
    out = {"features_identical": bool(np.array_equal(p_in.features, p_sp.features[:h0]))}
    # restart signatures: a pipeline restarted at the boundary would leave unwarmed (all-zero)
    # feature rows, a walk-forward with no position, and zero market states at the first
    # holdout row
    first = p_sp.features[h0:h0 + 253]
    out["holdout_features_warm"] = bool(not np.any(np.all(first == 0, axis=(1, 2))))
    out["ridge_stack_position_at_boundary"] = bool(np.abs(pos_sp["ridge_stack"][h0]).sum() > 0) \
        if "ridge_stack" in pos_sp else True
    st = I.market_states(np.asarray(p_sp.returns, float))
    out["states_live_at_boundary"] = bool(np.all(st[h0, :2] != 0))
    for name in pos_in:
        out[f"{name}_positions_identical"] = bool(np.array_equal(pos_in[name], pos_sp[name][:h0]))
        w = pos_sp[name]
        start = 0 if name == "member_2937" else RIDGE_FIRST_ROW
        s = net_fn(p_sp, w, start)
        gross = float(w[h0] @ p_sp.returns[h0])
        carried = float(np.abs(w[h0] - w[h0 - 1]) @ p_sp.cost_rate[h0]
                        + np.clip(-w[h0], 0, None) @ p_sp.borrow_rate[h0])
        out[f"{name}_book_carried"] = bool(abs(s[h0 - start] - (gross - carried)) <= 1e-13)
        out[f"{name}_carried_position_nonzero"] = bool(np.abs(w[h0 - 1]).sum() > 0)
    return out


def refuse_if_failed(checks: dict, what: str) -> None:
    bad = [k for k, v in checks.items() if v is False]
    if bad:
        raise GradingRefused(f"{what} failed: {', '.join(bad)}; nothing graded")


# -- quantities ---------------------------------------------------------------------------

def curve_at(conf: dict, x: float) -> tuple[float, bool]:
    lo, step, n = conf["grid"]
    grid = lo + step * np.arange(int(n))
    curve = np.asarray(conf["curve"], float)
    clipped = bool(x < grid[0] or x > grid[-1])
    return float(np.interp(x, grid, curve)), clipped


def quantities(streams: dict, base_cols_ho: np.ndarray, insample: dict, ppy=252.0) -> dict:
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    T = len(next(iter(streams.values())))
    L = int(select_block_length(base_cols_ho - base_cols_ho.mean(axis=0)))
    rng = np.random.default_rng(SEED)
    idx = [stationary_bootstrap_indices(T, L, rng) for _ in range(B)]
    out = {"n_periods": T, "block_length": L, "B": B, "seed": SEED, "objects": {}}
    for name, s in streams.items():
        S = sharpe(s, ppy)
        reps = np.array([sharpe(s[i], ppy) for i in idx])
        lo, hi = np.quantile(reps, [0.025, 0.975])
        L90 = insample[name]["L90"]
        C, clipped = curve_at(insample[name]["confidence"], S)
        out["objects"][name] = {"realized": S, "ci95": [float(lo), float(hi)], "L90_insample": L90,
                                "realized_minus_L90": S - L90, "ci95_minus_L90": [float(lo - L90), float(hi - L90)],
                                "C_at_realized": C, "C_clipped": clipped, "held": bool(S >= L90)}
    return out


def grade(dates_in, names, R_in, dates_ho, R_ho, X_pin, refs: dict, insample: dict) -> dict:
    """Steps 2-4, in order; raises GradingRefused before any holdout value on a failure."""
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    p_in, p_sp, h0 = build(dates_in, names, R_in, dates_ho, R_ho)
    tol = check_tolerances(p_in, X_pin, refs)
    refuse_if_failed(tol["pass"], "Option A tolerances")
    pos_in = {"member_2937": member_positions(p_in), "ridge_stack": ridge_positions(p_in)}
    pos_sp = {"member_2937": member_positions(p_sp), "ridge_stack": ridge_positions(p_sp)}
    nr = check_no_restart(p_in, p_sp, h0, pos_in, pos_sp)
    refuse_if_failed({k: v for k, v in nr.items() if not k.endswith("_nonzero")}, "no-restart checks")
    streams = {"member_2937": net(p_sp, pos_sp["member_2937"], 0)[h0:],
               "ridge_stack": net(p_sp, pos_sp["ridge_stack"], RIDGE_FIRST_ROW)[h0 - RIDGE_FIRST_ROW:]}
    bc = np.asarray(RealSandbox(p_sp, spec_class=CLS).base_feature_columns(), float)[h0:]
    q = quantities(streams, bc, insample)
    ed = p_sp.meta["earned_dates"]
    q.update({"tolerances": tol, "no_restart": nr, "first_holdout_date": str(ed[h0]),
              "last_date": str(ed[-1]), "registration": LIVE})
    return q


# -- refusals and main ----------------------------------------------------------------------

def refusals(expect_head: str) -> list[str]:
    import subprocess
    import lightgbm
    from environments import french_panel as fp
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    bad = []
    if g("merge-base", "--is-ancestor", LIVE, "HEAD").returncode != 0:
        bad.append(f"the registration {LIVE} is not an ancestor of HEAD")
    if g("rev-parse", "HEAD").stdout.strip() != expect_head:
        bad.append("HEAD is not --expect-head")
    if g("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    if f"{platform.system()} {platform.machine()}" != "Linux x86_64":
        bad.append("not Linux x86_64 (Option A: the holdout host)")
    lib = Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.so"
    if lightgbm.__version__ != "4.7.0" or not lib.exists() or hashlib.sha256(lib.read_bytes()).hexdigest() != LIB_SHA256:
        bad.append("LightGBM is not the Linux pin (4.7.0, lib_lightgbm.so 573d57e8...)")
    if not fp.PINNED_X.exists() or hashlib.sha256(fp.PINNED_X.read_bytes()).hexdigest() != fp.PINNED_X_SHA256:
        bad.append("the pinned French X is missing or not its registered SHA-256")
    from data.french_loader import INSAMPLE_CSV
    if not INSAMPLE_CSV.exists() or hashlib.sha256(INSAMPLE_CSV.read_bytes()).hexdigest() != INSAMPLE_CSV_SHA256:
        bad.append("the in-sample CSV is missing or not its registered SHA-256")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-head", required=True)
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    if (out / "grades.json").exists():
        raise SystemExit("grades exist; grading happens once")
    from data.french_loader import load_insample
    from environments import french_panel as fp
    dates_in, names, R_in = load_insample()
    dates_ho, names_ho, R_ho = load_holdout(Path(a.holdout).expanduser())
    if names_ho != names:
        raise SystemExit("REFUSED: the holdout's industries are not the in-sample's")
    res = json.loads(INSAMPLE_RESULTS.read_text())
    insample = {"ridge_stack": {"L90": res["i_stream"]["L90"], "confidence": res["i_stream"]["confidence"]},
                "member_2937": {"L90": res["ii_class"]["L90"], "confidence": res["ii_class"]["confidence"]}}
    refs = {"member_2937": 0.679, "ridge_stack": 0.547}
    try:
        g = grade(dates_in, names, R_in, dates_ho, R_ho, fp.pinned_features(), refs, insample)
    except GradingRefused as e:
        raise SystemExit(f"REFUSED: {e}")
    out.mkdir(parents=True, exist_ok=True)
    g["holdout_csv_sha256"] = hashlib.sha256(Path(a.holdout).expanduser().read_bytes()).hexdigest()
    g["git_head"] = a.expect_head
    (out / "grades.json").write_text(json.dumps(g, indent=1, default=float))
    print(f"grades written to {out / 'grades.json'}; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
