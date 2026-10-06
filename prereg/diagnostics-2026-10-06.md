# Diagnostics on 7.5, 2026-10-06 (America/Chicago). EXPLORATORY

**Exploratory.** Computed on data that has already been read. These diagnostics
generate hypotheses. **They change no recorded result**, and no rule, verdict or
registered readout of `prereg/planted-edge.md` is reread or revised by them.

**Order:** this file is committed before anything below is computed. Then the script
(`experiments/diagnostics_2026_10_06.py`) is committed, run once, and its output
(`runs/diagnostics/2026-10-06.txt`) is committed.

## Inputs

- **Stage 1:** `runs/planted_edge_scripted/draws.jsonl` (`30ee870`), seeds
  **600000–600199** only, at levels 0, 0.5, 1.0 and 1.5. Only the
  **extend-while-improving** searcher and the **realized class argmax** are used.
- **V2:** `runs/confidence_cell/draws.jsonl` (`0edab26`), seeds 620000–620999 at levels
  0, 1.0 and 1.5, six scripted searchers. Used **for C2 only**.
- **Stage 2:** the 202 priced agent files, `runs/planted_agent/*.json` (`06a5284`).
- **Check 2:** the fidelity presentation log,
  `runs/planted_agent_fidelity/fidelity_live_presentations.jsonl` (`09e9235`).
- **Fresh panels:** design seeds **640100–640149** only, for E.

**Not touched.** No registered seed block is run, and there is no box, no agent session
and no model call.
- The in-sample panels of seeds 600000–600199 and 630000–630019 are rebuilt from their
  seeds on the pinned X.
- The rebuild exists **only** to recompute positions and population Sharpes, as the
  request directs.
- No holdout rows are generated. The holdout quantities used are the ones already
  stored in the files above.

## The request, as written

What follows is copied exactly from the request.

> Ground rules
> - Exploratory, on data already read: the stage-1 file (30ee870), the V2
>   file (0edab26), the 202 priced agent files (06a5284) and the fidelity
>   presentation log (09e9235). Anything needing fresh panels uses design
>   seeds 640100-640149 only. No registered block is touched, no box, no
>   agent sessions, no model calls.
> - Before computing anything, commit prereg/diagnostics-2026-10-06.md,
>   labelled exploratory, listing every definition and threshold below
>   exactly as written. Then commit the script, then run it once, then commit
>   the output. These generate hypotheses; they change no recorded result.
> - Recompute positions and population Sharpes with the fast kernel on the
>   pinned X. For stage 1, use seeds 600000-600199 and the
>   extend-while-improving searcher plus the realized class argmax, to keep
>   it small.
> - "Truth" is in-sample population Sharpe unless stated. m* is the planted
>   member, m+ the population-best member. Report quartiles and n for every
>   table, per arm or searcher and per planted level.
>
> A. Recovery: was it the metric?
> A1. Edge capture: SR_pop(submission) / SR_pop(m+). Also report it for the
>     realized class argmax and for m* itself. Split agent rows by whether
>     the registered two-of-three test against m+ was a hit or a miss.
> A2. Position overlap: the correlation between the submission's weight path
>     and m*'s, pooled over days and assets, and the same against m+'s.
>     Cross-tabulate against the number of signed features shared (0, 1, 2,
>     3).
> A3. Feature families: the 40 x 40 matrix of weight-path correlations
>     between single-feature members. Group features into families at
>     |correlation| >= 0.8, and also report the grouping at 0.7 and 0.9.
>     Re-score recovery at family level: the submission shares at least two
>     of m*'s three signed families. Report beside the registered rate.
>
> B. Identifiability: what is the ceiling?
> B1. Per panel and level: the number of members with SR_pop within 0.05,
>     0.10 and 0.20 of m+; the number whose weight path correlates >= 0.9 and
>     >= 0.8 with m+'s; whether m* is in each set; whether the submission is.
> B2. Decompose the capture shortfall into noise and search:
>     SR_pop(m+) - SR_pop(realized argmax), and
>     SR_pop(realized argmax) - SR_pop(submission).
>
> C. Rule 4: what are agents doing, and can the gate do better?
> C1. Stated mean against the submission's in-sample realized score: the
>     median ratio and a least-squares line, per arm, pooled and by level.
>     Then stated mean against truth: the slope.
> C2. Candidate estimates of the true Sharpe, each scored against truth and
>     against holdout population Sharpe by bias, mean absolute error and root
>     mean square error:
>       E0 the realized score;
>       E1 the score minus the mean of the replay null, where a full replay
>          exists;
>       E2 the score minus the mean of the class null;
>       E3 the agent's stated mean (agent files only).
>     On the agent files per arm and level; on the V2 file for the scripted
>     searchers per level. Say how each null mean is obtained from what is
>     stored, and any approximation.
> C3. Calibration of the stated distribution: CRPS of the agent's
>     normal(mean, sd) against truth and against realized holdout Sharpe,
>     beside the CRPS of the gate's confidence curve read as a distribution,
>     class tier and replay tier.
>
> D. Rules: where do they break?
> D1. Trigger changes: per arm and level, how many runs changed a trigger,
>     at which move number, and which trigger and in which direction.
> D2. Stop fidelity: the agreement rate per level, and for disagreements,
>     whether the model continued where the rule said stop or stopped where
>     it said continue.
>
> E. Conservatism of the class null, on the 50 design seeds at levels 0, 1.0
>    and 1.5:
> E1. The share of members whose realized Sharpe is below minus one and
>     minus two standard errors.
> E2. The 95% quantile of the null maximum over all members, beside the
>     same quantile over only members with realized Sharpe >= minus two
>     standard errors. Label this a preview with no validity claim.
>
> Output
> Write runs/diagnostics/2026-10-06.txt with every table, and commit it.
> Paste it to me in full. After the tables, in a separate section, give a
> one-sentence direct answer to each of these, citing the table it rests on:
> (1) was low recovery mostly the metric; (2) how many members are
> indistinguishable from the best on a typical panel; (3) which estimate of
> the true Sharpe had the lowest error, and how the agents' compared;
> (4) how much would restricting the null tighten it.

