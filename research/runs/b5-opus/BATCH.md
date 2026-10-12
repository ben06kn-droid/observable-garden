# b5-opus

Amendments 11 and 12: s3 at the recalibrated σ=194.407, Opus. Seeds 581–660.
Amendment 12 also allocated a Fable arm on these seeds; it was aborted, so this
batch is Opus alone.

- **Runs**: 80, seeds 581–660 · **Cells**: 2 · **Cost**: $33.74
- Schedule: `experiments/schedule_80_s3_opus.txt`

| cell | n | evaluations | stated mean | deflation gap | realized OOS | verdicts |
|---|---|---|---|---|---|---|
| s3 control opus | 40 | 93.0 | 0.85 | 0.590 | 0.456 | 26 PASS, 14 FAIL |
| s3 gate opus | 40 | 81.0 | 0.85 | 0.538 | 0.883 | 25 PASS, 15 FAIL |

## What it showed

**The gate moves search effort in opposite directions for different models.**
Opus searched *less* when shown the bar — 81 evaluations against 93 — where
Sonnet on the same task searched substantially more (115.5 against 76, b4). Same
intervention, same data, opposite sign. Any claim that the gate makes agents
search harder is a claim about a particular model.

**Opus states a much higher belief than Sonnet and is further from
calibrated.** 0.85 in both arms against Sonnet's 0.625 and 0.65, with a
deflation gap of 0.538–0.590 against Sonnet's 0.345–0.366. It also does not move
its stated belief at all between arms, to two decimals.

PASS rates are 65% and 62.5%, close to Sonnet's on the same task and well above
the 46% preflight power, for the same reason (see `b4-s3-recal/BATCH.md`).
Seeds are disjoint from b4's, so the between-model comparison is unpaired.
