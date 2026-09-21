# fixed-sequence-replay (7.1): what does freezing a decision cost?

**DRAFT — committed but not live.** It authorises nothing and 7.1 does not run
until it has been read. Code exists and is unit-tested
(`searchers/meta_adaptive.py`, `estimator/trigger_replay.py`,
`tests/test_meta_adaptive.py`); no sweep has been run.

## Question

The replay gate re-executes a search's typed moves on each bootstrap resample.
Its moves split in two:

- **Content choices** — which feature to extend by — are rules. They are
  functions of the sample, so a replicate re-executes them exactly.
- **Meta choices** — when to stop, when to restart, whether to move at all —
  were made *after seeing results*. Freezing them at their realized positions is
  the realized-menu error one level up (THEORY.md P4), and stop-when-cleared is
  its winner-anchored case.

How large is the error from freezing meta choices, and does declaring them as
re-evaluable **triggers** remove it?

## Design

**Searchers.** Four scripted meta-adaptive policies, each recording its move
sequence and, per move, the predicate behind the meta choice and the value that
predicate saw.

| searcher | meta trigger | continue-move |
|---|---|---|
| `StopWhenCleared` | best-so-far exceeds a bar fixed before the search | greedy extension |
| `RestartAfterKFailures` | k consecutive non-improving extensions | greedy extension |
| `ExtendWhileImproving` | last gain exceeds `min_gain` | greedy extension |
| `ExtendBySecondBest` | last gain exceeds `min_gain` | **second-best** extension |

The fourth exists for a specific reason. The fill rule below supplies greedy
extension when a replicate runs past the realized sequence. For the first three
that is also their continue-move, so the fill's *content* choice is never
exercised — they can only diverge in the meta dimension, and only when the
realized sequence is short. 7.3 cannot exercise it either, an agent having no
exact policy null to compare against. `ExtendBySecondBest` diverges on every
filled step, so the fill's content rule is tested somewhere.

**Nulls.** Four per draw. Nulls 1-3 are drawn on one shared resampled index, so
they are paired replicate by replicate and any difference between them is the
replay rule alone.

1. **fixed_sequence** — meta choices frozen at their realized positions, content
   rules re-executed. The error being measured.
2. **trigger** — each declared predicate re-evaluated on the replicate. A
   replicate whose predicate fires earlier stops there; one that would run past
   the realized sequence has no declared trigger left and is **filled with greedy
   extension to the budget**.
3. **policy** — the policy re-executed, exact because the policy is code. The
   reference.
4. **declared_class** — the full-class bound, priced by
   `garden._full_class_engine`, independent of the search.

**The realized sequence is taken on the data as they are, not demeaned.** The
sequence null 1 freezes must be the one the real search actually produced,
including a stop that fired because the real data cleared a bar. Replicates are
drawn from the demeaned columns. Taking the realized sequence from demeaned data
would freeze a sequence no search ever ran and invert the effect being measured.

**Known invariant, asserted in the unit tests, recorded here so it is not
mistaken for a result.** Nulls 2 and 3 agree step for step up to the realized
length — up to there the predicates *are* the policy — and can diverge only past
it. So a small Kolmogorov distance between them is expected and is not evidence
that trigger replay works; the informative quantity is its **sign** and the
behaviour of null 1.

**Draws.** 2,000 per searcher on seeds 300000-301999, a block used by no other
pre-registration. K = 40, M = 50, T = 5,000, rho = 0, s0 only — this experiment
is about size, not power. B = 10,000.

## Decision rules

Per `prereg/README.md`: validity claims get one-sided rules, exactness rules name
the proposition predicting them, and every rule states both directions.

