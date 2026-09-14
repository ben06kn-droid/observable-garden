# observable-garden

Transcript-based overfitting estimator. A search over specifications logs the
full in-sample return stream of every trial it evaluates; the estimator
computes a bootstrapped null-maximum over the *observed* trial correlation
structure — no independence assumption, no guessed trial count — and reports
a deflated Sharpe and a p-value against that null.

See `estimator_build_spec.md` (build spec) for the full design. This README
will lead with results once there are any (see spec §7, "days 14-16"); for
now it tracks build status.

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

**Next (days 7-9):** scripted searchers (`Honest`, `Greedy`, `GridSearch`,
`Adaptive`) and experiment 1, the null-calibration gate — uniform p-values
under `s=0` across every searcher and trial budget, tested via
Kolmogorov-Smirnov against U(0,1). This is the pass/fail gate for the whole
project; if it fails, stop and fix before building anything else.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```