## Operational definitions, fixed before computing

The request leaves the following choices open. Each is fixed here, before any number
is computed.

### General

- **Kernel.** `environments/planted_fast.py` (`ffcdbac`), with its cache built from
  `base.in_sample` and `base.members` (82,240 members, signed, depth ≤ 3). Positions
  are the kernel's: `pos_t(m) = D_t w_m / g_t(m)`, where `D_t` is X_t demeaned across
  the 40 names. **Positions depend on X alone**, so they are the same for every seed
  and level. The script asserts that every rebuilt panel's features equal the base's.
- **Feature indexing.** Every support is in the true (unmasked) indexing. For agent
  runs this is `planted_truth.submitted_support_true`.
- **Truth** is `SR_pop`, each member's in-sample population Sharpe:
  - from `pp.population_from_moments`, using the moments of the kernel's overlap pass
    (`E[a]`, `E[a²]`, `E[ak]`, as in `class_pass_levels`) and `pp.invariants_for(base)`;
  - **checked** against the stored values: stage 1's searcher `truth.in_sample` and
    `pop_best_sr`, and the agents' `submitted_truth.in_sample` and `pop_best_sr`. The
    largest absolute difference is printed. Above 1e-8 the script stops.
- **m+** is the recomputed argmax of `SR_pop`, checked against the stored `pop_best`.
  **m\*** is the stored `planted`.
- **Weight path:** a member's `pos` array over the 3,019 in-sample days and 40 assets.
  - **Correlation** between two weight paths is the Pearson correlation over the pooled
    3,019 × 40 entries.
  - Every day's positions sum to zero across assets, so the pooled mean is 0 and the
    correlation is `Σ pa·pb / sqrt(Σ pa² · Σ pb²)`. The script asserts the zero mean.
  - It is computed through `Q_t = D_t' D_t`.
- **Quartiles:** the 25th, 50th and 75th percentiles (numpy, linear), always printed with
  n. Rows are per arm (agents) or per source (stage 1: extend-while-improving, class
  argmax), and per level.
- **Level 0.** Every member's `SR_pop` is negative there (stage 1's read), so ratios to
  `SR_pop(m+)` change sign. They are printed, labelled "level 0: m+ negative, ratio not
  a capture".
