# Roadmap: testing the gate where it hasn't been tested

Order and reasoning only. Every cell gets its own `prereg/<name>.md`, committed
before it runs, with its gate, and removed once it has reported — as every experiment here has. What the gate does,
and what it has been shown to do, is in SCOPE.md. Nothing below is expected to
overturn any of it; each item bounds where it applies. About 160 seat runs, under
$60. Free and local work first, the seat last.

| # | test | where | gate |
|---|---|---|---|
| 6.1 | **Calibration at 1%.** 5.0% at α=0.05 is one point on a distribution; allocation decisions run at 1%, with 5× fewer events and more of the bootstrap tail. Re-score stored s0 p-values at α ∈ {0.10, 0.05, 0.01} (Wilson, KS against U(0,1)); then 5,000 scripted Greedy and Adaptive draws under the full-class null, and 500 at B=50,000 to check tail resolution. | free, then local | 1% inside its interval and KS not rejecting, every searcher. A high 1% with a fine 5% means an under-resolved tail: raise B before anything else runs. |
| 6.2 | **Costs and regime change**, which the gate ignores by construction. Positions follow from the submitted specification and the DGP seed, so re-grade the 160 s3 runs net of 5/10/20 bps turnover, and under a halved β, a flipped β, and doubled σ. | free | — replaces "not checked" with what they cost |
| 6.3 | **Heterogeneous correlation and fat tails** under the full-class null, calibrated so far only on equicorrelated Gaussian features. unequal-correlation's one-factor loadings; t(4) innovations with a GARCH path. 2,000 draws each of s0, Greedy and Adaptive. | local | holds at 5% and 1%. If t/GARCH is liberal at 1%, suspect the block-length selector and report the lengths chosen. |
| 6.4 | **Explicit classes in `watch`**, which refuses them at open today — so an agent whose tool grammar emits rules rather than equal-weight feature subsets cannot be watched. `audit` already prices such a class; give `watch` the same path. | code | bar equals `audit`'s explicit-class null on the same inputs; membership refused by id; bar does not move |
| **6.5** | **An agent on real data — the headline.** Every agent run so far used a synthetic panel with a known oracle. ~40 liquid US ETFs with continuous history from 2005, the universe recorded before any search; in-sample 2005–2021, holdout 2022–2026 never on the machine the agent runs on. K=40 price signals at strict one-day lag, dollar-neutral cross-sectional, so zero excess return is the right null and no benchmark subtraction is needed. `preflight` fixes the admissible class before any run. control and gate, 40 runs each, Sonnet. | seat, ~80 | — |
| 6.6 | **T sweep.** Agents have only seen T=5,000, where the pinned class is admissible. At T ∈ {1,000, 2,500} the gate says INADMISSIBLE at open, and nothing has shown what an agent does when told in advance that nothing can be certified. | seat, ~40 | — |
| 6.7 | **Fat tails for agents**, only if 6.3 holds. | seat, ~40 | — |

**6.5's readouts, pre-registered.** Verdict distribution with its interval (no
oracle, so no expected rate). Holdout Sharpe of PASS against FAIL submissions,
gross and net of 10 bps — **if PASS does not predict holdout, that is the
result.** The haircut regression on real data beside the synthetic one. Which
features the agents converge on. After 6.4, twenty runs on a rule-grammar tool:
the first watched agent whose actions are not feature subsets. It cannot show
whether any PASS is a real edge — one holdout is one draw of the future.

Cut order if time runs short: the rule-grammar arm, then 6.7, then 6.6. Never 6.5.

## 6.9 Does PASS predict out-of-sample performance?

**A — sealed forward test.** Seal 6.5's submissions and verdicts at a
pre-registered cutoff, before any later data exist, so nothing can leak. Same
runs, two holdouts: 2022–2026 answers weakly now, the seal answers strongly at
12–18 months. The gate's claim is the FAIL side — nothing it refused should have
been believed; PASS is the weaker claim and the test should say so.

**B — intraday.** Twenty years of daily data hold four or five independent
windows: a direction with a wide interval, never a rate. Five-minute bars give
dozens of month-long rolling holdouts. Decide and record before any search:
costs are first-order (a spread crossing is comparable to the expected move), so
the null is zero return net of a pre-registered cost model via `--benchmark`;
sessions are not one series (gaps removed, session-edge bars flagged, annualize
by bars-per-year); and the effective sample sits well below the bar count, so
preflight runs on the bar series rather than on T. Fast decay is the point —
does PASS decay slower than FAIL? Two to four weeks of data acquisition and a
session-aware sandbox come first, so this follows the note and the paper. It
yields the number nobody has: the share of FAIL submissions with positive net
holdout Sharpe, the gate's false-negative rate on real data.

## Where the results go

Nothing to the note, which is finished as scoped. Paper: 6.1, 6.2, 6.3, 6.5.
README: 6.5's verdict table beside the SPY three-null table.

## Logged, not scheduled

The haircut equation across models (one window); whether the gate's feedback
improves outcomes and not only beliefs (it did not for Sonnet); whether an agent
can deflate when handed the DSR formula and the count, separating "cannot" from
"was not asked" (40 runs); the effective-N note (a day); a Thresholdout hybrid,
exploring on a noisy holdout and certifying a declared class on fresh data (a
week of code, no new theory).

Out of scope without a large amount of new work: interior-rank sign in closed
form, bootstrap consistency under partial separation, large-K asymptotics for
studentized maxima, the recursive tier for LLM agents, training agents to be
calibrated, a matched human baseline, non-Sharpe settings such as prediction
markets.
