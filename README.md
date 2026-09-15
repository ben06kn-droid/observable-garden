# observable-garden

**An estimator for how much of a reported backtest is search rather than
signal, and a gate that turns it into a verdict.**

## Quickstart

```
pip install -e .
garden audit --example null_grid     # FAIL          exit 1
garden audit --example real_edge     # PASS          exit 0
garden audit --example overwide      # INADMISSIBLE  exit 2
garden audit --example null_grid --menu-kind unknown   # UNDECIDABLE  exit 3
```

Moving-average crossover searches on simulated prices, where the right
answer is known by construction (`garden/examples.py`):

| example | search | verdict |
|---|---|---|
| `null_grid` | 362 rules, 10 years, no edge anywhere | **FAIL**: best Sharpe 0.57 vs. critical value 0.97 |
| `real_edge` | 32 rules, 10 years, one rule with true Sharpe 1.5 | **PASS**: 1.74 vs. 0.79 |
| `overwide` | 10,000 rules, 4 years, one rule with true Sharpe 0.75 | **INADMISSIBLE**: 8% power for a single pre-specified strategy with true Sharpe 1.0 |

These are fixed transcripts in `garden/data/` (data seed 0; `python -m
garden.examples` regenerates them), so the quickstart is deterministic. On
other seeds the verdicts vary the way a calibrated test should: across 20
data seeds `null_grid` fails 19 times, the 5% type-I rate the test is
designed to have, and `real_edge` passes all 20. Every verdict prints its
null maximum, critical value, power, and a reason per check, so it can be
checked by eye.

Before a search, size it:

```
garden preflight --specs 1000 --periods 2520 --reference-sharpe 1.0 --rho 0.5
```

On your own search: `garden audit run.npz` (fields `returns` T×N,
`spec_ids`, `submitted`, `menu_kind`, `periods_per_year`), `garden audit
run.csv --submitted <id> --menu-kind oblivious`, or from Python,
`garden.audit(garden.from_matrix(R, submitted_index, menu_kind="oblivious"))`.
`menu_kind` defaults to `unknown`, which returns UNDECIDABLE; `garden explain
menu` walks through whether your menu was fixed in advance. An adaptive search
can still get a verdict from a version-2 transcript that declares the class of
every specification it could have produced (`spec_class`, e.g.
`subsets:max_size=3`), with `base_returns` for every feature it could have
used and each logged specification's weights (`spec_members`). The gate then
runs the Reality Check over the whole class (`garden explain full-class`).
From a sandbox that enforces the class this is automatic
(`spec_class_source="sandbox"`); in a supplied file the class and
`base_returns` are attestations, like `menu_kind`. Exit codes are
0 PASS, 1 FAIL, 2 INADMISSIBLE, 3 UNDECIDABLE, 4 DEGENERATE (the test statistic broke on this menu), 64 usage error.

The deflated Sharpe ratio judges a reported result against what the
research process that produced it could have delivered without skill
(López de Prado & Porcu 2025). Its closed-form benchmark, DSR-L, needs the
number of trials behind a result — for human research, nobody knows that
number. For an agent, it's observable: every specification it evaluates,
kept or discarded, sits in a log. This estimator builds the search null
nonparametrically from that log's observed trials — no independence
assumption, no invented trial count — validated against a synthetic DGP with
a computable oracle before any claim about real backtests.

**Relationship to prior work.** The verdict engine is White's Reality
Check (2000). That correction is twenty-six years old and is the right
tool. What this adds is: (i) a characterization of when a *logged
transcript* suffices to apply it — the candidate menu must be
data-oblivious — and what breaks when a searcher generates candidates
from its own realized results; (ii) a demonstration that plugging a
participation-ratio effective N into DSR-L is anti-conservative, because
DSR-L already absorbs trial correlation through its variance term; (iii) a pre-flight power
calculation that tells you before searching whether your intended breadth
can certify anything; and (iv) an instrumented sandbox for the case the
correction was never able to reach, where the searcher is an LLM agent and
the trial count is observable for the first time.

## How it works

A search evaluates candidate specs against a sandbox that logs every
return stream, used or not, then submits one spec plus a predictive
distribution over its own OOS Sharpe. The estimator demeans every logged
column, resamples one time index across all of them jointly (preserving
their observed correlation), and reports a deflated Sharpe and p-value
from the resampled maximum.

## Validated scope

Works whenever the search's candidate menu is **data-oblivious** — fixed
given the search's configuration, independent of outcomes — for any trial
count and any correlation, including duplicates. Breaks when trials are
chosen conditional on their own earlier results (a real agent's
tool-calling loop): the log alone isn't enough, since untried candidates
can't be reconstructed from it in general. A recursive bootstrap fixes
this for specification classes rich enough to reconstruct candidates
algebraically — checked against a reconstruction-free gold standard.

## Results

- **Null calibration**: Honest/Greedy/GridSearch pass under the naive
  bootstrap; **Adaptive fails** because its candidate menu depends on
  outcomes: naive type-I 13.6% against nominal 5% (n=500), where a
  recursive bootstrap gives 3.4%. Those two figures come from an earlier
  configuration (K=25 features, M=60, T=600) and block-length rule, not the
  one used in the rest of this list. On K=20, M=50, T=500 the same test
  gives 9.2% naive and 5.4% recursive (SCOPE.md §17). The scoring rule is
  not the difference: for Adaptive, scoring its own selection or the
  transcript maximum gives identical p-values (E18b).
