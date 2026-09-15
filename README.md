# observable-garden

**An estimator for how much of a reported backtest is search rather than
signal.**

Bailey & López de Prado's deflated Sharpe ratio needs the number of trials
behind a result — for human research, nobody knows that number. For an
agent, it's observable: every specification it evaluates, kept or
discarded, sits in a log. This estimator bootstraps directly over that
log's observed trial correlation structure — no independence assumption,
no invented trial count — validated against a synthetic DGP with a
computable oracle before any claim about real backtests.

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
  bootstrap; **Adaptive fails** (type-I 13.6% vs. nominal 5%, n=500)
  because its candidate menu depends on outcomes. A recursive bootstrap
  fixes it (type-I 3.4%).
- **Dose-response**: type-I rate rises monotonically as the candidate
  menu gets more data-dependent (0.060 → 0.127 across 5 points) — not one
  searcher's quirk.
- **Predictive power** (`s=3`, real signal): only **bootstrap deflation is
  unbiased** for average decay; closed-form (raw N) is conservative, less
  so as correlation rises; the "effective N" eigenvalue correction is
  substantially anti-conservative wherever trials are correlated. One
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
environments/   DGP + Sandbox contract
searchers/      scripted, dose-response, and diagnostic searchers
estimator/      naive/recursive/procedure-level bootstrap, closed-form baseline, metrics
experiments/    e1-e11, numbered in the order they ran
tests/, figures/
```
