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
  menu gets more data-dependent (0.060 → 0.127 across 5 points, `figures/
  e5_dose_response_primary.png`) — not one searcher's quirk.
- **Predictive power** (`s=3`, real signal, `figures/e9_decay_vs_N.png`,
  `figures/e9_bias_vs_rho.png`): of the three corrections, only
  **bootstrap deflation is unbiased** for average decay. Closed-form with
  the raw trial count is conservative, less so as correlation rises. The
  "sophisticated" eigenvalue correction is substantially anti-conservative
  wherever trials are correlated at all.

Every number, caveat, and diagnostic behind these — including two real
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
experiments/    e1-e9, numbered in the order they ran
tests/, figures/
```
