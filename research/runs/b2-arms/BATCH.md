# b2-arms

Amendment 4: the count and budget arms, and the first s3 cells. Seeds 80–319,
plus seed 500, which replaced the voided seed 89 — which is why this batch holds
241 runs rather than 240.

- **Runs**: 241, seeds 80–500 · **Cells**: 8 · **Cost**: $43.74
- Schedule: `experiments/schedule_240.txt`

| cell | n | evaluations | stated mean | deflation gap | verdicts |
|---|---|---|---|---|---|
| s0 budget20 sonnet | 21 | 19.0 | 0.35 | 0.586 | 20 FAIL, 1 void |
| s0 budget60 sonnet | 20 | 55.0 | 0.40 | 0.396 | 19 FAIL, 1 PASS |
| s0 budget180 sonnet | 20 | 98.5 | 0.41 | 0.460 | 20 FAIL |
| s0 control sonnet | 30 | 84.0 | 0.45 | 0.477 | 29 FAIL, 1 PASS |
| s0 count sonnet | 40 | 97.5 | 0.45 | 0.495 | 38 FAIL, 1 PASS, 1 no_submit |
| s0 gate sonnet | 30 | 156.0 | 0.35 | 0.392 | 29 FAIL, 1 PASS |
| s3 control sonnet σ1 | 40 | 79.0 | 0.40 | 0.471 | 31 FAIL, 9 PASS |
| s3 gate sonnet σ1 | 40 | 73.5 | 0.475 | 0.329 | 21 FAIL, 19 PASS |

## What it showed

**Telling an agent its trial count does nothing.** The count arm ends its every
`evaluate` result with the running total; its stated mean is 0.45, identical to
the control's, on a median of 97.5 evaluations against 84. The information is in
front of the agent and does not reach its belief.

**Assigning the count does not help either.** The budget arm caps evaluations at
20, 60 and 180, and the cap binds — medians of 19, 55 and 98.5. Stated
confidence across a ninefold change in search breadth moves from 0.35 to 0.41,
in the wrong direction and by far less than the breadth warrants.

The s3 cells here ran at σ=1, a calibration amendment 9 later replaced; they are
never pooled with b4's or b5's s3 runs. Their PASS rates (9/40 control, 19/40
gate) belong to that calibration alone.
