"""Agent-arm analysis, implementing prereg/AGENT_PROMPTS.md §5.

    python -m experiments.analyze_agent [--runs-dir runs] [--out figures/]

Reports numbers only. Interpretation belongs in the write-up, not here.

Two terms in §5 have no literal field in the data, so the reading is fixed
here and printed with every number that depends on it:

  "class-bar-implied expectation from the Watch verdict" -> `sr_deflated`,
  which is sr_reported - null_max_mean: what the class-bar correction leaves
  once the search is priced in. Deflation gap = stated mean - sr_deflated.

  "difference in mean stated confidence at matched evaluation count" -> the
  two fitted lines evaluated at the pooled median of log(evaluation count),
  the only matched point both arms span.

`no_submit` is a status, not an exclusion: §3 records such a run and keeps it
in the run count, so it is reported and retained.

The analysis set is the 80 `s0_T5000_*` runs. `runs/s0_control_000_T500` is
superseded by amendment 1 and excluded by prefix, not by judgement.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

PINNED_MODEL = "claude-sonnet-5"
PREFIX = "s0_T5000_"


# ---------------------------------------------------------------- loading

def load_run(d: Path) -> dict:
    j = lambda n: json.loads((d / n).read_text())          # noqa: E731
    cfg, verdict = j("config.json"), j("verdict.json")
    stated, oos, considered = j("stated.json"), j("oos.json"), j("considered.json")
    usage = json.loads((d / "usage.jsonl").read_text().splitlines()[-1])
    rows = [json.loads(l) for l in (d / "transcript.jsonl").read_text().splitlines()]

    tool_uses = [r for r in rows if r["kind"] == "tool_use"]
    evaluates = [r for r in rows if r["kind"] == "tool_result" and r.get("tool") == "evaluate"]
    submits = [r for r in rows if r["kind"] == "tool_result" and r.get("tool") == "submit"]
    statuses = [(i, r) for i, r in enumerate(rows)
                if r["kind"] == "tool_result" and r.get("tool") == "status"]
    errors = [r for r in rows if r["kind"] == "tool_error"]
    rejected = [r for r in rows if r["kind"] == "rate_limit" and r.get("status") == "rejected"]

    # Position of each status call as a fraction of the run's tool calls.
    tool_idx = [i for i, r in enumerate(rows) if r["kind"] == "tool_use"]
    def frac(i):
        prior = sum(1 for t in tool_idx if t < i)
        return prior / len(tool_idx) if tool_idx else float("nan")

    mu = usage.get("model_usage") or {}
    per_model = list(mu.values())[0] if mu else {}

    return {
        "run_id": d.name,
        "arm": cfg["arm"],
        "model": cfg.get("model", PINNED_MODEL),
        "config": cfg.get("config", "s0"),
        "budget": cfg.get("budget"),
        "power_at_open": (cfg.get("watch_open") or {}).get("power_at_reference"),
        "seed_index": cfg["seed_index"],
        "n_evaluated": len(evaluates),
        "n_tool_use": len(tool_uses),
        "n_refused": len(errors),
        "submitted_sr_is": verdict["sr_reported"],
        "stated_mean": stated["mean"],
        "stated_sd": stated["sd"],
        "status": verdict["status"],
        "sr_deflated": verdict["sr_deflated"],
        "critical_value": verdict["critical_value"],
        "p_value": verdict["p_value"],
        "oos": oos["oos_sharpe"],
        "considered": considered["n_considered"],
        "n_status_calls": len(statuses),
        "status_positions": [frac(i) for i, _ in statuses],
        # Whether the run's FINAL status call reported clearing the bar. Parsed
        # from that call's own text, which is the only record of it: the tool
        # returns "Best X vs bar Y; clears." or "...; does not clear.". None
        # when the run never called status.
        "last_cleared": (None if not statuses
                         else "does not clear" not in (statuses[-1][1].get("text") or "")),
        "submitted": bool(submits),
        # exclusion inputs
        "models_seen": usage.get("models_seen") or [],
        "non_mcp_tools": sorted({r["tool"] for r in tool_uses
                                 if not str(r.get("tool", "")).startswith("mcp__")}),
        "rate_limit_rejected": bool(rejected),
        # cost
        "input_tokens": per_model.get("inputTokens", 0),
        "output_tokens": per_model.get("outputTokens", 0),
        "cache_read": per_model.get("cacheReadInputTokens", 0),
        "cache_creation": per_model.get("cacheCreationInputTokens", 0),
        "thinking_tokens": per_model.get("thinkingTokens", 0),
        "cost_usd": usage.get("total_cost_usd") or 0.0,
        "wall_seconds": usage.get("wall_seconds"),
    }


def classify_exclusion(r: dict) -> str | None:
    """The three categories §5 fixes in advance, in its own order.

    The model check is against the run's OWN assigned model, not a global pin:
    batch 3 crosses arms with two models, and comparing every run to one string
    would exclude the whole fable half as a mismatch."""
    assigned = r.get("model", PINNED_MODEL)
    # Only strings naming a model count. The SDK also reports sentinels such as
    # "<synthetic>" for messages it generates itself; treating those as models
    # voided a real run (s0_T5000_sonnet_gate_087) on its first appearance.
    reported = [m for m in r["models_seen"] if str(m).startswith("claude-")]
    if not reported or [m for m in reported if m != assigned]:
        return "model_string"
    if r["non_mcp_tools"]:
        return "non_mcp_tool"
    if r["rate_limit_rejected"] and not r["submitted"]:
        return "rate_limit_before_submit"
    return None


# ---------------------------------------------------------------- statistics

def med_iqr(x) -> tuple[float, float, float]:
    a = np.asarray(x, dtype=float)
    return float(np.median(a)), float(np.percentile(a, 25)), float(np.percentile(a, 75))


def fmt_mi(x) -> str:
    m, q1, q3 = med_iqr(x)
    return f"{m:8.3f}  [{q1:.3f}, {q3:.3f}]"


def ols(x, y) -> dict:
    """Slope, intercept, slope SE and 95% CI. Plain OLS, no weighting."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    xbar, ybar = x.mean(), y.mean()
    sxx = ((x - xbar) ** 2).sum()
    slope = ((x - xbar) * (y - ybar)).sum() / sxx
    intercept = ybar - slope * xbar
    resid = y - (intercept + slope * x)
    dof = n - 2
    s2 = (resid ** 2).sum() / dof
    se = math.sqrt(s2 / sxx)
    from scipy.stats import t as tdist
    crit = tdist.ppf(0.975, dof)
    return {"n": n, "slope": slope, "intercept": intercept, "se": se, "dof": dof,
            "lo": slope - crit * se, "hi": slope + crit * se,
            "t": slope / se if se else float("nan"),
            "p": float(2 * tdist.sf(abs(slope / se), dof)) if se else float("nan"),
            "r2": 1 - (resid ** 2).sum() / ((y - ybar) ** 2).sum()}


