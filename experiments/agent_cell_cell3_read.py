"""Read `prereg/agent-cell.md`'s cell 3 ONCE: 6.5's orientation arm against its
replay-gate arm, on the ETF panel.

Registered (`agent-cell.md` "3. 6.5, ETF panel"; `agent-on-real-data.md`, the
orientation amendment). Predicted, for the oriented agent:

1. fewer z/rank near-duplicate pairs evaluated (a pair counts when both members are);
2. fewer moves to `submit`;
3. more `pick_prior` use;
4. fewer trigger changes;
5. more accepted picks.

Registered failure mode: stated confidence rises with no change in the deflation
gap. The haircut regression is reported beside. Cell 2 read a difference on s3, as
priming by the paragraph, so the ETF readout is reported NET of it.

**Operationalised here, before the numbers are computed**, where the registration
names a quantity without fixing its measurement:

- **a feature is "evaluated"** when it appears in a support the search scored -- a
  `support_after` of any logged record. Candidates the harness scored inside one
  move are not counted: `extend_best` scores every extension, so on that reading
  every pair is hit on every run and the readout is degenerate by construction;
- the near-duplicate pairs are the panel's twenty (z, rank) pairs, features
  (2j, 2j + 1) (`prereg/etf-features.md`);
- **stated confidence is the stated sd** of the agent's `predict`; lower is more
  confident. The stated mean is reported beside it;
- **deflation gap** is `analyze_agent`'s: stated mean - sr_deflated, with
  `sr_deflated = submitted Sharpe - mean(M_b)` and `M_b` the run's own
  declared-class null maxima (`agent-on-real-data.md`, "Verdict addition");
- **evaluation count** for the haircut is the run's total harness-scored candidates
  (`SessionLog.total_candidates`), the count the trial-count arguments use;
- **net of priming** is a difference in differences of means: (ETF orientation -
  ETF replay) - (s3 orientation - s3 replay), for the measures cell 2 read a
  difference on. Descriptive; no test on the net.

Comparisons are Mann-Whitney U, two-sided, as cell 2's. No threshold; n = 20
against 20 sees only a large difference, and a null result is not equivalence.

    python -m experiments.agent_cell_cell3_read
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats

from experiments.agent_cell_full_read import ROOT, behaviour, load

PAIRS = [(2 * j, 2 * j + 1) for j in range(20)]
PRIMED = ("moves to submit", "pick_prior used", "trigger changes")


def extras(arm_dir: str) -> list[dict]:
    """Per run: pairs hit, the stated distribution, the gap and the count."""
    cp = {r["run_id"]: r for r in json.loads((ROOT / arm_dir / "class_p.json").read_text())}
    out = []
    for f in sorted((ROOT / arm_dir).glob("cell_*.json"),
                    key=lambda p: int(p.name.split("_")[2])):
        x = json.loads(f.read_text())
        recs = [e for e in x["events"] if e["kind"] == "session_log"][0]["records"]
        hit = {int(k) for r in recs for k, _ in (r["support"] or [])}
        pred = x.get("prediction") or {}
        sr = x.get("submitted_sharpe")
        defl = sr - cp[x["run_id"]]["null_max_mean"] if sr is not None else None
        out.append({
            "pairs_hit": sum(1 for a, b in PAIRS if a in hit and b in hit),
            "stated_mean": pred.get("mean"), "stated_sd": pred.get("sd"),
            "sr_is": sr, "sr_deflated": defl,
            "gap": (pred["mean"] - defl) if pred.get("mean") is not None else None,
            "count": sum(int(r["n_candidates"] or 0) for r in recs),
            "submitted": tuple(tuple(p) for p in (x.get("submitted_support") or [])),
        })
    return out


def _u(a, b):
    a, b = [v for v in a if v is not None], [v for v in b if v is not None]
    if not a or not b:
        return None, a, b
    if len(set(a) | set(b)) == 1:
        return "degenerate", a, b
    return stats.mannwhitneyu(a, b, alternative="two-sided").pvalue, a, b


def _row(A, key, a, b, predicted: str):
    p, a, b = _u(a, b)
    ma, mb = np.mean(a), np.mean(b)
    direction = ("lower" if ma < mb else "higher" if ma > mb else "equal")
    agrees = {"fewer": "lower", "more": "higher"}[predicted] == direction
    ptxt = ("identical/degenerate" if p == "degenerate" else f"U p = {p:.4f}"
            + ("  <0.05" if p < 0.05 else ""))
    A(f"    {key:<26} orientation {ma:7.3f} (n {len(a)})   replay {mb:7.3f} "
      f"(n {len(b)})   predicted {predicted:<5} observed {direction:<6}"
      f"{'  AGREES' if agrees and direction != 'equal' else '  does not agree'}   {ptxt}")
    return ma - mb


def haircut(A, label, rs):
    from experiments.analyze_agent import mols
    g = [r for r in rs if r["stated_mean"] is not None]
    X = np.column_stack([np.ones(len(g)), [r["sr_is"] for r in g],
                         np.log([r["count"] for r in g])])
    try:
        f = mols(X, [r["stated_mean"] for r in g], ["const", "sr_is", "log_count"])
    except np.linalg.LinAlgError:
        A(f"    {label:<22} n {len(g)}   singular design; not estimable")
        return
    A(f"    {label:<22} n {f['n']:>3}   b (sr_is) {f['beta'][1]:+9.3f} "
      f"[{f['lo'][1]:+9.3f},{f['hi'][1]:+9.3f}]   c (log count) {f['beta'][2]:+7.4f} "
      f"[{f['lo'][2]:+7.4f},{f['hi'][2]:+7.4f}]   R2 {f['r2']:.3f}")


def read() -> str:
    L: list[str] = []
    A = L.append
    eo, er = load("etf_orientation"), load("etf_replay")
    xo, xr = extras("etf_orientation"), extras("etf_replay")
    so, sr3 = load("agent_cell_s3_orientation"), load("agent_cell_s3_replay")
    bo, br = behaviour(eo), behaviour(er)

    A("prereg/agent-cell.md — CELL 3 (6.5, ETF PANEL), READ ONCE")
    A("=" * 78)
    A(f"  orientation runs/etf_orientation n = {len(eo)};  replay gate runs/etf_replay "
      f"n = {len(er)}")
    A("  Operationalisations fixed in this reader's docstring before computing.")
    A("  Mann-Whitney U, two-sided, descriptive. n = 20 against 20 sees only a large")
    A("  difference; no difference is not equivalence.")
    A("")
    A("THE FIVE PREDICTIONS")
    A("-" * 78)
    d = {}
    d["pairs"] = _row(A, "near-dup pairs evaluated", [r["pairs_hit"] for r in xo],
                      [r["pairs_hit"] for r in xr], "fewer")
    for key, pred in (("moves to submit", "fewer"), ("pick_prior used", "more"),
                      ("trigger changes", "fewer"), ("accepted picks", "more")):
        d[key] = _row(A, key, bo[key], br[key], pred)
    A("")
    A("  Fact about the panel, stated beside readout 1 and not read into it: the class")
    A("  maximum, (18+, 19-), IS a z/rank pair (vol252_z long, vol252_rank short). A")
    A("  search that avoids evaluating near-duplicate pairs cannot reach it.")
    for lab, xs in (("orientation", xo), ("replay", xr)):
        sub = {}
        for r in xs:
            sub[r["submitted"]] = sub.get(r["submitted"], 0) + 1
        A(f"    submitted, {lab}: " + ", ".join(
            "[" + ", ".join(f"{k}{'+' if s > 0 else '-'}" for k, s in key) + f"] x{n}"
            for key, n in sorted(sub.items(), key=lambda kv: -kv[1])))
    A("")

    A("NET OF PRIMING (cell 2 read a difference on these three)")
    A("-" * 78)
    ps2o, ps2r = behaviour(so), behaviour(sr3)
    A("    NET = ETF diff - s3 placebo diff, each orientation minus replay. It agrees")
    A("    with the prediction when its sign does: negative for 'fewer', positive for")
    A("    'more'.")
    for key, pred in zip(PRIMED, ("fewer", "more", "fewer")):
        plac = np.mean(ps2o[key]) - np.mean(ps2r[key])
        net = d[key] - plac
        ok = (net < 0) if pred == "fewer" else (net > 0)
        A(f"    {key:<26} ETF diff {d[key]:+7.3f}   s3 placebo diff {plac:+7.3f}   "
          f"NET {net:+7.3f}   predicted {pred:<5} {'AGREES' if ok else 'does not agree'}")
    A("    Readout 1 and accepted picks have no placebo: s3 has no z/rank pairs, and")
    A("    picks were zero in both cell-2 arms.")
    A("")

    A("REGISTERED FAILURE MODE: confidence up, deflation gap unchanged")
    A("-" * 78)
    _row(A, "stated sd (lower = conf.)", [r["stated_sd"] for r in xo],
         [r["stated_sd"] for r in xr], "fewer")
    p_m, a_m, b_m = _u([r["stated_mean"] for r in xo], [r["stated_mean"] for r in xr])
    A(f"    {'stated mean':<26} orientation {np.mean(a_m):7.3f}   replay {np.mean(b_m):7.3f}"
      f"   U p = {p_m:.4f}")
    p_g, a_g, b_g = _u([r["gap"] for r in xo], [r["gap"] for r in xr])
    A(f"    {'deflation gap':<26} orientation {np.mean(a_g):+7.3f} (n {len(a_g)})   "
      f"replay {np.mean(b_g):+7.3f} (n {len(b_g)})   U p = {p_g:.4f}")
    A(f"    sr_deflated: orientation mean {np.mean([r['sr_deflated'] for r in xo]):+.3f}, "
      f"replay {np.mean([r['sr_deflated'] for r in xr]):+.3f}")
    p_sd, _, _ = _u([r["stated_sd"] for r in xo], [r["stated_sd"] for r in xr])
    conf_up = np.mean([r["stated_sd"] for r in xo if r["stated_sd"] is not None]) < \
        np.mean([r["stated_sd"] for r in xr if r["stated_sd"] is not None])
    fires = conf_up and p_sd < 0.05 and not (p_g < 0.05)
    A(f"  FAILURE MODE: {'OBSERVED' if fires else 'NOT OBSERVED'} — it requires a "
      "difference in stated sd toward confidence AND no difference in the gap")
    A("")

    A("HAIRCUT REGRESSION — stated mean = a + b*sr_is + c*log(evaluation count)")
    A("-" * 78)
    haircut(A, "ETF orientation", xo)
    haircut(A, "ETF replay gate", xr)
    A("    sr_is takes three values on this panel (0.2890, 0.2995, 0.3159): every run")
    A("    submits one of three members, so b is fitted on a range of 0.027 Sharpe and")
    A("    its interval is read as such. 6.5's control, declared-class and prior-weighted")
    A("    arms have not run, so 'beside the others' is beside the replay arm only.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/agent_cell_read_cell3.txt")
    a = ap.parse_args(argv)
    text = read()
    print(text)
    Path(a.out).write_text(text + "\n")
    print(f"\nwritten to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
