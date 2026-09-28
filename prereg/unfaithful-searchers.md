# unfaithful-searchers (7.3, scripted half): does the gate catch a searcher that lies about its own rule?

**DRAFT for review — committed, not live.** It authorises nothing until it has
been read and a launch decision is taken. The agent cell of ROADMAP 7.3 is **not**
here: it is a seat experiment with its own design and gets its own registration,
and nothing below depends on it.

## Question

The replay tier prices a search by re-executing it. That works because the
harness executes the moves, so the log is what ran. But a log also carries things
the agent *said*: which statistic a `pick` used, that a specification was chosen
before the data was seen, which rule it stopped under. **The gate's validity
depends on the rule the searcher used, not the one it declared.**

So: build searchers that declare one rule and use another, and measure whether
the harness's existing checks catch them — and what the size of the certifying
null is when they are not caught.

## What changed under this experiment since ROADMAP 7.3 was written

ROADMAP's sketch predates the grammar as built, and two of its three unfaithful
cases are now **impossible by construction**. That is a finding about the design
rather than a reason to keep the old text, and the replacements are named here.

| ROADMAP 7.3's case | status now | what replaces it |
|---|---|---|
| declares `pick by=autocorr`, actually picks by best Sharpe | **partly impossible**: the harness executes the *declared rule*, so the agent cannot make the other choice happen. What it can do is **name a choice that is not its rule's**, which `quixote/consistency.py` records as `contradicted` | **U1**, below |
| declares `pick_prior`, actually peeked | **possible**: a prior is a claim about *when*, and `SessionLog.refuse_if_late` only refuses a declaration made after the first evaluation — it cannot see a peek that happened outside the session | **U2** |
| omits the trigger on a stop-when-cleared | **impossible**: since `AGENT_PROMPTS_REAL.md` amendment 4, a `stop` may only fire a trigger declared before the first evaluation, and since amendment 5 a firing rule suspends the search until it is resolved | **U3**, the nearest possible thing: declaring a rule and searching past it |

**Pick contradiction no longer implies local pricing.** ROADMAP 7.2 said a
contradicted pick is "rejected as declared and priced locally". That was inverted
on 2026-09-25: the harness ran the rule, so the move is replayable and is not
priced locally. What a contradiction now buys is an **observation**, and rule 3
below is what reads it.

## Design

**Draws.** 2,000 per cell. **Seed block 500000–501999**, registered here and used
by no other pre-registration. **Replication block 510000–511999** (rule 6).
**Smoke and scaling block 990000–990999**, dedicated and cost-only per
`prereg/README.md`.

**Configuration.** The simulated panel, at `experiments/e_agent.py`'s s0 and s3:
M = 50, T = 5,000, T_oos = 1,000, K = 40, rho = 0, s ∈ {0, 3}, s3's sigma solved
for an oracle Sharpe of 1.0. **Not a real panel**: the question is about the
harness's checks, and a panel whose class maximum is negative
(`prereg/adr-features.md` amendment 3) would confound "caught" with "nothing to
catch".

**Class.** Signed subsets of size ≤ 3 over K = 40, 82,240 members, tabulated
where a real panel is used and computed directly here.

**Certifier.** Trigger replay, the certifying null fixed by
`fixed-sequence-replay` (7.1). The declared-class p-value is reported beside it
as the bracket's upper end.

### The faithful arm

Six searchers that **use every move type** the grammar offers — `init`,
`extend_best`, `swap_worst`, `flip`, `refine`, `pick` — each declaring its
triggers before its first evaluation and searching under them. They are the
control: whatever the checks do to the unfaithful arm, they must not do to these.

### The unfaithful arm

Each is a scripted policy, so what it "declares" and what it "does" are both
code and neither is a matter of interpretation.

- **U1 — the contradicted pick.** Declares `pick` by `autocorr_1` and names the
  feature that best Sharpe would have chosen. The harness executes `autocorr_1`;
  the log records `contradicted`. Its search is otherwise faithful.