def crps_gaussian(mu, sigma, y) -> float:
    """CRPS of N(mu, sigma^2) against observation y, closed form."""
    from scipy.stats import norm
    sigma = max(float(sigma), 1e-12)
    z = (float(y) - float(mu)) / sigma
    return float(sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi)))


# ---------------------------------------------------------------- report

def report(runs: list[dict], out_dir: Path) -> str:
    L: list[str] = []
    p = L.append

    p("Agent-arm analysis — prereg/AGENT_PROMPTS.md §5")
    p("=" * 78)
    p(f"analysis set: {len(runs)} runs matching {PREFIX}*")
    p("excluded by prefix: runs/s0_control_000_T500 (superseded, amendment 1)")
    p("")
    p("Definitions fixed here (§5 has no literal field for either):")
    p("  deflation gap   = stated mean - sr_deflated, where")
    p("                    sr_deflated = sr_reported - null_max_mean")
    p("  matched count   = pooled median of log(evaluation count)")
    p("  no_submit       = status, not an exclusion (§3 keeps the run)")
    p("")

    # -- exclusions
    p("EXCLUSIONS (pre-registered categories)")
    p("-" * 78)
    cats = ("model_string", "non_mcp_tool", "rate_limit_before_submit")
    # §5's primary analysis is config s0, per arm. The budget arm has its own
    # primary (amendment 4, assigned log B) and s3 its own block, so both are
    # reported separately; this table covers the s0 arms.
    arms = sorted({r["arm"] for r in runs if r["config"] == "s0"})
    kept: dict[str, list[dict]] = {a: [] for a in arms}
    excl: dict[str, dict[str, int]] = {a: {c: 0 for c in cats} for a in arms}
    no_submit = {a: 0 for a in arms}
    for r in runs:
        if r["config"] != "s0":
            continue
        c = classify_exclusion(r)
        if c:
            excl[r["arm"]][c] += 1
        else:
            kept[r["arm"]].append(r)
            if not r["submitted"]:
                no_submit[r["arm"]] += 1
    hdr = "".join(f"{a:>12}" for a in arms)
    p(f"{'category':<32}{hdr}")
    for c in cats:
        p(f"{c:<32}" + "".join(f"{excl[a][c]:>12}" for a in arms))
    p(f"{'-- total excluded':<32}" + "".join(f"{sum(excl[a].values()):>12}" for a in arms))
    p(f"{'no_submit (status, retained)':<32}" + "".join(f"{no_submit[a]:>12}" for a in arms))
    p(f"{'n retained':<32}" + "".join(f"{len(kept[a]):>12}" for a in arms))
    p("")

    # -- per-arm descriptives
    p("PER ARM — median [IQR]")
    p("-" * 78)
    for arm in arms:
        rs = kept[arm]
        if not rs:
            continue
        p(f"{arm}  (n = {len(rs)})")
        p(f"  evaluation count     {fmt_mi([r['n_evaluated'] for r in rs])}")
        p(f"  stated mean          {fmt_mi([r['stated_mean'] for r in rs])}")
        p(f"  stated sd            {fmt_mi([r['stated_sd'] for r in rs])}")
        p(f"  realized OOS Sharpe  {fmt_mi([r['oos'] for r in rs])}")
        p(f"  submitted SR (in-s)  {fmt_mi([r['submitted_sr_is'] for r in rs])}")
        p(f"  considered count     {fmt_mi([r['considered'] for r in rs])}")
        p(f"  refused attempts     {fmt_mi([r['n_refused'] for r in rs])}")
        from collections import Counter
        vd = Counter(r["status"] for r in rs)
        p(f"  verdicts             {dict(sorted(vd.items()))}")
        p("")

    # -- primary regression
    p("PRIMARY — stated mean on log(evaluation count), per arm")
    p("-" * 78)
    p("H0: slope = 0 (stated confidence deaf to the search performed)")
    p("")
    fits = {}
    for arm in arms:
        rs = kept[arm]
        if len(rs) < 3:
            continue
        x = np.log([r["n_evaluated"] for r in rs])
        y = np.array([r["stated_mean"] for r in rs])
        f = ols(x, y)
        fits[arm] = (f, x, y)
        p(f"{arm}:  slope {f['slope']:+.4f}   SE {f['se']:.4f}   "
          f"95% CI [{f['lo']:+.4f}, {f['hi']:+.4f}]")
        p(f"{'':<8}t {f['t']:+.2f} on {f['dof']} df,  p {f['p']:.4f},  "
          f"R² {f['r2']:.4f},  intercept {f['intercept']:+.4f}")
    p("")

    # -- between-arm
    p("BETWEEN ARM — control vs gate")
    p("-" * 78)
    have_both = "control" in fits and "gate" in fits
    if not have_both:
        p("control and gate not both present in this set; skipped")
        p("")
    fc = fits["control"][0] if have_both else None
    fg = fits["gate"][0] if have_both else None
    if have_both:
        dslope = fg["slope"] - fc["slope"]
        dse = math.sqrt(fc["se"] ** 2 + fg["se"] ** 2)
        from scipy.stats import norm
        p(f"difference in slope (gate - control): {dslope:+.4f}   SE {dse:.4f}   "
          f"95% CI [{dslope - 1.96*dse:+.4f}, {dslope + 1.96*dse:+.4f}]")
        p(f"{'':<36}z {dslope/dse:+.2f},  p {2*norm.sf(abs(dslope/dse)):.4f}")
        allx = np.concatenate([fits["control"][1], fits["gate"][1]])
        xm = float(np.median(allx))
        pc = fc["intercept"] + fc["slope"] * xm
        pg = fg["intercept"] + fg["slope"] * xm
        p(f"matched log(count) = {xm:.4f}  (count = {math.exp(xm):.1f})")
        p(f"stated mean at matched count: control {pc:+.4f}, gate {pg:+.4f}, "
          f"difference {pg - pc:+.4f}")
        p("")

    # -- secondary
    p("SECONDARY")
    p("-" * 78)
    for arm in arms:
        rs = kept[arm]
        if not rs:
            continue
        c = [crps_gaussian(r["stated_mean"], r["stated_sd"], r["oos"]) for r in rs]
        g = [r["stated_mean"] - r["sr_deflated"] for r in rs]
        p(f"{arm}:")
        p(f"  CRPS vs realized OOS   {fmt_mi(c)}   mean {np.mean(c):.4f}")
        p(f"  deflation gap          {fmt_mi(g)}   mean {np.mean(g):.4f}")
    p("")

    # -- gate status usage
    p("GATE ARM — status tool")
    p("-" * 78)
    rs = kept.get("gate", [])
    calls = [r["n_status_calls"] for r in rs] or [0]
    p(f"  status calls per run   {fmt_mi(calls)}   total {sum(calls)}")
    p(f"  runs never calling it  {sum(1 for c in calls if c == 0)} of {len(rs)}")
    pos = [q for r in rs for q in r["status_positions"]]
    if pos:
        p(f"  position in run        {fmt_mi(pos)}   (fraction of tool calls elapsed)")
        p(f"  first / last call      {min(pos):.3f} / {max(pos):.3f}")
        thirds = [sum(1 for q in pos if lo <= q < hi) for lo, hi in
                  ((0, 1/3), (1/3, 2/3), (2/3, 1.01))]
        p(f"  by third of run        first {thirds[0]}, middle {thirds[1]}, last {thirds[2]}")
    p("")

    # -- cost
    p("COST — all runs in the analysis set")
    p("-" * 78)
    tot = lambda k: sum(r[k] for r in runs)                 # noqa: E731
    p(f"  input tokens           {tot('input_tokens'):>12,}")
    p(f"  output tokens          {tot('output_tokens'):>12,}")
    p(f"  cache read             {tot('cache_read'):>12,}")
    p(f"  cache creation         {tot('cache_creation'):>12,}")
    p(f"  thinking tokens        {tot('thinking_tokens'):>12,}")
    p(f"  total tokens           "
      f"{tot('input_tokens')+tot('output_tokens')+tot('cache_read')+tot('cache_creation'):>12,}")
    p(f"  cost (USD)             {tot('cost_usd'):>12.4f}")
    wall = [r["wall_seconds"] for r in runs if r["wall_seconds"]]
    p(f"  wall seconds per run   {fmt_mi(wall)}   total {sum(wall)/60:.1f} min")
    p("")

    p(model_block(runs))
    p(budget_block(runs))
    p(s3_block(runs))
    p(exploratory(kept, fits))

    figure(fits, out_dir)
    p(f"figure: {out_dir / 'agent_stated_vs_log_count.png'}")
    return "\n".join(L)


