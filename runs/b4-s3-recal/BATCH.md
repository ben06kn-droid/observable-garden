# b4-s3-recal

Amendment 9: s3 re-run at the recalibrated σ=194.407, Sonnet. Seeds 501–580.

- **Runs**: 80, seeds 501–580 · **Cells**: 2 · **Cost**: $15.26
- Schedule: `experiments/schedule_80_s3.txt`
- A real edge is present, so a PASS is the correct outcome, not an error.

| cell | n | evaluations | stated mean | deflation gap | realized OOS | verdicts |
|---|---|---|---|---|---|---|
| s3 control sonnet | 40 | 76.0 | 0.625 | 0.345 | 0.602 | 28 PASS, 12 FAIL |
| s3 gate sonnet | 40 | 115.5 | 0.65 | 0.366 | 0.508 | 24 PASS, 15 FAIL, 1 no_submit |

## What it showed

**The gate certifies a real edge more often than a single pre-specified strategy
could.** 70% and 60% PASS against a preflight power of 46% at the reference
Sharpe. That is not the gate being liberal: a searcher that can find the edge
submits the best of its neighbourhood, so the specification it reports carries
more than the reference strategy does. The s0 batches are the control that makes
this readable — the same machinery passes 5% of searches when there is nothing
to find.

**Seeing the bar again buys more searching and not better outcomes.** The gate
arm ran a median 115.5 evaluations against the control's 76, stated essentially
the same belief (0.65 against 0.625), and realized a *lower* median
out-of-sample Sharpe (0.508 against 0.602). Neither difference in PASS rate is
significant at this n.

These runs share no seeds with b5, so the Sonnet/Opus comparison across them is
unpaired. They are never pooled with b2's s3 cells, which ran at σ=1.
