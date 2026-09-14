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

**Next (days 4-6):** bootstrap estimator (`estimator/bootstrap.py`) plus the
closed-form DSR baseline, with the duplicate-invariance test as the one that
most directly tests the thesis.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```
