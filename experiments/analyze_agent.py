"""Agent-arm analysis, implementing prereg/AGENT_PROMPTS.md §5 as amended.

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
in the run count, so it is reported and retained. It carries no stated belief
and no verdict, so it enters every n and no statistic.

The analysis set is every `s0_T5000_*` and `s3_T5000_*` run directory. Until
batch 2 was analysed the prefix here was `s0_T5000_` alone, which silently
dropped all 80 s3 runs: the s3 block reported "no s3 runs in the analysis set"
however many had been produced. `runs/s0_control_000_T500` is superseded by
amendment 1 and excluded by prefix, not by judgement; `runs/_aborted/` and
`runs/_excluded/` are not data and are never read.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

PINNED_MODEL = "claude-sonnet-5"
PREFIXES = ("s0_T5000_", "s3_T5000_")

# Directory names are the fallback identity for a run whose config.json is
# missing. Batch 1 ran before the model tag existed, so the tag is optional.
RUN_ID_RE = re.compile(
    r"^(?P<config>s\d+)_T(?P<T>\d+)_(?:(?P<mtag>sonnet|fable)_)?"
    r"(?P<arm>control|gate|count|budget|pushed)(?P<budget>\d+)?_(?P<seed>\d+)$")
TAG_MODEL = {"sonnet": "claude-sonnet-5", "fable": "claude-fable-5-1"}

# prereg §6: amendment 4 allocated seeds 80-319 (500 is seed 89's replacement),
# amendment 7 seeds 320-499. Used only to label contemporaneous comparison sets.
def batch_of(seed: int) -> str:
    if seed < 80:
        return "b1"
    if seed < 320 or seed == 500:
        return "b2"
    if seed < 500:
        return "b3"
    return "b4"


# ---------------------------------------------------------------- loading

def load_run(d: Path) -> dict:
    """Read one run directory. Tolerant of the three states that are not a
    plain graded run, each of which is reported rather than dropped:

      no verdict.json + no_submit.json -> the run ended without submitting
      no verdict.json at all           -> void (amendment 5, seed 89)
      no config.json                   -> identity recovered from the dir name

    The last happens once, at seed 314: two runners overlapped on that row and
    one parked the directory the other was writing into, taking config.json to
    runs/_aborted/ with it. The results themselves are intact and committed."""
    def maybe(name: str):
        p = d / name
        return json.loads(p.read_text()) if p.exists() else None

    cfg = maybe("config.json")
    verdict, stated = maybe("verdict.json"), maybe("stated.json")
    oos, considered = maybe("oos.json"), maybe("considered.json")

    m = RUN_ID_RE.match(d.name)
    if cfg is None:
        if m is None:
            raise ValueError(f"{d.name}: no config.json and the name does not parse")
        cfg = {
            "config": m["config"], "arm": m["arm"],
            "budget": int(m["budget"]) if m["budget"] else None,
            "model": TAG_MODEL.get(m["mtag"] or "sonnet"),
            "seed_index": int(m["seed"]),
        }

    # usage.jsonl is absent when a run ended between its verdict and the harness
    # finishing with it (seed 599, a rate limit on a trailing turn). Missing is not
    # the same as empty: a run with no usage record never reported a model string,
    # which §5's model-string exclusion does not cover.
    usage_path = d / "usage.jsonl"
    usage_missing = not usage_path.exists()
    usage = {} if usage_missing else json.loads(usage_path.read_text().splitlines()[-1])
    rows = [json.loads(l) for l in (d / "transcript.jsonl").read_text().splitlines()]

    tool_uses = [r for r in rows if r["kind"] == "tool_use"]
    evaluates = [r for r in rows if r["kind"] == "tool_result" and r.get("tool") == "evaluate"]
    submits = [r for r in rows if r["kind"] == "tool_result" and r.get("tool") == "submit"]
    statuses = [(i, r) for i, r in enumerate(rows)
                if r["kind"] == "tool_result" and r.get("tool") == "status"]
    errors = [r for r in rows if r["kind"] == "tool_error"]
    rejected = [r for r in rows if r["kind"] == "rate_limit" and r.get("status") == "rejected"]

    tool_idx = [i for i, r in enumerate(rows) if r["kind"] == "tool_use"]
    def frac(i):
        prior = sum(1 for t in tool_idx if t < i)
        return prior / len(tool_idx) if tool_idx else float("nan")

    mu = usage.get("model_usage") or {}
    per_model = list(mu.values())[0] if mu else {}
    code = cfg.get("code") or {}

    if verdict is not None:
        status = verdict["status"]
    elif (d / "no_submit.json").exists():
        status = "no_submit"
    elif (d / "void.json").exists() or oos is not None:
        # oos.json is written only after a submit, so a run carrying one but no
        # verdict really did finish and fail to be graded (amendment 5).
        status = "void"
    else:
        # Nothing terminal at all: the harness is still working on this row.
        # Reporting it as void would invent a defect out of a live batch.
        status = "in_flight"

    return {
        "run_id": d.name,
        "arm": cfg["arm"],
        "model": cfg.get("model", PINNED_MODEL),
        "config": cfg.get("config", "s0"),
        "budget": cfg.get("budget"),
        # Amendment 9 gave s3 a second calibration. sigma is what separates the
        # two; s0's is pinned at 1 by construction and never varies.
        "sigma": float((cfg.get("dgp") or {}).get("sigma", 1.0)),
        "seed_index": cfg["seed_index"],
        "batch": batch_of(cfg["seed_index"]),
        "config_recovered": not (d / "config.json").exists(),
        "power_at_open": (cfg.get("watch_open") or {}).get("power_at_reference"),
        "fingerprint": code.get("fingerprint"),
        "worker": cfg.get("worker"),
        "n_evaluated": len(evaluates),
        "n_tool_use": len(tool_uses),
        "n_refused": len(errors),
        "graded": verdict is not None and stated is not None,
        "status": status,
        "submitted_sr_is": verdict["sr_reported"] if verdict else None,
        "sr_deflated": verdict["sr_deflated"] if verdict else None,
        "critical_value": verdict["critical_value"] if verdict else None,
        "p_value": verdict["p_value"] if verdict else None,
        "stated_mean": stated["mean"] if stated else None,
        "stated_sd": stated["sd"] if stated else None,
        "oos": oos["oos_sharpe"] if oos else None,
        "considered": considered["n_considered"] if considered else None,
        "n_status_calls": len(statuses),
        "status_positions": [frac(i) for i, _ in statuses],
        "last_cleared": (None if not statuses
                         else "does not clear" not in (statuses[-1][1].get("text") or "")),
        "submitted": bool(submits),
        # exclusion inputs
        "usage_missing": usage_missing,
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
    # A run with no usage record at all reported no model string. §5 excludes a run
    # whose reported string DIFFERS from the pin; silence is a different condition,
    # and failing it under this rule would drop a run whose config pins the model and
    # whose transcript holds the model's own output. Reported in the integrity block.
    reported = [m for m in r["models_seen"] if str(m).startswith("claude-")]
    if not r.get("usage_missing") and (not reported or [m for m in reported if m != assigned]):
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
    if not len(x):
        return f"{'n/a':>8}  {'':16}"
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


def mols(X, y, names: list[str]) -> dict:
    """OLS against an explicit design matrix, with per-coefficient SE, 95% CI
    and p, plus the residual sum of squares an F-test needs. `ols` above stays
    the univariate path §5 asks for; this is for the joint fits."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = n - k
    rss = float((resid ** 2).sum())
    se = np.sqrt(np.diag((rss / dof) * np.linalg.inv(X.T @ X)))
    from scipy.stats import t as tdist
    crit = tdist.ppf(0.975, dof)
    tss = float(((y - y.mean()) ** 2).sum())
    return {"names": names, "beta": beta, "se": se, "dof": dof, "n": n,
            "lo": beta - crit * se, "hi": beta + crit * se,
            "t": beta / se, "p": 2 * tdist.sf(np.abs(beta / se), dof),
            "rss": rss, "r2": 1 - rss / tss}