- **Agent rows:** runs with a submission. Runs without one are counted and excluded.

### A — Recovery

- **A1.** `capture(x) = SR_pop(x) / SR_pop(m+)` for x = submission, realized class
  argmax, and m\*.
  - Agents: the submission per run. Argmax and m\* once per (seed, level) panel.
  - Agent rows are split by the stored, registered
    `submitted_recovery.two_of_three_pop_best` (hit or miss).
- **A2.**
  - **Shared signed features:** the number of (index, sign) pairs common to the
    submission and the reference (m\* or m+), from 0 to 3.
  - **The table:** for each source and level, against each reference, rows 0–3, each
    row giving n and the quartiles of the weight-path correlation.
- **A3.**
  - **The 40 × 40 matrix:** weight-path correlations of the single-feature members
    `((k, +1.0),)`. It is panel-independent.
  - **Families:** the connected components of the graph with an edge wherever
    `|corr| ≥ τ` (single linkage), for τ = 0.7, 0.8 and 0.9. **τ = 0.8 is the
    primary.** The families are printed at each τ.
  - **Signed match:** a submission feature (k, s) matches an m\* feature (j, t) iff k
    and j share a family and `s·t·sign(corr(k, j)) > 0`. When k = j this means s = t.
    Within a single-linkage family, `corr(k, j)` may be below τ; its sign is used
    regardless.
  - **Family-level recovery:** the maximum matching of distinct submission features to
    distinct m\* features is at least 2.
  - **Printed beside the registered** `two_of_three` (against m\*) for every source and
    level, at each τ.

### B — Identifiability

- **B1.** Per (seed, level) panel:
  - `S_δ = {m : SR_pop(m) ≥ SR_pop(m+) − δ}` for δ = 0.05, 0.10 and 0.20;
  - `R_ρ = {m : corr(path m, path m+) ≥ ρ}` for ρ = 0.9 and 0.8.

  Each set includes m+ itself. For each set the script prints:
  - the quartiles of its size over panels;
  - the share of panels with m\* in it;
  - per source or arm, the share of submissions in it.

  The panels are stage 1's 200 seeds at four levels, and the 20 agent seeds at levels
  0, 1.0 and 1.5. The arms share panels.
- **B2.**
  - **noise** = `SR_pop(m+) − SR_pop(realized argmax)`;
  - **search** = `SR_pop(realized argmax) − SR_pop(submission)`.

  Printed as quartiles, mean and n, per source or arm and level.

### C — Rule 4

- **C1.** μ is the agent's stated mean (`prediction.mean`). S is the submission's
  in-sample realized score (`submitted_sharpe`). Per arm, pooled and per level, the
  script prints:
  - n and the quartiles of μ/S;
  - the least-squares line μ = a + b·S;
  - the least-squares slope of μ on truth, `SR_pop(submission)`.
- **C2.** The estimates, each scored against truth and against the holdout `SR_pop`
  (stored `truth.holdout`, or `submitted_truth.holdout`).
  - **Error** = estimate − target. The script prints the bias (the mean error), MAE,
    RMSE, n and the quartiles of the error.
  - **E0** = S.
  - **E2** = S − the mean of the class null, where the class null is the replicates of
    the class maximum `M_b` and its mean is stored as `null_max_mean`: in `class_p` for
    agents, and per level for V2. **Exact, stored.**
  - **E1** = S − the mean of the replay null, approximated from the stored curve:
    - **What is stored.** For each grid point s_k (−1.00 to 3.00 in steps of 0.05),
      `n_ge[k] = #{N_b ≥ S − s_k}`. V2 stores this directly as `conf_replay.n_ge`.
      Agents store `verdict.confidence.curve`, and the script recovers
      `n_ge = round((1 − C)(B + 1) − 1)`.
    - **The mean.** Replicates between consecutive points x_k = S − s_k are placed at
      the midpoint, which costs at most 0.025 each. Those at or above S + 1 are placed
      at S + 1, and those below S − 3 at S − 3.
    - **Reported with it:** the number of runs with any mass at either end of the grid.
  - **E1's subset.** "A full replay exists" means the verdict carries replay-tier
    confidence. This is the stage-2 reader's replay subset for agents, and every row
    for V2. On that subset, E0 is printed alongside for comparison.
  - **E3** = μ, on agents only.
  - **Where each is computed.** Agents: per arm and level. V2: per searcher and level,
    over the six searchers and 1,000 seeds.