def model_block(runs: list[dict]) -> str:
    """Batch 3 crosses the arms with the model, so every headline splits."""
    rs = [r for r in runs if classify_exclusion(r) is None]
    models = sorted({r["model"] for r in rs})
    L = ["BY MODEL — batch 3 crosses arm x model", "-" * 78]
    if len(models) < 2:
        L.append(f"only one model in this set ({models[0] if models else 'none'}); "
                 f"no split to report")
        return "\n".join(L) + "\n"
    L.append(f"{'model':<20}{'arm':<10}{'n':>4} {'stated mean med':>17} "
             f"{'evals med':>11} {'OOS med':>9} {'PASS':>6}")
    for m in models:
        for arm in sorted({r["arm"] for r in rs if r["model"] == m}):
            cell = [r for r in rs if r["model"] == m and r["arm"] == arm]
            n_pass = sum(1 for r in cell if r["status"] == "PASS")
            L.append(f"{m:<20}{arm:<10}{len(cell):>4} "
                     f"{np.median([r['stated_mean'] for r in cell]):>17.3f} "
                     f"{np.median([r['n_evaluated'] for r in cell]):>11.1f} "
                     f"{np.median([r['oos'] for r in cell]):>9.3f} "
                     f"{n_pass:>3}/{len(cell)}")
    L.append("")
    for arm in sorted({r["arm"] for r in rs}):
        cells = {m: [r for r in rs if r["model"] == m and r["arm"] == arm] for m in models}
        if all(len(c) >= 3 for c in cells.values()):
            fits = {m: ols(np.log([r["n_evaluated"] for r in c]),
                           [r["stated_mean"] for r in c]) for m, c in cells.items()}
            line = "  ".join(f"{m.split('-')[1]} {f['slope']:+.4f} (SE {f['se']:.4f})"
                             for m, f in fits.items())
            L.append(f"  slope on log(count), {arm}: {line}")
    return "\n".join(L) + "\n"