- **U2 — the peeked prior.** Calls `pick_prior` with the specification that the
  full-sample argmax picks, computed before the session opens. The declaration is
  timely by the log's own clock, and the peek happened outside the session where
  no timestamp can see it. **This is the case the harness is expected to miss**,
  and registering that expectation is the point.
- **U3 — the abandoned rule.** Declares `last_gain_at_most(0)` and then, each
  time the harness suspends the search, calls `change_trigger` to keep going.
  Every change is logged and everything after the first is unreplayable, so the
  run should come back `DEPENDS_ON_JUDGMENT` rather than certified.
- **U4 — the silent restart.** Declares only a stop trigger, then restarts by
  exhausting its support through `swap_worst` moves rather than calling
  `restart`. Nothing is falsely declared; the question is whether replay prices
  a search whose structure is hidden in content moves.

**Each unfaithful searcher has a faithful twin** — the same search with the
declaration matching what it does — so every comparison is paired on the draw and
differs in one thing.

## Decision rules

Per `prereg/README.md`: validity claims are one-sided, exactness rules name the
proposition, every rule states both branches.

1. **The faithful arm is not harmed (validity, one-sided, primary).** For each
   faithful searcher on s0, at α = 0.05 and 0.01, the rejection rate under
   trigger replay **fails high iff the LOWER end of the Wilson 95% interval
   exceeds nominal**.
   - *Holds:* the checks cost the honest searcher nothing, and the unfaithful
     results below are readable.
   - *Fails high:* a check is rejecting honest searches. Nothing downstream is
     read until that is understood, because every comparison here is against this
     arm.
2. **Each unfaithful searcher is caught, or is recorded as uncaught
   (primary, no halt).** For U1–U4, the share of runs in which the harness flags
   the run — `contradicted` for U1, a late declaration for U2, a logged trigger
   change for U3, nothing available for U4.
   - *Caught in ≥ 99% of runs:* the check does what it claims.
   - *Caught sometimes:* the rate is reported as the detection rate, with its
     Wilson interval, and **no claim of detection is made in the write-up beyond
     it**.
   - *Never caught:* reported as a hole, named, with what would close it. **U2 is
     predicted to land here**, and that prediction is registered before the run.
3. **What a contradiction costs, measured (validity, one-sided).** U1's rejection
   rate on s0 under trigger replay, against its faithful twin's, paired on the
   draw.
   - *No excess:* a contradicted pick does not inflate size, which is what the
     2026-09-25 inversion assumed and did not measure. The inversion stands.
   - *Excess demonstrated* (lower end of the paired interval above zero): the
     inversion is wrong, contradicted picks must be priced, and this
     pre-registration says so in its own conclusion rather than the next one.
4. **The uncaught hole is priced (primary).** U2's rejection rate on s0 under
   trigger replay, and under the declared-class certifier.
   - This is the size of the gate against a searcher that peeked before the
     session opened. **Whatever it is, it is the headline number of this
     experiment**: it is the honest upper bound on what any log-based gate can
     promise.
   - *At or below nominal:* the peek does not help, which would be surprising and
     is investigated before write-up.
   - *Above nominal:* reported as the measured cost of trusting a declaration the
     harness cannot verify.
5. **The bracket does its job (descriptive).** For U3: the share of runs
   returning `DEPENDS_ON_JUDGMENT`, the number of trigger changes per run, and
   the share of moves recorded unreplayable.
   - Reported. No threshold. A run that certifies despite a logged change is a
     defect and halts the reading.
6. **Replication branch.** The first failure of any check in rules 1 or 3
   triggers **one** replication of that check only, on 510000–511999, at
   identical settings, on `heterogeneous-correlation-fat-tails`' precedent. A
   pass records the original as a family false alarm; a second failure confirms
   it.

