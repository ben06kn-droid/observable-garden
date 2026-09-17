# `garden watch` — build plan

**What it is.** A wrapper on `Sandbox` that gives a searcher a running view of
where it stands against a search-adjusted bar, and runs the audit at submit
time. The agent-facing form of the gate, and the gate-in-the-loop arm of the
agent experiment.

**The constraint it is built around.** Any feedback watch gives makes the
next candidate depend on realized results, so the menu is adaptive by
construction and the realized-menu tier is unavailable to a watched search.
Watch therefore runs in the declared-class tier: the searcher declares Θ
before it sees anything, the null is the maximum over Θ, and the bar is
fixed from that moment (P3/Prop. 6). Nothing the searcher does inside Θ
moves the bar. What watch adds is enforcement, standing, diagnostics, and a
verdict at submit — not a per-query price. The lever that changes power is
class size at declaration, which is `preflight`.

Dependence on open experiments: none in design. E21 confirms the estimator
the class null rests on; E22 measures the conservatism watch will report.

---

## 0. Contract (½ day)

```
w = watch.open(base_returns, spec_class, alpha=0.05, ref_sharpe=1.0,
               periods_per_year=252)
    -> WatchState: bar (null-max distribution over Θ), power at ref_sharpe,
       class size, verdict_at_open ∈ {OK, INADMISSIBLE}

r = w.evaluate(spec)
    -> WatchReport: in_class (bool), sr_is, best_so_far, margin_to_bar,
       cleared (bool), n_evaluated, n_class, diagnostics {...}
       Refuses (or marks the run as off-tier) if spec ∉ Θ.

v = w.submit(spec, predicted_oos)
    -> Verdict (existing audit object), plus the watch log.
```

Three invariants, tested:
1. `evaluate` never touches out-of-sample data.
2. The bar watch reports equals `audit`'s full-class null on the same inputs.
3. `cleared` at any step equals the final verdict's PASS for that spec.

## 1. Core (2 days)

`garden/watch.py`. Reuse `_full_class_engine.full_class_null_max` (already
moment-based, scales to 10⁶ members), `preflight` for power at open,
`audit` at submit. New code is state, membership checking against
`SubsetClass` / `ExplicitClass`, and the report objects. JSON output for
every report so an agent tool can consume it.

Verdict at open: if power at `ref_sharpe` is below the floor, return
INADMISSIBLE *before any evaluation* with the smallest class size that would
clear the floor. This is the moment the design is still changeable.

Tests: the three invariants; membership rejection; a scripted Greedy under
watch reproduces the unwatched Greedy's verdict exactly.

## 2. Diagnostics (1 day) — informational, never the verdict

- **Shadow realized-menu p-value** on the evaluated columns so far, labeled
  as what the naive test would say. Its divergence from the class bar is the
  liberal error of §4 made visible in real time.
- **Anchoring coupling.** Per step, how strongly the new candidate tracks
  the current best (the κ statistic from E17). Reported as a drift warning:
  the search is winner-chasing, and the shadow p-value is turning liberal.
- **Latent-forking counter.** A hook for agents that emit reasoning traces:
  candidates named but never evaluated, so considered/evaluated is logged
  per run (plan §5.5). Irrelevant to validity under the declared tier; the
  number is the point.

## 3. Class ladder (1 day, optional)

Nested classes Θ₁ ⊂ Θ₂ ⊂ … declared up front, with a pre-registered rule
for moving up. The bar is priced at the union; standing is reported per
level. The benefit is computational, not statistical — a searcher can work
a small class first without changing what it is being held to. Any
expansion not on the declared ladder drops the run to UNDECIDABLE and says
so.

## 4. Agent binding (1–2 days)

Tool schema for an LLM: `evaluate`, `status`, `submit`. The declared class is
fixed by run config and opened by the harness; it is not an agent tool.
`status` returns the current WatchReport. Pre-register the system prompt at
the same time (plan §5.2); the control arm sees the same tools minus
`status`. This is `searchers/llm_agent.py` plus the arm-3 wiring; no
sandbox changes.

## 5. Validation (1 day)

- Scripted searchers under watch, `s = 0`: submit-verdict type-I at or below
  nominal for every class size run.
- Scripted searchers under watch, `s = 3`: realized power equals the
  `preflight` number at open, within Monte Carlo error.
- Five-run LLM pilot, `s = 0`: the deflation gap is measurable and the
  `status` tool is actually called.

Total ≈ 6–8 days. Gates: §1 invariants before §2; §5 first two bullets
before the pilot.

---

## Non-goals, stated in the docstring

- No realized-menu verdicts for a watched search, ever.
- No recursive tier unless the searcher is scripted and re-executable; then
  watch may offer it at submit as a second verdict, labeled.
- No claim about costs, regime change, or look-ahead in the features.
- Not a Thresholdout. A noisy reusable holdout for an exploration phase is a
  different estimator with different guarantees; if wanted, it is a separate
  module feeding a declared class for a certified second stage.

## What E22 changes

Only the expectation. If the declared tier's power at agent-scale classes
is small, watch is still correct and will say INADMISSIBLE at open for most
realistic searches. The `s = 0` arm is unaffected, which is why it is
primary.
