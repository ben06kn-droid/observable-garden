"""calibration-at-1pct: is the gate calibrated at 1%, not just at 5%?

    python -m experiments.calibration_at_1pct --arm A            # local, seconds
    python -m experiments.calibration_at_1pct --arm B --smoke 50  # sizing measurement
    python -m experiments.calibration_at_1pct --arm B --workers 32
    python -m experiments.calibration_at_1pct --arm C --workers 32

Pre-registered in prereg/calibration-at-1pct.md.

**Arm A** reads the p-value every graded s0 run already stored and reports the
rejection rate at three levels with Wilson intervals plus a KS test against
U(0,1), per model and pooled. It gates nothing: at n = 419 a true rate of 1% has
a Wilson half-width of about 0.95 points, so it cannot resolve the 1% tail. The
counts were computed on 2026-09-19, before the pre-registration existed, and are
recorded there as observed rather than registered.

**Arm B** is what the decision rules turn on: the agent arm's own configuration
(s0, K=40, M=50, T=5,000, sigma=1) with scripted searchers, priced against the
same 82,240-member declared class the agents were held to, at the same
B = 10,000 `watch.open` gave every agent run.

**Arm C** re-runs arm B's first 500 draws at B = 50,000 to ask whether 10,000
replicates place the 1% critical value.

The class null depends on the base columns and the class, not on the searcher,
so one null per draw serves both searchers. That is why arm B costs one bootstrap
per draw rather than two.

Reports numbers only. Interpretation belongs in the write-up.
"""
from __future__ import annotations

import argparse
import csv
import json
import pickle
import time
from pathlib import Path

import numpy as np
from scipy.stats import kstest, norm

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length
from estimator.metrics import ks_critical_value, type1_rate
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from garden._full_class_engine import full_class_null_max, full_class_observed_max
from garden.spec_class import SubsetClass
from searchers.scripted import Adaptive, Greedy

ALPHAS = (0.10, 0.05, 0.01)
BATCHES = ("b1-baseline", "b2-arms", "b3-models", "b4-s3-recal", "b5-opus")
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"

# Arms B and C: the agent arm's configuration, from experiments/e_agent.py CONFIGS["s0"].
M, T, T_OOS, K, D = 50, 5000, 1000, 40, 3
CLASS = SubsetClass(max_size=D, signed=True)      # 82,240 members at K=40
SEED0, BLOCK = 100_000, 25                        # used by no earlier experiment
N_DRAWS_B, B_B = 5000, 10_000
N_DRAWS_C, B_C = 500, 50_000
SEARCHERS = ("greedy", "adaptive")

# Arm D, from amendment 2: the exhaustive searcher, on arm B's first 2,000 seeds
# so every draw is paired. Four statistics are scored against one signed class
# null -- the two closed-form maxima cost ~8 ms against the bootstrap's ~160 s,
# so the unsigned sublattice and both scripted searchers ride along free.
N_DRAWS_D, B_D = 2000, 10_000
N_PAIRED_D, B_D_PAIRED = 500, 50_000
UNSIGNED = SubsetClass(max_size=D, signed=False)   # 10,700 members at K=40
MEMBERS_D = ("exhaustive-signed", "exhaustive-unsigned", "adaptive", "greedy")
NULL_QUANTILES = (0.90, 0.95, 0.99, 0.999)

BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#8a8a86", "#222222", "#8a8a86"


# ------------------------------------------------------------------ arm A

def read_manifest(runs_root: Path) -> list[dict]:
    rows: list[dict] = []
    for b in BATCHES:
        p = runs_root / b / "runs.csv"
        if not p.exists():
            continue
        with p.open(newline="") as fh:
            rd = csv.reader(fh)
            fields = next(rd)
            rows += [{k: json.loads(v) for k, v in zip(fields, row)} for row in rd]
    return rows


def s0_pvalues(rows: list[dict]) -> list[dict]:
    """Every graded s0 run carrying a p-value. s0 is the pure null, so every
    rejection is a type-I error; s3 carries a real edge and is not this
    question."""
    return [r for r in rows
            if r["config"] == "s0" and r["graded"] and r["p_value"] is not None]


def summarize(name: str, p: np.ndarray) -> dict:
    ks = kstest(p, "uniform")
    out = {"group": name, "n": int(p.size),
           "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue),
           "ks_crit_05": float(ks_critical_value(p.size, 0.05)), "levels": {}}
    for a in ALPHAS:
        rate, lo, hi = type1_rate(p, alpha=a)
        out["levels"][a] = {"rejections": int(np.sum(p < a)), "rate": rate,
                            "lo": lo, "hi": hi}
    return out