def ftest(full: dict, restricted: dict) -> tuple[float, float, int, int]:
    """F for the coefficients `restricted` drops, against the full fit."""
    from scipy.stats import f as fdist
    q = restricted["dof"] - full["dof"]
    F = ((restricted["rss"] - full["rss"]) / q) / (full["rss"] / full["dof"])
    return float(F), float(fdist.sf(F, q, full["dof"])), q, full["dof"]


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. The normal approximation is useless at the ends,
    and s3 PASS counts sit near them."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def crps_gaussian(mu, sigma, y) -> float:
    """CRPS of N(mu, sigma^2) against observation y, closed form."""
    from scipy.stats import norm
    sigma = max(float(sigma), 1e-12)
    z = (float(y) - float(mu)) / sigma
    return float(sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi)))


def mw(a, b) -> tuple[float, float, float]:
    """Mann-Whitney U, two-sided, with rank-biserial correlation."""
    from scipy.stats import mannwhitneyu
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    return float(u), float(p), 1 - 2 * u / (len(a) * len(b))


def gap(r: dict) -> float:
    return r["stated_mean"] - r["sr_deflated"]


def cell_label(key) -> str:
    config, arm, budget, model, sigma = key
    tag = arm if budget is None else f"{arm}{budget}"
    base = f"{config} {tag} {model.split('-')[1]}"
    # s0 is pinned at sigma=1 by construction, so naming it there would be noise;
    # every other config carries its calibration in the label (amendment 9).
    return base if config == "s0" else f"{base} σ{sigma:g}"


def cells_of(runs: list[dict]) -> dict:
    """Group kept runs by (config, arm, budget, model, sigma), in a stable order.

    sigma is in the key because amendment 9 recalibrated s3: runs under the two
    calibrations are different experiments and must never share a cell. Without
    it the first four batch-4 runs landed in the s3 control cell alongside the
    forty produced at sigma=1, moving its PASS rate from 9/40 to 11/44."""
    out: dict = {}
    for r in runs:
        out.setdefault((r["config"], r["arm"], r["budget"], r["model"],
                        round(float(r["sigma"]), 6)), []).append(r)
    return dict(sorted(out.items(), key=lambda kv: (kv[0][0], kv[0][1],
                                                    kv[0][2] or 0, kv[0][3], kv[0][4])))


def pick(runs, **kw) -> list[dict]:
    """Filter helper: pick(rs, config="s0", arm="count") and so on."""
    return [r for r in runs
            if all(r.get(k) == v for k, v in kw.items() if not isinstance(v, (set, tuple)))
            and all(r.get(k) in v for k, v in kw.items() if isinstance(v, (set, tuple)))]


def graded(rs) -> list[dict]:
    return [r for r in rs if r["graded"]]


# ---------------------------------------------------------------- report

def report(runs: list[dict], incomplete: list[str], out_dir: Path) -> str:
    L: list[str] = []
    p = L.append

    kept = [r for r in runs if classify_exclusion(r) is None]

    p("Agent-arm analysis — prereg/AGENT_PROMPTS.md §5, as amended (batches 1-3)")
    p("=" * 78)
    p(f"analysis set: {len(runs)} runs matching {' / '.join(s + '*' for s in PREFIXES)}")
    p("excluded by prefix: runs/s0_control_000_T500 (superseded, amendment 1)")
    p("not data, never read: runs/_aborted/, runs/_excluded/")
    p("")
    p("Definitions fixed here (§5 has no literal field for either):")
    p("  deflation gap   = stated mean - sr_deflated, where")
    p("                    sr_deflated = sr_reported - null_max_mean")
    p("  matched count   = pooled median of log(evaluation count)")
    p("  no_submit       = status, not an exclusion (§3 keeps the run)")
    p("")

    p(integrity_block(runs, incomplete))
    p(exclusion_block(runs))
    p(per_cell_block(kept))
    p(provenance_block(kept))
    p(primary_block(kept))
    p(haircut_block(kept))
    p(count_vs_control_block(kept))
    p(budget_block(kept))
    p(s3_block(kept))
    p(pushed_block(kept))
    p(model_block(kept))
    p(status_tool_block(kept))
    p(cost_block(runs))

    names = figures(kept, out_dir)
    p("FIGURES")
    p("-" * 78)
    for n in names:
        p(f"  {out_dir / n}")
    return "\n".join(L)


def integrity_block(runs, incomplete) -> str:
    L = ["RUN INTEGRITY", "-" * 78]
    n_graded = sum(1 for r in runs if r["graded"])
    no_sub = [r for r in runs if r["status"] == "no_submit"]
    void = [r for r in runs if r["status"] == "void"]
    recov = [r for r in runs if r["config_recovered"]]
    unverified = [r for r in runs if r.get("usage_missing")]
    L.append(f"  run directories read      {len(runs):>4}")
    L.append(f"  graded (verdict + stated) {n_graded:>4}")
    L.append(f"  no_submit (§3, retained)  {len(no_sub):>4}"
             + (f"   {', '.join(r['run_id'] for r in no_sub)}" if no_sub else ""))
    L.append(f"  void (amendment 5)        {len(void):>4}"
             + (f"   {', '.join(r['run_id'] for r in void)}" if void else ""))
    flight = [r for r in runs if r["status"] == "in_flight"]
    L.append(f"  in flight (not yet graded){len(flight):>4}"
             + (f"   {', '.join(r['run_id'] for r in flight)}" if flight else ""))
    L.append(f"  config.json recovered     {len(recov):>4}"
             + (f"   {', '.join(r['run_id'] for r in recov)}" if recov else ""))
    if recov:
        L.append("    (identity taken from the directory name; fingerprint, worker and")
        L.append("     preflight power are unrecorded for these and shown as such)")
    L.append(f"  model string unverified   {len(unverified):>4}"
             + (f"   {', '.join(r['run_id'] for r in unverified)}" if unverified else ""))
    if unverified:
        L.append("    (no usage.jsonl, so no reported model string to check against §5's")
        L.append("     pin; the model is the one config.json assigns. Retained, not excluded)")
    if incomplete:
        L.append(f"  unreadable, skipped       {len(incomplete):>4}   {', '.join(incomplete)}")
    return "\n".join(L) + "\n"