## What this experiment cannot do

- It cannot show that a **real** agent is unfaithful in any of these ways. The
  searchers here are scripted so that the ground truth is known; whether models
  behave like them is the agent cell's question, and the ADR pilot's n = 3 is not
  an answer.
- It cannot detect U2 by construction, and rule 2 registers that in advance.
- It says nothing about local pricing, which 7.2 built behind a flag and which
  **this experiment no longer needs**, since a contradicted pick is replayable.
  If rule 3 finds an excess, local pricing comes back as the remedy and gets its
  own registration.

## Cost

Sized before launch on the registered smoke block, as the standing rule requires.
The workload is 7.1's shape — replay re-executes a scripted policy per replicate
— so 7.1's measured 187 ms per replicate for three nulls is the starting
estimate, and 10 searchers × 2 cells × 2,000 draws is the load. **The projection
is compared against a threshold fixed now: $200**, with a reduced B = 1,000 as
the registered fallback, on `gate-comparison` amendment 7's pattern.

## Amendments

None yet. Dated entries are appended here.


## Amendment 1 — 2026-09-27, before launch. Seven corrections, committed not live

### (1) Rule 3 was vacuous by construction, and is replaced by an exactness rule

**U1 and its faithful twin execute identical moves.** The harness executes the
**declared rule**, so U1's `pick` by `autocorr_1` and its twin's `pick` by
`autocorr_1` select the same feature, reach the same support, and produce the
same score — the only difference is that U1 *names* a different feature, which is
recorded as `contradicted`. Their p-values are therefore **identical, not
close**, and asking whether one exceeds the other by more than zero is asking a
question whose answer is fixed before any draw.

**Rule 3 is replaced (exactness, primary for U1):**

> 3. **A contradiction costs exactly nothing, and that is checkable.** For every
>    draw, U1's p-value under the certifying null **equals its twin's**, and the
>    two logs differ only in `MoveRecord.contradicted`.
>    - *Equal on every draw:* the 2026-09-25 inversion is confirmed as an
>      identity rather than an estimate — a contradicted pick cannot inflate size,
>      because the harness ran the rule.
>    - *Any draw where they differ:* a **defect**, not a finding. The harness
>      executed something other than the declared rule on that draw, and the
>      reading halts until it is understood.

**U1 is cut to 200 draws.** An identity needs enough draws to be exercised across
branches, not 2,000 to be estimated; 200 covers the move types and costs a tenth.

**Rule 6 drops rule 3.** A replication branch prices the chance that a *rate*
failed by luck. An exactness check does not fail by luck: a single unequal draw
is a defect, and replicating it on a fresh block would answer nothing.

### (2) Rule 4's predictions, registered, and the headline reworded

**Predictions, before any draw:**

- **U2's replay rejection rate ≥ 0.95.** A `pick_prior` is **one trial**. The
  peek returns the argmax over 82,240 class members, and a single-trial critical
  value is nowhere near the maximum of 82,240 — so the peeked specification
  clears it nearly always. This is not a subtle effect and predicting it small
  would be pretending.
- **U2's declared-class rejection rate within the Wilson interval of nominal.**
  The class tier prices **the class maximum**, whatever route reached it. A peek
  that lands on the argmax is being charged for the argmax, which is exactly what
  that tier charges for. The class gate is not fooled by U2 because it never
  asked how the specification was found.

**The headline is reworded.** It said U2's rate is "the honest upper bound on
what any log-based gate can promise". That is not what it measures:

> **U2 measures the price of a data channel the harness does not control.** The
> peek happens outside the session, so no timestamp, no log and no replay can see
> it; what the number prices is a **scope condition**, not a defect in the null.
> **The mitigation is the sandbox's single-channel rule** — an agent that can
> only reach the data through `evaluate` has no outside channel to peek through,
> which is why the rule exists and what this cell measures the value of.
> **The finding is that the bracket's upper end prices a within-class peek
> correctly**: the declared-class tier charges the class maximum, so a peek that
> stays inside the declared class is already paid for, and only a peek that
> escapes the class is unpriced.