def groups_of(runs: list[dict]) -> dict[str, np.ndarray]:
    g = {"pooled": np.array([r["p_value"] for r in runs], dtype=float)}
    for model in sorted({r["model"] for r in runs}):
        g[model] = np.array([r["p_value"] for r in runs if r["model"] == model],
                            dtype=float)
    return g


def arms_of(runs: list[dict]) -> dict[str, np.ndarray]:
    """Not pre-registered; reported for context. The pre-registration notes that
    the gate and pushed arms saw a 5% bar during their search, which changes
    behaviour rather than the validity of the p-value."""
    return {arm: np.array([r["p_value"] for r in runs if r["arm"] == arm], dtype=float)
            for arm in sorted({r["arm"] for r in runs})}


def table(rows: list[dict], title: str, note: str = "") -> list[str]:
    L = [title, "-" * 78]
    if note:
        L += [note, ""]
    L += [f"{'group':<22}{'n':>6}" + "".join(f"{f'a={a}':>22}" for a in ALPHAS),
          f"{'':<22}{'':>6}" + "".join(f"{'k    rate (95% CI)':>22}" for _ in ALPHAS)]
    for s in rows:
        line = f"{s['group']:<22}{s['n']:>6}"
        for a in ALPHAS:
            d = s["levels"][a]
            line += f"{d['rejections']:>4}  {d['rate']:.4f} ({d['lo']:.3f}-{d['hi']:.3f})".rjust(22)
        L.append(line)
    L += ["", f"{'group':<22}{'n':>6}{'KS stat':>12}{'KS p':>12}{'KS crit .05':>14}"]
    for s in rows:
        L.append(f"{s['group']:<22}{s['n']:>6}{s['ks_stat']:>12.4f}"
                 f"{s['ks_p']:>12.4f}{s['ks_crit_05']:>14.4f}")
    return L + [""]


def figure(groups: dict[str, np.ndarray], out: Path) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"pooled": INK, "claude-sonnet-5": BLUE, "claude-fable-5-1": ORANGE,
              "greedy": BLUE, "adaptive": ORANGE,
              "exhaustive-signed": INK, "exhaustive-unsigned": GRAY}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, hi, label in ((axes[0], 1.0, "all p-values"),
                          (axes[1], 0.10, "the left tail, where 1% lives")):
        ax.plot([0, hi], [0, hi], color=GRAY, lw=1.2, ls="--", zorder=1,
                label="U(0,1)" if hi == 1.0 else None)
        for name, p in groups.items():
            x = np.sort(p)
            y = np.arange(1, x.size + 1) / x.size
            ax.step(np.concatenate([[0], x]), np.concatenate([[0], y]), where="post",
                    color=colors.get(name, GRAY), lw=1.6, zorder=2,
                    label=f"{name} (n={p.size})" if hi == 1.0 else None)
        ax.set_xlim(0, hi)
        ax.set_ylim(0, hi if hi < 1 else 1.0)
        ax.set_xlabel(f"p-value — {label}", color=INK, fontsize=10)
        ax.grid(alpha=0.25, zorder=0, linewidth=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9)
    for a in ALPHAS:
        axes[1].axvline(a, color=GRAY, lw=0.8, alpha=0.7, zorder=1)
    axes[0].set_ylabel("empirical CDF", color=INK, fontsize=10)
    axes[0].legend(frameon=False, fontsize=9, loc="lower right")
    fig.suptitle("s0 p-values against U(0,1) — calibration-at-1pct", fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def arm_a(out_dir: Path, runs_dir: Path) -> None:
    rows = read_manifest(runs_dir)
    runs = s0_pvalues(rows)
    if not runs:
        raise SystemExit("no graded s0 runs carrying a p-value")

    groups, arms = groups_of(runs), arms_of(runs)
    by_group = [summarize(k, v) for k, v in groups.items()]
    by_arm = [summarize(k, v) for k, v in arms.items()]

    s0_all = [r for r in rows if r["config"] == "s0"]
    L = ["calibration-at-1pct — arm A: the existing s0 runs, re-scored", "=" * 78,
         f"manifest rows {len(rows)}; s0 runs {len(s0_all)}; graded and carrying a "
         f"p-value {len(runs)}", ""]
    L += table(by_group, "PRE-REGISTERED — per model and pooled")
    L += table(by_arm, "BY ARM — context, not pre-registered",
               "The gate and pushed arms saw a 5% bar during their search.")
    L += ["FIGURE", "-" * 78,
          "  " + figure(groups, out_dir / "calibration_at_1pct_ecdf.png"), ""]

    text = "\n".join(L)
    print(text)
    (out_dir / "calibration_at_1pct.txt").write_text(text + "\n")
    with (out_dir / "calibration_at_1pct_data.pkl").open("wb") as fh:
        pickle.dump({"groups": groups, "arms": arms, "by_group": by_group,
                     "by_arm": by_arm, "alphas": ALPHAS}, fh)


# ------------------------------------------------------------ arms B and C

def build(name: str, seed: int):
    return Greedy(seed=seed) if name == "greedy" else Adaptive(max_features=D, seed=seed)


def run_draw(B: int, seed: int) -> dict:
    """One null draw: price the declared class once, then score each searcher's
    own submission against it. The class null is a property of the base columns
    and the class, so both searchers share it."""
    t0 = time.time()
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    ann = float(np.sqrt(cfg.periods_per_year))
    data = generate(cfg)

    base = Sandbox(data, periods_per_year=cfg.periods_per_year).base_feature_columns()
    L = int(select_block_length(base - base.mean(axis=0)))
    M_b, _, floor, cap = full_class_null_max(base, CLASS, B=B, block_length=L,
                                             annualization=ann, seed=seed)
    out: dict = {"_draw": {"block_length": L, "floor": int(floor), "cap": int(cap),
                           "null_max_mean": float(M_b.mean())}}
    for name in SEARCHERS:
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=CLASS)
        build(name, seed).run(sb)
        _, dist = sb.submission
        sr = float(dist.mean)
        out[name] = {"p_value": float((1 + np.sum(M_b >= sr)) / (B + 1)), "sr_sel": sr}
    out["_draw"]["seconds"] = time.time() - t0
    return out