1. **Trigger replay is valid (primary, one-sided).** For each of the four
   searchers, the **upper** end of the Wilson 95% interval for the rejection rate
   under null 2 does not exceed nominal by more than 0.5 points at alpha = 0.05
   or 0.2 at alpha = 0.01. Only validity is claimed, so only an excess fails;
   **conservative is acceptable**.
   - *Holds:* in-the-loop agents are certifiable with triggers declared, and 7.2
     builds the replay tier on declared triggers.
   - *Fails high:* trigger replay is liberal for that searcher. The replay tier
     requires full policy replay instead — the agent writes a policy rather than
     searching in the loop — and the searcher that broke it is named.
   - *Fails low:* conservative, reported with its size, and the power cost is
     carried into 7.0's comparison rather than treated as a defect.
2. **The frozen-decision error, measured (primary readout, no halt).** The
   rejection rate under null 1 at alpha = 0.05 and 0.01, per searcher, beside
   null 3's. Predicted direction: **liberal**, because freezing an early stop
   holds replicates to fewer moves than their own trigger would allow, making the
   null too small.
   - *Liberal as predicted:* reported as the size of the error that declaring
     triggers removes. This is the number 7.1 exists to produce.
   - *Not liberal:* the P4 argument does not bite for that searcher, which is
     reported rather than explained away; the likely cause is a realized
     sequence long enough that freezing binds on almost no replicate, and the
     realized length is reported alongside so this is checkable.
3. **Direction of the fill (secondary, no halt).** The **signed** Kolmogorov
   distance between nulls 2 and 3, per searcher, with the sign convention that
   positive means null 2 is stochastically smaller, hence a lower bar, hence
   liberal.
   - *Negative or zero:* the fill errs conservatively, which is the acceptable
     direction, and `ExtendBySecondBest` is the searcher that establishes it,
     for the reason in the Design section.
   - *Positive and material:* the conservative-fill rule is not conservative.
     This gates the replay tier's use of triggers on any search that can run past
     its realized length, and the fill rule is redesigned before 7.2 builds on
     it.
4. **Distance of null 1 from null 3 (secondary, no halt).** Unsigned Kolmogorov
   distance per searcher, reported with null 2's for contrast. Expected to be
   much the larger of the two; if it is not, freezing costs little for that
   searcher and that is reported.

## Cost

Per draw, three nulls are computed on one shared index. Each replicate runs the
search three times over K = 40 at depth up to the budget, in closed form on
resampled columns — no full-class bootstrap, which is what makes this cheaper
per draw than `calibration-at-1pct` despite re-executing the search.

**Not yet sized, and 7.1 does not launch until it is.** Per-draw cost is
dominated by B re-executions of the search and cannot be inferred from the
75.03 s/draw measured for the full-class null, which does no re-execution. The
standing pre-launch step in `ROADMAP.md`'s Compute section applies: a four-point
scaling curve at 1/4/16/32 workers and an end-to-end smoke at the worker count
the run will use. Skipping it cost `calibration-at-1pct` arm B 4.7x its estimate.

**Standing configuration:** 16 workers on the 32-core instance.

## Amendments

**1 — 2026-09-20, before the experiment runs. Rule 1's one-sided form is
corrected.**

Rule 1 above says the **upper** end of the Wilson interval must not exceed
nominal by more than 0.5 points at α = 0.05 or 0.2 at α = 0.01. Wrong, for the
reason `prereg/README.md` amendment 1 records: at n = 2,000 that passes only at
an observed rate of 4.50% or below (0.70% at α = 0.01), which an exactly valid
test manages 16.5% (10.4%) of the time, and which `calibration-at-1pct` arm D's
exactly-calibrated anchor fails at both levels.

**Rule 1 is replaced.** For each searcher, trigger replay **fails high iff the
LOWER end of the Wilson 95% interval for its null-2 rejection rate exceeds
nominal**. The **upper** end is reported as the largest liberality not ruled out.
The three outcome branches are unchanged: a pass licenses the replay tier on
declared triggers, a demonstrated excess sends the tier to full policy replay and
names the searcher that broke it, and a low rate is reported as conservatism with
its size carried into 7.0.

