# costs-and-regime-change: what does a PASS survive?

To be committed before running. Code: `experiments/costs_and_regime_change.py`.

## Question

The gate corrects for search breadth and nothing else. Its own verdict string
says so: "Trading costs, regime change and look-ahead bias are not checked." A
practitioner's question is what a PASS is worth once those are priced, and the
honest answer is currently a sentence rather than a number.

Both are answerable offline, with no new runs and no model calls, because a
submitted specification plus its DGP seed reproduces the position path exactly
(`tests/test_oos_regrade.py` holds this to floating point).

## Design

**Population.** The 160 s3 runs at sigma = 194.407: `b4-s3-recal` (Sonnet, 80)
and `b5-opus` (Opus, 80). `b2-arms`'s 80 s3 runs are at sigma = 1, a different
calibration that amendment 9 forbids pooling, and are excluded. One `b4` run is
`no_submit` and carries no specification; it enters every n and no statistic.

**Reconstruction.** For each run: weights from `submitted_features` and
`submitted_signs`, panel from `DGPConfig(..., sigma, seed=dgp_seeds()[seed_index])`,
positions `p = x_oos @ w`, portfolio return `R_t = mean_i(p_{t,i} r_{t,i})`. The
recomputed gross Sharpe must equal the stored `oos` to within 1e-9 relative for
every run before any of what follows is computed; a mismatch on any run halts
the experiment rather than being dropped.

**Cost model, fixed now.** Positions are weights of ±1 on at most three
standardized features, so their scale is arbitrary and a per-unit cost charged
against them would be meaningless. The whole path is therefore scaled by the
single constant that sets `mean_t mean_i |p_{t,i}| = 1` — a unit-gross,
dollar-neutral convention. Scaling a position path does not change its gross
Sharpe, so this fixes the cost's interpretation without moving the quantity
being corrected.

Turnover is `u_t = mean_i |p_{t,i} - p_{t-1,i}|`, and the net return is
`R_t - c u_t` at **c ∈ {5, 10, 20} bps**. The first period carries no turnover
charge.

**Regime shifts.** Three counterfactual out-of-sample panels per run, each
regenerated from the same seed with one field of `DGPConfig` changed, so the
feature draws are identical and only the return process moves:

- **(a)** one true beta halved;
- **(b)** one true beta sign-flipped;
- **(c)** sigma doubled.

The submission is held fixed: the agent searched the real in-sample data, and
only its grading changes. Which beta is altered is the first index of
`true_signal_set`, recorded, not chosen after seeing results.

## Readouts, all pre-registered

1. Median gross and net OOS Sharpe by verdict (PASS, FAIL) at each cost, per
   model and pooled.
2. The fraction of PASS runs whose net OOS Sharpe stays above 0, and above 0.5,
   at each cost. The same for FAIL runs.
3. The same table under each regime shift, at 10 bps.
4. The PASS − FAIL gap in net OOS Sharpe, at each cost and under each shift.

## Decision rules

This experiment measures rather than tests, so it has one directional rule and
one falsifier, both fixed now so the table cannot be read selectively afterwards.

1. **The gate's discrimination survives realistic costs.** The PASS − FAIL gap in
   median net OOS Sharpe is positive at 5 and 10 bps, by a one-sided
   Mann-Whitney test at p < 0.05, in the pooled population.
   - **Holds:** the limitations section reports the gap and its decay with cost.
   - **Fails at 10 bps:** a material limitation, and the paper says plainly that
     the gate's advantage does not survive costs at that level. This is a
     reportable result, not a defect to be tuned away; no cost model will be
     changed after seeing it.
2. **PASS is expected to lose predictive value under each shift, not to
   invert.** A PASS − FAIL gap that goes significantly *negative* under any shift
   would mean the gate selects specifications that are worse than those it
   refuses once the regime moves, which nothing in the theory predicts. It would
   be investigated before it is written up.

What this cannot show: anything about real data. The shifts are synthetic
perturbations of a known process, chosen to bound the claim, not to imitate a
market.

## Cost

Free and local. 160 runs × four panels (gross plus three shifts) is 640 calls to
`generate` at M = 50, K = 40, T = 5,000, T_oos = 1,000 — about 100 MB transient
each, sequential, well inside the laptop's 8 GB. Expect tens of minutes. No
bootstraps, no model calls, no EC2.
