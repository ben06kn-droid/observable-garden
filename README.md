# observable-garden

**An estimator for how much of a reported backtest is search rather than
signal.**

The deflated Sharpe ratio of Bailey & López de Prado subtracts an expected
null maximum from a reported result, but that subtraction needs the number
of trials behind it — and for human research, nobody knows what that number
is. For an agent it doesn't need to be: every specification it evaluates,
kept or discarded, sits in a log. This estimator takes that log as its only
input — a stationary bootstrap over the search's *observed* trial
correlation structure, resampled jointly so ten near-duplicate variants of
one idea deflate like roughly one trial, not ten. No independence
assumption, no invented trial count.

Validated first against a synthetic data-generating process with a
computable oracle — where "how much did the search cost you" has a right
answer to check against — before any claim about real backtests. Long-run
aim (`estimator_build_spec.md`, `The Observable Garden.pdf`): an
instrumented sandbox an agent searches against, scoring its stated
confidence against what its own transcript implies it should have expected.

## How it works

1. A search evaluates candidate specifications one at a time against a
   sandbox (`environments/sandbox.py`). Every evaluation is logged with its
   full return stream, used or not.
2. The searcher submits one specification plus a predictive distribution
   over its own out-of-sample Sharpe.
3. The estimator (`estimator/bootstrap.py`) demeans every logged column
   (imposing the null), then repeatedly resamples one time index and
   applies it to *all* columns at once — preserving their observed
   correlation exactly — tracking the resampled maximum. That gives a
   deflated Sharpe and a p-value.
4. `environments/dgp.py` provides the synthetic world this is validated
   against: a known signal set and a closed-form oracle Sharpe.

## Validated scope

Full argument in `SCOPE.md`. Short version: the bootstrap is valid whenever
the search's *candidate menu* is **data-oblivious** — fixed given the
search's own configuration, independent of realized outcomes — for any
trial count and any correlation among candidates, including exact
duplicates. Strictly weaker than "independent trials," and it's what makes
a huge, correlated grid search just as tractable as one honest backtest.

It breaks when later trials are chosen conditional on earlier *realized*
outcomes — a real agent's tool-calling loop. A logged transcript licenses a
valid correction only when the candidate set is fixed; when the search
generates candidates conditional on its own results, the log alone isn't
enough. A **recursive bootstrap** (`estimator/recursive_bootstrap.py`) that
re-derives each round's selection per replicate fixes this, but depends on
the specification class being algebraically rich enough to reconstruct
untried candidates — a real dependency, checked against a
reconstruction-free gold standard (`estimator/procedure_level_bootstrap.py`).

## Results

*Type-I rate = fraction of null draws with p<0.05 (should be ≈0.05). Every
number below, every caveat, and every diagnostic that produced it is in
`SCOPE.md`; this is the summary.*

**Null calibration** — is the p-value actually uniform under the null,
regardless of search shape? (`K=25, M=60, T=600`)

| searcher | naive bootstrap | recursive bootstrap |
|---|---|---|
| Honest | pass | pass |
| Greedy | pass | pass |
| GridSearch | pass | pass |
| Adaptive | **fail** — type-I 13.6% (n=500) | pass — type-I 3.4% (n=500) |

Adaptive's candidate menu depends on realized outcomes; a control
(`LatticeAdaptive`) isolated the cause as candidate *generation*, not
*selection*. The recursive-bootstrap fix was validated against a
reconstruction-free gold standard: agrees within noise (mean diff +0.019,
SD 0.043 over 20 draws).

**Dose-response** — does the failure scale with how data-dependent the
candidate set is, or is it one searcher's quirk? (`experiments/
e5_dose_response.py`, n=150, `K=20`; figure: `figures/
e5_dose_response_primary.png`)

| beam width `k` | 20 (full menu) | 16 | 4 | 2 | 1 (Adaptive) |
|---|---|---|---|---|---|
| naive type-I | 0.060 | 0.067 | 0.093 | 0.107 | 0.127 |
| recursive type-I | 0.060 | 0.060 | 0.060 | 0.060 | 0.060 |

Strictly monotone as `k` shrinks, no falsifier triggered — the effect isn't
narrow to one searcher. (Recursive's five identical readings were checked
directly, not assumed correct — verified mechanically correct, and it's one
measurement at n=150, not five independent ones; `SCOPE.md` §5.) A
structural variant (`NeighborAdaptive`, a different selection rule with the
same *amount* of data-dependence) lands on the same rate as Adaptive: it's
data-dependence itself that breaks the naive bootstrap, not the specific rule.

**Predictive power under the alternative** (`s=3`, real signal, with the
correlation sweep folded in — `experiments/e7_predictive_power.py`, `N ∈
{10,100,1000} × ρ ∈ {0,0.3,0.6,0.9}`, n=100/cell) — a mixed result, not the
clean win that would most simply close this project's remaining gap.
Closed-form DSR (raw N) narrowly beats bootstrap deflation on per-draw RMSE
in 11/12 cells, and every predictor's R² is negative — none out-predicts a
flat mean of `SR_OOS` here. Bootstrap *does* track mean realized decay
more closely than closed-form at every grid point, a different (and
favorable) criterion from per-draw RMSE. The ρ=0 consistency check (should
show bootstrap ≈ closed-form) didn't pass cleanly — traced to ρ=0 not
meaning "independent trials" for a combinatorial searcher (confirmed: mean
trial correlation ≈0.10 at ρ=0), though the gap's growth with `N` remains
unexplained. Full account, including the ruled-out hypothesis, in
`SCOPE.md` §8.

## Repository layout

```
environments/   the DGP (computable oracle) and the Sandbox contract
searchers/      scripted.py: Honest, Greedy, GridSearch, Adaptive.
                dose_response.py: BeamAdaptive, DepthAdaptive, NeighborAdaptive.
                diagnostic.py: LatticeAdaptive. Each implements run()
                (against a Sandbox) and replay() (pure-array, for the
                recursive bootstrap).
estimator/      bootstrap.py (naive), recursive_bootstrap.py, procedure_
                level_bootstrap.py (gold standard), deflated_sharpe.py
                (closed-form baseline), divergence.py (candidate-set
                instability diagnostics), metrics.py (type-I rate + CI,
                RMSE/R², KS critical value)
experiments/    e1-e5: null calibration through the dose-response sweep.
                e6: precondition check before Experiment 2. e7: predictive
                power + correlation sweep.
tests/          correctness tests -- duplicate-invariance, run()/replay()
                agreement, lattice greedy-optimality
figures/        plots referenced above
```

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```
