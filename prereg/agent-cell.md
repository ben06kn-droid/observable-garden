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
- **On a real panel, as a fixed menu.** The block bootstrap resamples **streams
  in time**, so `X` moves with the replicate and is *not* held fixed; an earlier
  draft of this paragraph said it was, and that was wrong. The correct statement
  is that the menu is **computed once from the realized `X`, and is constant
  across replicates — never recomputed inside one.** That is exactly the
  fixed-menu case White's theorem covers, and it is what obliviousness is for:
  what it forbids is a menu that adapts to the realized returns, and `T(X)`
  cannot, because it never sees one.

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
2. **Per-feature excess kurtosis**, pooled, 2dp.
3. **Per-feature autocorrelation at lags 1 and 5**, 2dp.
4. **Per-feature turnover of a unit position path**, `mean |x_t - x_{t-1}|`,
   because costs are charged on turnover and turnover is an X-only quantity.

**Excluded, by name:** feature means signed against anything; a Sharpe of any
kind; IC; correlation with returns; spread or cost levels, which are
price-derived; dates.

**Recorded:** the delivered table is hashed per run and the hash is stored in the
run config, so what an agent was shown is fixed and checkable afterwards.

**Why the fourth moment and not the second.** Both panels z-score
cross-sectionally, which **pins the first two moments by construction**: a
cross-sectional sd line would read 1.00 for every feature and a mean line 0.00,
so neither carries information about anything. The fourth is the first that
survives the construction and distinguishes features.

**The rank features' value, computed rather than approximated.**
`environments/real_panel._rank` maps each period's ranks to `N` **equally spaced
points** on [−1, 1], so a rank feature is a **discrete** uniform on the names
present, not a continuous one. The discrete uniform on `N` points has excess
kurtosis

    −(6/5)·(N² + 1)/(N² − 1)

which at the ETF panel's **N = 40** names is **−1.2015** (the continuous limit
−6/5 = −1.20 is the `N → ∞` case, and at `N = 2` the same formula gives −2, the
Bernoulli value). The table's 2dp rounding therefore **delivers −1.20**, and the
underlying construction value is −1.2015. Checked numerically against the actual
mapping in `tests/test_orientation.py`.

Either way the number is a fact about the feature's *form*, not about the data,
and is read as such. A period with fewer names present has a slightly different
`N`, so a rank feature's pooled value can sit a little off −1.2015 without that
meaning anything either.

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
information**. Every correlation is below the threshold, the features are
exchangeable so their kurtoses and turnovers are equal in expectation, and
autocorrelations are zero in expectation. Whatever the table says there, it says
about noise.

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


## Amendments

**1 — 2026-09-25, before anything is live. Excess kurtosis replaces the
volatility line.**

Item 2 of the table was per-feature cross-sectional volatility. On a panel whose
features are cross-sectionally z-scored that is 1.00 for every feature **by
construction**: the first two moments are pinned, so the line cost tokens and
said nothing. It is replaced by **per-feature excess kurtosis at 2dp, pooled**,
the fourth moment being the first that survives the construction.

Registered with it, so the number is not over-read when it appears: on the ETF
panel the **rank features sit at −1.2015**, because `_rank` maps a period's ranks
to `N` equally spaced points, making a rank feature a **discrete** uniform on the
names present, whose excess kurtosis is `−(6/5)(N² + 1)/(N² − 1)` — −1.2015 at
`N = 40`, delivered as −1.20 after the table's 2dp rounding. The continuous
uniform's −6/5 is the `N → ∞` limit and is not the panel's value. That is a fact
about the feature's form, not about the panel.

The builder's signature is unchanged — `orientation_table(X, labels, seed)` —
and the poisoned-sentinel test stands unchanged with it.

**2 — 2026-09-25, before anything is live. Why the threshold check is scoped,
stated as structure rather than convenience.**

`tests/test_agent_prompts_real.py` forbids the literal strings `0.05`, `0.04`
and `0.01` in any prompt, so that no certifier's decision boundary is stated to
an agent. A two-decimal feature statistic can contain those characters, so the
bare-number half of that check is applied to the prompt **minus the delivered
table**.

The reason is structural. **`orientation_table(X, labels, seed)` has no alpha
and no threshold among its inputs**, so the table cannot carry one; an
autocorrelation of 0.01 in it is arithmetic about a feature.
`tests/test_orientation.py` asserts that signature directly, rejecting `alpha`,
`threshold` and `critical_value` as keyword arguments. What the numeric check
guards is therefore **authored text**, which is where a threshold could be
written down by hand, and the word half — "alpha", "critical value", "p-value" —
still applies to the whole prompt, because no table has a reason to say those.

`CORR_THRESHOLD = 0.5` is the format's own cutoff for which pairs are worth
listing: a module constant, identical on every panel, deciding nothing about any
specification.

**3 — 2026-09-25, before anything is live. The conditional validity claim is
corrected.**

The draft said the gate's nulls "hold `X` fixed and resample the return-driven
part". **That is wrong.** The block bootstrap resamples streams in time, and `X`
moves with the replicate.