def exclusion_block(runs) -> str:
    cats = ("model_string", "non_mcp_tool", "rate_limit_before_submit")
    L = ["EXCLUSIONS (pre-registered categories, §5)", "-" * 78]
    L.append(f"{'cell':<26}" + "".join(f"{c.split('_')[0]:>14}" for c in cats)
             + f"{'total':>8}{'kept':>7}")
    grand = Counter()
    for key, rs in cells_of(runs).items():
        per = Counter(classify_exclusion(r) for r in rs)
        grand.update({c: per.get(c, 0) for c in cats})
        tot = sum(per.get(c, 0) for c in cats)
        L.append(f"{cell_label(key):<26}"
                 + "".join(f"{per.get(c, 0):>14}" for c in cats)
                 + f"{tot:>8}{len(rs) - tot:>7}")
    L.append(f"{'-- all cells':<26}" + "".join(f"{grand[c]:>14}" for c in cats)
             + f"{sum(grand.values()):>8}"
             + f"{sum(1 for r in runs if classify_exclusion(r) is None):>7}")
    return "\n".join(L) + "\n"


SIGNAL_SR = 5.0


def split_line(g: list[dict]) -> str:
    """Where a cell holds runs that found real signal, say so in counts.

    Config s3 has s=3 true features, so a run that finds them reports an
    in-sample Sharpe near 74 (about 4.7 per period times sqrt(252)) and an OOS
    Sharpe to match. That is the DGP, not a defect, but it makes the cell
    bimodal: the mean of any quantity built on sr_reported is then a statement
    about the mix, not about a typical run. Medians and both subgroup medians
    are given so the mix is visible rather than implied. No s0 run reaches the
    threshold, so the line appears only where it applies."""
    big = [r for r in g if (r["submitted_sr_is"] or 0) > SIGNAL_SR]
    if not big:
        return ""
    rest = [r for r in g if (r["submitted_sr_is"] or 0) <= SIGNAL_SR]
    out = [f"  sr_reported > {SIGNAL_SR:.0f}       {len(big)} of {len(g)} runs "
           f"(max {max(r['submitted_sr_is'] for r in big):.1f}); the means above "
           f"are a mix of these"]
    if rest:
        out.append(f"    deflation gap      >{SIGNAL_SR:.0f}: "
                   f"{np.median([gap(r) for r in big]):+10.3f}   "
                   f"rest: {np.median([gap(r) for r in rest]):+.3f}")
        out.append(f"    stated mean        >{SIGNAL_SR:.0f}: "
                   f"{np.median([r['stated_mean'] for r in big]):+10.3f}   "
                   f"rest: {np.median([r['stated_mean'] for r in rest]):+.3f}")
    return "\n".join(out)


def per_cell_block(kept) -> str:
    L = ["PER CELL — config × arm × model, median [IQR]", "-" * 78]
    for key, rs in cells_of(kept).items():
        g = graded(rs)
        L.append(f"{cell_label(key)}  (n = {len(rs)}"
                 + (f", graded {len(g)}" if len(g) != len(rs) else "") + ")")
        L.append(f"  evaluation count     {fmt_mi([r['n_evaluated'] for r in rs])}")
        L.append(f"  stated mean          {fmt_mi([r['stated_mean'] for r in g])}")
        L.append(f"  stated sd            {fmt_mi([r['stated_sd'] for r in g])}")
        L.append(f"  realized OOS Sharpe  {fmt_mi([r['oos'] for r in rs if r['oos'] is not None])}")
        L.append(f"  submitted SR (in-s)  {fmt_mi([r['submitted_sr_is'] for r in g])}")
        L.append(f"  considered count     "
                 f"{fmt_mi([r['considered'] for r in rs if r['considered'] is not None])}")
        L.append(f"  verdicts             {dict(sorted(Counter(r['status'] for r in rs).items()))}")
        if g:
            gaps = [gap(r) for r in g]
            crps = [crps_gaussian(r["stated_mean"], r["stated_sd"], r["oos"]) for r in g]
            L.append(f"  deflation gap        {fmt_mi(gaps)}   mean {np.mean(gaps):.4f}")
            L.append(f"  CRPS vs realized OOS {fmt_mi(crps)}   mean {np.mean(crps):.4f}")
            extra = split_line(g)
            if extra:
                L.append(extra)
        L.append("")
    return "\n".join(L)


def provenance_block(kept) -> str:
    """Amendment 6 records worker index and harness fingerprint per run; batch 1
    and the early batch-2 rows predate the field and report None."""
    L = ["PROVENANCE — harness fingerprint and worker index per cell (amendment 6)",
         "-" * 78]
    fmt = lambda c: ", ".join(  # noqa: E731
        f"{k if k is not None else 'unrecorded'}:{v}" for k, v in sorted(
            c.items(), key=lambda kv: (kv[0] is None, str(kv[0]))))
    for key, rs in cells_of(kept).items():
        L.append(f"{cell_label(key)}  (n = {len(rs)})")
        L.append(f"  fingerprint  {fmt(Counter(r['fingerprint'] for r in rs))}")
        L.append(f"  worker       {fmt(Counter(r['worker'] for r in rs))}")
    return "\n".join(L) + "\n"


def primary_block(kept) -> str:
    """§5's primary: regress stated mean on log(evaluation count), per cell."""
    L = ["PRIMARY — stated mean on log(evaluation count), per cell (§5)", "-" * 78,
         "H0: slope = 0 (stated confidence deaf to the search performed)", ""]
    L.append("log-count span is the spread of the predictor. Where it is narrow the")
    L.append("slope is large and weakly identified whatever its p-value; where the")
    L.append("response is heavy-tailed (s3) the fit is on the raw stated scale.")
    L.append("")
    L.append(f"{'cell':<26}{'n':>4}{'slope':>11}{'SE':>9}"
             f"{'95% CI':>24}{'p':>9}{'R2':>7}{'log-count span':>17}")
    for key, rs in cells_of(kept).items():
        g = graded(rs)
        if len(g) < 3:
            continue
        x = np.log([r["n_evaluated"] for r in g])
        f = ols(x, [r["stated_mean"] for r in g])
        L.append(f"{cell_label(key):<26}{f['n']:>4}{f['slope']:>+11.4f}{f['se']:>9.4f}"
                 f"   [{f['lo']:+9.4f}, {f['hi']:+9.4f}]{f['p']:>9.4f}{f['r2']:>7.3f}"
                 f"      {x.min():.2f}-{x.max():.2f}")
    return "\n".join(L) + "\n"