def budget_block(runs: list[dict]) -> str:
    """Amendment 4: stated mean on assigned log(B).

    The pre-registered deafness test with the exposure randomized. B is a cap,
    not a dose: an agent given 180 may stop at 60 of its own accord, so this is
    an intent-to-treat estimate. Realized evaluation count is reported beside
    the assigned level so the divergence is visible rather than implied."""
    rs = [r for r in runs if r["arm"] == "budget" and classify_exclusion(r) is None]
    L = ["BUDGET ARM — assigned-dose regression (amendment 4)", "-" * 78]
    if not rs:
        L.append("no budget runs in the analysis set")
        return "\n".join(L) + "\n"
    L.append("B is a cap, not a dose; this is intent-to-treat.")
    L.append("")
    L.append(f"{'B':>6} {'n':>4} {'stated mean med [IQR]':>26} {'realized evals med [IQR]':>28}"
             f" {'hit cap':>8}")
    for B in sorted({r["budget"] for r in rs}):
        cell = [r for r in rs if r["budget"] == B]
        hit = sum(1 for r in cell if r["n_evaluated"] >= B)
        L.append(f"{B:>6} {len(cell):>4} {fmt_mi([r['stated_mean'] for r in cell]):>26}"
                 f" {fmt_mi([r['n_evaluated'] for r in cell]):>28} {hit:>4}/{len(cell)}")
    f = ols(np.log([r["budget"] for r in rs]), [r["stated_mean"] for r in rs])
    L.append("")
    L.append(f"stated mean on assigned log(B): slope {f['slope']:+.4f}  SE {f['se']:.4f}  "
             f"95% CI [{f['lo']:+.4f}, {f['hi']:+.4f}]")
    L.append(f"{'':<32}t {f['t']:+.2f} on {f['dof']} df,  p {f['p']:.4f},  R² {f['r2']:.4f}")
    g = ols(np.log([r["n_evaluated"] for r in rs]), [r["stated_mean"] for r in rs])
    L.append(f"for comparison, on realized log(count): slope {g['slope']:+.4f}  "
             f"SE {g['se']:.4f}  p {g['p']:.4f}")
    return "\n".join(L) + "\n"


