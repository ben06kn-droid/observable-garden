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
answer to check against, before any claim is made about real backtests.

Full design in `estimator_build_spec.md`; motivating essay in
`The Observable Garden.pdf`. This README tracks build status and will lead
with results once there are any.

## Status

**Days 1-3 (done):** synthetic DGP with a computable oracle, and the sandbox
contract that scripted searchers and an eventual LLM agent will both run
against.

- `environments/dgp.py` — panel DGP (`M` assets x `T` periods x `K` features,
  `s` of them carrying signal), an equicorrelation `Sigma_x`, and a closed-form
  oracle Sharpe derived from the true linear strategy. Verified against a
  chunked Monte Carlo simulation (`tests/test_oracle.py`) across correlation
  and noise-scale sweeps, including fat-tailed noise.
- `environments/sandbox.py` — `get_data` / `evaluate` / `submit` contract.
  Every `evaluate()` call logs its full return stream regardless of use; OOS
  data is reachable only through a harness-only grading method a searcher
  never calls.

**Days 4-6 (done):** bootstrap estimator and closed-form DSR baseline.

- `estimator/bootstrap.py` — stationary bootstrap (Politis-Romano) with joint
  row resampling across all trial columns simultaneously, block length chosen
  per-column via Politis-White (`arch.bootstrap.optimal_block_length`, median
  across columns). `null_max_bootstrap` / `deflate`.
- `estimator/deflated_sharpe.py` — closed-form DSR (Bailey & Lopez de Prado),
  with both raw and eigenvalue-based effective trial count, kept only as the
  baseline the bootstrap is measured against.
- Tests 2-5 (spec §6) passing: independent-trial agreement with the closed
  form, ~zero deflation at N=1, block length correctly under-deflates
  autocorrelated data at L=1. Test 4 (duplicate invariance) is the one
  the spec calls "the thesis in eight lines of code": duplicating every trial
  column leaves the bootstrap's mean null-max unchanged while the naive
  closed form moves up meaningfully — verified for both iid and
  factor-correlated base trials.
- Known limitation to revisit if it bites: at large N (tens of thousands of
  trials, e.g. a full GridSearch sweep) the bootstrap's B=10,000 default gets
  slow (~1.7s at N=50, ~85s extrapolated at N=2000). Not optimized yet since
  Days 7-9 hasn't produced a real large-N transcript to profile against.

**Days 7-9 (blocked — the gate caught something real):** the four scripted
searchers are built and tested (`searchers/scripted.py`, `tests/
test_searchers.py`), and experiment 1 (`experiments/e1_null_calibration.py`)
ran: 100 pure-null (`s=0`) draws, every searcher, KS test against U(0,1).

| searcher   | KS statistic | KS p-value | verdict |
|---|---|---|---|
| Honest     | 0.110 | 0.167 | pass |
| Greedy     | 0.042 | 0.992 | pass |
| GridSearch | 0.048 | 0.966 | pass |
| Adaptive   | 0.173 | **0.004** | **fail** |

(figure: `figures/e1_null_calibration.png`)

Adaptive — the searcher the spec calls "the one that matters most" because
it reproduces a real agent's sequential structure — is *not* calibrated.
GridSearch has far more trials and equally correlated ones, and passes; so
it isn't N and it isn't correlation.

`experiments/diagnose_adaptive_calibration.py` isolates why: `PseudoAdaptive`
runs the identical round structure and trial count as `Adaptive`, but
round-2+ candidates always extend a *fixed* anchor feature instead of
whichever feature round 0's data happened to pick as best. Same N, same
correlated/overlapping subsets, same number of rounds — the only thing
removed is choosing later trials conditional on an earlier trial's outcome.
At matched scale (`K=30`, 80 draws): Adaptive KS p=0.020 (fails), PseudoAdaptive
KS p=0.539 (passes).

So the failure isn't the trial count and isn't the correlation structure —
both of those are exactly what the bootstrap is built to handle, and it
handles them correctly (that's what Greedy and GridSearch show). It's that
the bootstrap resamples the *observed* transcript's columns holding the
column *set* fixed, while Adaptive's later-round column set is itself a
function of the realized null noise: which pairs even get tried in round 2
depends on which single won round 1, on this specific draw. A resample that
reuses the same fixed weight vectors doesn't reproduce the counterfactual
where a different round-1 winner would have sent round 2 down a different
path entirely. Spec §4.1 calls this the pass/fail gate for the whole project
— it is failing for exactly the searcher the spec flags as the one that
matters most, so Days 10+ are on hold pending a decision on how to handle
sequentially-adaptive search (see conversation / open question below).

**Resolved (for now): scope the claim, ground the failure in theory.** Full
writeup in `SCOPE.md`. Short version:

- The bootstrap's actual sufficient condition isn't independence (what the
  spec's own framing says) — it's that the candidate *menu* be
  **data-oblivious** (fixed given the search's configuration, independent of
  realized outcomes). That's strictly weaker than independence and it's
  exactly what Honest/Greedy/GridSearch have, however large or correlated
  their menus get — which is why all three are calibrated.
- Adaptive's menu isn't oblivious: round 2's candidates are built on top of
  whichever feature *actually* won round 1 on this realized data. Because
  `Specification` is linear (a pair's return stream is exactly
  `single(a)+single(b)`, confirmed to float precision), this is directly
  checkable: an "oracle" bootstrap that re-derives each round's winner from
  every replicate's *own* resampled data — instead of freezing it at the
  observed winner, which is what the naive bootstrap does — raises
  `mean_null_max` (0.061→0.070 on a single draw) and restores calibration
  (KS p: 0.001→0.558 over 80 null draws). That's a controlled confirmation
  of the mechanism, not just a plausible story.
- This is a known phenomenon (Leeb & Pötscher 2005 on the impossibility of
  naive post-selection bootstraps; Efron 2014's prescription to re-run
  selection inside the bootstrap, which is exactly what the oracle bootstrap
  above does; the selective-inference program of Berk et al. 2013 and Lee et
  al. 2016), not a novel one — `SCOPE.md` §3 has the precise citations.
- **Validated claim going forward:** the estimator is correctly calibrated
  for any data-oblivious search — any trial count, any correlation,
  duplicates included — which covers Honest/Greedy/GridSearch-shaped agent
  behavior (menu fixed up front, best result reported). Sequential search
  (Adaptive, and a real agent's tool-calling loop) is a documented open
  boundary, not silently swept in.

Days 10-13 (experiments 2-4, decay/scaling/correlation curves) proceed on
Honest, Greedy, and GridSearch, within this scoped claim.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```