- **C3.** CRPS, scored against truth and against the realized holdout Sharpe
  (`submitted_holdout_realized`, which equals the archive figure to 8.9e-16 by the
  addendum's comparison).
  - **Agent:** the normal(μ, σ), in closed form, with σ = `prediction.sd`. Runs with
    σ ≤ 0 are excluded and counted.
  - **Gate:** the curve read as atoms on the grid with `quixote.confidence.masses`.
    The CRPS is that of the discrete distribution: `E|X − y| − ½ E|X − X'|`.
  - **Coverage:** the class tier (`class_p.confidence.curve`) on all runs, and the
    replay tier (`verdict.confidence.curve`) on the replay subset, with the agent's
    normal also printed on that subset.
  - **Printed:** the mean CRPS, its quartiles and n, per arm and level.

### D — Rules

- **D1.** From each run's `trigger_changes` event:
  - **Move number:** `at_step`, as the harness records it.
  - **Previous setting:** the most recent setting of the same trigger kind, starting
    from `triggers_predeclared`. A kind with no previous setting is "new".
  - **Direction:** whether the parameter went up, down or stayed the same, and whether
    the action was the same or changed.
  - **Loosened** means the rule fires on fewer states: `best_so_far_above` up,
    `failures_at_least` up, or `last_gain_at_most` down. The opposite move is
    **tightened**.
  - **Printed, per arm and level:** the runs with at least one change out of the runs;
    the number of changes; the quartiles of the first change's `at_step` and of every
    change's; and the counts by (kind, direction).
- **D2.** The `stop` presentations in the log. Agreement means `answer == predicted`.
  - **Per level:** the agreement rate, presentations and decisions. The total must
    equal `fidelity_read`'s 335 of 580; the script asserts it.
  - **Disagreements, classified:**
    - **continued where the rule said stop:** predicted stop, answered continue;
    - **restarted where the rule said stop:** predicted stop, answered restart;
    - **stopped where the rule said continue:** predicted continue, answered stop;
    - every other (predicted, answer) pair, and no answer, listed as is.

### E — Conservatism of the class null (preview, no validity claim)

- **Panels:** seeds 640100–640149 at levels 0, 1.0 and 1.5.
- **Replicates:** B = 1,000, made exactly as `planted_fast.class_pass_levels` makes
  them: `select_block_length` on the panel's base feature columns, `default_rng(seed)`
  and stationary-bootstrap counts.
  - Realized Sharpe `obs` and the replicate Sharpes come from the kernel's streams.
  - They are reduced chunk by chunk, so the full replicate matrix is not stored.
- **Check first:** the same code on stage-1 seed 600000 at all four levels must
  reproduce the stored `class_max` and `null_max_mean` within 1e-9. A larger difference
  stops the script before E.
- **Standard error** of an annualised Sharpe: `SE = sqrt((1 + SR_p²/2) / T) · sqrt(ppy)`,
  with `SR_p = obs / sqrt(ppy)`, T = 3,019 and ppy the panel's periods per year. This
  is Lo (2002) under i.i.d. returns.
- **E1:** per panel, the share of the 82,240 members with `obs < −SE`, and the share
  with `obs < −2·SE`. Quartiles over the 50 panels, per level.
- **E2:** per panel:
  - `q95(max over all members of the replicate Sharpe)`;
  - `q95(max over members with obs ≥ −2·SE)`;
  - their difference;
  - the subset's size.

  Quartiles over panels, per level. **Labelled a preview with no validity claim.**

## Output

- The output is `runs/diagnostics/2026-10-06.txt`, with every table.
- A closing section gives one sentence for each of the request's four questions, each
  citing its table. It is the only interpretation, and it is labelled exploratory.
- The laptop was on battery in Low Power Mode when this was written. The run's wall
  time is recorded in the output, but it is not a cost measurement.