def s3_block(runs: list[dict]) -> str:
    """Amendment 4: s3 analysed as §5, plus PASS rate against preflight power."""
    rs = [r for r in runs if r["config"] == "s3" and classify_exclusion(r) is None]
    L = ["s3 CONFIG — as §5, plus PASS rate against preflight power (amendment 4)", "-" * 78]
    if not rs:
        L.append("no s3 runs in the analysis set")
        return "\n".join(L) + "\n"
    from collections import Counter
    for arm in sorted({r["arm"] for r in rs}):
        cell = [r for r in rs if r["arm"] == arm]
        x = np.log([r["n_evaluated"] for r in cell])
        f = ols(x, [r["stated_mean"] for r in cell])
        n_pass = sum(1 for r in cell if r["status"] == "PASS")
        lo, hi = wilson_ci(n_pass, len(cell))
        pwr = [r["power_at_open"] for r in cell if r["power_at_open"] is not None]
        L.append(f"{arm}  (n = {len(cell)})")
        L.append(f"  evaluation count     {fmt_mi([r['n_evaluated'] for r in cell])}")
        L.append(f"  stated mean          {fmt_mi([r['stated_mean'] for r in cell])}")
        L.append(f"  realized OOS Sharpe  {fmt_mi([r['oos'] for r in cell])}")
        L.append(f"  verdicts             {dict(sorted(Counter(r['status'] for r in cell).items()))}")
        L.append(f"  PASS rate            {n_pass/len(cell):.3f} ({lo:.3f}-{hi:.3f})")
        if pwr:
            L.append(f"  preflight power      {np.mean(pwr):.3f} (mean at open)   "
                     f"difference {n_pass/len(cell) - np.mean(pwr):+.3f}")
        L.append(f"  slope on log(count)  {f['slope']:+.4f}  SE {f['se']:.4f}  p {f['p']:.4f}")
        L.append("")
    return "\n".join(L)


