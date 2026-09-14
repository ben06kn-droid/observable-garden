# observable-garden

**An estimator for how much of a reported backtest is search rather than
signal — with the one input every version of this problem has had to guess
replaced by a number read off the transcript.**

The deflated Sharpe ratio of Bailey & López de Prado subtracts an expected
null maximum from a reported result, but that subtraction needs the number
of trials behind it — and for human research, nobody knows what that number
is. The "garden of forking paths" (Gelman & Loken) is usually a metaphor for
exactly this unknowability. For an agent it doesn't need to be: every
specification it evaluates, kept or discarded, sits in a log. This estimator
takes that log as its only input — a stationary bootstrap over the search's
*observed* trial correlation structure, resampled jointly across trials so
ten near-duplicate variants of one idea deflate like roughly one trial, not
ten. No independence assumption, no invented trial count.

It's validated first against a synthetic data-generating process with a
computable oracle, where "how much did the search cost you" has a right
answer to check against, before any claim is made about real backtests. The
long-run aim (`estimator_build_spec.md`, `The Observable Garden.pdf`) is an
instrumented sandbox an agent searches against, where the estimator scores
the agent's stated confidence against what its own transcript implies it
should have expected — testing whether agents discount for the search
they've just run, or are simply deaf to their own trial count.

## How it works

1. A search evaluates candidate specifications one at a time against a
   sandbox (`environments/sandbox.py`). Every evaluation is logged with its
   full in-sample return stream, whether or not the search goes on to use it.
2. The searcher submits one specification plus a predictive distribution
   over its own out-of-sample Sharpe.
3. The estimator (`estimator/bootstrap.py`) demeans every logged column
   (imposing the null that nothing in the transcript carries real edge),
   then repeatedly draws one stationary-bootstrap time index and applies it
   to *all* logged columns at once — preserving their observed correlation
   structure exactly — and tracks the resampled maximum. That empirical
   distribution gives a deflated Sharpe and a p-value: how surprising is the
   reported result, given a search that looked exactly like this one?
4. `environments/dgp.py` provides the synthetic world this is validated
   against: a panel with a known signal set and a closed-form oracle Sharpe,
   so "how much did the search cost" has a computable right answer.

## Validated scope

Full argument and citations in `SCOPE.md`. The short version: the bootstrap
is exactly valid whenever the search's *candidate menu* is **data-oblivious**
— fixed given the search's own configuration, independent of realized
outcomes — for *any* trial count and *any* correlation structure among
candidates, including exact duplicates. That's a strictly weaker condition
than the "independent trials" framing usually attached to this kind of
method, and it's what makes a huge, heavily-correlated grid search just as
tractable as one honest pre-registered backtest.

It breaks for search where later trials are chosen conditional on earlier
trials' *realized* outcomes within the same run — the structure of a real
agent's tool-calling loop — and the reason is sharper than "the naive
bootstrap has a bug": **a logged transcript licenses a valid correction only
when the candidate set is fixed. When the search generates candidates
conditional on its own earlier results, the transcript alone is not enough.**
A **recursive bootstrap** (`estimator/recursive_bootstrap.py`) that
re-derives each round's selection inside every replicate fixes this, but it
depends on the specification class being algebraically rich enough to
reconstruct candidates that were never actually evaluated (linearity, here)
— which is a real, load-bearing dependency, not a detail, and is checked
explicitly against a reconstruction-free gold standard
(`estimator/procedure_level_bootstrap.py`). Full argument, including the
experiment that isolates *why* it fails — adaptive candidate generation, not
adaptive selection — is in `SCOPE.md` §§2–4.

## Results

*Updated as experiments run. See `figures/` for plots and `SCOPE.md` for the
theory behind anything non-obvious below. Type-I rate = fraction of null
draws with p < 0.05 (should be ≈0.05); reported with a 95% Wilson CI
alongside the KS statistic, since a bare KS p-value near its critical value
doesn't settle the question either way.*

