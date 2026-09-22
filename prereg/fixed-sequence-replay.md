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

**4 — 2026-09-21, before the driver is written and before any draw. Null 4 is
withdrawn.**

Null 4 was "the full-class bound, priced by `garden._full_class_engine`,
independent of the search". It cannot be computed, and the reason is a property
of the searchers this experiment registered.

**`MetaAdaptive` is bounded only by `BUDGET = 12` moves**, not by any declared
class. Measured on the registered configuration (K = 40, M = 50, T = 5,000,
s0, seed 300000), the five searchers reach final support sizes of 1, 2, 3, 4 and
5. Nothing stops a support reaching 12. So the reachable set is signed subsets
up to size 12, which at K = 40 is

| class | members |
|---|---|
| `SubsetClass(max_size=3, signed=True)` | 82,240 |
| `SubsetClass(max_size=5, signed=True)` | 22,600,736 |
| **`SubsetClass(max_size=12, signed=True)`** | **28,648,668,522,528** |

The moment engine enumerates members, so cost is close to linear in class size.
Arm D priced 82,240 members at **29.4 s per draw single-core**, which puts
max_size = 12 at roughly **348 million times that — about 325 years per draw**.
At 2,000 draws it is not a question of a bigger instance.

**No registered rule reads null 4.** Rule 1 is trigger replay's size, rule 2 the
frozen-decision error, rules 3 and 4 distances among nulls 1–3. Null 4 was
context. **Rules 1–4 stand unchanged on nulls 1–3.**

**Why capping the searchers at depth 3 was rejected.** It would make every search
end at the cap rather than at its trigger, which shrinks exactly the
meta-adaptivity 7.1 exists to measure: a stop-when-cleared search that is forced
to stop at depth 3 is no longer stopping *because it cleared*. The measurement
would survive in name and lose its content.

**Licence transfer — an argument, not a measurement.** Quixote agents search
under a declared class; 7.1's searchers do not. So 7.1's conclusion has to
travel from an uncapped setting to a capped one, and the argument is:

> A capped search is the uncapped search with some moves refused. The harness
> refuses a move that would leave the class, and **a replicate refuses the same
> moves**, because membership is a function of the support and the class, not of
> the data. So the capped policy is a deterministic restriction of the uncapped
> one, applied identically in the realized run and in every replicate. Rule 1
> asks whether re-evaluating a declared trigger on a replicate keeps the
> rejection rate at or below nominal; that question is about the trigger, and
> the restriction does not touch it.

**This is reasoning, not evidence, and it is flagged as such.** It has two known
soft spots. The restriction changes *which* states a search visits, so a trigger
could fire at a different rate under the cap even though its re-evaluation is
faithful — the size could move without the mechanism failing. And the fill rule
past the realized length is greedy over the grammar, which the cap also
restricts. Neither is measured here. If 7.0 or 7.3 shows capped and uncapped
searchers behaving differently under replay, this argument is what to suspect
first.

**5 — 2026-09-21, before the driver is written and before any draw.
`MetaAdaptive` submits a support that does not match its score after a
restart; the fix, and why no null moves.**

**The defect.** `MetaAdaptive._search` keeps `best`, the best score seen, and
`support`, the support currently being extended. A restart replaces `support`
with the next anchor but deliberately keeps `best`, so that later extensions must
beat the global best. At the end, `trace.support` is the *current* support and
`trace.score` is `best`. `run()` submits that pair. After any restart that is not
followed by a new global best, the submitted weights belong to one support and
the claimed Sharpe to another.

**Measured, 2026-09-21**, on the registered data configuration (K = 40, M = 50,
T = 5,000, s0), on scratch seeds 900000–900039, outside this experiment's block:
`RestartAfterKFailures(k=2)` restarted in **21 of 40** runs, and **all 21**
submitted a support whose recomputed Sharpe differs from the claimed one. The
other four searchers never restart and are unaffected (0 of 40 each). A smaller
check (K = 10, T = 600, 60 seeds, two DGP settings) found 120 of 120 restart
runs mismatched.

**The fix.** Track `best_support` alongside `best`, updated in the same place
`best` is and only there. `trace.support` and the submission become
(`best_support`, `best`). The current support is still what the policy extends,
and each move record still carries it.

**Why no registered quantity moves, stated as a prediction and checked before
commit.** Every null, the realized score and the realized action sequence are
functions of `best` and of the path of current supports, and neither changes;
only which support is *reported* at the end changes. **Prediction:** nulls 1–3,
the realized score and the realized actions are **bit-identical** before and
after the fix for all five searchers. It is checked on saved pre-fix nulls (K =
10, T = 600, two seeds, B = 150, all five searchers), and the result is recorded
in the fix's commit. If any array differs, the fix is wrong and does not go in.