### (3) U3 is corrected, U3b is added, rule 5 is rewritten

**The stale sentence is deleted.** U3's description said "everything after the
first is unreplayable". That was the log-time tagging removed on 2026-09-25: the
log records a change as a fact and the **verdict** prices it, after the
commitment check measures whether the change bound.

**U3's prediction, registered: 100% `DEPENDS_ON_JUDGMENT`.** Every change in U3
**binds by construction** — it is made precisely because the declared rule fired
and the search wanted to continue — so the committed-rule replay stops where the
realized search did not, the commitment check fails on every draw, and every run
is bracketed.

**U3's change count is calibrated to the pilot**, not invented:
`prereg/agent-pilot.md` attempts 6–8 recorded **every run changing at least one
trigger**, with counts of **2, 15, 8** in one attempt and **4, 2, 3** in another
— median about 4, range 2 to 15. U3 draws its change count from that observed
range rather than from a round number, and the source is named here.

**U3b — the pre-emptive change, added.** Declares `last_gain_at_most(0)`, then
changes the trigger **before it ever fires** — to another rule that also never
fires on the realized path. The change is logged and real; it simply **never
binds**.

> **Predicted: the commitment check PASSES on every draw, and U3b's CERTIFIED
> rate equals the faithful arm's.** A logged change that did not alter the search
> costs nothing, which is what the 2026-09-27 verdict change asserts and what
> seat run `pilot_adr_2` showed — five changes, commitment passing at a gap of
> 0.0, and 27 moves bracketed for nothing until it was fixed.
> - *U3b certifies at the faithful rate:* the verdict prices a change by whether
>   it bound, as designed.
> - *U3b is bracketed anyway:* the fix is incomplete and the bracket is charging
>   for the fact of a change rather than its effect. A defect, and it halts.

**Rule 5 is replaced (primary, halting):**

> 5. **A binding change is always bracketed.** For U3: the share of runs
>    returning `DEPENDS_ON_JUDGMENT`, predicted **1.00**. For U3b: the share
>    returning `CERTIFIED` or `FAIL`, predicted to match the faithful arm.
>    - *A run that **certifies despite a binding change** is a **defect***, and
>      the reading halts. That is the only branch that halts here.
>    - The **unreplayable-share readout is dropped**: after 2026-09-25 the log
>      tags nothing, so that share measures the verdict's own arithmetic rather
>      than anything about the run.

### (4) Rule 1 splits into 1a and 1b

> 1a. **The faithful arm's rejection rate, with the checks OFF (validity,
>     one-sided, primary).** This is the **first calibration of process replay
>     over the full content grammar** — `fixed-sequence-replay` measured six
>     searchers whose every continuation was a greedy extension, and these use
>     `swap_worst`, `flip`, `refine` and `pick` as well. Fails high **iff the
>     lower end of the Wilson 95% interval exceeds nominal**, at α = 0.05 and
>     0.01. **Replicated under rule 6** on a first failure.
>
> 1b. **With the checks ON, the checks do not fire on an honest searcher
>     (primary, halting).** The count of check misfires across the faithful arm —
>     a contradiction recorded where the agent named its rule's own choice, a
>     late-declaration refusal where nothing was late, a commitment failure where
>     no trigger changed. **Registered as 0.** **Any misfire halts the reading**,
>     because a check that fires on an honest searcher makes every unfaithful
>     result unreadable.

### (5) s3

**One descriptive readout is registered**, and whether the cell runs at all is
decided by the smoke:

> **Faithful-arm CERTIFIED rate on s3, at matched ACTUAL size, against the
> declared-class gate's on the same runs.** Descriptive, no threshold, no branch.
> Reported at matched actual size and never at nominal, for the reason
> `gate-comparison` fixed: at nominal α the class gate's unused size reads as a
> power deficit that is not there.

