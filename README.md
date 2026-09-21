# observable-garden

**Every backtest is the best of many tries. Nobody writes down the tries.
An agent does.**

A good backtest may only be the luckiest of a thousand attempts, and the
correction for that has always needed a number no human researcher keeps: how
hard they searched. This repo is a gate that reads the search's own log and
returns a verdict.

```
pip install -e .
garden audit --example null_grid     # FAIL          the best of nothing
garden audit --example real_edge     # PASS          survives the search that found it
garden audit --example overwide      # INADMISSIBLE  too broad to prove anything
```

Every verdict prints its bar, its power and a reason per check, so you can
argue with it. It refuses rather than flatter: **UNDECIDABLE** when the log
can't license a correction, **DEGENERATE** when the statistic breaks.

## What it has measured

- A search over 1,000 noise-heavy trials reports Sharpe **2.03**. The truth
  is **0.21**. Reading only the transcript, the gate calls the decay to
  within **0.017**.
- Let a search chase its own winners and the textbook correction fails: over
  **a third** of pure-noise searches clear a nominal 5% bar.
- Two repairs hold everywhere tested. With a searcher that reaches its
  declared class, the gate rejects **9.60 / 5.50 / 0.95%** at nominal
  10 / 5 / 1.
- Declare the tightest class your search can reach. Over-declaring took one
  searcher from nominal to **1.35%**, which is power thrown away.
- A PASS is not a promise. Reverse the true signal and its advantage erodes
  from **+0.46** to **+0.08**. It never inverts.

## Next: a gate for agents that think

*In build. Pre-registered before it runs. Nothing in this section is a
result yet.*

An agent doesn't search a fixed menu. It decides what to try next. The new
gate prices the decisions, not just the trials:

- **Replays what can be replayed.** Moves are typed and harness-executed, so
  each resample re-runs the agent's rules and lets them choose differently.
- **Charges for what can't.** A decision with no stated rule is priced at the
  best of its alternatives. Ambiguity costs power, never validity.
- **Reports its own doubt.** When the verdict turns on a judgment call, it
  says so and names the call.
- **Twins.** The same agent, re-run on placebo copies of the data where the
  null is true. The real run's rank among them is the p-value, whatever the
  log missed.

Design, rules and gates: `ROADMAP.md`, Phase 7.

## Prior work

The engine is White's Reality Check (2000). It is twenty-six years old and
it is the right tool. This project asks what a logged search lets you do with
it. `SCOPE.md` has every number and caveat, `THEORY.md` the proofs, and
`EXPERIMENTS.md` the commit each pre-registration was fixed at.
