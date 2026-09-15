# Transcript-Based Overfitting Estimator — Build Specification

**Goal of the prototype:** demonstrate, on synthetic data with a known oracle, that a bootstrapped null-maximum computed over a search's observed trial correlation structure predicts out-of-sample decay better than the reported in-sample number, and better than closed-form DSR with an estimated effective trial count.

This is the artifact that converts the proposal from an argument into evidence. Target: two to three weeks of part-time work, ~1,500 lines of Python, four figures.

---

## 1. What the estimator actually computes

### 1.1 Setup

A search produces `N` candidate specifications. Each specification `n` has an in-sample return series `r_n ∈ R^T`. The searcher selects one, typically `argmax_n SR(r_n)`, and reports its in-sample Sharpe `SR_sel`.

The question: how much of `SR_sel` is attributable to having looked at `N` things rather than one?

### 1.2 The existing answer and its weakness

The estimator below is White's Reality Check (White, H. (2000), "A Reality
Check for Data Snooping," Econometrica 68(5)) — a stationary-bootstrap test
over the observed maximum of a candidate set, applied here to a logged
search transcript rather than a fixed list of trading rules. It is not a
new statistical procedure; the contribution is characterizing when a
*logged transcript* suffices to apply it (see `SCOPE.md` §§1, 6), where
that breaks for a searcher that generates candidates from its own results,
and a fix for the case where the specification class permits it.

Bailey and López de Prado's closed-form deflated Sharpe ratio is a
parametric shortcut for approximately the same quantity White's bootstrap
estimates non-parametrically, and is the baseline this project's estimator
is compared against throughout — not the prior art it replaces. It
subtracts an expected maximum under the null:

```
SR_0 = sqrt(Var[SR_n]) * [ (1 - γ) * Φ⁻¹(1 - 1/N) + γ * Φ⁻¹(1 - 1/(N·e)) ]
```

where `γ ≈ 0.5772` is Euler–Mascheroni, `Φ⁻¹` is the inverse standard normal CDF, and `Var[SR_n]` is the variance of Sharpe estimates across trials.

Two inputs are problems in practice. `N` is unobservable for human research — this is the whole motivation. And the extreme-value formula assumes independent trials, which is false for any real search: the twentieth variant of an idea is nearly the same series as the third. When trials are highly correlated, `N` overstates the effective breadth of the search and the formula over-deflates.

### 1.3 The replacement

Both problems dissolve if you have the trial return streams themselves.

```
Input:  R ∈ R^(T × N)   — in-sample return matrix, one column per evaluated specification
        B               — bootstrap replicates (default 10,000)
        L               — block length (Politis–White automatic selection)

1. Impose the null: demean each column, R̃[:, n] = R[:, n] - mean(R[:, n])
   Every specification now has exactly zero true edge.
2. For b in 1..B:
     a. Draw a stationary bootstrap index sequence over TIME, length T,
        with mean block length L.
     b. Apply the SAME index sequence to all N columns simultaneously.
        This preserves the cross-sectional correlation structure exactly
        and the autocorrelation within each series approximately.
     c. Compute SR for each column on the resampled data.
     d. Record M_b = max_n SR_b(n).
3. Return the empirical distribution {M_b}.
```

Two outputs:

- **Deflated estimate:** `SR_deflated = SR_sel − mean(M_b)`
- **p-value:** `p = (1 + #{b : M_b ≥ SR_sel}) / (B + 1)`

The p-value is the primary reported quantity. It is the probability of observing a maximum this large from a search of this shape had nothing in the candidate set carried real edge.

**Why resampling rows jointly is the crux.** Resampling each column independently would destroy the correlation and reproduce the independence assumption we are trying to escape. Joint row resampling means that if 40 of 50 trials are near-duplicates, the bootstrap maximum reflects a search of effective breadth ~11, not 50 — and no estimate of "effective N" is needed, because the geometry is used directly.

### 1.4 Handling non-normality

Sharpe estimates are skew- and kurtosis-sensitive. The bootstrap inherits the empirical moments, so no Mertens-style analytic correction is needed. State this explicitly; it is an advantage over the closed form, not an omission.

---

## 2. Synthetic environment

The environment must satisfy three properties: a computable oracle, tunable difficulty, and no possibility of leakage into any model's pretraining.

### 2.1 Data-generating process

A panel of `M` assets over `T` periods with `K` observable features:

```
x[i, k, t]  ~ multivariate normal, cross-feature correlation Σ_x
r[i, t]     = Σ_{k ∈ S} β_k · x[i, k, t-1] + ε[i, t]
ε[i, t]     ~ N(0, σ²),  optionally t-distributed for fat tails
```