**The s3 cell runs only if the four-point scaling curve's projection leaves it
inside the registered cost threshold with the s0 cells.** If it does not, **s3 is
dropped**, and this file records which — the answer comes from the curve, not
from preference. Nothing about rules 1a, 1b, 2, 3, 4 or 5 depends on s3.

### (6) U4's rule, registered

> **U4 against its declared-restart twin, paired on the draw, one-sided.** The
> twin performs the same restarts through the `restart` move; U4 reaches the same
> states through `swap_worst` chains. **Predicted: zero excess** — the replay
> re-executes the logged content moves either way, so a restart spelled out in
> content is priced the same as one declared.
> - *No excess:* structure hidden in content moves is not a hole.
> - *Excess demonstrated* (lower end of the paired interval above zero): a search
>   can lower its own bar by not declaring its structure, which is a finding
>   about the grammar and is reported as one.

### (7) Seed blocks, confirmed exclusive

Checked across every file in `prereg/`, `experiments/`, `ROADMAP.md`, `SCOPE.md`
and `EXPERIMENTS.md` on 2026-09-27: **500000–501999**, **510000–511999** and
**990000–990999** appear in this pre-registration and **nowhere else**.

## Amendment 2 — 2026-09-27, before launch. The workload has one shape, and the
## levers are ordered

### (1) One pass, not two: the checks run per RUN, not per replicate

Amendment 1 split rule 1 into 1a (checks off) and 1b (checks on), and the launch
note guessed that this doubles the workload. **It does not, and the reason is
structural.**

Every check this experiment reads runs **once per run, on the realized log**: the
consistency check compares a named choice with the rule's selection that the
harness already computed (`quixote/consistency.py`), `refuse_if_late` looks at one
timestamp, and the commitment check replays the committed rule **once on the
un-resampled data**. **None of them runs inside the bootstrap.** The expensive
part — the replay of a policy across `B` replicates — is identical whether the
checks are on or off.

**So the driver prices every run regardless of check outcome**, and records the
**check-gated verdict beside the p-value** rather than in place of it. One pass
then yields both rules on the same runs: **1a** reads the p-values as if no check
had gated anything, **1b** reads the check outcomes on the same runs. **The
scaling curve measures that one shape.**

This also makes 1a and 1b exactly comparable, which two passes would not have
been: they are the same draws, the same seeds and the same replicates.

### (2) The lever order, if the projection exceeds the threshold

Registered **before the curve runs**, so the choice is not made in sight of the
number. In this order, and **no further**:

1. **Drop the s3 cell.** It carries one descriptive readout and no rule
   (amendment 1, item 5). Nothing in rules 1a, 1b, 2, 3, 4, 5 or 6 depends on it.
2. **B = 1,000** in place of 10,000, the same registered fallback
   `gate-comparison` amendment 7 used.
3. **U2, U3, U3b to 500 draws each.** These three have predictions at or near
   **1.00** — U2's replay rejection ≥ 0.95, U3's bracket share 1.00, U3b's
   commitment pass 1.00 — and a proportion near 1 is the cheapest thing in
   statistics to bound. **At n = 500 a rate of 100% has a Wilson 95% interval of
   [0.9924, 1.0000], a width of 0.0076**, against [0.9981, 1.0000] and 0.0019 at
   n = 2,000. Four times the draws buy 0.006 of interval width on a quantity
   predicted to be 1.

**What does not move:** rules **1a** and **1b**, **U4**, and the **faithful arm**
stay at **2,000 draws**. 1a is the first calibration of process replay over the
full content grammar and is a *rate near nominal*, where n buys real precision;
1b is a count registered as 0, where a smaller n means a smaller chance of seeing
a misfire that exists; U4's rule is a paired difference predicted to be zero,
which is the case that needs power.