**What the fix does change:** the submitted weights of `RestartAfterKFailures`
after an unrecovered restart, and so anything graded from those weights (an
out-of-sample Sharpe, a sandbox evaluation). 7.1's rules read none of these. No
7.1 draw has been run, so nothing already reported is affected. The fix is in
`searchers/`, inside `CODE_PATHS`, so the published fingerprint moves with it.

**Test added with the fix:** for every `MetaAdaptive` subclass, the claimed score
equals the recomputed Sharpe of the submitted support, on the replay path (base
columns) exactly, and on the live path (`run()` on a sandbox) to the recorded
~1e-12 difference between the two scoring paths.

**Also recorded: the searchers' own parameters are not registered.**
`StopWhenCleared` has no default bar, and the `k` of `RestartAfterKFailures` and
the `min_gain` and `min_support` values appear only in the tests. They must be
fixed here before the driver is written, not chosen in it.

**6 — 2026-09-21, before the driver is written and before any draw. The fill is
redefined, rule 3 becomes a paired content test with a size readout, and the
searcher set and its parameters are fixed.**

*Every number below is a **design measurement, not a 7.1 draw**.* The design seed
block is 960000–960999, disjoint from the registered 300000–301999 and the
replication block 310000–311999. The configuration is the registered one (K = 40,
M = 50, T = 5,000, rho = 0, s0). `experiments/fsr_design.py` produces the numbers
and mirrors `replay_nulls`' resampling exactly. One Sharpe standard error at
T = 5,000 is se = 0.2245.

### (a) The fill, redefined

**The fill is the best one-step content move over extend, swap and flip, with
the declared triggers still evaluated at every filled step.** Past the realized
length, the replicate's own triggers decide whether it stops, restarts or
continues, exactly as in the policy. Only when they say continue is the
continuation replaced by the fill's move. This supersedes amendment 2's fill
("the best one-step move ... applied to the budget"), which never stopped.

**Why.** Under the old fill a stop searcher's replicate kept moving where the
policy would have stopped, so null 2 could only come out larger than null 3.
That forced a conservative sign, whatever the fill's content did. It masked
exactly the liberal case a stronger continuation produces, and it was a
property of the gate, not only of the measurement. With the triggers evaluated,
nulls 2 and 3 can differ **only in content**. **7.2 part two builds the fill this
way.** Rules 1, 2 and 4 read null 2 as redefined here.

**Consequence for the comparison.** The searcher's own continuation with its
triggers evaluated *is* the policy, so the content-only null 2′ is **null 3
itself**. Rule 3 compares null 2 with null 3, and the difference is the fill's
content choice and nothing else.

### (b) The structural property, and engagement as a readout

**The fill engages only on replicates that run past the realized length.** A
searcher whose realized search always runs to the budget therefore has nulls 2
and 3 equal **by construction**, whatever the fill is. **The engagement rate** —
the share of replicates in which at least one step past the realized length is
filled — **is a registered readout for every searcher**, reported beside rules 1–4
so that a null result can be told apart from a fill that never ran.

### (c) Findings on the design block, not failures

- **Restart carries no size cost for greedy content policies at K = 40.**
  `RestartAfterKFailures` (k = 2) restarted in 936 of 2,000 replicates. A
  post-restart climb beat the pre-restart best in **0 of 2,000**, and nulls 2 and 3
  differed in **0 of 2,000**. It has no stop trigger, so it runs to the budget in
  100% of null runs. Random-anchor restart does no better: 0 of 2,000
  differences at k = 1 and 2, and post-restart climbs winning in 0.75% and 0.45%.
  Adding a stop made nulls 2 and 3 separate (16–19%), but the separation was the
  stop's, not the restart's.
- **The fill's choice is immaterial for greedy continuations.** Swap's post-swap
  climb beat the earlier best in 0.45% of replicates. Under the redefined fill,
  stop-when-cleared, extend-while-improving and ClearedRestart engage on about
  24% of replicates, yet show nulls 2 and 3 identical in **0 of 2,000**, because
  the fill's best one-step move is their own.
- Both are **consistent with arm D**: sub-maximal greedy search near its class
  maximum costs almost nothing, so there is little for a replay rule to get
  wrong.

### (d) The searcher set: six