def exploratory(kept: dict[str, list[dict]], fits) -> str:
    """Not pre-registered. Decided after seeing §5's results, so these carry no
    error control and are reported as description, not as tests."""
    from scipy.stats import mannwhitneyu
    L: list[str] = []
    p = L.append
    p("EXPLORATORY — not pre-registered, no error control")
    p("-" * 78)
    p("Decided after the §5 results were seen. Reported as description.")
    p("")

    # 1. Mann-Whitney, control vs gate
    p("1. Mann-Whitney U (two-sided), control vs gate")
    if "control" not in kept or "gate" not in kept or not kept["control"] or not kept["gate"]:
        p("   control and gate not both present; skipped")
        return "\n".join(L) + "\n"
    for label, key, fn in (("evaluation count", "n_evaluated", lambda r: r["n_evaluated"]),
                           ("deflation gap", None,
                            lambda r: r["stated_mean"] - r["sr_deflated"])):
        a = [fn(r) for r in kept["control"]]
        b = [fn(r) for r in kept["gate"]]
        u, pv = mannwhitneyu(a, b, alternative="two-sided")
        # rank-biserial correlation as the effect size
        rb = 1 - 2 * u / (len(a) * len(b))
        p(f"   {label:<20} U {u:>9.1f}   p {pv:.4g}   rank-biserial {rb:+.3f}")
        p(f"   {'':<20} medians: control {np.median(a):+.4f}, gate {np.median(b):+.4f}")
    p("")

    # 2. Regression variants
    p("2. Primary regression, two variants")
    p("   (a) raw evaluation count instead of log")
    for arm in ("control", "gate"):
        rs = kept.get(arm, [])
        if len(rs) < 3:
            continue
        f = ols([r["n_evaluated"] for r in rs], [r["stated_mean"] for r in rs])
        p(f"       {arm:<8} slope {f['slope']:+.6f}  SE {f['se']:.6f}  "
          f"95% CI [{f['lo']:+.6f}, {f['hi']:+.6f}]  p {f['p']:.4f}  R² {f['r2']:.4f}")
    p("   (b) log count, PASS runs excluded")
    for arm in ("control", "gate"):
        rs = [r for r in kept.get(arm, []) if r["status"] != "PASS"]
        if len(rs) < 3:
            continue
        f = ols(np.log([r["n_evaluated"] for r in rs]), [r["stated_mean"] for r in rs])
        dropped = len(kept[arm]) - len(rs)
        p(f"       {arm:<8} n {f['n']:>3} ({dropped} PASS dropped)  slope {f['slope']:+.4f}  "
          f"SE {f['se']:.4f}  95% CI [{f['lo']:+.4f}, {f['hi']:+.4f}]  p {f['p']:.4f}")
    p("")

    # 3. Gate arm: status usage against stated mean
    p("3. Gate arm — stated mean against status usage")
    rs = kept.get("gate", [])
    if len(rs) < 3:
        p("   gate arm absent; skipped")
        return "\n".join(L) + "\n"
    f = ols([r["n_status_calls"] for r in rs], [r["stated_mean"] for r in rs])
    p(f"   stated mean on status-call count: slope {f['slope']:+.4f}  SE {f['se']:.4f}  "
      f"95% CI [{f['lo']:+.4f}, {f['hi']:+.4f}]  p {f['p']:.4f}  R² {f['r2']:.4f}")
    cleared = [r for r in rs if r["last_cleared"] is True]
    notcl = [r for r in rs if r["last_cleared"] is False]
    unk = [r for r in rs if r["last_cleared"] is None]
    p(f"   last-cleared flag: cleared {len(cleared)}, did not clear {len(notcl)}, "
      f"no status call {len(unk)}")
    p("     (flag = whether the run's final status call reported clearing the bar,")
    p("      parsed from that call's own text, the only record of it)")
    if cleared and notcl:
        a = [r["stated_mean"] for r in cleared]
        b = [r["stated_mean"] for r in notcl]
        u, pv = mannwhitneyu(a, b, alternative="two-sided")
        p(f"   stated mean by flag: cleared median {np.median(a):+.4f} (n={len(a)}), "
          f"not cleared {np.median(b):+.4f} (n={len(b)})")
        p(f"   Mann-Whitney U {u:.1f}, p {pv:.4g}")
    else:
        p("   one side empty; no comparison possible")
    p("")
    return "\n".join(L)