**Detectable liberality at n = 2,000**: the rule fires at k ≥ 120 (6.00%) at
α = 0.05 and k ≥ 29 (1.45%) at α = 0.01, giving 80% power against true rates of
**6.44%** and **1.67%**, and firing on an exactly valid procedure 2.51% and 3.36%
of the time. **7.1 cannot detect trigger replay rejecting at 5.5% against a
nominal 5%.** If the measured rate lands between nominal and the firing
threshold, the correct report is that liberality of that size was not excluded —
not that trigger replay is valid.

**2 — 2026-09-20, before the experiment runs. The fill rule is widened, and a
fifth searcher is added so rule 3 has an informative case.**

Null 2's fill was *greedy extension to the budget*. Greedy extension dominates
any other single-feature **extension**, so `ExtendBySecondBest` — whose
continuation is a weaker extension — was bound to show a conservative fill by a
near-monotone argument rather than by measurement. It says little, because the
fill was never faced with a continuation it does not dominate. 7.2's content
grammar contains `swap_worst` and `flip`, which greedy extension does **not**
dominate.

**The fill is redefined** as the best **one-step move across the whole content
grammar** — `extend`, `swap`, `flip` — applied to the budget. Supports therefore
carry signs, so `flip` is a real move rather than a no-op, and the reachable set
is the **signed** class; null 4's declared-class bound is priced over
`SubsetClass(max_size=3, signed=True)` accordingly.

**A fifth searcher is added.** `SwapWorstWhileImproving` grows to a support of
three by extension and then continues by **swapping** the worst member for the
best replacement. The fill's move dominates a swap at each single step, since
swap is in its grammar — but a search is a path and the locally best move is not
globally optimal, so the filled path can still finish below the swap path. The
direction is a genuine empirical question here, which it was not before.

| searcher | continue-move | fill dominates it? |
|---|---|---|
| `StopWhenCleared` | greedy extension | identical move; diverges only in the meta dimension |
| `RestartAfterKFailures` | greedy extension | **no** — the fill never restarts, so it cannot follow the policy's anchor change |
| `ExtendWhileImproving` | greedy extension | identical move; meta dimension only |
| `ExtendBySecondBest` | second-best extension | **yes, step by step** — the dominated case |
| `SwapWorstWhileImproving` | best swap | per step yes, along the path **no** |

**Rule 3 is replaced.** The signed Kolmogorov distance between nulls 2 and 3 is
reported for all five searchers, but the rule is **read on
`RestartAfterKFailures` and `SwapWorstWhileImproving`** — the two whose
continuation the fill does not dominate along the path.
`ExtendBySecondBest` is reported as the **dominated case** and is expected to
read conservative; a conservative reading there is not evidence about the fill,
and the pre-registration says so in advance rather than after.

- *Negative or zero on both informative searchers:* the fill errs
  conservatively, the acceptable direction.
- *Positive and material on either:* the conservative-fill rule is not
  conservative. This gates the replay tier's use of triggers for any search that
  can run past its realized length, and the fill is redesigned before 7.2 builds
  on it.
- *The two informative searchers disagree in sign:* the fill's direction depends
  on the continuation, which is itself the finding, and the replay tier is
  restricted to continuations of the kind that read conservative.

**Recorded now, from the unit tests and not from the experiment**
(`tests/test_meta_adaptive.py`, K=10, T=600, 200 replicates): under the widened
fill, `SwapWorstWhileImproving` separates nulls 2 and 3 on 65 of 200 replicates
with a signed distance of **−0.045**, and `ExtendBySecondBest` on 107 of 200 at
**−0.115**. Both conservative, the dominated case by the larger margin, as the
argument above predicts. This is a single small fixture, not the experiment, and
is stated here only so the prediction is on record before 7.1 runs.

**Cost implication.** The grammar's swap moves make a filled step O(|support| × K)
rather than O(K), so 7.1's per-draw cost rises with the budget. It remains
unsized and still gates the launch.