def run_draw_d(B: int, seed: int) -> dict:
    """Arm D's draw. The same class null as arm B on the same seed, with four
    statistics scored against it instead of two.

    Both exhaustive maxima are scored against the *signed* class null, because
    that is the null the gate prices and rule 4's decomposition needs one common
    bar: the gap between the two measures confinement to the sublattice, which
    is only a gap if the bar does not move with the searcher."""
    t0 = time.time()
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    ann = float(np.sqrt(cfg.periods_per_year))
    data = generate(cfg)

    base = Sandbox(data, periods_per_year=cfg.periods_per_year).base_feature_columns()
    L = int(select_block_length(base - base.mean(axis=0)))
    M_b, _, floor, cap = full_class_null_max(base, CLASS, B=B, block_length=L,
                                             annualization=ann, seed=seed)

    def score(sr: float) -> float:
        return float((1 + np.sum(M_b >= sr)) / (B + 1))

    sr_s, _, f_s, c_s = full_class_observed_max(base, CLASS, annualization=ann)
    sr_u, _, f_u, c_u = full_class_observed_max(base, UNSIGNED, annualization=ann)
    out: dict = {
        "_draw": {"block_length": L, "floor": int(floor), "cap": int(cap),
                  "null_max_mean": float(M_b.mean()),
                  "observed_floor": int(f_s + f_u), "observed_cap": int(c_s + c_u),
                  "null_q": np.quantile(M_b, NULL_QUANTILES)},
        "exhaustive-signed": {"p_value": score(sr_s), "sr_sel": float(sr_s)},
        "exhaustive-unsigned": {"p_value": score(sr_u), "sr_sel": float(sr_u)}}
    for name in SEARCHERS:
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=CLASS)
        build(name, seed).run(sb)
        sr = float(sb.submission[1].mean)
        out[name] = {"p_value": score(sr), "sr_sel": sr}
    out["_draw"]["seconds"] = time.time() - t0
    return out