**Dropped as inert on the design block:**
- `RestartAfterKFailures`: 0 of 2,000 differences; always at budget.
- random-extend at the 3.5 se bar: engagement 0 of 2,000; always at budget.
- `SwapWorstWhileImproving`: engagement 0 of 2,000 under the redefined fill,
  because its gain trigger stops a filled replicate before any content step.

| searcher | continuation | stop trigger | engagement | nulls 2 ≠ 3 | role |
|---|---|---|---|---|---|
| `StopWhenCleared` | greedy extension | best > 3.5 se | 24.1% | 0 | rules 1, 2, 4 |
| `ExtendWhileImproving` | greedy extension | gain ≤ 0 | 24.5% | 0 | rules 1, 2, 4 |
| `ClearedRestart` | greedy extension; restart after k failures | best > 3.5 se | 24.1% | 0 | rules 1, 2, 4; the one searcher with two declared triggers |
| **`LookaheadStopWhenCleared`** | width-2 beam over extend and swap | best > 3.5 se | 24.1% | **3.8%** | rules 1–4; **predicted liberal** |
| **`RandomExtendWhileImproving`** | the next feature of a permutation fixed by the draw's seed | gain ≤ 0 | 3.9% | 3.9% | rules 1–4; **predicted conservative** |
| **`ExtendBySecondBest`** | second-best extension | gain ≤ 0 | 33.1% | 33.1% | rules 1–4; **predicted conservative** |

Engagement and divergence are from seeds 960000–960019, 100 replicates each,
under the redefined fill. **Direction on the design block:** lookahead's policy
scored higher than the fill on all 76 divergent replicates, with 13 of 13
non-zero seeds positive. Random-extend's fill scored higher on all 77 (19 of 19
seeds negative), and second-best's on all 662 (12 of 12 negative).

### (e) Parameters, registered with their reasons

Chosen on design seeds 960100–960299 (200 realized null runs per configuration),
so that each meta decision fires in a meaningful share of null runs rather than
always or never.

| parameter | value | firing on null runs | reason |
|---|---|---|---|
| budget | **12** steps | the stop searchers stop before it in 47–73% of runs | cost is linear in it |
| stop bar (`StopWhenCleared`, `ClearedRestart`, lookahead) | **3.5 se = 0.786** annualised | 73%, median at step 5 | see below |
| `ClearedRestart` k | **1** | restarts in 17.7% of replicates | at k = 2 the bar ends most searches first (15.0%) |
| `ExtendWhileImproving`, `ExtendBySecondBest`, `RandomExtendWhileImproving` min_gain | **0** | 47%, 51%, and early (median realized length 2) | 0.1 se already fires in 99% |
| lookahead beam width | **2**, over extend and swap | — | the smallest beam that can pass through a non-improving step |
| searcher seed | the draw's seed | — | used only by random-extend's permutation |

**The stop bar is a fixed Sharpe in standard-error units, not a critical value.**
A critical value at level α fires in about α of null runs by construction. 7.1
runs entirely under the null, so such a bar would almost never fire. 3.5 se is
fixed before the search, depends on no statistic of the draw, and means the same
thing if T changes.

**Seed blocks.** Design: 960000–960999, used. **Smoke and scaling curve:
970000–970999**, reports printing no rule quantities (`prereg/README.md`).
Registered 300000–301999 and replication 310000–311999, unchanged.

### (f) Rule 3, replaced: null 2 against null 3, a sign test with a tie rule

Read on **lookahead (predicted liberal), random-extend (predicted conservative)
and second-best (predicted conservative)**. The other three are reported and
expected to read "identical".

Per searcher and per draw, the signed Kolmogorov distance between null 2 and
null 3 is computed over that draw's B replicates (positive means null 2 is
smaller, a lower bar, liberal). Then:

- **Draws with distance exactly zero are excluded**, and their share is reported.
- On the remaining draws, a **one-sided sign test at 0.005 in each direction**
  tests the share positive against one half.

Branches, per searcher:

- **Identical:** every draw is zero. The fill never engaged, and nothing is said
  about its direction.
- **Predicted direction confirmed:** the sign test rejects in the predicted
  direction.
- **Opposite direction:** it rejects against the prediction. Reported as the
  finding, and explained before 7.2 builds on the fill.
- **No direction detected:** neither. Reported as "no direction detected at this
  number of draws", which is not evidence either way.

**Standing check on this rule, per searcher** (20,000 simulated experiments of
2,000 draws each):