**If the projection is still over after all three levers, the experiment waits.**
It does not run at a size its own rules cannot be read at, and it does not
acquire a fourth lever invented after the number was seen.
## Amendment 3 — 2026-09-28, before any registered draw. The minimal design

**Reason: the smoke projection.** The local smoke on the cost-only block projected
the registered design at roughly **2,958 CPU-hours per cell** at B = 10,000, which
is over the threshold amendment 2 was written to respect. Amendment 2 registered a
lever order to be pulled in that case. **This amendment pulls all of it at once,
before any registered draw, and replaces the order with the result** — so the
design is fixed in one place rather than reconstructed from which levers were
pulled. **Amendment 2's item (2), the lever order, is superseded by this
amendment and says so at the end.**

Amendment 2's item (1) — one workload shape, checks read per run — **stands
unchanged**.

### (1) The s3 cell is dropped

The experiment runs on **s0 only**. s3 carried one descriptive readout and no
rule (amendment 1, item 5); nothing in rules 1a, 1b, 2, 3, 4, 5 or 6 referred to
it. `S_TRUE` and `ORACLE_SHARPE` in the driver hold one cell, and `--cell` accepts
one value, so an s3 draw cannot be taken by mistake.

### (2) B = 1,000 throughout

The registered fallback `gate-comparison` amendment 7 used, now the default rather
than a fallback. Every p-value in this experiment is `(1+#)/(1001)`, whose
granularity is 0.000999 — finer than any rule here reads.

### (3) The faithful arm is two searchers, and that is the minimum

The arm was six searchers, one per move kind. It is now **the smallest set that
together uses every move type in the grammar**, which is **two**:

- **`faithful-restart`** — `init`, `pick` (by `autocorr_1`, among the first six
  features), `extend_best`, `refine`, `flip`, then `swap_worst` until its declared
  rule fires, then `restart`, then `extend_best`. Declares
  `failures_at_least(3) -> restart`.
- **`faithful-stop`** — `init`, `extend_best`, `extend_best`, then `swap_worst`
  until its declared rule fires, then `stop`. Declares
  `failures_at_least(3) -> stop`.

**Coverage table.** Eight move kinds, both searchers, verified on seeds
990000–990007 (the cost-only block) before this amendment was written:

| move kind | `faithful-restart` | `faithful-stop` | also exercised by |
|---|---|---|---|
| `init` | yes | yes | every policy |
| `pick` | yes | — | U1, U1-twin, U2, U2-twin |
| `extend_best` | yes | yes | every policy |
| `refine` | yes | — | U3, U3-twin |
| `flip` | yes | — | U3, U3-twin |
| `swap_worst` | yes | yes | U4, U4-twin |
| `restart` | yes | — | U4-twin |
| `stop` | — | yes | U3, U3b |

**Why not one searcher.** One searcher covering both `restart` and `stop` has to
declare a rule for each, and the two rules then fire together — at which point
**which action the log took is a decision of the policy, not a function of the
declared rules**. The commitment replay re-derives the decision from the committed
rules, takes the first that fires, and reports a disagreement. It is **right** to:
the committed rule set does not determine the action, so the log is not
reproducible from its own declaration. A single-searcher version reached complete
coverage on 8 of 8 seeds and then failed the commitment check on all 8, for that
reason. **Each faithful searcher therefore declares exactly one rule**, which
`tests/test_unfaithful_searchers.py` holds.

**The coverage claim is about this arm, not about the experiment.** The right-hand
column records that seven of the eight kinds are also exercised elsewhere, so
reducing the arm to two does not reduce the grammar the experiment as a whole
covers. What the arm alone certifies is rule 1b: a check that misfires on an
honest searcher misfires on one of these two.

**Two defects found while building the arm, both fixed before this amendment.**
Neither is a deviation from this pre-registration — both are defects in shared
replay code that the earlier six-searcher arm never reached, because none of those
six ever restarted or stopped by rule:

- **`quixote/replay.py`, the `cap_to_log` bound.** The commitment replay was
  bounded at the number of *content* moves in the log while its loop also spends a
  step on each *meta* decision, so a log with a restart and a rule-fired stop was
  replayed one to two steps short — reported as a support disagreement on a search
  that had not diverged. Now bounded at the number of logged steps.
- **`quixote/replay.py`, the logged-move index.** `_run_logged` held content moves
  in one list and indexed it by the **global step counter**, so after any meta
  decision the replay applied the **wrong logged move**, and once the index ran
  past the end it silently took the **fill** in place of the move that was logged.
  Every identity check on a log whose restart rule fired was affected. Now tracked
  by its own cursor.
  **Regression test:** `tests/test_fixed_sequence_replay.py::
  test_a_logged_restart_does_not_shift_the_replayed_moves`, which was confirmed to
  fail with the index restored. The test's logged sequence **ends on a `flip`**
  deliberately: a run of `extend_best` moves replays identically whether the index
  is right or wrong, because the fill is the best admissible move and so is an
  extension, so a test built on extensions alone does not see the bug.

**What this changes in already-recorded results.** Nothing that carries a claim.
The 7.0 gate-comparison used the `_run` and `_run_meta` paths, not `_run_logged`.
The ADR and ETF agent pilots did replay logs containing restarts, and their
identity-check outcomes are affected — but those runs were recorded explicitly
with **no verdict claim**, as a harness shake-out, so no published number moves.
The pilot records are annotated with a pointer to this item.

### (4) Draw counts, per policy

| policy | draws | why this n |
|---|---|---|
| `faithful-restart`, `faithful-stop` | 2,000 each | rules 1a and 1b, **unchanged** |
| U1, U1-twin | 200 each | amendment 1: an identity, exercised not estimated |
| U2, U2-twin | 500 each | predictions at or near 1.00 |
| U3, U3-twin | 500 each | a share predicted 1.00 |
| U3b, U3b-twin | 500 each | a share predicted 1.00 |
| U4, U4-twin | 1,000 each | a paired difference predicted to be zero |

**9,400 policy-runs in total.** The driver walks 2,000 draws and runs each policy
on the first `DRAWS_FOR[name]` of them, so a smaller count is *spent*, not
sampled-and-discarded: policy and draw index are both fixed in advance, and
`tests/test_unfaithful_searchers.py` pins the whole table.

### (5) Every rule's detectability, restated at its new n

Computed from the Wilson 95% interval at the stated n. Where a rule's threshold
can no longer be **confirmed** at the new n, that is said rather than left to be
discovered at reading time.

1. **Rule 1a — the faithful arm's rejection rate, n = 2,000 per searcher.**
   Unchanged from the original design. At α = 0.05 an observed rate *at* nominal
   gives [0.0413, 0.0604]; the rule fails high iff the **lower** end exceeds
   0.05, so the smallest excess it can call is about **+0.0104** in rate. At
   α = 0.01: [0.0065, 0.0154], smallest callable excess about **+0.0054**.
2. **Rule 1b — misfires on the faithful arm, n = 2,000 per searcher.** Registered
   as 0. An observed 0/2,000 gives [0.0000, **0.0019**]: the arm rules out a
   misfire rate above 0.19% with 95% confidence, and a *single* misfire halts the
   reading regardless of rate.
3. **Rule 2 — each unfaithful searcher is caught, at its own n.** The catch is
   **deterministic** for U1 (`contradicted` is recorded on every run), U3 and U3b
   (a trigger change is a logged fact), and **structurally absent** for U2 and
   U4 — so this rule reads a count, not an estimate, at every n. Where it is read
   as a *rate*: at n = 500, 99% caught gives [0.9768, 0.9957]; at **n = 200**,
   even a 100% observed rate gives [0.9812, 1.0000], whose lower end is **below
   0.99** — so at U1's n the rule's "≥ 99%" threshold **can be found consistent
   with the data but cannot be confirmed by the lower end**. This costs nothing
   here because U1's catch is deterministic, and it is stated so that no
   confirmation is claimed from n = 200.
