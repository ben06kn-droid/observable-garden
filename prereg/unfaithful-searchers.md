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