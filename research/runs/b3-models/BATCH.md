# b3-models

Amendment 7: the pushed arm, and the first comparison of two models across every
arm. Seeds 320–499.

- **Runs**: 180, seeds 320–499 · **Cells**: 6 · **Cost**: $65.13
- Schedule: `experiments/schedule_180.txt` · pure noise (`s=0`)

| cell | n | evaluations | stated mean | deflation gap | verdicts |
|---|---|---|---|---|---|
| s0 control sonnet | 30 | 79.0 | 0.45 | 0.501 | 29 FAIL, 1 PASS |
| s0 gate sonnet | 30 | 125.0 | 0.35 | 0.412 | 29 FAIL, 1 PASS |
| s0 pushed sonnet | 30 | 110.5 | 0.35 | 0.361 | 29 FAIL, 1 PASS |
| s0 control fable | 30 | 45.0 | 0.11 | 0.141 | 28 FAIL, 2 PASS |
| s0 gate fable | 30 | 46.5 | 0.05 | 0.085 | 29 FAIL, 1 PASS |
| s0 pushed fable | 30 | 46.0 | 0.075 | 0.161 | 30 FAIL |

## What it showed

**The arm effect on search effort is model-specific.** Sonnet's evaluation count
moves with the arm — 79 control, 125 gate, 110.5 pushed. Fable's does not: 45,
46.5, 46.0, flat across every arm. Whatever the gate changes about how hard a
model searches, it is a property of the model, not of the intervention.

**The two models state very different beliefs about the same kind of
nothing.** Fable's stated mean is 0.05–0.11 against Sonnet's 0.35–0.45, and its
deflation gap is correspondingly smaller (0.085–0.161 against 0.361–0.501).
Fable is closer to calibrated here, but by stating low confidence generally
rather than by responding to its own search — its gap is flat across arms too.

Both models are near nominal on verdicts: 6 PASSes in 180 searches over pure
noise. The between-model comparison is exploratory under amendment 7, with no
error control.