`S ⊂ {1..K}` is the true signal set, `|S| = s`, with `s << K`. The remaining `K − s` features are pure noise but are correlated with the true features through `Σ_x`, which is what makes the search genuinely hard rather than trivially solvable.

Defaults: `M = 200`, `T = 2000` in-sample, `T_oos = 1000`, `K = 60`, `s = 3`.

### 2.2 Difficulty knobs

- `σ` calibrated so the oracle achieves a target annualized Sharpe, swept over {0.5, 1.0, 2.0}
- `K`, the number of candidate features, swept over {20, 60, 200}
- `Σ_x` off-diagonal magnitude, controlling how much trials will resemble each other
- A **pure-null variant** with `s = 0`. This is the single most important configuration in the project; see §4.1.

### 2.3 The oracle

Because `S` and `β` are known, the optimal linear strategy is known. Compute its expected Sharpe by simulating the DGP for `T = 10^6` periods once per configuration and caching the result. This is the ceiling — the number no searcher can legitimately exceed, and the reference against which every reported Sharpe is measured.

---

## 3. The searcher

### 3.1 Phase 1: scripted searchers, not an LLM

Deliberate choice. A scripted searcher has a known, exact trial count, so the estimator can be validated before agent messiness is introduced. If the estimator fails here it will fail everywhere, and you will not be able to tell whether the fault is the method or the agent.

Implement four, each with a trial budget parameter:

| Searcher | Behavior | Why include it |
|---|---|---|
| `Honest` | Fits one pre-registered specification, no selection | Control. Deflation should be ~0 and p-value ~ uniform. |
| `Greedy` | Evaluates all `K` single-feature strategies, takes the best | Minimal selection, exactly `N = K` |
| `GridSearch` | Feature subsets up to size 3 × lookback ∈ {5,20,60} × threshold ∈ {1.0,1.5,2.0} | Large `N`, heavily correlated trials — the regime where the bootstrap should beat the closed form |
| `Adaptive` | Sequential: evaluates, keeps the best direction, expands around it | Mimics an agent. Trials are *sequentially dependent*, not just correlated. |

`Adaptive` is the one that matters most, because it is the only one that reproduces the structure of a real agent's search, where later trials are chosen conditional on earlier results.

### 3.2 The sandbox contract

Every searcher runs against one interface, and this interface is the eventual API for an LLM agent:

```python
class Sandbox:
    def get_data(self) -> pd.DataFrame: ...
    def evaluate(self, spec: Specification) -> EvalResult: ...
        # Logs: spec, full in-sample return stream, timestamp, call index.
        # Returns: in-sample Sharpe and summary stats ONLY.
    def submit(self, spec: Specification,
               predicted_oos_sharpe: Distribution) -> None: ...
```

Three properties that must hold:

1. `evaluate` never exposes out-of-sample data. Not once.
2. Every call to `evaluate` is logged with its full return stream, whether or not the searcher uses the result.
3. `submit` requires a predictive distribution over out-of-sample Sharpe. Scripted searchers supply a degenerate or naive one; this field only becomes live in Phase 2, but the contract should exist from day one so the harness does not need rewriting.

### 3.3 Phase 2: LLM agent

Once the estimator is validated, swap in a tool-calling agent against the identical sandbox. No changes to the estimator or the logging. The only new complication is latent forking — trials the model considers without calling `evaluate` — which biases the logged count downward and therefore makes measured deflation blindness a **lower bound**. Say this in the README.

---

## 4. Validation experiments

### 4.1 Calibration under the pure null (do this first)

Configuration with `s = 0`: no feature has any predictive power. Run all searchers, 500 independent DGP draws each.

**Prediction:** the p-value distribution is uniform on [0, 1] for every searcher at every trial budget.

**Test:** Kolmogorov–Smirnov against U(0,1). Plot the empirical CDF with a 45° reference line.

This is the pass/fail gate for the entire project. A correct null-maximum estimator must produce uniform p-values when the null is true, regardless of how hard the searcher searched. If `Greedy` at `N=60` and `GridSearch` at `N=2000` both produce uniform p-values, the estimator is doing its job. If `GridSearch` produces p-values concentrated near zero, the bootstrap is under-correcting for search breadth and the method is broken.

### 4.2 Predictive power under the alternative

Configuration with `s = 3`. For each of 500 runs, record `SR_IS`, `SR_deflated`, `SR_OOS`, and `SR_oracle`.

Compare three predictors of `SR_OOS`:

| Predictor | Expected behavior |
|---|---|
| `SR_IS` (naive) | Biased upward, bias grows with trial budget |
| Closed-form DSR with `N` = raw trial count | Over-deflates when trials are correlated |
| Closed-form DSR with effective `N` from eigenvalues of the trial correlation matrix | Better, still assumes a shape |
| **Bootstrap deflation** | Should dominate on RMSE, and the gap should widen with `Σ_x` |

