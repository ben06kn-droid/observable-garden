"""Read 7.5 stage 2, the agent half, ONCE, in the registered order.

`prereg/planted-edge.md`, "Decision rules" and the stage-2 live section. The input is
the directory of **priced** run files (`experiments/price_runs.py` has written
`class_p`, `planted_truth`, and for the grammar arms the replay verdict). The
certificate is the **class tier's**: `p_class < α`, the tier rule.

1. **Rule 1**, per arm and level, at α = 0.05 and 0.01. A **false certificate** is a
   certified run whose submission has in-sample population Sharpe <= 0. It **fails high
   iff the lower Wilson 95% end exceeds α**. The prior-weighted arm is read **per
   route**: the list route against 0.04, the search route against 0.01, and the run's
   combined certificate against 0.05. **If any rule fails high, the reader stops there**
   and names the arm for the one-shot replication on 631000-631019.
2. **Rule 2**, power: correct certificates (population Sharpe > 0) per arm and level at
   0.05, against the scripted curve's pooled rate at that level (exact binomial test).
3. **Rule 3**, recovery of `m*` and of `m+`, exact and two of three, beside the
   exhaustive base rates (stage 1's realized class argmax).
4. **Rule 4**, the deflation gap: stated mean minus the submission's in-sample
   population Sharpe, as mean and median, with a one-sample t test and a Wilcoxon test.
5. **Rule 5**, certified against uncertified within level.
   - **PRIMARY:** the holdout population Sharpe, combined over levels with weights
     `nc*nu/(nc+nu)`.
   - **SECONDARY:** the realized holdout Sharpe on the sealed returns, opened here from
     a plaintext archive only against its registered SHA-256 (`--sealed`, `--sha256`).
6. **Rule 6** is read by `experiments/fidelity_read.py`, from the live presentation
   log, and is not repeated here.
7. **Rule 7**, check 4, on the unsaturable arm at 1.5. The replay tier's rate is set
   against the class tier's, each at the threshold that gives one rejection of 20 on
   the same arm's level-0 runs (actual size 0.05). The realized actual sizes are
   printed.

**Descriptive, registered, per arm and level, on both tiers:**
- coverage of `L_g` and tightness (`SR_pop - L_g`, median and quartiles);
- `P_5` against the sealed holdout (Brier score, and the observed share positive), for
  all runs and **for certified runs separately**, each tier by its own certificate
  (the class tier `p_class < 0.05`, the replay tier its verdict's status);
- the agent's stated distribution beside the gate's confidence curve: stated
  `P(SR > 0) = Phi(mean/sd)` against `C0`, and the stated mean against the gate's
  median, the smallest grid `s` with `C(s) <= 0.5`.

**The prior-weighted readouts:** route shares, declines, and whether the list contains
or overlaps `m*`.

It refuses to run unless the directory holds exactly the registered set of priced
runs (arms, levels and seeds; the reasoned-pick arm at 14, 16, 18 or 20 per level,
equal across levels).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, norm, ttest_1samp, wilcoxon

from estimator.metrics import wilson_ci

SEED0 = 630_000
N = 20
LEVELS = (0.0, 1.0, 1.5)
ARMS = {"replay gate": LEVELS, "unsaturable": LEVELS,
        "replay gate (reasoned pick)": LEVELS, "prior-weighted": (0.0, 1.5)}
GRAMMAR = ("replay gate", "unsaturable", "replay gate (reasoned pick)")
RP_COUNTS = (14, 16, 18, 20)      # the reasoned-pick arm: 14, then +2 per level, cap 20
ALPHAS = (0.05, 0.01)
ALPHA_PRIOR, ALPHA_SEARCH = 0.04, 0.01
GS = ("0.90", "0.95", "0.99")
# stage 1 (8660508): pooled scripted power at 0.05, and the exhaustive base rates
SCRIPTED_POWER = {0.0: 0.0, 1.0: 0.2035, 1.5: 0.4391}
BASE_RATES = {1.0: {"equals": 0.0450, "two_of_three": 0.2765, "equals_pop_best": 0.1160,
                    "two_of_three_pop_best": 0.3610},
              1.5: {"equals": 0.1215, "two_of_three": 0.4370, "equals_pop_best": 0.2230,
                    "two_of_three_pop_best": 0.5135}}


def _start(d):
    return next(e for e in d["events"] if e.get("kind") == "start")


def load(directory: Path, seed0: int = SEED0) -> dict:
    """{(arm, level): [run dicts in seed order]}, or a refusal."""
    runs = {}
    for f in sorted(Path(directory).glob("cell_planted_*.json")):
        d = json.loads(f.read_text())
        st = _start(d)
        runs.setdefault((d["arm"], float(st["level"])), []).append(d)
    want = {(a, lv) for a, lvs in ARMS.items() for lv in lvs}
    if set(runs) != want:
        raise SystemExit(f"arms and levels {sorted(runs)} are not the registered "
                         f"{sorted(want)}; refused")
    rp = {lv: len(runs[("replay gate (reasoned pick)", lv)]) for lv in LEVELS}
    if len(set(rp.values())) != 1 or rp[0.0] not in RP_COUNTS:
        raise SystemExit(f"the reasoned-pick arm has {rp} runs per level, not one of "
                         "14/16/18/20 equal across levels; refused")
    for (arm, lv), rs in runs.items():
        n = rp[0.0] if arm == "replay gate (reasoned pick)" else N
        rs.sort(key=lambda d: d["seed"])
        if [d["seed"] for d in rs] != list(range(seed0, seed0 + n)):
            raise SystemExit(f"{arm} at {lv}: seeds are not {seed0}-{seed0 + n - 1}; refused")
        for d in rs:
            kinds = {e.get("kind") for e in d["events"]}
            need = {"end", "class_p", "planted_truth"}
            if arm in GRAMMAR and not ({"verdict", "certify_error"} & kinds):
                need.add("verdict")
            if not need <= kinds:
                raise SystemExit(f"{d['run_id']}: not priced ({sorted(need - kinds)}); "
                                 "refused")
    return runs


def sr_in(d):
    t = d["planted_truth"].get("submitted_truth")
    return None if t is None else t["in_sample"]


def certified(d, alpha=0.05) -> bool:
    return d["class_p"]["p_upper"] < alpha and sr_in(d) is not None


def _wl(k, n, alpha):
    lo, hi = wilson_ci(k, n)
    return lo, hi, ("FAILS HIGH" if lo > alpha else "pass")


def rule1(runs, A) -> list:
    A("RULE 1 — false certification (certified with population Sharpe <= 0), per run")
    A("-" * 78)
    A("   fails high iff the lower Wilson 95% end exceeds alpha")
    fails = []
    for (arm, lv), rs in sorted(runs.items()):
        n = len(rs)
        if arm == "prior-weighted":
            for label, alpha, pick in (
                    ("list route", ALPHA_PRIOR,
                     lambda d: d["class_p"]["prior_weighted"]["route"] in ("list", "both")),
                    ("search route", ALPHA_SEARCH,
                     lambda d: d["class_p"]["prior_weighted"]["route"] in ("search", "both")),
                    ("combined", 0.05,
                     lambda d: d["class_p"]["prior_weighted"]["status"] == "CERTIFIED")):
                k = sum(1 for d in rs if pick(d) and sr_in(d) is not None and sr_in(d) <= 0)
                lo, hi, v = _wl(k, n, alpha)
                if v == "FAILS HIGH":
                    fails.append((arm, lv, label))
                A(f"   {arm:<28}{lv:>5.1f}  {label:<13} a={alpha:<5} {k:>3}/{n:<3} "
                  f"[{lo:.4f}, {hi:.4f}] {v}")
            continue
        for alpha in ALPHAS:
            k = sum(1 for d in rs if certified(d, alpha) and sr_in(d) <= 0)
            lo, hi, v = _wl(k, n, alpha)
            if v == "FAILS HIGH":
                fails.append((arm, lv, alpha))
            A(f"   {arm:<28}{lv:>5.1f}  {'class tier':<13} a={alpha:<5} {k:>3}/{n:<3} "
              f"[{lo:.4f}, {hi:.4f}] {v}")
    A(f"   RULE 1: {len(fails)} fail high" + (": " + "; ".join(map(str, fails)) if fails else ""))
    A("")
    return fails


def rule2(runs, A):
    A("RULE 2 — power at 0.05 (class tier): correct certificates, against the scripted curve")
    A("-" * 78)
    for (arm, lv), rs in sorted(runs.items()):
        n = len(rs)
        k = sum(1 for d in rs if certified(d) and sr_in(d) > 0)
        lo, hi = wilson_ci(k, n)
        ref = SCRIPTED_POWER[lv]
        p = binomtest(k, n, ref).pvalue if 0 < ref < 1 else float("nan")
        A(f"   {arm:<28}{lv:>5.1f}  {k:>3}/{n:<3} = {k / n:.4f} [{lo:.4f}, {hi:.4f}]   "
          f"scripted {ref:.4f}, exact binomial p {p:.4f}")
    A("")


def rule3(runs, A):
    A("RULE 3 — recovery, beside the exhaustive base rates (stage 1's class argmax)")
    A("-" * 78)
    keys = ("equals", "two_of_three", "equals_pop_best", "two_of_three_pop_best")
    for (arm, lv), rs in sorted(runs.items()):
        if lv == 0.0:
            continue
        n = len(rs)
        cells = []
        for k in keys:
            c = sum(1 for d in rs if d["planted_truth"]["submitted_recovery"][k])
            cells.append(f"{k} {c}/{n} (base {BASE_RATES[lv][k]:.4f})")
        A(f"   {arm:<28}{lv:>5.1f}  " + "; ".join(cells))
    A("")


def stated(d):
    p = d.get("prediction") or {}
    if p.get("mean") is None:
        return None, None
    return float(p["mean"]), float(p.get("sd") or 0.0)


def rule4(runs, A):
    A("RULE 4 — deflation gap: stated mean minus the submission's in-sample SR_pop")
    A("-" * 78)
    for (arm, lv), rs in sorted(runs.items()):
        g = np.array([stated(d)[0] - sr_in(d) for d in rs
                      if stated(d)[0] is not None and sr_in(d) is not None])
        if g.size < 2:
            A(f"   {arm:<28}{lv:>5.1f}  n {g.size}: too few stated means")
            continue
        t = ttest_1samp(g, 0.0)
        w = wilcoxon(g) if np.any(g != 0) else None
        A(f"   {arm:<28}{lv:>5.1f}  n {g.size}  mean {g.mean():+.4f}  median "
          f"{np.median(g):+.4f}  t p {t.pvalue:.4f}  Wilcoxon p "
          f"{(w.pvalue if w is not None else float('nan')):.4f}")
    A("")


def realized_holdout(runs, sealed):
    """{run_id: realized holdout Sharpe} from the sealed returns, or {} if not opened."""
    if sealed is None:
        return {}
    from dataclasses import replace
    from environments import planted_panel as pp
    from experiments.planted_edge import StreamCache, _sharpe
    base = pp.load_base()
    ann = float(np.sqrt(base.holdout.periods_per_year))
    out = {}
    for rs in runs.values():
        for d in rs:
            sup = d["planted_truth"].get("submitted_support_true")
            lv = float(_start(d)["level"])
            if not sup:
                continue
            panel = replace(base.holdout, returns=sealed[(int(d["seed"]), lv)])
            out[d["run_id"]] = _sharpe(StreamCache(panel).get(tuple(map(tuple, sup))), ann)
    return out


def rule5(runs, A, realized):
    A("RULE 5 — certified (0.05) against uncertified, within level")
    A("-" * 78)
    for label, val in (("PRIMARY: holdout population Sharpe",
                        lambda d: d["planted_truth"]["submitted_truth"]["holdout"]),
                       ("SECONDARY: realized holdout Sharpe, sealed returns",
                        lambda d: realized.get(d["run_id"]))):
        A(f"   {label}")
        if label.startswith("SECONDARY") and not realized:
            A("     the sealed holdout was not opened (--sealed, --sha256); not printed")
            continue
        for arm in ARMS:
            parts, wsum, num = [], 0.0, 0.0
            for lv in ARMS[arm]:
                rs = [d for d in runs[(arm, lv)] if sr_in(d) is not None]
                c = [val(d) for d in rs if certified(d) and val(d) is not None]
                u = [val(d) for d in rs if not certified(d) and val(d) is not None]
                if not c or not u:
                    parts.append(f"{lv}: n/a ({len(c)} cert)")
                    continue
                diff = np.mean(c) - np.mean(u)
                se = np.sqrt(np.var(c, ddof=1) / len(c) + np.var(u, ddof=1) / len(u)) \
                    if len(c) > 1 and len(u) > 1 else float("nan")
                w = len(c) * len(u) / (len(c) + len(u))
                wsum, num = wsum + w, num + w * diff
                parts.append(f"{lv}: {diff:+.4f} (SE {se:.4f}; {len(c)}/{len(u)})")
            comb = f"{num / wsum:+.4f}" if wsum else "n/a"
            A(f"     {arm:<28} " + "  ".join(parts) + f"   combined {comb}")
    A("")


def rule7(runs, A):
    A("RULE 7 — check 4 on the unsaturable arm at 1.5, at matched actual size")
    A("-" * 78)
    r0, r15 = runs[("unsaturable", 0.0)], runs[("unsaturable", 1.5)]
    for tier, p_of in (("class tier", lambda d: d["class_p"]["p_upper"]),
                       ("replay tier", lambda d: (d.get("verdict") or {}).get("p_certifying"))):
        p0 = [p_of(d) for d in r0 if p_of(d) is not None]
        if not p0:
            A(f"   {tier}: no level-0 p-values; not computable")
            continue
        thr = min(p0)                                   # one rejection of 20 at level 0
        size = sum(1 for p in p0 if p <= thr) / len(r0)
        p15 = [p_of(d) for d in r15]
        k = sum(1 for p in p15 if p is not None and p <= thr)
        A(f"   {tier:<12} threshold {thr:.4f} (actual size at level 0 {size:.4f}); "
          f"at 1.5 {k}/{len(r15)} = {k / len(r15):.4f}")
    A("")


def _stated_p_pos(mean, sd):
    if sd > 0:
        return float(norm.cdf(mean / sd))
    return 1.0 if mean > 0 else (0.5 if mean == 0 else 0.0)


def descriptive(runs, A, realized):
    A("DESCRIPTIVE (registered) — confidence coverage, tightness, P_5, stated vs gate")
    A("-" * 78)
    for (arm, lv), rs in sorted(runs.items()):
        for tier, conf_of in (("class", lambda d: d["class_p"].get("confidence")),
                              ("replay", lambda d: (d.get("verdict") or {}).get("confidence"))):
            got = [(d, conf_of(d)) for d in rs if conf_of(d) and sr_in(d) is not None]
            if not got:
                continue
            cells = []
            for g in GS:
                gap = np.array([sr_in(d) - c["L"][g] for d, c in got])
                q = np.quantile(gap, [0.25, 0.5, 0.75])
                cells.append(f"g{g[2:]} cover {int((gap >= 0).sum())}/{gap.size} gap "
                             f"{q[1]:+.3f} [{q[0]:+.3f},{q[2]:+.3f}]")
            A(f"   {arm:<28}{lv:>4.1f} {tier:<6} " + "; ".join(cells))
            if realized:
                cert = (certified if tier == "class" else
                        lambda d: (d.get("verdict") or {}).get("status") == "CERTIFIED")
                for subset, keep in (("all", lambda d: True), ("certified", cert)):
                    sel = [(d, c) for d, c in got if d["run_id"] in realized and keep(d)]
                    if not sel:
                        A(f"   {'':<28}{'':>4} {tier:<6} P_5 {subset:<9} none")
                        continue
                    P = np.array([c["P_H"] for d, c in sel])
                    y = np.array([realized[d["run_id"]] > 0 for d, c in sel], dtype=float)
                    A(f"   {'':<28}{'':>4} {tier:<6} P_5 {subset:<9} mean {P.mean():.3f} "
                      f"against observed {y.mean():.3f} (n {P.size}), Brier "
                      f"{np.mean((P - y) ** 2):.4f}")
            sp = [(stated(d), c) for d, c in got if stated(d)[0] is not None]
            if sp:
                dp = np.array([_stated_p_pos(m, s) - c["C0"] for (m, s), c in sp])
                med_gap = []
                for (m, s), c in sp:
                    C = np.asarray(c["curve"])
                    grid = c["grid"][0] + c["grid"][1] * np.arange(c["grid"][2])
                    idx = np.flatnonzero(C <= 0.5)
                    if idx.size:
                        med_gap.append(m - grid[idx[0]])
                A(f"   {'':<28}{'':>4} {tier:<6} stated P(SR>0) - C0: mean {dp.mean():+.3f}"
                  f" median {np.median(dp):+.3f}; stated mean - gate median: "
                  + (f"median {np.median(med_gap):+.3f} (n {len(med_gap)})" if med_gap
                     else "n/a"))
    A("")


def prior_weighted_readouts(runs, A):
    A("PRIOR-WEIGHTED — route shares, declines, the list and m*")
    A("-" * 78)
    for lv in ARMS["prior-weighted"]:
        rs = runs[("prior-weighted", lv)]
        routes = [d["class_p"]["prior_weighted"]["route"] for d in rs]
        decl = sum(1 for d in rs if d["class_p"]["prior_weighted"].get("declined"))
        cont = sum(1 for d in rs if d["planted_truth"].get("short_list_contains_m_star"))
        over = sum(1 for d in rs if d["planted_truth"].get("short_list_overlaps_m_star"))
        A(f"   level {lv}: certified by list {routes.count('list')}, search "
          f"{routes.count('search')}, both {routes.count('both')}, none "
          f"{routes.count(None)}; declined {decl}; list contains m* {cont}, overlaps {over}"
          f" (of {len(rs)})")
    A("")


def read(runs, sealed=None) -> tuple[str, bool]:
    L: list[str] = []
    A = L.append
    A("7.5 stage 2 — the agent half, READ ONCE, in the registered order")
    A("=" * 78)
    A(f"  {sum(len(v) for v in runs.values())} priced runs; certificate = class tier p < alpha")
    A("")
    fails = rule1(runs, A)
    if fails:
        A("THE READ STOPS HERE. By the registered branch, the one-shot replication on")
        A("631000-631019 runs for each failing arm before anything else is read:")
        for arm in sorted({f[0] for f in fails}):
            A(f"   {arm}")
        return "\n".join(L), True
    realized = realized_holdout(runs, sealed)
    rule2(runs, A)
    rule3(runs, A)
    rule4(runs, A)
    rule5(runs, A, realized)
    A("RULE 6 — read by experiments/fidelity_read.py from the live presentation log")
    A("")
    rule7(runs, A)
    prior_weighted_readouts(runs, A)
    descriptive(runs, A, realized)
    return "\n".join(L), False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="runs/planted_agent")
    ap.add_argument("--sealed", default=None, help="the plaintext holdout archive")
    ap.add_argument("--sha256", default=None, help="its registered SHA-256")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    runs = load(Path(a.dir))
    sealed = None
    if a.sealed:
        if not a.sha256:
            raise SystemExit("--sealed needs the registered --sha256")
        from experiments.planted_holdout import open_sealed
        _, sealed = open_sealed(a.sealed, a.sha256)
    text, _ = read(runs, sealed)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