def haircut_block(kept) -> str:
    """stated mean on submitted in-sample Sharpe and log(evaluation count),
    jointly, per cell; then pooled over the s0 sonnet cells with arm dummies
    interacting with the in-sample Sharpe.

    b, the coefficient on the submitted in-sample Sharpe, is the haircut: how
    much of the Sharpe it actually submitted a run carries into the belief it
    states. c is what §5's univariate slope measures once b is held fixed."""
    L = ["HAIRCUT — stated mean on in-sample Sharpe and log(count), jointly",
         "-" * 96,
         "stated_mean = a + b*sr_is + c*log(evaluation count);  95% CI beside each.",
         "b is the haircut: stated belief per unit of submitted in-sample Sharpe.",
         ""]
    L.append(f"{'cell':<24}{'n':>4}   {'b (in-sample SR)':^28}  "
             f"{'c (log count)':^28}{'R2':>7}")
    for key, rs in cells_of(kept).items():
        g = graded(rs)
        if len(g) < 5:
            continue
        X = np.column_stack([np.ones(len(g)),
                             [r["submitted_sr_is"] for r in g],
                             np.log([r["n_evaluated"] for r in g])])
        f = mols(X, [r["stated_mean"] for r in g], ["const", "sr_is", "log_count"])
        L.append(f"{cell_label(key):<24}{f['n']:>4}   "
                 f"{f['beta'][1]:+8.4f} [{f['lo'][1]:+8.4f},{f['hi'][1]:+8.4f}]  "
                 f"{f['beta'][2]:+8.4f} [{f['lo'][2]:+8.4f},{f['hi'][2]:+8.4f}]"
                 f"{f['r2']:>7.3f}")
    L.append("")

    rs = graded(pick(kept, config="s0", model=PINNED_MODEL))
    arms = sorted({r["arm"] for r in rs})
    ref = "control" if "control" in arms else arms[0]
    others = [a for a in arms if a != ref]
    L.append(f"POOLED — all s0 {PINNED_MODEL.split('-')[1]} cells, arm dummies x in-sample Sharpe")
    L.append("-" * 96)
    L.append(f"reference arm: {ref}.  budget doses are pooled into one arm.")
    L.append(f"n = {len(rs)}   arms: " +
             ", ".join(f"{a} {sum(1 for r in rs if r['arm'] == a)}" for a in arms))
    L.append("")
    y = np.array([r["stated_mean"] for r in rs], float)
    sr = np.array([r["submitted_sr_is"] for r in rs], float)
    lc = np.log([r["n_evaluated"] for r in rs])
    dum = {a: np.array([1.0 if r["arm"] == a else 0.0 for r in rs]) for a in others}
    base_cols, base_names = [np.ones(len(rs)), sr, lc], ["const", "sr_is", "log_count"]
    d_cols = [dum[a] for a in others]
    d_names = [f"arm[{a}]" for a in others]
    x_cols = [dum[a] * sr for a in others]
    x_names = [f"arm[{a}]:sr_is" for a in others]

    full = mols(np.column_stack(base_cols + d_cols + x_cols), y,
                base_names + d_names + x_names)
    no_int = mols(np.column_stack(base_cols + d_cols), y, base_names + d_names)
    no_arm = mols(np.column_stack(base_cols), y, base_names)

    L.append("full model (intercept shifts and slope shifts, both vs the reference arm)")
    for nm, b, se, lo, hi, pv in zip(full["names"], full["beta"], full["se"],
                                     full["lo"], full["hi"], full["p"]):
        L.append(f"  {nm:<20}{b:+9.4f}  SE {se:.4f}  [{lo:+9.4f},{hi:+9.4f}]  p {pv:.4g}")
    L.append(f"  R² {full['r2']:.4f} on {full['dof']} df")
    L.append("")
    F, p, q, d = ftest(full, no_int)
    L.append(f"do the arms differ in SLOPE?      F({q},{d}) {F:7.3f}   p {p:.4g}"
             f"   (all arm x sr_is = 0)")
    F, p, q, d = ftest(no_int, no_arm)
    L.append(f"do they differ in INTERCEPT?      F({q},{d}) {F:7.3f}   p {p:.4g}"
             f"   (all arm dummies = 0, common slope)")
    L.append(f"R²: no arm terms {no_arm['r2']:.4f}  ->  intercepts only "
             f"{no_int['r2']:.4f}  ->  full {full['r2']:.4f}")
    return "\n".join(L) + "\n"


def count_vs_control_block(kept) -> str:
    """Pre-registered comparison 1: count vs control, deflation gap and count.

    The count arm ran inside batch 2's schedule (amendment 4), which also ran a
    30-run control replication. Control exists in all three batches under three
    harness fingerprints, so the comparison is reported against each control set
    separately rather than against a pool that mixes them."""
    L = ["COMPARISON 1 — count arm vs control (deflation gap, evaluation count)",
         "-" * 78]
    count = graded(pick(kept, config="s0", arm="count", model=PINNED_MODEL))
    ctrl = graded(pick(kept, config="s0", arm="control", model=PINNED_MODEL))
    sets = {
        "all sonnet control": ctrl,
        "b2 contemporaneous": [r for r in ctrl if r["batch"] == "b2"],
        "b1 original": [r for r in ctrl if r["batch"] == "b1"],
        "b3 replication": [r for r in ctrl if r["batch"] == "b3"],
    }
    L.append(f"count arm: n = {len(count)} (all s0, sonnet, batch 2)")
    L.append("")
    for metric, fn in (("deflation gap", gap), ("evaluation count",
                                                lambda r: r["n_evaluated"])):
        L.append(f"{metric}:")
        a = [fn(r) for r in count]
        L.append(f"  count            median {np.median(a):+9.4f}   mean {np.mean(a):+9.4f}"
                 f"   n {len(a)}")
        for name, cs in sets.items():
            if len(cs) < 3:
                continue
            b = [fn(r) for r in cs]
            u, pv, rb = mw(a, b)
            L.append(f"  vs {name:<18} median {np.median(b):+9.4f}   "
                     f"difference {np.median(a) - np.median(b):+.4f}   "
                     f"U {u:.1f}  p {pv:.4g}  rb {rb:+.3f}  n {len(b)}")
        L.append("")
    return "\n".join(L)


def budget_block(kept) -> str:
    """Pre-registered comparison 2, amendment 4: stated mean on assigned log(B).

    The pre-registered deafness test with the exposure randomized. B is a cap,
    not a dose: an agent given 180 may stop at 60 of its own accord, so this is
    an intent-to-treat estimate. Realized evaluation count is reported beside
    the assigned level so the divergence is visible rather than implied."""
    rs = graded(pick(kept, config="s0", arm="budget"))
    L = ["COMPARISON 2 — budget arm, assigned-dose regression (amendment 4)", "-" * 78]
    if not rs:
        return "\n".join(L + ["no budget runs in the analysis set"]) + "\n"
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
             f"SE {g['se']:.4f}  95% CI [{g['lo']:+.4f}, {g['hi']:+.4f}]  p {g['p']:.4f}")
    return "\n".join(L) + "\n"