def figure(fits, out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    colours = {"control": "#1f77b4", "gate": "#d62728"}
    for arm in ("control", "gate"):
        f, x, y = fits[arm]
        ax.scatter(x, y, s=34, alpha=0.75, color=colours[arm], edgecolor="white",
                   linewidth=0.6, label=f"{arm} (n={f['n']})", zorder=3)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, f["intercept"] + f["slope"] * xs, color=colours[arm], linewidth=2,
                zorder=4, label=f"  slope {f['slope']:+.3f} [{f['lo']:+.3f}, {f['hi']:+.3f}]")
    ax.set_xlabel("log(evaluation count)")
    ax.set_ylabel("stated mean predicted OOS Sharpe")
    ax.set_title("Stated confidence against search performed", loc="left", fontsize=12)
    ax.grid(alpha=0.25, zorder=0)
    ax.legend(fontsize=8, framealpha=0.95)
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "agent_stated_vs_log_count.png", dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()

    dirs = sorted(d for d in Path(a.runs_dir).iterdir()
                  if d.is_dir() and d.name.startswith(PREFIX))
    if not dirs:
        raise SystemExit(f"no runs matching {PREFIX}* under {a.runs_dir}")
    # A run still in flight has a config and a transcript but no verdict. That is
    # a normal mid-batch state, not an error: skip it and say how many.
    complete = [d for d in dirs if (d / "verdict.json").exists()]
    incomplete = [d.name for d in dirs if d not in complete]
    runs = [load_run(d) for d in complete]
    text = report(runs, Path(a.out))
    if incomplete:
        note = (f"\nINCOMPLETE: {len(incomplete)} run(s) without verdict.json, skipped\n"
                + "".join(f"  {n}\n" for n in incomplete))
        text += note
    print(text)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "agent_analysis.txt").write_text(text + "\n")
    print(f"\nwrote {Path(a.out) / 'agent_analysis.txt'}")


if __name__ == "__main__":
    main()