The claim that is actually true, and sufficient: the menu is **computed once from
the realized `X` and is constant across replicates, never recomputed inside
one** — the fixed-menu case. Obliviousness forbids a menu that adapts to the
realized returns; a menu fixed before any resampling does not adapt to anything.
The `s0` statement is unchanged, since there `X` and returns are independent by
construction and the menu is oblivious unconditionally.

Corrected in this file and in `quixote/orientation.py`'s own statement of the
argument, which carried the same wording.

**2 — 2026-09-27, before anything is live. The calibration and fidelity
measurements, from ROADMAP 7.3's checks 1 and 2.**

The draft registered the orientation arm and deferred the rest of the agent cell
to this amendment. It is written now so the registration is **complete before the
seat window opens**, not during it.

### Check 1 — calibration

**Design.** Each **s0** run's submitted Sharpe is placed within **its own replay
null**: the position is the certifying null's p-value for that run. If the gate
reproduces what the agent does on noise, those positions are uniform — `e1`,
applied to agent plus gate together rather than to either alone.

**Readouts.** KS against U(0,1), and the type-I rate at α = 0.05 and 0.01. **Per
decision kind**, the fraction of runs whose p-value falls in the lowest decile,
because skew toward small p means a decision kind is leaking and the per-kind
fractions say which.

**Rule (validity, one-sided).** Fails high **iff the lower end of the Wilson 95%
interval for the type-I rate exceeds nominal**.

**What n buys, stated before the run.** At **n = 80** this detects a true rate
near **13%** or worse. It **rules out gross leakage and no more**, and the
scripted arms of `prereg/unfaithful-searchers.md` carry the calibration claim.
A pass is not a calibration result and the write-up says so.

- *Holds:* no gross leakage, and the per-kind fractions are reported flat.
- *Fails high:* the per-kind fractions name the suspect kind, and **no
  behavioural readout from the cell is reported as a finding** until it is
  understood — the same order the orientation arm's rule uses.
- *KS rejects with the rate inside its interval:* reported as a shape departure
  with the ECDF, not as a size failure, exactly as 6.3 handled its one KS
  rejection.

### Check 2 — fidelity

**Design.** For a **pre-registered subsample — 10 runs per config, every `pick`
and every meta move** — re-present that single decision to the agent about **20
times with resampled numbers in context**, and record how often **the declared
rule predicts the choice**. Reported as a **rate by move type**.

**It runs on the reasoned-pick arm.** A fidelity rate has no unit of analysis
without picks, and the pilot recorded **0 picks in 5 runs** when picks were merely
permitted (`prereg/agent-pilot.md`). Amendment 3 of
`prereg/AGENT_PROMPTS_REAL.md` registers the arm that asks for one. **A fidelity
readout taken from any other arm has to say why**, and that conditional carries
into 7.4.

**Tolerance, fixed now: 0.80.** A move type whose measured fidelity rate falls
**below 0.80** is **priced locally in the certifying null from then on**
(`quixote/pricing.py`'s fidelity-driven pricing, which exists behind a flag that
defaults to off). The tolerance is registered here rather than chosen after
seeing the rates.

- *Every kind at or above 0.80:* no kind is priced locally, and the flag stays
  off. The local-max conjecture is then **untested by this cell**, which is
  stated rather than read as support.
- *A kind below 0.80:* that kind is priced locally, and the verdict says which
  kinds were priced and why. **Local pricing being liberal anywhere** drops the
  run to the class tier instead, as ROADMAP 7.3 already requires.
- *A kind with too few instances to estimate:* reported as unmeasured with its
  count, never as passing.

**Prior art, to be searched before claiming the measurement.** Turpin et al.
(2023) and the chain-of-thought faithfulness literature are the neighbours.
**They are to be verified before citing** — neither has been read against this
design yet, and that is recorded here so the write-up cannot quietly assume it.

### What these two license

**7.3 licenses `p_upper` and the two pricing flags.** Nothing switches a flag on
before this cell reports: `quixote/pricing.py`'s local-max and fidelity-driven
pricing both default to off, and a verdict that used either says it is unlicensed
and names what would license it. Check 2 is what licenses the fidelity-driven
one; the local-max conjecture is 7.3's scripted half.

### Checks 3 and 4

ROADMAP 7.3's **behaviour** and **power** checks are descriptive and gate nothing:
share of moves by kind; how often `pick_prior` is used and refused; triggers
declared against filled; predictions made before the first look; and the
CERTIFIED rate on s3 against the class gate's PASS rate on the same runs. The
three readouts registered on 2026-09-25 — **trigger changes, `trigger_is_firing`
refusals, and engagement, per run** — join check 3.

**Power is reported at matched ACTUAL size**, not at nominal, for the reason
`gate-comparison` fixed: at nominal α the class gate's unused size reads as a
power deficit. 7.0 measured replay and class as **indistinguishable at matched
actual size** (+0.0003, straddling zero), so a difference here would be a fact
about the agent, not about the certifiers.