def run_scripted(arm: str, n_draws: int, B: int, workers: int | None,
                 checkpoint_dir: str | None, git: dict) -> dict:
    is_d = arm.startswith("D")
    members = MEMBERS_D if is_d else SEARCHERS
    starts = list(range(0, n_draws, BLOCK))
    cells = {(arm, s): [(B, SEED0 + i) for i in range(s, min(s + BLOCK, n_draws))]
             for s in starts}
    got = run_cells(run_draw_d if is_d else run_draw, cells,
                    checkpoint_dir=checkpoint_dir, workers=workers)
    rows = [d for s in starts for d in got[(arm, s)]]
    data = {"arm": arm, "git_at_launch": git, "seeds": SEED0 + np.arange(n_draws),
            "settings": {"M": M, "T": T, "K": K, "d": D, "B": B, "draws": n_draws,
                         "class_size": CLASS.size(K), "class": CLASS.name},
            "seconds": np.array([r["_draw"]["seconds"] for r in rows]),
            "block_length": np.array([r["_draw"]["block_length"] for r in rows]),
            "floor": np.array([r["_draw"]["floor"] for r in rows]),
            "cap": np.array([r["_draw"]["cap"] for r in rows]),
            "members": members}
    for name in members:
        data[name] = {f: np.array([r[name][f] for r in rows])
                      for f in ("p_value", "sr_sel")}
    if is_d:
        data["quantiles"] = NULL_QUANTILES
        data["null_q"] = np.array([r["_draw"]["null_q"] for r in rows])
        for f in ("observed_floor", "observed_cap"):
            data[f] = np.array([r["_draw"][f] for r in rows])
    return data


def report_scripted(data: dict, out_dir: Path, full_n: int) -> str:
    s, n = data["settings"], data["settings"]["draws"]
    secs = data["seconds"]
    git = data["git_at_launch"]
    L = [f"calibration-at-1pct — arm {data['arm']}: scripted searchers under the declared class",
         "=" * 78,
         f"n={n} draws, B={s['B']:,}, K={s['K']}, M={s['M']}, T={s['T']:,}, "
         f"class {s['class']} ({s['class_size']:,} members)",
         f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}", ""]

    rows = [summarize(name, data[name]["p_value"])
            for name in data.get("members", SEARCHERS)]
    L += table(rows, "TYPE-I AND UNIFORMITY")

    L += ["COST", "-" * 78,
          f"  per draw   mean {secs.mean():7.2f}s   median {np.median(secs):7.2f}s"
          f"   max {secs.max():7.2f}s",
          f"  this run   {secs.sum() / 3600:.2f} CPU-hours over {n} draws"]
    if n < full_n:
        L.append(f"  projected  {secs.mean() * full_n / 3600:.1f} CPU-hours for the full "
                 f"{full_n} draws "
                 f"({secs.mean() * full_n / 3600 / 32:.1f} h wall on 32 cores)")
    L += ["", "GUARDS AND BLOCK LENGTHS", "-" * 78,
          f"  variance floor binds {int(data['floor'].sum())}   "
          f"sharpe cap binds {int(data['cap'].sum())}",
          f"  block length: min {int(data['block_length'].min())}, "
          f"median {int(np.median(data['block_length']))}, "
          f"max {int(data['block_length'].max())}", ""]
    return "\n".join(L)


def compare_arms(arm_c: dict, out_dir: Path) -> list[str]:
    """Decision rule 3: the B=50,000 rejection rate at 1% must lie inside the
    B=10,000 Wilson interval computed on the same draws."""
    p = out_dir / "calibration_at_1pct_armB_data.pkl"
    if not p.exists():
        return ["TAIL RESOLUTION", "-" * 78,
                "  arm B's data file is absent; run arm B first", ""]
    with p.open("rb") as fh:
        arm_b = pickle.load(fh)
    n = arm_c["settings"]["draws"]
    L = ["TAIL RESOLUTION — arm C against arm B on the same first "
         f"{n} draws", "-" * 78]
    for name in SEARCHERS:
        pb, pc = arm_b[name]["p_value"][:n], arm_c[name]["p_value"][:n]
        rb, lo, hi = type1_rate(pb, alpha=0.01)
        rc, _, _ = type1_rate(pc, alpha=0.01)
        inside = lo <= rc <= hi
        L.append(f"  {name:<10} B=10,000 {rb:.4f} ({lo:.4f}-{hi:.4f})   "
                 f"B=50,000 {rc:.4f}   inside: {'yes' if inside else 'NO'}")
    return L + [""]