def s3_block(kept) -> str:
    """Pre-registered comparison 3, amendment 4: s3 as §5, plus PASS rate against
    the preflight power at reference, and s3 control vs gate."""
    rs_all = pick(kept, config="s3")
    L = ["COMPARISON 3 — s3: PASS rate vs preflight power, and control vs gate",
         "-" * 78]
    if not rs_all:
        return "\n".join(L + ["no s3 runs in the analysis set"]) + "\n"
    from scipy.stats import binomtest, fisher_exact
    sigmas = sorted({round(float(r["sigma"]), 6) for r in rs_all})
    if len(sigmas) > 1:
        L.append("Amendment 9 recalibrated s3. The two calibrations are separate")
        L.append("experiments and are never pooled; each is reported on its own.")
        L.append("")
    for sg, model in sorted({(round(float(r["sigma"]), 6), r["model"]) for r in rs_all}):
        rs = [r for r in rs_all
              if round(float(r["sigma"]), 6) == sg and r["model"] == model]
        # Model is in the key, not only sigma. Batch 5 put Opus on s3 at the same
        # sigma batch 4 ran Sonnet at, and grouping by (sigma, arm) alone silently
        # pooled the two into one control cell of 79 and one gate cell of 80.
        L.append(f"===== sigma = {sg:g}, {model.split('-')[1]}   (n = {len(rs)}) =====")
        for arm in sorted({r["arm"] for r in rs}):
            cell = [r for r in rs if r["arm"] == arm]
            g = graded(cell)
            n_pass = sum(1 for r in cell if r["status"] == "PASS")
            lo, hi = wilson_ci(n_pass, len(cell))
            pwr = [r["power_at_open"] for r in cell if r["power_at_open"] is not None]
            L.append(f"{arm}  (n = {len(cell)})")
            L.append(f"  evaluation count     {fmt_mi([r['n_evaluated'] for r in cell])}")
            L.append(f"  stated mean          {fmt_mi([r['stated_mean'] for r in g])}")
            L.append(f"  realized OOS Sharpe  "
                     f"{fmt_mi([r['oos'] for r in cell if r['oos'] is not None])}")
            L.append(f"  verdicts             "
                     f"{dict(sorted(Counter(r['status'] for r in cell).items()))}")
            extra = split_line(g)
            if extra:
                L.append(extra)
            L.append(f"  PASS rate            {n_pass}/{len(cell)} = "
                     f"{n_pass/len(cell):.3f}  Wilson 95% [{lo:.3f}, {hi:.3f}]")
            if pwr:
                ref = float(np.mean(pwr))
                bt = binomtest(n_pass, len(cell), ref)
                L.append(f"  preflight power      {ref:.3f} (mean at open)   "
                         f"difference {n_pass/len(cell) - ref:+.3f}   "
                         f"binomial p {bt.pvalue:.4g}")
            if len(g) >= 3:
                f = ols(np.log([r["n_evaluated"] for r in g]),
                        [r["stated_mean"] for r in g])
                L.append(f"  slope on log(count)  {f['slope']:+.4f}  SE {f['se']:.4f}  "
                         f"p {f['p']:.4f}")
            L.append("")

        c, gt = graded(pick(rs, arm="control")), graded(pick(rs, arm="gate"))
        if len(c) >= 3 and len(gt) >= 3:
            L.append(f"control vs gate (sigma {sg:g}, {model.split('-')[1]}):")
            for metric, fn in (("deflation gap", gap),
                               ("evaluation count", lambda r: r["n_evaluated"]),
                               ("stated mean", lambda r: r["stated_mean"])):
                a, b = [fn(r) for r in c], [fn(r) for r in gt]
                u, pv, rb = mw(a, b)
                L.append(f"  {metric:<18} control {np.median(a):+8.4f}   "
                         f"gate {np.median(b):+8.4f}"
                         f"   difference {np.median(b) - np.median(a):+.4f}"
                         f"   U {u:.1f}  p {pv:.4g}  rb {rb:+.3f}")
            pc = sum(1 for r in pick(rs, arm="control") if r["status"] == "PASS")
            pg = sum(1 for r in pick(rs, arm="gate") if r["status"] == "PASS")
            nc, ng = len(pick(rs, arm="control")), len(pick(rs, arm="gate"))
            odds, pv = fisher_exact([[pc, nc - pc], [pg, ng - pg]])
            L.append(f"  {'PASS rate':<18} control {pc}/{nc} = {pc/nc:.3f}   "
                     f"gate {pg}/{ng} = {pg/ng:.3f}   Fisher p {pv:.4g}")
        elif len(sigmas) > 1:
            L.append(f"  control vs gate: not both arms present at sigma {sg:g} yet "
                     f"(control {len(c)}, gate {len(gt)} graded); skipped")
        L.append("")

    # Between-model, within a calibration. UNPAIRED by construction: batch 4 ran
    # Sonnet on seeds 501-580 and batch 5 ran Opus on 581-660, so the two share no
    # DGP draw and cannot be differenced by seed. Amendment 11 reserves the paired
    # design for Fable, which runs Opus's own seeds once the allowance resets.
    for sg in sigmas:
        at_sigma = [r for r in rs_all if round(float(r["sigma"]), 6) == sg]
        models = sorted({r["model"] for r in at_sigma})
        if len(models) < 2:
            continue
        seeds = {m: {r["seed_index"] for r in at_sigma if r["model"] == m} for m in models}
        shared = set.intersection(*seeds.values())
        L.append(f"BETWEEN MODEL at sigma {sg:g} — unpaired ({len(shared)} shared seeds)")
        L.append("-" * 78)
        for m in models:
            s = sorted(seeds[m])
            L.append(f"  {m.split('-')[1]:<8} n={len(seeds[m]):<4} seeds {s[0]}-{s[-1]}")
        for arm in sorted({r["arm"] for r in at_sigma}):
            cells = {m: graded([r for r in at_sigma
                                if r["model"] == m and r["arm"] == arm]) for m in models}
            if not all(len(c) >= 3 for c in cells.values()):
                continue
            L.append(f"  {arm}:")
            for metric, fn in (("deflation gap", gap),
                               ("evaluation count", lambda r: r["n_evaluated"]),
                               ("stated mean", lambda r: r["stated_mean"]),
                               ("realized OOS", lambda r: r["oos"])):
                a = [fn(r) for r in cells[models[0]]]
                b = [fn(r) for r in cells[models[1]]]
                u, pv, rb = mw(a, b)
                L.append(f"    {metric:<18} {models[0].split('-')[1]} {np.median(a):+8.4f}   "
                         f"{models[1].split('-')[1]} {np.median(b):+8.4f}   "
                         f"difference {np.median(b) - np.median(a):+.4f}   "
                         f"U {u:.1f}  p {pv:.4g}  rb {rb:+.3f}")
            raw = {m: [r for r in at_sigma if r["model"] == m and r["arm"] == arm]
                   for m in models}
            pk = {m: sum(1 for r in raw[m] if r["status"] == "PASS") for m in models}
            odds, pv = fisher_exact([[pk[models[0]], len(raw[models[0]]) - pk[models[0]]],
                                     [pk[models[1]], len(raw[models[1]]) - pk[models[1]]]])
            L.append(f"    {'PASS rate':<18} "
                     + "   ".join(f"{m.split('-')[1]} {pk[m]}/{len(raw[m])} = "
                                  f"{pk[m]/len(raw[m]):.3f}" for m in models)
                     + f"   Fisher p {pv:.4g}")
        L.append("")
    return "\n".join(L) + "\n"


