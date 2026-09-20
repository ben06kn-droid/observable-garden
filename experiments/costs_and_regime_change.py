"""costs-and-regime-change: what does a PASS survive?

Pre-registered in `prereg/costs-and-regime-change.md`. Amendment 2 withdrew the
cost half entirely: the DGP draws features independently each period, so every
submission's position path is serially independent, turnover is `sqrt(2)` for
every specification, and any charge is a drag common to PASS and FAIL alike. A
cost cannot discriminate here by construction, so it is not tested here. The
`sqrt(2)` result and the size of a 20 bps charge are reported as properties of
the DGP, which is the reason the synthetic arm carries no cost result.

What remains is the regime half: three counterfactual out-of-sample panels per
run, each regenerated from the same seed with one field of `DGPConfig` changed,
the submission held fixed, and the PASS - FAIL gap in gross OOS Sharpe read under
each.

    python -m experiments.costs_and_regime_change

Free and local; no bootstraps, no model calls.
"""
from __future__ import annotations

import csv
import dataclasses
import json
import pickle
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu

from environments.dgp import DGPConfig, generate, true_signal_set
from experiments.e_agent import dgp_seeds

RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"
BATCHES = ("b4-s3-recal", "b5-opus")          # the s3 runs at sigma = 194.407
M, T, T_OOS, K, S_TRUE = 50, 5000, 1000, 40, 3
ANN = np.sqrt(252)
SHIFTS = ("unshifted", "beta-halved", "beta-flipped", "sigma-doubled")
NAMES_A_B = ("beta-halved", "beta-flipped")   # the shifts that name a feature
BOOT, RNG_SEED = 10_000, 20260920

INK, BLUE, ORANGE, GRAY = "#222222", "#2a78d6", "#eb6834", "#8a8a86"


def cell(row: dict, key: str):
    try:
        return json.loads(row[key])
    except (json.JSONDecodeError, TypeError):
        return row[key]


def population() -> list[dict]:
    """The graded s3 submissions at sigma = 194.407, as the Design section fixes
    them. `b2-arms`'s s3 runs are at sigma = 1 and are a different population."""
    rows: list[dict] = []
    for b in BATCHES:
        rows += list(csv.DictReader((RUNS_ROOT / b / "runs.csv").open()))
    keep = [r for r in rows
            if cell(r, "config") == "s3" and cell(r, "graded")
            and cell(r, "has_submission") and cell(r, "submitted_features")]
    sigmas = {float(cell(r, "sigma")) for r in keep}
    if len(sigmas) != 1:
        raise SystemExit(f"population spans several sigma values: {sigmas}")
    return keep


def weights_of(row: dict) -> np.ndarray:
    w = np.zeros(K)
    for f, s in zip(cell(row, "submitted_features"), cell(row, "submitted_signs")):
        w[int(f)] = float(s)
    return w


def sharpe(R: np.ndarray) -> float:
    return float(R.mean() / R.std(ddof=1) * ANN)


def panels(row: dict) -> tuple[dict[str, float], np.ndarray, float]:
    """Gross OOS Sharpe under each shift, plus the true signal set and turnover.

    One `generate` call, not four. Shifts (a) and (b) change only `beta`, which
    `generate` applies after every random draw, so the features and the noise are
    bit-identical and the shifted return is `x_oos @ beta_shift + eps` with the
    same `eps`. Shift (c) doubles `sigma`, and `rng.normal(0, sigma)` scales the
    same standard draws, so its noise is exactly `2 * eps`. `true_signal_set`
    keys off `seed` alone, so S does not move under any of them. Equivalence to
    four full `generate` calls is asserted in `verify_shift_shortcut`.
    """
    seed = int(dgp_seeds()[int(cell(row, "seed_index"))])
    sigma = float(cell(row, "sigma"))
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=S_TRUE, rho=0.0, sigma=sigma, seed=seed)
    d = generate(cfg)
    w = weights_of(row)

    p = d.x_oos @ w                                      # (T_oos, M) positions
    eps = d.r_oos - d.x_oos @ d.beta_full                # the realised noise

    beta_a = d.beta_full.copy(); beta_a[d.S[0]] *= 0.5
    beta_b = d.beta_full.copy(); beta_b[d.S[0]] *= -1.0
    returns = {
        "unshifted": d.r_oos,
        "beta-halved": d.x_oos @ beta_a + eps,
        "beta-flipped": d.x_oos @ beta_b + eps,
        "sigma-doubled": d.x_oos @ d.beta_full + 2.0 * eps,
    }
    out = {k: sharpe(np.mean(p * r, axis=1)) for k, r in returns.items()}

    # reported as a property of the DGP, not as a cost result
    pn = p / np.mean(np.abs(p))
    turnover = float(np.mean(np.abs(np.diff(pn, axis=0))))
    return out, d.S, turnover