def arm_d_rules(data: dict) -> list[str]:
    """Amendment 2's rules 1-4. Exactness is admissible here and was not in arm
    B, because `ExhaustiveClass` submits the class argmax: P2 binds with equality,
    its conservatism vanishes, and P1 predicts exact calibration up to o(1)."""
    ex = data["exhaustive-signed"]["p_value"]
    s = summarize("exhaustive-signed", ex)
    L = ["DECISION RULES — amendment 2", "-" * 78,
         "  Rules 1-2 (exactness). The Wilson interval must contain nominal.",
         "  One-sided halt: only an excess triggers it."]
    for a in ALPHAS:
        v = s["levels"][a]
        inside = v["lo"] <= a <= v["hi"]
        side = "" if inside else ("  EXCESS -> halt" if v["lo"] > a else "  low, reported not gating")
        L.append(f"    a={a:<5} k={v['rejections']:<5} rate {v['rate']:.4f} "
                 f"({v['lo']:.4f}-{v['hi']:.4f})   contains {a}: "
                 f"{'yes' if inside else 'NO'}{side}")
    L += ["",
          f"  Rule 3 (uniformity). KS D={s['ks_stat']:.4f} vs 5% critical "
          f"{s['ks_crit_05']:.4f}, p={s['ks_p']:.4f}: "
          f"{'does not reject' if s['ks_p'] >= 0.05 else 'REJECTS'}", ""]

    order = ("exhaustive-signed", "exhaustive-unsigned", "adaptive", "greedy")
    ps = {k: data[k]["p_value"] for k in order}
    n = ex.size
    L += ["  Rule 4 (secondary, no halt). P2's ordering, all four scored against",
          "  the same signed class null. A liberal violation falsifies P2.",
          f"    {'link':<48}{'holds':>8}{'violations':>13}"]
    chain = np.ones(n, dtype=bool)
    for lo_name, hi_name in zip(order, order[1:]):
        ok = ps[lo_name] <= ps[hi_name]
        chain &= ok
        L.append(f"    {f'p[{lo_name}] <= p[{hi_name}]':<48}"
                 f"{ok.sum() / n:8.2%}{int((~ok).sum()):>13}")
    L.append(f"    {'full chain':<48}{chain.sum() / n:8.2%}{int((~chain).sum()):>13}")

    L += ["", "    Decomposition of arm B's 1.0% at a=0.05, on the paired draws:"]
    for name in order:
        r = [f"a={a} {np.mean(ps[name] < a):7.2%}" for a in ALPHAS]
        L.append(f"    {name:<24}" + "   ".join(r))
    L += ["    The gap signed->unsigned is the cost of confinement to the",
          "    sublattice; unsigned->adaptive is sub-maximal search within it.", ""]
    return L


def arm_d_paired(paired: dict, out_dir: Path) -> list[str]:
    """Amendment 2's rule 5 (tail resolution, superseding arm C's rule 3 as the
    evidence) and amendment 4's rule 6 (reproducibility: the verdict flip rate).

    Rule 5 asks whether the two bootstrap sizes give the same *rate*; rule 6 asks
    whether they give the same *verdict on the same draw*. They are different
    questions, and only rule 6 can implicate B."""
    f = out_dir / "calibration_at_1pct_armD_data.pkl"
    if not f.exists():
        return ["TAIL RESOLUTION", "-" * 78, "  arm D's data file is absent", ""]
    with f.open("rb") as fh:
        base = pickle.load(fh)
    n = paired["settings"]["draws"]
    L = [f"RULE 5 — tail resolution, B=50,000 against B=10,000 on the same {n} draws",
         "-" * 78]
    for name in paired["members"]:
        p10, p50 = base[name]["p_value"][:n], paired[name]["p_value"][:n]
        r10, lo, hi = type1_rate(p10, alpha=0.01)
        r50, _, _ = type1_rate(p50, alpha=0.01)
        L.append(f"  {name:<22} B=10,000 {r10:.4f} ({lo:.4f}-{hi:.4f})   "
                 f"B=50,000 {r50:.4f}   inside: {'yes' if lo <= r50 <= hi else 'NO'}")

    L += ["", "RULE 6 — reproducibility (amendment 4). Secondary, no halt.",
          "-" * 78,
          "  Flip rate: the share of paired draws whose verdict differs between",
          "  the two bootstrap sizes. This, not the rate, is what B controls.",
          f"    {'member':<22}{'flip a=0.05':>13}{'flip a=0.01':>13}"
          f"{'mean p50k-p10k':>17}{'t':>8}"]
    for name in paired["members"]:
        p10, p50 = base[name]["p_value"][:n], paired[name]["p_value"][:n]
        d = p50 - p10
        tstat = d.mean() / (d.std(ddof=1) / np.sqrt(n)) if d.std(ddof=1) > 0 else 0.0
        flips = [np.mean((p10 < a) != (p50 < a)) for a in (0.05, 0.01)]
        L.append(f"    {name:<22}{flips[0]:12.2%} {flips[1]:12.2%} "
                 f"{d.mean():16.6f} {tstat:7.2f}")
    L += ["", "  Signed shift on draws with p(B=10,000) < 0.05 — the region the",
          "  verdict actually turns on. Selected on the quantity differenced, so",
          "  it is descriptive, not a test."]
    for name in paired["members"]:
        p10, p50 = base[name]["p_value"][:n], paired[name]["p_value"][:n]
        sel = p10 < 0.05
        k = int(sel.sum())
        if k < 2:
            L.append(f"    {name:<22}n={k}, too few to difference")
            continue
        d = (p50 - p10)[sel]
        L.append(f"    {name:<22}n={k:<5} mean {d.mean():+.6f}   "
                 f"sd {d.std(ddof=1):.6f}   "
                 f"MC prediction {np.sqrt(0.05 * 0.95 / B_D_PAIRED):.6f}")
    L += ["", "  A shift near zero exonerates B and leaves rule 1's fails-high",
          "  branch pointing at T, the block length and the studentization.", ""]
    return L