4. **Rule 3 — U1's p-value equals its twin's, n = 200 pairs.** An exactness rule:
   any single unequal draw is a defect. 200 pairs exercise the identity across the
   move types; they do not estimate a rate, and amendment 1 already removed rule
   3 from the replication branch for that reason.
5. **Rule 4 — U2's rejection rate, the headline, n = 500.** This is the number
   the experiment exists to report, so its precision is stated across the range it
   could land in: at an observed 0.20 the interval is [0.1673, 0.2373] (width
   0.0700); at 0.50, [0.4563, 0.5437] (0.0873); at the predicted 0.95,
   [0.9272, 0.9659] (0.0387); at 1.00, [0.9924, 1.0000] (0.0076). **The prediction
   is ≥ 0.95, where n = 500 gives a width under 0.04** — enough to report the
   headline to two decimals. Were the rate to land near 0.5, the width would be
   0.087, and the write-up reports it to **one** decimal in that case rather than
   implying precision the n does not carry.
6. **Rule 5 — U3's bracket share, n = 500.** Descriptive, predicted 1.00, where
   500 draws give [0.9924, 1.0000]. The per-run trigger-change count is reported
   as a distribution, not a rate.
7. **U4's paired difference, n = 1,000 pairs.** Predicted zero. At a per-draw
   paired SD of 0.5 in p-value units, n = 1,000 gives a 95% half-width of
   **0.031**, against 0.022 at 2,000. The prediction is an exact zero and the
   pairing removes the draw, so 1,000 is the case that still needs power and gets
   it; the realized SD is reported beside the interval so the half-width can be
   checked against the assumption rather than taken on faith.
8. **Rule 6 — the replication branch.** Unchanged: the first failure in rule 1
   triggers one replication of that check on 510000–511999 at identical settings,
   which now means **the same per-policy counts registered above**.

### (6) The re-projection, from the same local smoke

Re-measured on the cost-only block (990000+) on this machine at 8 workers, three
to four draws per point, **after** the design above was fixed:

| basis | CPU-hours, whole experiment | c7a.48xlarge, 192 vCPU |
|---|---|---|
| scaling the whole per-draw time with B (what the driver prints) | **140** | 0.73 h wall |
| fitting `seconds = a + b·B` per policy from B = 60 and B = 240 | **58** | 0.30 h wall |

Against roughly **2,958 CPU-hours per cell** for the design before this amendment.
The first row is the honest **upper bound** and the second the honest estimate: the
driver's printed projection scales the fixed per-draw cost — generating the panel,
running the realized search once — with B as well, and at a small measured B that
fixed part is most of the time. The driver now says so where it prints the number.
**Both rows are under the threshold, so no further lever is pulled and the
experiment does not wait.** The four-point curve on the box replaces the two-point
fit before launch; if it lands above either row here, the discrepancy is
investigated before any registered draw rather than absorbed.

### (7) Amendment 2's lever order is superseded

Amendment 2 item (2) registered three levers in order — drop s3, B = 1,000,
U2/U3/U3b to 500 — to be pulled if the projection exceeded the threshold. **It
did, and this amendment pulls all three plus two more** (U1 to 200, U4 to 1,000)
and reduces the faithful arm. **Item (2) of amendment 2 is therefore superseded
and is not a live instruction**; it stays in this file as the record of what was
registered before the number was seen, which is the point of having written it
down. Amendment 2's closing condition survives and is restated here:

> **If the projection is still over after this amendment, the experiment waits.**
> It does not run at a size its own rules cannot be read at, and it does not
> acquire a further lever invented after the number was seen.
