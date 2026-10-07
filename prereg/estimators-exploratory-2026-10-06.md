# Estimators and selection stability, 2026-10-06 (America/Chicago). EXPLORATORY

Exploratory build and evaluation. Committed before any code, then the code, one run,
and the output (`runs/diagnostics/estimators_2026-10-06.txt`). Hypothesis-generating;
it changes no recorded result.

**Scope.** Design seeds **640150-640249** only (100 seeds; collides with nothing but
planted-edge's own design block; disjoint from the 640100-640149 used earlier today), at
levels 0, 0.5, 1.0, 1.5, on the fast kernel (`environments/planted_fast.py`) and the
pinned X. No registered block, no agent sessions, no model calls, no box. **The run
starts only with the laptop on mains and Low Power Mode off**, checked and printed at
launch.

**Check 0, done before this note** (the registered agent prompts, searched for halving,
a haircut or a default discount on in-sample Sharpe): **nothing**. The four arms'
system prompts were rebuilt from `experiments/planted_agent.prompt_for` and each matches
the hash stored in all of its stage-2 run files; neither they nor the tool descriptions
(`predict`: "State the out-of-sample Sharpe you expect.") contain such wording. The
only instruction is to give "a mean and standard deviation representing your belief
about that specification's annualized Sharpe ratio on data you have not seen".

## Definitions, verbatim from the request

> 1. In one pass per panel and level, compute for every member its realized
>    Sharpe S(m) and its Sharpe on each of B = 1,000 stationary-bootstrap
>    replicates of the UN-demeaned streams, S*_b(m), using the same index
>    draws as the null.
>
> 2. Point estimates of the true Sharpe of a submission with score S:
>    E0  S
>    E2  S - mean of the class null maximum
>    EH  0.5 * S                       (the agents' observed rule)
>    EC  S - (1 - C0) * mean of the class null maximum, C0 = 1 - p_class
>    EB  S - bias, bias = mean over b of [S*_b(m_b) - S(m_b)], where m_b is
>        the argmax of S*_b over the class     (bootstrap winner's-curse
>        correction for a class-maximum submission)
>    EBs as EB but with m_b chosen by replaying the searcher's own procedure
>        on replicate b; report for extend-while-improving.
>    Score each against in-sample population Sharpe and holdout population
>    Sharpe: bias, MAE, RMSE, per level, for the realized class argmax and
>    for extend-while-improving.
>
> 3. Selection stability, from the same replicates:
>    - f(m): the share of replicates in which m is the class argmax;
>    - the smallest set of members covering 90% of f, its size, and whether
>      it contains m+ and m*;
>    - per feature and per family (tau 0.8, complete linkage this time), the
>      share of replicates whose argmax contains it; and whether m*'s three
>      families are the top three by that share;
>    - a denoised selector: the member with the highest f. Report its edge
>      capture SR_pop/SR_pop(m+) beside the realized argmax's.

## Operational choices, fixed before any computation

- **Index draws:** exactly the class null's, as `planted_fast.class_pass_levels` makes
  them: block length `select_block_length` on the panel's base feature columns,
  `default_rng(seed)` per level, and stationary-bootstrap counts `C` (T x B).
- **Streams:** the kernel's net streams `X(m)` (T days). `S(m)` is the kernel's
  annualised realized Sharpe.
- **The class null (registered, centred):** the replicate Sharpe of `X - mean(X)`;
  `M_b` is its maximum over the class; "the mean of the class null maximum" is
  `mean_b M_b`; `p_class = (1 + #{M_b >= S}) / (B + 1)`.
- **Un-demeaned replicates:** `S*_b(m)` is the replicate Sharpe of `X` itself,
  computed in the same pass from the same `X @ C` and `X^2 @ C`. Kept per level as
  float32 (relative error about 1e-7) for the searcher replay.
- **m_b:** the argmax of `S*_b` over all 82,240 members (ties to the lowest index).
  `S(m_b)` is that member's realized Sharpe.
- **Submissions:** the realized class argmax (S = the class max) and
  extend-while-improving (`planted_edge._searchers`, run on the realized `S` exactly
  as `planted_fast.run_levels` runs it; S = its score, n = its moves).
- **EBs:** on each replicate, extend-while-improving's `_search` on `S*_b` with
  `meta_steps = n`, as `run_levels` replays it for the trigger null; `m_b^s` is its
  support; bias = `mean_b [S*_b(m_b^s) - S(m_b^s)]`. Reported for extend-while-improving
  only. EB is reported for both submissions (the same class-argmax bias).
- **Targets:** in-sample population Sharpe (the kernel's overlap pass and
  `population_from_moments`) and holdout population Sharpe
  (`planted_panel.truth(...)["holdout"]`). Error = estimate - target; bias, MAE, RMSE,
  n, per level and per submission, and "overall" pooled over the four levels.
- **The answers' criteria:** "lowest RMSE" and "beats both E0 and E2" are read on the
  in-sample target, per submission (holdout given alongside). "Beats" means strictly
  lower RMSE than both E0 and E2 at each of the four levels.
- **f, the 90% set:** f(m) = share of replicates with m_b = m. Members sorted by f
  descending (ties by index); the 90% set is the shortest prefix with cumulative f
  >= 0.90. Per level: quartiles of its size, and the share of panels where it contains
  m+ and m*.
- **Features and families:** a replicate's argmax "contains" feature k if k is in its
  support (either sign); it contains a family if it contains any of its features.
  - Families: complete-linkage clustering of the 40 single-feature weight-path
    correlations, distance `1 - |corr|`, cut at 0.2 (`scipy` `fcluster`, criterion
    "distance"), so every pair inside a family has |corr| >= 0.8.
  - m*'s families are the distinct families of its three features (k <= 3 of them).
    "Top three" holds iff they equal the top k families by share (ties broken by
    the lower family label). Also reported: all k of them in the top three.
  - Per level: the share of panels where the check holds, and the quartiles of each
    of m*'s features' shares and families' shares.
- **Denoised selector:** the member with the highest f (ties to the higher realized S,
  then the lower index). Capture `SR_pop / SR_pop(m+)` beside the realized argmax's,
  quartiles and n; also their difference in SR_pop and the share of panels where the
  denoised member's SR_pop is higher. Level 0: m+ is negative, the ratio is not a
  capture, and is labelled so.
- **The answers** are one sentence each, after the tables, citing the table.

## Reading, 2026-10-06 (America/Chicago). Exploratory findings

From the one run's output, `6726871` (`runs/diagnostics/estimators_2026-10-06.txt`;
code `b2e3a40`, run on the c7a.48xlarge, as its commit records). **Exploratory, on 100
panels per level**; in-sample target unless stated. Hypotheses for a registration, not
results.

a. **EBs is near-unbiased for extend-while-improving at all four levels**: bias +0.055,
   0.000, -0.013, -0.009 at 0, 0.5, 1.0, 1.5; RMSE 0.239-0.268, lower than E0's and
   E2's at every level.
b. **EB is near-unbiased for the class argmax at the planted levels** (+0.008, -0.027,
   -0.019 at 0.5, 1.0, 1.5) and **overstates by +0.166 at level 0**.
c. **The correction must match the procedure.** EB applied to extend-while-improving
   is biased **-0.097 to -0.178** (low at every level).
d. **EH (halving) is unbiased only at level 0.5**: for the class argmax, +0.446 at
   level 0 and -0.623 at 1.5.
e. **The 90% selection set is not a coverage set.** It contains m+ on 0, 46, 69 and
   84% of panels, with median size 331, 208, 106 and 46, at 0, 0.5, 1.0 and 1.5.
f. **The denoised selector (highest f) does not beat the realized argmax at any
   level.** Its median capture is at or below the argmax's at every planted level, and
   it is higher on only 11-16% of panels. **Dropped.**
g. **Consequence:** identity recovery is limited by sample length, and **capture is
   the recovery measure to carry forward** (the realized argmax's median capture
   0.732, 0.902, 0.931 at 0.5, 1.0, 1.5). [Note: T was fixed at 3,019 in-sample days in
   this run; sample length was not varied, so the dependence on it is inferred from
   the width of the selection set at fixed T, not measured.]

## Addendum, 2026-10-06 (America/Chicago): error conditional on certification. Exploratory

**Why.** A point estimate is to be shown only beside a certified verdict, and certified
submissions are selected for high scores. The unconditional biases above (`6726871`) are
therefore not the quantity a display rule depends on.

**What will be tabulated**, exploratory, before any number is computed:
- **Submissions and estimates:**
  - the realized class argmax, with E0, EH and EB;
  - extend-while-improving, with E0, EH, EBs, and EB as the fallback.
- **Certification:** the class tier at alpha = 0.05,
  `p_class = (1 + #{M_b >= S}) / (B + 1) < 0.05`, the centred class null exactly as
  defined above.
- **Per submission and per level (0, 0.5, 1.0, 1.5):**
  - the number certified out of 100;
  - among certified submissions only, the bias, MAE and RMSE of each estimate against
    in-sample SR_pop and against holdout SR_pop.
  - A cell with no certified submission is reported as n 0, never as a zero error.

**Source.** The run of `b2e3a40` saved no per-panel rows: it wrote only the text tables.
The rows therefore come from **a regeneration on the same seeds, 640150-640249, with the
committed code unchanged plus a per-panel dump**. The dump records each panel's score,
p_class, every estimate and both targets. The regeneration starts only after a further
go; its outputs must reproduce `6726871`'s tables, checked before the tabulation is read.
The order is: this addendum alone, then the dump and tabulation code, then the run,
then the output.