def verify_shift_shortcut(rows: list[dict], n: int = 3) -> list[str]:
    """`panels` computes the shifted returns algebraically. That is only
    admissible if it reproduces what four `generate` calls would give, which is
    what the pre-registration specifies. Checked on a sample, exactly."""
    L = ["SHIFT CONSTRUCTION — algebraic against four full generate() calls", "-" * 78]
    worst = 0.0
    for row in rows[:n]:
        seed = int(dgp_seeds()[int(cell(row, "seed_index"))])
        sigma = float(cell(row, "sigma"))
        base = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=S_TRUE, rho=0.0,
                         sigma=sigma, seed=seed)
        d0 = generate(base)
        b = list(d0.beta_full[d0.S])
        full = {
            "beta-halved": dataclasses.replace(base, beta=tuple([b[0] * 0.5] + b[1:])),
            "beta-flipped": dataclasses.replace(base, beta=tuple([-b[0]] + b[1:])),
            "sigma-doubled": dataclasses.replace(base, sigma=sigma * 2),
        }
        got, _, _ = panels(row)
        w = weights_of(row)
        for name, cfg in full.items():
            d = generate(cfg)
            want = sharpe(np.mean((d.x_oos @ w) * d.r_oos, axis=1))
            worst = max(worst, abs(want - got[name]) / max(abs(want), 1e-12))
    L.append(f"  {n} runs x 3 shifts, worst relative difference {worst:.2e}")
    if worst > 1e-12:
        raise SystemExit(f"shift shortcut disagrees with generate() at {worst:.2e}")
    L.append("  exact; the algebraic path is what the rest of the run uses")
    return L + [""]


def gap(sr: np.ndarray, is_pass: np.ndarray) -> float:
    return float(np.median(sr[is_pass]) - np.median(sr[~is_pass]))


def paired_gap_ci(sr_shift: np.ndarray, sr_base: np.ndarray, is_pass: np.ndarray):
    """Bootstrap interval for (gap under shift) - (gap unshifted), resampling
    runs so the two gaps move together. Rule 1's fails-high branch compares
    against this, not against a fresh interval per shift."""
    rng = np.random.default_rng(RNG_SEED)
    n = sr_base.size
    draws = np.empty(BOOT)
    for i in range(BOOT):
        idx = rng.integers(0, n, n)
        p = is_pass[idx]
        if p.all() or not p.any():
            draws[i] = np.nan
            continue
        draws[i] = gap(sr_shift[idx], p) - gap(sr_base[idx], p)
    draws = draws[~np.isnan(draws)]
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def gap_ci(sr: np.ndarray, is_pass: np.ndarray, mask: np.ndarray):
    """Percentile interval for a stratum's PASS - FAIL median gap, resampling
    PASS and FAIL within the stratum separately so each side's n is preserved.
    Reported because one stratum (FAIL, contains S[0]) is small."""
    rng = np.random.default_rng(RNG_SEED)
    a, b = sr[is_pass & mask], sr[~is_pass & mask]
    if a.size < 2 or b.size < 2:
        return float("nan"), float("nan")
    draws = np.array([np.median(rng.choice(a, a.size)) - np.median(rng.choice(b, b.size))
                      for _ in range(BOOT)])
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def _verdict_row(label: str, sr: np.ndarray, is_pass: np.ndarray,
                 group: np.ndarray) -> list[str]:
    """One row of readout 1: PASS and FAIL medians within a group, and the gap.
    A group with one side empty prints a dash rather than a nan."""
    p, f = sr[is_pass & group], sr[~is_pass & group]
    if p.size == 0 or f.size == 0:
        return [label, str(p.size), str(f.size), "-", "-", "-"]
    return [label, str(p.size), str(f.size), f"{np.median(p):+.4f}",
            f"{np.median(f):+.4f}", f"{np.median(p) - np.median(f):+.4f}"]


def table(title: str, header: list[str], rows: list[list[str]], note: str = "") -> list[str]:
    L = [title, "-" * 78] + ([note, ""] if note else [])
    # auto-size each column to its widest cell; a table whose numbers run into
    # one another is a table that gets misread
    w = [max(len(h), *(len(r[i]) for r in rows)) + 2 if rows else len(h) + 2
         for i, h in enumerate(header)]
    L.append("".join(h.ljust(w[i]) if i == 0 else h.rjust(w[i])
                     for i, h in enumerate(header)))
    for r in rows:
        L.append("".join(c.ljust(w[i]) if i == 0 else c.rjust(w[i])
                         for i, c in enumerate(r)))
    return L + [""]


