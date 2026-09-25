# agent-cell (7.3): what does a model do inside the gate, and does the gate still hold?

**DRAFT — committed, not live.** It authorises nothing. The scripted half of 7.3
is registered separately in `prereg/unfaithful-searchers.md`; this file is the
agent cell, and it does not depend on that one having run.

## What is here now

This draft registers the **orientation arm** in full — its design, its prompt,
its cells, its predictions and its rule — because that is the arm whose validity
argument has to be written down before anyone is tempted to run it. The rest of
the agent cell (the calibration and fidelity measurements ROADMAP 7.3 sketches)
is registered in a later amendment to this file, before it runs.

## The orientation arm

### The idea

Before its first `evaluate`, the agent is handed a summary of the **feature
panel's structure** and nothing about returns. It may spend as much context as it
likes reading it. The question is whether an agent that knows the map **searches
better** — shorter, fewer duplicates, better priors — **without the gate's
false-certification rate moving**.

### The line, which is the whole design

The orientation table `T(X)` is a function of the feature matrix `X` **alone**.
Returns, prices, and anything derived from them never enter it.

`SCOPE.md`'s obliviousness condition is the thing this buys. It asks that the
candidate menu `C(ω)` be "measurable with respect to some σ-field independent of
the return-generating randomness — which specifications get tried does not
depend, even indirectly, on the realized in-sample returns", and it says what is
allowed: "A trial count, subset sizes, and an independently-seeded PRNG are
allowed; realized Sharpe values feeding back into which columns appear next are
not."

A menu chosen as a function of `T(X)` and the agent's prior is measurable with
respect to `σ(X, prior)`. Two statements, kept apart because they are not equally
strong:

- **On `s0`, unconditionally.** Returns are independent of `X` by construction,
  so `σ(X, prior)` is independent of the return-generating randomness and the
  menu is data-oblivious in exactly SCOPE's sense. Every null the gate uses stays
  valid, for the reason SCOPE gives: "Conditional on a fixed menu, the observed
  columns are the null process evaluated at `N` fixed linear functionals."
- **On a real panel, conditionally on `X`.** The gate's nulls hold `X` fixed and
  resample the return-driven part — the base feature columns, which are
  `x · r` products. A menu measurable w.r.t. `σ(X)` is therefore **fixed across
  replicates**, which is the fixed-menu case White's theorem covers. What
  obliviousness forbids is a menu that adapts to the realized returns, and
  `T(X)` cannot: it never sees one.

**Enforced in code, not asserted in prose.** `quixote/orientation.py`'s builder
takes `X` and nothing else — there is no parameter through which a return could
arrive — and `tests/test_orientation.py` passes a returns array as a **poisoned
sentinel** that raises on any access, asserting the builder never touches it.

**Orientation consumes no evaluation budget and is not a trial.** It is delivered
in the prompt before the session opens. Nothing is evaluated to produce it; it
adds nothing to the transcript, nothing to the candidate count, and nothing to
the breadth any null is taken over.

### The table, registered exactly

Feature labels are **masked**, and the **feature order is shuffled by the masking
seed**, so a feature's position in the table carries nothing.

Contents, and only these:

1. **Pairwise feature correlations**, pooled over the panel, rounded to 2dp,
   delivered as **the list of pairs with `|corr| >= 0.5`** plus a note that every
   other pair is below 0.5. This keeps the ETF panel's z/rank near-duplicate
   pairs visible at a fraction of the tokens the full 780-pair matrix would cost.
2. **Per-feature volatility** — cross-sectional sd, pooled — 2dp.
3. **Per-feature autocorrelation at lags 1 and 5**, 2dp.
4. **Per-feature turnover of a unit position path**, `mean |x_t - x_{t-1}|`,
   because costs are charged on turnover and turnover is an X-only quantity.

**Excluded, by name:** feature means signed against anything; a Sharpe of any
kind; IC; correlation with returns; spread or cost levels, which are
price-derived; dates.