- **Dose-response**: naive type-I rises monotonically as the candidate
  menu gets more data-dependent: 5.4% → 6.0% → 8.0% → 8.4% → 9.2% from a
  full lattice to greedy search (n=500 per point, pre-registered). It is
  not one searcher's quirk. What drives it is building on the search's own
  best results. Rules that anchor on a random or uncorrelated feature stay
  at or near nominal, and inflation rises with how strongly the anchor
  tracks performance (SCOPE.md §14–18).
- **Wider searches make the naive correction worse.** For a search that
  builds on its own best feature, naive type-I rose from 10% to 36% as the
  candidate features grew from 10 to 80 with uncorrelated features, and
  from 7% to 14% at correlation 0.3, matching a Gaussian-limit prediction
  fixed in advance. The recursive and full-class corrections stayed at 4–5%
  throughout (SCOPE.md §19).
- **Predictive power** (`s=3`, real signal): only **bootstrap deflation is
  unbiased** for average decay; closed-form DSR-L with the raw trial count
  is conservative, less so as correlation rises; DSR-L with a
  participation-ratio effective N is substantially anti-conservative
  wherever trials are correlated. One
  cell makes the case concretely: at ρ=0, N=1000, a search reports Sharpe
  **2.03** — double the population ceiling — when the truth is 0.21. The
  bootstrap calls the decay to within 0.017; raw-N over-corrects by 14%;
  effective-N leaves a quarter of the overfitting standing.
- **Power**:
  naively, power rises with correlation (16%→43%, ρ 0→0.9) — but that's
  the DGP getting easier (true achievable Sharpe rises sixfold over the
  same axis), not the estimator improving; at ρ=0 power is correctly
  *below nominal* for a weak signal, not a flaw. A second, subtler
  confound: power appearing to rise with trial budget `N` at fixed signal
  strength turned out to mean the searcher finds a *better* spec at
  larger `N`, not that searching more is free. Pinning the submitted spec
  to the true signal and growing only the transcript around it isolates
  the real cost: power **falls** 15%→6%→2% (`N`=10→100→1000) at one
  signal strength, 69%→42%→26% at a stronger one — the pure
  multiple-testing cost of having looked, and the number this project
  exists to produce.
- **An underpowered pass overstates the edge, steeply.** Bootstrap
  `sr_deflated` is unbiased unconditionally (mean error −0.005 across
  Experiment 2's 1,200 draws), but not conditional on passing. Oversampled
  at one breadth (N=100), 200 passes per signal strength
  (`experiments/e12_type_m_by_power.py`), a passing result's deflated
  Sharpe is **11.9×** the truth at 6% search power, 3.1× at 9%, 1.55× at
  16%, 1.10× at 30%, and 0.75× / 0.67× at 66% / 89%. The fall is monotone,
  as predicted before running (Gelman & Carlin's type-M error). Above about
  30% power it reverses: a strong search's winner is mostly signal, and
  subtracting the null maximum over-deflates it. The bundled `overwide`
  example shows the low-power end live: on the 6 of 20 data seeds where it
  passes instead of returning INADMISSIBLE, the winning rules have true
  Sharpes of 0.13–0.58 and deflated Sharpes of 0.65–1.07, and every one
  carries the gate's warning. The warning quotes this curve rather than
  interpolating on it, because the gate's single-strategy power is not on
  the search-power axis (SCOPE.md §12).
- **Preflight against measurement, signed.** Predicted minus measured
  power in the six pinned-experiment cells (n=100 each): +0.002, −0.017,
  −0.010 at true Sharpe ≈1.0 (N=10/100/1,000), and +0.006, +0.013, −0.038
  at ≈2.0. Independence should make preflight conservative: correlated
  trials (about 0.1 mean correlation in these menus) lower the true null
  maximum and raise true power. Across the six cells the residuals showed no
  consistent sign (mean −0.007; Σz² = 2.5 on 6 df), so any bias is small
  relative to sampling noise at n=100.
- **A fifth verdict, DEGENERATE, for menus where the test statistic
  breaks.** Re-estimating Sharpe in every replicate lets rules that rarely
  trade set the null maximum: one 10,000-rule band-filter menu gave
  critical values from 2.03 to 155 across seeds. The gate refuses when more
  than half of the replicates that set the critical value came from
  resamples with fewer than 50 active periods, or when excluding them would
  flip the verdict. A pre-registered calibration on fresh seeds refused 0
  of 9,000 dense transcripts, 90% of sparse menus with a broken critical
  value, and 4% of those with a sound one (SCOPE.md §11).

Every number, caveat, and diagnostic behind these — including three real
bugs found and fixed along the way — is in **`SCOPE.md`**. This is the
summary.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Layout

```
garden/         the gate: transcript format, audit, preflight, explain, CLI, examples
environments/   DGP + Sandbox contract
searchers/      scripted, dose-response, and diagnostic searchers
estimator/      naive/recursive/procedure-level bootstrap, closed-form baseline, metrics
experiments/    e1-e18 in the order they ran; _parallel.py runs draws across processes with checkpoints
prereg/         pre-registrations, each committed before its experiment ran; COMMIT_MAP.md
cloud/          EC2 setup and detached-run scripts
tests/, figures/
```