| fill | zero-distance share | rejects toward positive | rejects toward negative | no direction | identical |
|---|---|---|---|---|---|
| (i) exact in distribution | any, 0 to 0.99 | 0.4% | 0.3–0.5% | 99% | — |
| (ii) pointwise identical | 1.0 | — | — | — | **100%** |
| (iii) liberal, 55% of signs positive | 0 / 0.5 / 0.9 / 0.99 | 97% / 71% / 11% / 1% | 0 | the rest | — |
| (iii) liberal, 60% positive | 0 / 0.5 / 0.9 / 0.99 | ≈100% / ≈100% / 58% / 3% | 0 | the rest | — |

Lookahead runs to the budget in about 35% of draws (7 of 20 design seeds), where
it cannot engage, so its expected zero-distance share is about 0.35. The design
block's non-zero seeds were 13 of 13 positive.

**Size readout, lookahead.** Its type-I rate under null 2 and under null 3 at
α = 0.05 and 0.01, each with a Wilson interval, and its median signed distance.
Because both nulls price the same draws, **inflation** is tested as a paired
comparison: an exact one-sided McNemar test on the discordant draws (rejected
under null 2 and not null 3, against the reverse), at 0.05, per α level.

**Part-two consequence, keyed to size:**

- **Inflation not detectable** (McNemar does not reject at either level), even
  if the sign test confirms liberal: strengthening the agent-path fill is
  **optional**. The known liberal direction and the upper end of the inflation's
  interval are stated wherever the fill is used.
- **Inflation detectable** at either level: strengthening is **mandatory** before
  7.2 part two certifies with the fill. Either a **multi-step fill**, or pricing
  unreplayable continuations at the **local-max upper end**, or requiring the
  agent to **declare its continuation** so it replays exactly.

Rule 3's condition (ii) from amendment 3(d) is withdrawn; the size readout
replaces it.

### (g) B and cost: open

**B = [10,000 or 1,000]**, fixed in the next amendment after the scorer is
profiled. **Cost: [from the c7a scaling curve and smoke on 970000–970999].** No
7.1 draw runs until both are fixed.

**7 — 2026-09-21, before the scaling curve, the smoke and any draw. B is fixed by
a rule stated before its cost is measured.**

**The scorer.** Scoring every candidate from each replicate's mean vector and
covariance, computed once, is **9.6× faster** than summing base columns: 1,791 to
187 ms per replicate for all three nulls across the six searchers, single-core,
design seeds 960004–960005. It is held to identical actions and supports, and to
values within 1e-10 of the column path, by `tests/test_meta_adaptive.py`, at the
registered configuration on design seeds. The published fingerprint moved from
`cb0c1fed82c65939` to `d99d85c912a5d88a` (commit `a7623bd`).

**Projected at B = 10,000 and 2,000 draws: about 1,040–1,120 CPU-hours
single-core**, which is 5.5–9 hours on the c7a.48xlarge depending on contention,
and about $55–90 at $9.85/h.

**The rule, fixed now:**

- **B = 10,000** if the c7a scaling curve and smoke project the full registered
  run (2,000 draws, six searchers) at **$100 or less** at the measured contended
  rate;
- **B = 1,000** otherwise.

The threshold is set before either number exists. The smoke's projection is
recorded beside the choice.

**What B = 1,000 would change, restated so a B = 1,000 run is not read as more
than it is:**
- **Rule 1's detectable liberality is unchanged.** It depends on the number of
  draws, not B. At 2,000 draws the rule fires at k ≥ 120 (6.00%) at α = 0.05 and
  k ≥ 29 (1.45%) at α = 0.01, with 80% power against 6.44% and 1.67% (amendment 1).
- **P-value resolution** becomes 1/1,001. It still resolves α = 0.01: a draw
  rejects when at most 9 replicates reach the realized statistic. Monte Carlo
  noise in each p-value adds variance to the rejection indicators, not bias.
- **Rule 3 is coarser per draw.** Lookahead diverges on about 3.8% of
  replicates, so about 38 per engaging draw at B = 1,000 against about 380 at
  B = 10,000. The sign test's zero-distance share rises only through draws with
  no divergent replicate at all, which at that rate is rare; its standing-check
  table in amendment 6 applies with the measured share.
- **The size readout's McNemar test** is on draws, so it is unaffected except
  through the rejection indicators' Monte Carlo noise.

**Scaling curve and smoke, on the c7a, on seeds 970000–970999, printing cost
only.**
- **Scaling:** B = 500 at 1, 16, 48, 96, 144 and 192 workers, two draws per
  worker. Per-draw cost is linear in B, since replicates are independent and the
  per-draw fixed work is small, so contention measured at B = 500 transfers.
- **Smoke:** B = 10,000 at 192 workers, 192 draws, end to end, as the standing
  pre-launch rule requires.

The on-instance self-stop is installed before anything launches.