Report RMSE and R² for each. The headline claim is the bootstrap column winning, and the specific configuration where it wins by the most is the one that goes in the proposal.

### 4.3 Scaling

Sweep trial budget `N ∈ {10, 50, 200, 1000, 5000}` holding everything else fixed. Plot `E[SR_IS − SR_OOS]` (realized decay) and `E[SR_IS − SR_deflated]` (predicted decay) on the same axes. If the estimator works, the two curves track. This is the single most legible figure in the project and the one to lead with.

### 4.4 Correlation sensitivity

Sweep `Σ_x` off-diagonal from 0 to 0.9. At zero, the bootstrap and closed-form DSR should agree — a useful consistency check that the implementation is not simply wrong. As correlation rises they should diverge, with the bootstrap tracking realized decay and the closed form over-deflating. This figure is the empirical answer to "why not just use the closed form," and is worth more than any amount of argument.

---

## 5. Repository layout

```
observable-garden/
  README.md                  # results first, 3 figures, method second
  environments/
    dgp.py                   # generators, oracle computation, config dataclasses
    sandbox.py               # the Sandbox contract, trial logging
  searchers/
    base.py                  # Searcher ABC
    scripted.py              # Honest, Greedy, GridSearch, Adaptive
    llm_agent.py             # Phase 2
  estimator/
    bootstrap.py             # stationary bootstrap, joint row resampling
    deflated_sharpe.py       # closed-form DSR baselines for comparison
    metrics.py               # decay, CRPS, deflation gap
  experiments/
    e1_null_calibration.py
    e2_predictive_power.py
    e3_scaling.py
    e4_correlation.py
  figures/
  tests/
    test_bootstrap.py        # known-answer tests, see §6
```

Dependencies: numpy, pandas, scipy, matplotlib. `arch` for the Politis–White block length, or implement it directly — it is about 30 lines. Nothing else. Keep it installable in one command.

---

## 6. Correctness tests

These are not optional; the whole value of the artifact is that a reviewer believes the numbers.

1. **Uniformity under null** — §4.1, as a test rather than only an experiment.
2. **Independent-trial agreement** — with `Σ_x = I` and IID normal returns, `mean(M_b)` should match the closed-form `SR_0` to within Monte Carlo error. If it does not, the bootstrap is wrong.
3. **Degenerate search** — with `N = 1`, deflation must be approximately zero.
4. **Duplicate invariance** — take a set of `N` trials, duplicate every column so there are `2N`, and confirm `mean(M_b)` is nearly unchanged. The closed form will move; the bootstrap must not. This test *is* the thesis, in eight lines of code.
5. **Block length sanity** — with autocorrelated returns, confirm that `L = 1` (IID bootstrap) under-deflates relative to the automatic block length.

Test 4 is the one to feature in the README.

---

## 7. Build order

**Days 1–3.** DGP, oracle computation, sandbox with logging. Verify the oracle Sharpe empirically matches its analytic value.

**Days 4–6.** Bootstrap estimator plus closed-form DSR baselines. Tests 2, 3, 4 passing.

**Days 7–9.** Scripted searchers. Experiment 1, null calibration. **This is the gate.** If p-values are not uniform, stop and fix before building anything else.

**Days 10–13.** Experiments 2, 3, 4. Figures.

**Days 14–16.** README with results at the top, three figures, and a short method section. This is the deliverable people will actually read.

**Optional, days 17+.** Phase 2 LLM agent against the same sandbox. Even a single run with logged trials, showing the gap between an agent's stated confidence and its transcript-implied deflation, is worth more to a reviewer than another synthetic sweep.

---

## 8. Known limitations, to state in the README rather than wait to be asked

**Latent forking.** An agent that reasons about a feature without evaluating it has searched invisibly. The logged count is a floor. Measured deflation blindness is therefore a lower bound on the true effect — which is the direction that favors the claim, but say so.

**Synthetic to real transfer.** A DGP with linear signal and fat-tailed noise is not a market. The synthetic track establishes that the estimator is correct where truth is known; a rolling-holdout real-data run establishes that it survives contact with real correlation structure. Do not conflate the two.

**Selection at the DGP level.** If you tune the DGP until the estimator looks good, you have committed the exact sin the project is about. Fix configurations before running, log them, and report every configuration you ran including the ones that did not work.

**The estimator does not identify the source of decay.** Trading costs, regime change, and overfitting all produce out-of-sample decay. The bootstrap isolates the component attributable to search breadth only, and the synthetic environment is clean of the other two by construction. On real data it is not, and that limitation is structural.