**Null calibration, properly powered (n=200 matched null draws, `K=25,
M=60, T=600, B=1500`, `experiments/e1_null_calibration.py` /
`e1_recursive_calibration.py`):**

| searcher | naive bootstrap | recursive bootstrap |
|---|---|---|
| Honest     | KS p = 0.777 — pass | KS p = 0.777 — pass |
| Greedy     | KS p = 0.118 — pass | KS p = 0.118 — pass (identical to naive, as it must be — same math) |
| GridSearch | KS p = 0.174 — pass | KS p = 0.144 — pass |
| Adaptive   | **KS D = 0.205, p ≈ 0.0000 — fail, over 2x the critical value** | KS D = 0.088, p = 0.088 — pass, just under the n=200 critical value (0.096) |

**Isolating the cause** — Adaptive vs. `LatticeAdaptive` (same greedy
selection rule, but evaluates the full fixed lattice unconditionally instead
of building it round-by-round; `experiments/e2_lattice_control.py`, n=200,
`K=20, M=60, T=600, B=1500`):

| searcher | KS stat | KS p | type-I rate at α=0.05 (95% CI) |
|---|---|---|---|
| Adaptive | 0.211 | 0.0000 | 0.120 (0.082–0.172) — excludes nominal 5% |
| LatticeAdaptive | 0.100 | 0.034 | 0.065 (0.038–0.108) — includes nominal 5% |

Adaptive candidate *generation* — not adaptive *selection* — is what breaks
the naive bootstrap: on the operationally relevant statistic (type-I rate),
LatticeAdaptive isn't distinguishable from correctly calibrated; Adaptive is.

**Validating the fix against a dependency-free gold standard**
(`experiments/e3_procedure_level_validation.py`, 20 draws): the cheap
recursive bootstrap vs. a procedure-level bootstrap that re-executes the
actual search on nullified raw data (no linearity dependency) — mean
difference in `mean_null_max` = +0.019 (SD 0.043), sign flipping roughly
evenly across draws. No detectable systematic bias.

**Definitive Adaptive check at n=500** (`experiments/e4_adaptive_n500.py`,
`K=25, M=60, T=600, B=1500`) — properly powered enough that neither result
is close to its critical value:

| estimator | KS stat | KS p | type-I rate at α=0.05 (95% CI) |
|---|---|---|---|
| naive | 0.164 (critical: 0.061) | 0.0000 | 0.136 (0.109–0.169) — decisively excludes nominal 5% |
| recursive | 0.041 (critical: 0.061) | 0.363 | 0.034 (0.021–0.054) — consistent with nominal 5% |

Naive fails almost 3x its nominal rate; recursive is indistinguishable from
correctly calibrated. The fix holds at proper statistical power, not just
at the n=200 boundary case that motivated running this.

**Experiments 2-4 from the build spec** (predictive power under the
alternative, scaling with trial budget, correlation sensitivity) — not yet
run; blocked behind resolving the adaptive-search boundary above first.

## Repository layout

```
environments/   the DGP (computable oracle) and the Sandbox contract
searchers/      scripted.py: Honest, Greedy, GridSearch, Adaptive -- each
                implements run() (against a Sandbox) and replay() (pure-
                array, for the recursive bootstrap). diagnostic.py:
                LatticeAdaptive, the selection-vs-generation control.
estimator/      bootstrap.py (naive), recursive_bootstrap.py (re-derives
                selection per replicate via replay()), procedure_level_
                bootstrap.py (dependency-free gold standard: re-executes
                run() on nullified data), deflated_sharpe.py (closed-form
                baseline), metrics.py (type-I rate + Wilson CI, KS critical
                value)
experiments/    e1 (null calibration, both estimators), e2 (lattice
                control), e3 (procedure-level validation), e4 (n=500
                Adaptive), plus the diagnostic scripts behind SCOPE.md
tests/          correctness tests -- duplicate-invariance
                (estimator/bootstrap.py), run()/replay() agreement, the
                lattice greedy-optimality property e2 leans on
figures/        plots referenced above
```

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```