def arm_d_integrity(data: dict, out_dir: Path) -> list[str]:
    """Greedy's and Adaptive's p-values against arm B's stored values on the
    shared seeds.

    `run_draw` and `run_draw_d` build the same class null from the same seed and
    run the same searchers, so on a shared seed the p-values must be *bit*
    identical. Anything else means something drifted between the two runs -- the
    class definition, the block-length selector, a library version -- and rule 4's
    pairing with arm B would be comparing two different experiments.
    """
    f = out_dir / "calibration_at_1pct_armB_data.pkl"
    L = ["INTEGRITY — arm D against arm B on the shared seeds", "-" * 78]
    if not f.exists():
        return L + ["  arm B's data file is absent; check skipped", ""]
    with f.open("rb") as fh:
        arm_b = pickle.load(fh)

    shared = min(int(arm_b["settings"]["draws"]), int(data["settings"]["draws"]))
    same_b = arm_b["settings"]["B"] == data["settings"]["B"]
    if not np.array_equal(arm_b["seeds"][:shared], data["seeds"][:shared]):
        return L + ["  SEEDS DIFFER between the arms; pairing is invalid", ""]
    L.append(f"  {shared} shared seeds, both at B={data['settings']['B']:,}"
             if same_b else
             f"  {shared} shared seeds, arm B at B={arm_b['settings']['B']:,} vs "
             f"arm D at B={data['settings']['B']:,} -- expect MC agreement, not equality")
    for name in SEARCHERS:
        pb, pd = arm_b[name]["p_value"][:shared], data[name]["p_value"][:shared]
        d = np.abs(pb - pd)
        exact = bool(np.array_equal(pb, pd))
        verdict = "identical" if exact else f"max |diff| {d.max():.2e}"
        if same_b and not exact:
            se = float(np.sqrt(np.mean(pb * (1 - pb)) / data["settings"]["B"]))
            verdict += f"  MISMATCH at shared B (MC sd would be {se:.2e})"
        L.append(f"    {name:<12}{verdict}")
    return L + [""]


def arm_d_rule6_analytic(data: dict) -> list[str]:
    """Amendment 5: rule 6 computed from the stored p-values instead of bought.

    A verdict flips only if the p-value sits within Monte Carlo noise of the
    threshold, so the expected flip count is the summed per-draw crossing
    probability. `SE` treats the two bootstraps as independent, which they are
    not -- the larger nests the smaller -- so this is deliberately an upper bound.
    """
    L = ["RULE 6 — reproducibility, reported analytically (amendment 5)", "-" * 78,
         "  Expected verdict flips if the 2,000 draws were rerun at B=50,000.",
         "  Upper bound: the nested replicate streams make the truth ~18% smaller.",
         "  Amendment 6: the trigger compares the count on the 500 draws the",
         f"  conditional pass would run. Uniform p predicts 0.95 at a=0.05.",
         f"    {'member':<22}{'a':>6}{'per draw':>11}{'on 2,000':>11}{'on 500':>10}"]
    trigger = False
    for name in data["members"]:
        ph = data[name]["p_value"]
        for a in (0.05, 0.01):
            se = np.sqrt(ph * (1 - ph) * (1 / B_D + 1 / B_D_PAIRED))
            pr = np.where(se > 0, norm.cdf(-np.abs(ph - a) / np.where(se > 0, se, 1.0)), 0.0)
            on500 = pr.mean() * N_PAIRED_D
            trigger |= bool(on500 > 2.0)
            L.append(f"    {name:<22}{a:>6}{pr.mean():10.4%}{pr.sum():11.2f}"
                     f"{on500:10.2f}")
    L += ["", "  Amendment 5's escape hatch, as restated by amendment 6: the pass runs",
          "  anyway if the expected count on 500 draws exceeds 2.",
          f"  Exceeded: {'YES' if trigger else 'no'}", ""]
    return L, trigger