def main() -> None:
    out_dir = Path("figures")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = population()

    L = ["costs-and-regime-change: what does a PASS survive?", "=" * 78,
         f"{len(rows)} graded s3 submissions at sigma = "
         f"{float(cell(rows[0], 'sigma')):.5f}, from {' + '.join(BATCHES)}",
         "The cost half is withdrawn (amendment 2); see DGP PROPERTIES below.", ""]
    L += verify_shift_shortcut(rows)

    sr = {k: [] for k in SHIFTS}
    is_pass, models, hits, turnovers, verify = [], [], [], [], []
    for row in rows:
        got, S, u = panels(row)
        for k in SHIFTS:
            sr[k].append(got[k])
        is_pass.append(cell(row, "status") == "PASS")
        models.append(cell(row, "model"))
        hits.append(int(S[0]) in [int(f) for f in cell(row, "submitted_features")])
        turnovers.append(u)
        verify.append(abs(got["unshifted"] - float(cell(row, "oos")))
                      / max(abs(float(cell(row, "oos"))), 1e-12))

    sr = {k: np.array(v) for k, v in sr.items()}
    is_pass = np.array(is_pass); models = np.array(models)
    hits = np.array(hits, dtype=bool); turnovers = np.array(turnovers)

    worst = float(np.max(verify))
    L += ["RECONSTRUCTION", "-" * 78,
          f"  gross OOS Sharpe against the stored value, worst relative "
          f"difference {worst:.2e}"]
    if worst > 1e-9:
        raise SystemExit(f"reconstruction mismatch at {worst:.2e}; halting per the "
                         "pre-registration rather than dropping runs")
    L += ["  within the pre-registered 1e-9; no run dropped", ""]

    L += table("DGP PROPERTIES — why there is no cost result",
               ["quantity", "value"],
               [["turnover, mean", f"{turnovers.mean():.4f}"],
                ["turnover, sd", f"{turnovers.std(ddof=1):.5f}"],
                ["turnover, min", f"{turnovers.min():.4f}"],
                ["turnover, max", f"{turnovers.max():.4f}"],
                ["sqrt(2)", f"{np.sqrt(2):.4f}"]],
               "Features are drawn independently each period, so every position path is\n"
               "serially independent and turns over completely. Turnover cannot vary with\n"
               "the specification, so any charge is a drag common to PASS and FAIL.")

    n_pass = int(is_pass.sum())
    L += table("READOUT 1 — median gross OOS Sharpe by verdict",
               ["group", "n PASS", "n FAIL", "PASS", "FAIL", "gap"],
               [_verdict_row(lbl, sr["unshifted"], is_pass, m)
                for lbl, m in [(name, models == name)
                               for name in sorted(set(models.tolist()))]
                + [("pooled", np.ones(len(rows), dtype=bool))]])

    L += table("READOUT 2 — survival fractions, unshifted",
               ["verdict", "n", "SR > 0", "SR > 0.5"],
               [[v, str(int(m.sum())),
                 f"{np.mean(sr['unshifted'][m] > 0):.1%}",
                 f"{np.mean(sr['unshifted'][m] > 0.5):.1%}"]
                for v, m in (("PASS", is_pass), ("FAIL", ~is_pass))])

    L += table("READOUT 3 — the same, under each shift",
               ["shift", "PASS med", "FAIL med", "gap", "PASS>0", "FAIL>0"],
               [[k, f"{np.median(sr[k][is_pass]):+.4f}",
                 f"{np.median(sr[k][~is_pass]):+.4f}", f"{gap(sr[k], is_pass):+.4f}",
                 f"{np.mean(sr[k][is_pass] > 0):.1%}",
                 f"{np.mean(sr[k][~is_pass] > 0):.1%}"] for k in SHIFTS])

    L += ["DECISION RULE 1 — the gap survives each regime shift", "-" * 78,
          "  One-sided Mann-Whitney, PASS > FAIL, pooled, at p < 0.05.",
          "  Fails high if a shift widens the gap beyond the paired bootstrap",
          "  interval on (shift - unshifted); that is not predicted and is",
          "  investigated, not claimed.",
          f"    {'shift':<16}{'gap':>10}{'MWU p':>12}{'holds':>8}"
          f"{'shift - unshifted (95% CI)':>32}"]
    base_gap = gap(sr["unshifted"], is_pass)
    verdicts = {}
    for k in SHIFTS:
        g = gap(sr[k], is_pass)
        p = float(mannwhitneyu(sr[k][is_pass], sr[k][~is_pass],
                               alternative="greater").pvalue)
        if k == "unshifted":
            L.append(f"    {k:<16}{g:>+10.4f}{p:>12.2e}{'yes' if p < 0.05 else 'NO':>8}"
                     f"{'(reference)':>32}")
            verdicts[k] = p < 0.05
            continue
        lo, hi = paired_gap_ci(sr[k], sr["unshifted"], is_pass)
        high = lo > 0.0
        verdicts[k] = p < 0.05
        L.append(f"    {k:<16}{g:>+10.4f}{p:>12.2e}{'yes' if p < 0.05 else 'NO':>8}"
                 f"{f'{g - base_gap:+.4f} ({lo:+.4f}, {hi:+.4f})':>32}"
                 + ("  WIDER" if high else ""))
    L += ["",
          f"  Rule 1: {'HOLDS under every shift' if all(verdicts.values()) else 'FAILS LOW under: ' + ', '.join(k for k, v in verdicts.items() if not v)}",
          ""]

    split_rows = []
    for k in ("unshifted",) + NAMES_A_B:
        for g, m in (("contains S[0]", hits), ("does not", ~hits)):
            lo, hi = gap_ci(sr[k], is_pass, m)
            gg = np.median(sr[k][is_pass & m]) - np.median(sr[k][~is_pass & m])
            split_rows.append([k, g, f"{int((is_pass & m).sum())}/{int((~is_pass & m).sum())}",
                               f"{np.median(sr[k][is_pass & m]):+.4f}",
                               f"{np.median(sr[k][~is_pass & m]):+.4f}",
                               f"{gg:+.4f}", f"({lo:+.3f},{hi:+.3f})"])
    L += table("RULE 1 SPLIT — does the submission contain the altered feature?",
               ["shift", "group", "n P/F", "PASS med", "FAIL med", "gap", "gap 95% CI"],
               split_rows,
               "Registered by amendment 2. Shift (c) doubles sigma and names no\n"
               "feature, so it is not split. `unshifted` is each stratum's own\n"
               "baseline, so a shifted subgroup gap is read against it rather than\n"
               "against the pooled unshifted figure. Intervals are percentile\n"
               "bootstrap, resampling PASS and FAIL within the stratum separately;\n"
               "the FAIL/contains-S[0] cell is the small one.")

    L += ["COMPOSITION — who the feature-naming shifts land on", "-" * 78,
          "  EXPLORATORY: added after the result, not pre-registered. The split",
          "  above is registered (amendment 2); this readout explains it.",
          f"  PASS runs containing S[0]: {hits[is_pass].mean():.1%} "
          f"({int(hits[is_pass].sum())} of {int(is_pass.sum())})",
          f"  FAIL runs containing S[0]: {hits[~is_pass].mean():.1%} "
          f"({int(hits[~is_pass].sum())} of {int((~is_pass).sum())})",
          "  The gate selects for the true signal, so a shift that alters S[0]",
          "  lands disproportionately on PASS runs. Pooled and split gaps can",
          "  therefore differ without either being wrong; both are reported, and",
          "  rule 1 is read on the pooled figure exactly as pre-registered.", ""]

    L += ["DECISION RULE 2 — PASS loses value under a shift, it does not invert",
          "-" * 78,
          "  Falsifier: a significantly NEGATIVE gap under any shift.",
          f"    {'shift':<16}{'gap':>10}{'MWU p (FAIL > PASS)':>24}{'inverted':>10}"]
    inverted = []
    for k in SHIFTS[1:]:
        p = float(mannwhitneyu(sr[k][~is_pass], sr[k][is_pass],
                               alternative="greater").pvalue)
        bad = p < 0.05
        inverted.append(bad)
        L.append(f"    {k:<16}{gap(sr[k], is_pass):>+10.4f}{p:>24.2e}"
                 f"{'YES' if bad else 'no':>10}")
    L += ["", f"  Rule 2: {'HOLDS -- no inversion' if not any(inverted) else 'FALSIFIED; investigate before write-up'}", ""]

    text = "\n".join(L)
    print(text)
    (out_dir / "costs_and_regime_change.txt").write_text(text + "\n")
    with (out_dir / "costs_and_regime_change_data.pkl").open("wb") as fh:
        pickle.dump({"sharpe": sr, "is_pass": is_pass, "model": models,
                     "contains_altered": hits, "turnover": turnovers,
                     "shifts": SHIFTS}, fh)


if __name__ == "__main__":
    main()