def pushed_block(kept) -> str:
    """Pre-registered comparison 4: pushed vs gate vs control, on Sonnet.

    All three exist together only in batch 3, which ran them in one schedule
    under one fingerprint; that is the comparison set."""
    from scipy.stats import kruskal
    rs = [r for r in graded(pick(kept, config="s0", model=PINNED_MODEL))
          if r["batch"] == "b3"]
    L = ["COMPARISON 4 — pushed vs gate vs control, Sonnet (batch 3)", "-" * 78]
    arms = ("control", "gate", "pushed")
    groups = {a: [r for r in rs if r["arm"] == a] for a in arms}
    if not all(len(g) >= 3 for g in groups.values()):
        return "\n".join(L + ["not all three arms present in batch 3; skipped"]) + "\n"
    L.append("  " + "  ".join(f"{a} n={len(groups[a])}" for a in arms))
    L.append("")
    for metric, fn in (("deflation gap", gap),
                       ("evaluation count", lambda r: r["n_evaluated"]),
                       ("stated mean", lambda r: r["stated_mean"]),
                       ("realized OOS", lambda r: r["oos"])):
        vals = {a: [fn(r) for r in groups[a]] for a in arms}
        h, pv = kruskal(*vals.values())
        L.append(f"{metric}:")
        L.append("  medians   " + "   ".join(f"{a} {np.median(vals[a]):+8.4f}" for a in arms)
                 + f"   Kruskal-Wallis H {h:.3f}  p {pv:.4g}")
        for i in range(len(arms)):
            for j in range(i + 1, len(arms)):
                u, p2, rb = mw(vals[arms[i]], vals[arms[j]])
                L.append(f"  {arms[i]} vs {arms[j]:<8} U {u:>8.1f}  p {p2:.4g}  rb {rb:+.3f}")
        L.append("")
    pc = {a: sum(1 for r in groups[a] if r["status"] == "PASS") for a in arms}
    L.append("PASS rate   " + "   ".join(
        f"{a} {pc[a]}/{len(groups[a])} = {pc[a]/len(groups[a]):.3f}" for a in arms))
    return "\n".join(L) + "\n"


def model_block(kept) -> str:
    """Exploratory (amendment 7): Sonnet vs Fable within each arm, batch 3."""
    rs = [r for r in graded(pick(kept, config="s0")) if r["batch"] == "b3"]
    L = ["EXPLORATORY — Sonnet vs Fable within each arm (amendment 7, batch 3)",
         "-" * 78,
         "Between-model comparison is exploratory by amendment 7: no error control.", ""]
    models = sorted({r["model"] for r in rs})
    if len(models) < 2:
        return "\n".join(L + ["only one model in this set; no split to report"]) + "\n"
    for arm in sorted({r["arm"] for r in rs}):
        cells = {m: [r for r in rs if r["model"] == m and r["arm"] == arm] for m in models}
        if not all(len(c) >= 3 for c in cells.values()):
            continue
        L.append(f"{arm}:  " + "  ".join(f"{m.split('-')[1]} n={len(c)}"
                                         for m, c in cells.items()))
        for metric, fn in (("deflation gap", gap),
                           ("evaluation count", lambda r: r["n_evaluated"]),
                           ("stated mean", lambda r: r["stated_mean"]),
                           ("realized OOS", lambda r: r["oos"])):
            a = [fn(r) for r in cells[models[0]]]
            b = [fn(r) for r in cells[models[1]]]
            u, pv, rb = mw(a, b)
            L.append(f"  {metric:<18} {models[0].split('-')[1]} {np.median(a):+8.4f}   "
                     f"{models[1].split('-')[1]} {np.median(b):+8.4f}   "
                     f"difference {np.median(b) - np.median(a):+.4f}   "
                     f"U {u:.1f}  p {pv:.4g}  rb {rb:+.3f}")
        fits = {m: ols(np.log([r["n_evaluated"] for r in c]),
                       [r["stated_mean"] for r in c]) for m, c in cells.items()}
        L.append("  slope on log(count)  " + "  ".join(
            f"{m.split('-')[1]} {f['slope']:+.4f} (SE {f['se']:.4f})"
            for m, f in fits.items()))
        L.append("")
    return "\n".join(L)


def status_tool_block(kept) -> str:
    """The gate arm's `status` tool. The pushed arm has no such tool: its
    standing is appended to every evaluate result, so it logs no status calls."""
    L = ["GATE ARM — status tool", "-" * 78]
    rs = pick(kept, arm="gate")
    calls = [r["n_status_calls"] for r in rs] or [0]
    L.append(f"  status calls per run   {fmt_mi(calls)}   total {sum(calls)}")
    L.append(f"  runs never calling it  {sum(1 for c in calls if c == 0)} of {len(rs)}")
    pos = [q for r in rs for q in r["status_positions"]]
    if pos:
        L.append(f"  position in run        {fmt_mi(pos)}   (fraction of tool calls elapsed)")
        thirds = [sum(1 for q in pos if lo <= q < hi) for lo, hi in
                  ((0, 1/3), (1/3, 2/3), (2/3, 1.01))]
        L.append(f"  by third of run        first {thirds[0]}, middle {thirds[1]}, "
                 f"last {thirds[2]}")
    pushed_calls = sum(r["n_status_calls"] for r in pick(kept, arm="pushed"))
    L.append(f"  pushed-arm status calls {pushed_calls} (the arm defines no status tool)")
    return "\n".join(L) + "\n"


def cost_block(runs) -> str:
    L = ["COST — all runs in the analysis set", "-" * 78]
    tot = lambda k: sum(r[k] for r in runs)                 # noqa: E731
    L.append(f"  input tokens           {tot('input_tokens'):>12,}")
    L.append(f"  output tokens          {tot('output_tokens'):>12,}")
    L.append(f"  cache read             {tot('cache_read'):>12,}")
    L.append(f"  cache creation         {tot('cache_creation'):>12,}")
    L.append(f"  thinking tokens        {tot('thinking_tokens'):>12,}")
    L.append(f"  total tokens           "
             f"{tot('input_tokens')+tot('output_tokens')+tot('cache_read')+tot('cache_creation'):>12,}")
    L.append(f"  cost (USD)             {tot('cost_usd'):>12.4f}")
    wall = [r["wall_seconds"] for r in runs if r["wall_seconds"]]
    L.append(f"  wall seconds per run   {fmt_mi(wall)}   total {sum(wall)/3600:.1f} h")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- figures