def arm_d_conditional(data: dict) -> list[str]:
    """Amendment 5's trigger: the B=50,000 pass runs only on an excess at 1%."""
    s = summarize("exhaustive-signed", data["exhaustive-signed"]["p_value"])["levels"][0.01]
    excess = s["lo"] > 0.01
    L = ["CONDITIONAL B=50,000 PASS (amendment 5)", "-" * 78,
         f"  rule 1 at a=0.01: rate {s['rate']:.4f} ({s['lo']:.4f}-{s['hi']:.4f})",
         f"  excess at 1% (lower bound above nominal): {'YES' if excess else 'no'}"]
    if excess:
        L += ["  -> the pass RUNS. B must be separated from the bootstrap's tail",
              "     approximation before rule 1's fails-high branch names a culprit:",
              "     python -m experiments.calibration_at_1pct --arm Dpaired --workers 16"]
    else:
        L += ["  -> the pass does NOT run. Rule 5 is not run; arm C's rule 3 remains",
              "     the reported empirical evidence on tail resolution."]
    return L + [""]


def arm_bc(arm: str, out_dir: Path, workers: int | None, checkpoint_dir: str | None,
           smoke: int | None) -> None:
    full_n, B = {"B": (N_DRAWS_B, B_B), "C": (N_DRAWS_C, B_C),
                 "D": (N_DRAWS_D, B_D), "Dpaired": (N_PAIRED_D, B_D_PAIRED)}[arm]
    n = smoke if smoke else full_n
    data = run_scripted(arm, n, B, workers, checkpoint_dir, git_state())

    text = report_scripted(data, out_dir, full_n)
    if arm == "C":
        text += "\n" + "\n".join(compare_arms(data, out_dir))
    if arm == "D" and not smoke:
        text += "\n" + "\n".join(arm_d_rules(data))
        text += "\n" + "\n".join(arm_d_integrity(data, out_dir))
        rule6, forced = arm_d_rule6_analytic(data)
        cond = arm_d_conditional(data)
        if forced:
            cond = cond[:-1] + ["  Overridden by rule 6's escape hatch: the pass RUNS.", ""]
        text += "\n" + "\n".join(cond) + "\n" + "\n".join(rule6)
    if arm == "Dpaired" and not smoke:
        text += "\n" + "\n".join(arm_d_paired(data, out_dir))
    if not smoke:
        groups = {name: data[name]["p_value"] for name in data.get("members", SEARCHERS)}
        text += "\nFIGURE\n" + "-" * 78 + "\n  " + figure(
            groups, out_dir / f"calibration_at_1pct_arm{arm}_ecdf.png") + "\n"
    print(text)

    suffix = f"_arm{arm}_smoke{n}" if smoke else f"_arm{arm}"
    (out_dir / f"calibration_at_1pct{suffix}.txt").write_text(text + "\n")
    with (out_dir / f"calibration_at_1pct{suffix}_data.pkl").open("wb") as fh:
        pickle.dump(data, fh)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("A", "B", "C", "D", "Dpaired"), default="A")
    ap.add_argument("--runs-dir", default=str(RUNS_ROOT))
    ap.add_argument("--out", default="figures")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--checkpoint-dir", default=None)
    ap.add_argument("--smoke", type=int, default=None,
                    help="run this many draws instead of the full count, and "
                         "report the measured per-draw cost. Sizes the real run.")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if a.arm == "A":
        arm_a(out_dir, Path(a.runs_dir))
    else:
        arm_bc(a.arm, out_dir, a.workers, a.checkpoint_dir, a.smoke)


if __name__ == "__main__":
    main()