**3 — 2026-09-20, before the experiment runs. A replication branch for rule 1,
and a definition of "material" for rule 3.**

### (c) Rule 1's family false-alarm rate, and its replication branch

Rule 1 makes **10 one-sided checks** — five searchers × two levels. Under exact
calibration each fires at 0.0251 (α = 0.05) or 0.0336 (α = 0.01), so the family
rate is

    1 − (1 − 0.0251)^5 × (1 − 0.0336)^5 = **0.2577**

and these five searchers are **near-exact by design**: they are scripted
policies replayed by their own predicates, so null 2 differs from the exact
null 3 only past the realized length. A one-in-four chance of firing on nothing
is not acceptable when **the consequence of firing is abandoning in-the-loop
agents** — rule 1's fails-high branch sends the replay tier to full policy
replay, which means the agent must write a policy instead of searching in the
loop. That is a large architectural decision to hang on a single check.

**Replication branch.** The first failure of any rule 1 check triggers **one**
pre-registered replication of **that searcher and that level only**, on a fresh
seed block, at identical settings.

- **Replication seed block: 310000–311999**, registered now, used by no other
  experiment.
- **If the replication passes:** recorded as a family false alarm, both rates
  reported side by side, and rule 1's fails-high branch does **not** fire.
- **If the replication fails too:** confirmed, and rule 1's branch applies in
  full — the replay tier requires full policy replay and the searcher that broke
  it is named.
- **One replication per failing check**, fixed now.
- Two independent failures of an exactly-calibrated check occur with probability
  at most 0.0336² ≈ 0.0011, which is what this branch buys.

Rules 2 and 4 are unaffected: neither halts, so a false alarm in them costs a
sentence in the report rather than a decision.

### (d) Rule 3: what "positive and material" means

Undefined in the original, and fixed here before any data.

**Aggregation.** `signed_kolmogorov_distance` compares null 2 against null 3
**within one draw**, over that draw's B replicates, so the experiment yields
2,000 signed distances per searcher. They are aggregated by the **median**, and
the **share of draws with a positive distance** is reported beside it with a
Wilson interval. The median is used rather than the mean because a per-draw
Kolmogorov distance is bounded in [−1, 1] but heavily skewed toward zero, and a
few draws with short realized sequences would otherwise dominate the mean.

**"Material" is a conjunction**, so that a directional artefact too small to
change any decision cannot trigger a redesign:

> Rule 3 fires for a searcher iff **(i)** its median signed distance over the
> 2,000 draws is **positive**, and **(ii)** its null-2 rejection rate from
> rule 1 exceeds nominal in the **point estimate** at the same α.

Condition (i) says the fill's null is stochastically smaller — a lower bar.
Condition (ii) says that this actually reaches the type-I rate rather than
living in a part of the distribution no verdict depends on. Both are required
because either alone is uninformative: a positive median with the rejection rate
at or below nominal is a shift that no decision sees, and a rejection rate above
nominal with a non-positive median points at something other than the fill.

Note that (ii) is deliberately the **point estimate**, not rule 1's interval
test. Rule 1 asks whether liberality is *demonstrated*; rule 3 asks whether the
fill is the *direction of travel*, and requiring demonstrated liberality here
would make rule 3 strictly weaker than rule 1 and therefore redundant.

**Also reported, gating nothing:** the share of draws positive with its interval,
the median distance for all five searchers, and a one-sided sign test on the
share exceeding one half. At 2,000 draws the median is precisely determined, so
the sign test is a diagnostic rather than a gate — it is reported so that a
median near zero can be read as "no direction" rather than mistaken for evidence
of conservatism.

**Read on the informative searchers only**, as amendment 2 already establishes:
`RestartAfterKFailures` and `SwapWorstWhileImproving`. `ExtendBySecondBest`
reports the same quantities as the dominated case.