# Colours are the two-slot categorical set validated against the skill's six
# checks on a white surface (all PASS: worst all-pairs CVD ΔE 21.9 protan,
# normal-vision ΔE 31.2, contrast >= 3:1). A five-arm categorical set was tried
# first and could not clear the CVD floor -- gold against vermillion collapses
# under protanopia -- so the per-arm figure uses small multiples in one hue
# instead of five competing hues.
BLUE, ORANGE = "#0072B2", "#D55E00"
INK, MUTED = "#1a1a19", "#6b6b68"
# One colour per model across every figure: colour follows the entity, so a
# model must not change hue between panels or between figures. Reading the
# labels back off the first panel instead produced a legend naming only sonnet,
# because the leftmost arm (budget) has no fable runs to carry a label.
MODEL_COLOUR = {"claude-fable-5-1": ORANGE, "claude-sonnet-5": BLUE}
# Five arms need five categorical hues, which is where hand-picked palettes fall
# over: on a white surface the usual qualitative sets put gold against vermillion
# and the pair collapses under protanopia. These five were searched in OKLCH
# (lightness band, chroma floor, >= 3:1 on white) maximizing the worst all-pairs
# separation under the Machado protan/deutan simulations -- all-pairs because
# this is a scatter, where any two arms can land next to each other. Worst pair
# is dE 13.7 against a target of 8, normal-vision floor 16.9 against 15. Assigned
# in fixed alphabetical order and never cycled. Tritan separation is 4.0, which
# the checks report for information and do not gate on.
ARM_COLOUR = {"budget": "#1D9999", "control": "#AC2F3B", "count": "#654DB6",
              "gate": "#C8800D", "pushed": "#6D8AF3"}


