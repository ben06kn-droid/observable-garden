# b1-baseline

The original s0 control/gate arm, Sonnet, run before the model tag existed —
which is why these directory names carry no model and the loader treats the tag
as optional.

- **Runs**: 80, seeds 0–79 · **Cells**: 2 · **Cost**: $19.05
- Pure noise (`s=0`), so every PASS is a type-I error.

| cell | n | evaluations | stated mean | deflation gap | verdicts |
|---|---|---|---|---|---|
| s0 control sonnet | 40 | 81.0 | 0.45 | 0.453 | 39 FAIL, 1 PASS |
| s0 gate sonnet | 40 | 137.0 | 0.35 | 0.382 | 36 FAIL, 4 PASS |

## What it showed

Five PASSes in 80 searches over data with nothing in it — consistent with a
nominal 5% bar, and the first evidence that the declared-class tier holds when
the searcher is an agent rather than a script.

The two arms differ in what the agent *did*, not in what it believed. Showing
the agent its standing against the bar raised the median evaluation count from
81 to 137, and moved stated confidence from 0.45 to 0.35 — a shift small beside
the gap between either number and the deflated Sharpe, which is what the gate
says those searches were actually worth. Both arms state a belief far above what
their own search supports.