**Recorded:** the delivered table is hashed per run and the hash is stored in the
run config, so what an agent was shown is fixed and checkable afterwards.

**Noted rather than discovered later:** on a panel whose features are
cross-sectionally z-scored, item 2 is 1.00 for every feature by construction and
carries no information. It is delivered anyway, because a table that dropped a
line where it happened to be uninformative would not be the same table on every
panel.

### The prompt

The replay-gate prompt, plus **one paragraph**, registered verbatim in
`prereg/AGENT_PROMPTS_REAL.md` amendment 6. The shared text is byte-identical to
the replay-gate arm's, as §2 requires, and byte identity is a test.

## Cells and predictions

Each states both directions, per `prereg/README.md`.

### 1. 7.3 agent cell, s0 — validity

**Readout:** the false-certification rate of the orientation arm against the
replay-gate arm.

**Rule (validity, one-sided).** The orientation arm fails high **iff the lower
end of the Wilson 95% interval for its rejection rate exceeds nominal**, at
α = 0.05 and α = 0.01. At the registered **n = 20 runs per cell**, that fires
only at 3 or more rejections of 20 at α = 0.05 (15%), and the interval is wide:
**this cell can detect gross leakage and nothing finer**, which is stated here so
that a pass is not read as a calibration claim. The scripted arms carry the
calibration claim; this one rules out a hole.

- **Predicted: unchanged.** The X-only argument says the arm cannot be liberal.
- *If liberal:* **the arm is withdrawn**, and the **builder is audited for a
  returns leak before anything else is concluded** — because the argument above
  says a leak is the only way this outcome can happen. No behavioural readout
  from a liberal arm is reported as a finding.
- *If conservative:* reported, and compared with the replay-gate arm's own rate.

### 2. 7.3 agent cell, s3 at rho = 0 — the placebo

At `rho = 0` the feature covariance is the identity: **the table carries no
information**. Every correlation is below the threshold, volatilities are equal
by construction, and autocorrelations are zero in expectation.

**Predicted: no behavioural difference from the replay-gate arm.**

- *No difference:* the paragraph itself is not doing the work, and any effect
  measured on the ETF panel is attributable to the table's content.
- *A difference:* it is **priming by the paragraph, not information**, and is
  reported as such. It then **bounds how much of any ETF effect is priming**
  rather than orientation, and the ETF readout is reported net of it.

### 3. 6.5, ETF panel — behaviour, as a fourth arm

Registered in `prereg/agent-on-real-data.md` as an amendment. **Predicted: an
oriented agent**

- evaluates **fewer z/rank near-duplicate pairs** (counting a pair as hit when
  both members are evaluated),
- reaches `submit` in **fewer moves**,
- uses **`pick_prior` more**,
- **changes triggers less**,
- has **more accepted picks**.

**The failure mode is registered too:** stated confidence rises with **no change
in the deflation gap** — the agent feels it understands the data. That is the
outcome where orientation makes the agent worse calibrated while looking better
behaved, and it is named in advance so it cannot be reported as a success.

The **haircut regression** is reported for this arm beside the others.

## Size, and what gives way

**Twenty runs per cell where the window allows.** If it does not, **the
orientation arm drops before the reasoned-pick arm**: the reasoned-pick arm is
what makes 7.3's fidelity measurement possible at all
(`prereg/AGENT_PROMPTS_REAL.md` amendment 3), and a fidelity cell with no picks
measures nothing.

## What this arm cannot show

- It cannot show that orientation helps on a panel with **no edge to find**. The
  ADR panel has none (`prereg/adr-features.md` amendment 3), so the behavioural
  predictions are read on the ETF panel and the ADR panel contributes only the
  validity and placebo readings.
- It cannot separate "the agent used the table" from "the agent was primed by
  being handed something" **except** through cell 2, which is why cell 2 is
  registered as a cell rather than as a robustness check.
- At n = 20 it cannot measure a small change in the false-certification rate.
  Cell 1 rules out a hole; it does not calibrate.

## Amendments

None yet. Dated entries are appended here.