def _style(ax):
    ax.grid(alpha=0.25, zorder=0, linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    for lbl in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
        lbl.set_color(INK)


def figures(kept, out_dir: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    names = []

    # 1. stated mean vs log(count), per arm -- small multiples, s0, one fit per
    # model. Pooling the two models in a single per-arm fit inverts the slope:
    # fable evaluates ~45 times and states ~0.11, sonnet evaluates ~79 and
    # states ~0.45, so one line through both reads that between-model offset as
    # a within-arm trend (pooled control +0.236, against -0.037 for sonnet and
    # +2.56 for fable). The cells are what §5 regresses; the figure shows them.
    rs = graded(pick(kept, config="s0"))
    arms = sorted({r["arm"] for r in rs})
    models = sorted({r["model"] for r in rs})
    fig, axes = plt.subplots(1, len(arms), figsize=(3.1 * len(arms), 4.0),
                             sharex=True, sharey=True)
    axes = np.atleast_1d(axes)
    for ax, arm in zip(axes, arms):
        bits = []
        for m in models:
            cell = [r for r in rs if r["arm"] == arm and r["model"] == m]
            if not cell:
                continue
            x = np.log([r["n_evaluated"] for r in cell])
            y = np.array([r["stated_mean"] for r in cell], float)
            ax.scatter(x, y, s=20, alpha=0.7, color=MODEL_COLOUR[m],
                       edgecolor="white", linewidth=0.5, zorder=3)
            if len(cell) >= 3:
                f = ols(x, y)
                xs = np.linspace(x.min(), x.max(), 100)
                ax.plot(xs, f["intercept"] + f["slope"] * xs,
                        color=MODEL_COLOUR[m], linewidth=2, zorder=4)
                bits.append(f"{m.split('-')[1]} {f['slope']:+.3f} (n={len(cell)})")
        ax.set_title(f"{arm}\n" + "\n".join(bits), loc="left", fontsize=9, color=INK)
        ax.set_xlabel("log(evaluation count)", fontsize=9, color=INK)
        _style(ax)
    axes[0].set_ylabel("stated mean predicted OOS Sharpe", fontsize=9, color=INK)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7,
                      color=MODEL_COLOUR[m], label=m.split("-")[1]) for m in models]
    fig.legend(handles=handles, fontsize=9, loc="lower center", ncol=len(handles),
               frameon=False, bbox_to_anchor=(0.5, 0.005))
    fig.suptitle("Stated confidence against search performed, config s0",
                 x=0.005, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out_dir / "agent_stated_vs_log_count.png", dpi=150,
                facecolor="white")
    plt.close(fig)
    names.append("agent_stated_vs_log_count.png")

    # 2. s3 PASS rate against the preflight power at open.
    s3 = pick(kept, config="s3")
    if s3:
        # One bar per (calibration, arm): amendment 9's two sigmas are separate
        # experiments, and a bar pooling them would average across the change
        # the batch exists to measure.
        sigmas3 = sorted({round(float(r["sigma"]), 6) for r in s3})
        groups = sorted({(round(float(r["sigma"]), 6), r["model"], r["arm"]) for r in s3})
        arms3 = [f"{a}\n{m.split('-')[1]}\nσ{sg:g}" for sg, m, a in groups]
        fig, ax = plt.subplots(figsize=(1.6 * len(groups) + 1.6, 4.2))
        rates, los, his = [], [], []
        for sg, m, a in groups:
            cell = [r for r in s3 if r["arm"] == a and r["model"] == m
                    and round(float(r["sigma"]), 6) == sg]
            k = sum(1 for r in cell if r["status"] == "PASS")
            lo, hi = wilson_ci(k, len(cell))
            rates.append(k / len(cell)); los.append(lo); his.append(hi)
        xs = np.arange(len(groups))
        err = np.vstack([np.array(rates) - np.array(los),
                         np.array(his) - np.array(rates)])
        ax.bar(xs, rates, width=0.5, color=BLUE, zorder=3, linewidth=0)
        ax.errorbar(xs, rates, yerr=err, fmt="none", ecolor=INK, elinewidth=1.4,
                    capsize=5, zorder=4)
        # Headroom first, then the annotations: at the default limits the
        # reference-line label landed on the gate bar's own value label.
        pwr = [r["power_at_open"] for r in s3 if r["power_at_open"] is not None]
        ref = float(np.mean(pwr)) if pwr else None
        top = max(his + ([ref] if ref is not None else []))
        ax.set_ylim(0, top + 0.16)
        if ref is not None:
            ax.axhline(ref, color=ORANGE, linestyle="--", linewidth=2, zorder=5)
            ax.text(-0.45, top + 0.10, f"preflight power at open {ref:.3f}",
                    color=ORANGE, fontsize=9, ha="left", va="center")
        for x, r, h in zip(xs, rates, his):
            ax.text(x, h + 0.022, f"{r:.3f}", ha="center", fontsize=9, color=INK)
        ax.set_xticks(xs); ax.set_xticklabels(arms3)
        ax.set_ylabel("PASS rate (Wilson 95%)", fontsize=9, color=INK)
        ax.set_title("s3 PASS rate against preflight power at open",
                     loc="left", fontsize=12, color=INK)
        _style(ax)
        fig.tight_layout()
        fig.savefig(out_dir / "agent_s3_pass_rate.png", dpi=150, facecolor="white")
        plt.close(fig)
        names.append("agent_s3_pass_rate.png")

    # 3. Sonnet vs Fable deflation gap, per arm (batch 3).
    b3 = [r for r in graded(pick(kept, config="s0")) if r["batch"] == "b3"]
    models = sorted({r["model"] for r in b3})
    if len(models) == 2:
        arms3 = sorted({r["arm"] for r in b3})
        fig, ax = plt.subplots(figsize=(6.4, 3.9))
        w = 0.34
        for i, m in enumerate(models):
            colour = MODEL_COLOUR[m]
            meds, err = [], [[], []]
            for a in arms3:
                v = [gap(r) for r in b3 if r["arm"] == a and r["model"] == m]
                md, q1, q3 = med_iqr(v)
                meds.append(md); err[0].append(md - q1); err[1].append(q3 - md)
            xs = np.arange(len(arms3)) + (i - 0.5) * (w + 0.02)
            ax.bar(xs, meds, width=w, color=colour, zorder=3, linewidth=0,
                   label=f"{m.split('-')[1]} (n={sum(1 for r in b3 if r['model'] == m) // len(arms3)})")
            ax.errorbar(xs, meds, yerr=np.array(err), fmt="none", ecolor=INK,
                        elinewidth=1.2, capsize=4, zorder=4)
            for x, v in zip(xs, meds):
                ax.text(x, v + 0.008, f"{v:.3f}", ha="center", fontsize=8, color=INK)
        ax.set_xticks(np.arange(len(arms3))); ax.set_xticklabels(arms3)
        ax.set_ylabel("deflation gap (median, IQR)", fontsize=9, color=INK)
        ax.set_title("Deflation gap by model within arm, config s0, batch 3",
                     loc="left", fontsize=12, color=INK)
        # Headroom before the legend: at the default limits the box sat on the
        # tallest bar and hid its value label.
        ax.set_ylim(0, ax.get_ylim()[1] * 1.30)
        ax.legend(fontsize=9, frameon=False, loc="upper right", ncol=2)
        _style(ax)
        fig.tight_layout()
        fig.savefig(out_dir / "agent_sonnet_vs_fable_gap.png", dpi=150,
                    facecolor="white")
        plt.close(fig)
        names.append("agent_sonnet_vs_fable_gap.png")

    # 4. The paper figure: stated mean against the in-sample Sharpe actually
    # submitted, s0 sonnet, one point per run, arms in colour, with the two
    # lines that bound the claim -- y = x (stating the in-sample number back)
    # and y = x - null_max_mean (stating the search-corrected number).
    rs = graded(pick(kept, config="s0", model=PINNED_MODEL))
    if rs:
        x_all = np.array([r["submitted_sr_is"] for r in rs], float)
        y_all = np.array([r["stated_mean"] for r in rs], float)
        # null_max_mean is not stored on its own; it is exactly the distance the
        # verdict already records between the reported and the deflated Sharpe.
        nmm = x_all - np.array([r["sr_deflated"] for r in rs], float)
        nmm_med = float(np.median(nmm))

        fig, ax = plt.subplots(figsize=(7.0, 7.0))
        lo = min(x_all.min(), y_all.min()) - 0.10
        hi = max(x_all.max(), y_all.max()) + 0.10
        ends = np.array([lo, hi])
        ax.plot(ends, ends, color=MUTED, linestyle="--", linewidth=1.5, zorder=2)
        ax.plot(ends, ends - nmm_med, color=MUTED, linestyle="-.", linewidth=1.5,
                zorder=2)
        # Right-anchored, like the corrected line's label: left-anchored it ran
        # off the top-right corner of the frame.
        ax.text(hi - 0.06, hi - 0.06 + 0.035, "y = x   (stated = in-sample)",
                color=MUTED, fontsize=9, rotation=45, rotation_mode="anchor",
                transform_rotates_text=True, ha="right")
        ax.text(hi - 0.06, hi - 0.06 - nmm_med + 0.035,
                f"y = x − null-max-mean ({nmm_med:.3f})   (corrected)",
                color=MUTED, fontsize=9, rotation=45, rotation_mode="anchor",
                transform_rotates_text=True, ha="right")

        for arm in sorted({r["arm"] for r in rs}):
            cell = [r for r in rs if r["arm"] == arm]
            x = np.array([r["submitted_sr_is"] for r in cell], float)
            y = np.array([r["stated_mean"] for r in cell], float)
            colour = ARM_COLOUR.get(arm, INK)
            f = ols(x, y) if len(cell) >= 3 else None
            ax.scatter(x, y, s=26, alpha=0.70, color=colour, edgecolor="white",
                       linewidth=0.5, zorder=3,
                       label=f"{arm}  (n={len(cell)}"
                             + (f", b={f['slope']:+.2f})" if f else ")"))
            if f is not None:
                xs = np.linspace(x.min(), x.max(), 100)
                ax.plot(xs, f["intercept"] + f["slope"] * xs, color=colour,
                        linewidth=2, zorder=4)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("submitted in-sample Sharpe", fontsize=10, color=INK)
        ax.set_ylabel("stated mean predicted OOS Sharpe", fontsize=10, color=INK)
        ax.set_title("Stated belief against the in-sample Sharpe submitted\n"
                     f"config s0, {PINNED_MODEL}, n = {len(rs)}",
                     loc="left", fontsize=12, color=INK)
        ax.legend(fontsize=9, framealpha=0.95, loc="upper left")
        _style(ax)
        fig.tight_layout()
        fig.savefig(out_dir / "agent_stated_vs_insample.png", dpi=200,
                    facecolor="white")
        plt.close(fig)
        names.append("agent_stated_vs_insample.png")

    return names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()

    dirs = sorted(d for d in Path(a.runs_dir).iterdir()
                  if d.is_dir() and d.name.startswith(PREFIXES))
    if not dirs:
        raise SystemExit(f"no runs matching {PREFIXES} under {a.runs_dir}")

    runs, incomplete = [], []
    for d in dirs:
        try:
            runs.append(load_run(d))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            incomplete.append(f"{d.name} ({type(e).__name__})")

    text = report(runs, incomplete, Path(a.out))
    print(text)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "agent_analysis.txt").write_text(text + "\n")
    print(f"\nwrote {Path(a.out) / 'agent_analysis.txt'}")


if __name__ == "__main__":
    main()
