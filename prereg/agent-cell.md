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
  behavioural predictions are therefore read on the **ETF panel**, which is cell
  3.
- It cannot separate "the agent used the table" from "the agent was primed by
  being handed something" **except** through cell 2, which is why cell 2 is
  registered as a cell rather than as a robustness check.
- At n = 20 it cannot measure a small change in the false-certification rate.
  Cell 1 rules out a hole; it does not calibrate.

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

**4 — 2026-09-27, before anything is live. The calibration and fidelity
measurements, from ROADMAP 7.3's checks 1 and 2.**

*(Numbered 4. It was written as a second "2" — the number was taken by the
2026-09-25 threshold-scoping entry. Renumbered 2026-09-29 with the duplicate
`## Amendments` header, and the heading check strengthened to catch a repeat
rather than only a heading that precedes the first:
`tests/test_code_state.py`.)*

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
**5 — 2026-09-29, before anything is live. Which panel carries which cell, stated
so the runner is not chosen by inference.**

The file registered cells 1 and 2 as `s0` and `s3 at rho = 0` — the **simulated**
panel's configurations — while "What this arm cannot show" said the ADR panel
"contributes only the validity and placebo readings". Those are two different
panels for the same two cells, and a reader had to guess which. The sentence is
corrected above; this records what is meant and why.

**Cells 1 and 2 run on the SIMULATED panel**, at `e_agent.py`'s registered
configurations: `s0` (s = 0) and `s3` (s = 3), both at **`rho = 0`**, `K = 40`,
`M = 50`, `T = 5,000`.

**The ADR panel contributes NOTHING to the agent cell.** Not the validity reading,
not the placebo. Two reasons, and either alone is sufficient:

- **Its null is unknown.** Cell 1 is a validity cell: it asks whether the
  false-certification rate exceeds nominal, which presupposes a known null. On a
  real panel there is no such thing — whatever edge ADR does or does not contain is
  not a quantity this project knows, so a rejection there cannot be called false.
  On the simulated panel at `s0` the null is true **by construction**, which is the
  only footing a validity claim has.
- **Its features are correlated.** Cell 2 is a placebo: it needs a table that
  carries **no information**, which `rho = 0` delivers by making the feature
  covariance the identity — every correlation below the threshold, features
  exchangeable, autocorrelations zero in expectation. ADR's features are
  cross-correlated, so a table built on them says something, and a behavioural
  difference there would be uninterpretable: neither priming nor information, but
  both confounded.

So ADR is the **pilot's** panel (`prereg/agent-pilot.md`, a harness shake-out with
no verdict claim) and nothing more. The agent cell is **simulated for cells 1 and
2, ETF for cell 3**, and `experiments/agent_cell.py` takes `--panel {s0,s3,etf}`
with no ADR option, so the distinction is enforced by the runner rather than
remembered.

**6 — 2026-09-29, before anything is live. The reasoned-pick arm's size, and which
runs check 2's fidelity subsample is.**

Amendment 3 of `prereg/AGENT_PROMPTS_REAL.md` registers the reasoned-pick **arm**
and states **no run count**; check 2 above registers a **fidelity subsample** of
"10 runs per config". Those are two different quantities and the file let them be
read as one, so `experiments/agent_cell.py` was reading the subsample where it
needed the arm. Both are fixed here.

**The reasoned-pick arm is 20 runs on `s0` and 20 on `s3`.** Forty runs. It is
sized like the other arms rather than like its subsample, because it carries the
behavioural readouts of check 3 alongside the fidelity measurement, and a
behavioural rate at n = 10 is below what `prereg/README.md`'s low-n rule allows
to be reported at all.

**Check 2's fidelity subsample is the FIRST 10 RUNS OF EACH CONFIG, IN SEED
ORDER.** Not a random 10, not the 10 with the most picks. The runner draws its
seeds from a fixed block per panel and runs them in that order, so "the first 10
in seed order" is determined before any run happens and can be checked afterwards
against the seed list in `run_config.json`.

Naming it this way closes a hole the file had left open: a subsample chosen after
seeing which runs produced picks would select on the outcome the measurement is
about, and a fidelity rate computed on the pick-richest half of the arm is not the
arm's fidelity. **Every pick and every meta move in those 10 runs is
re-presented**, as check 2 registers; the other 10 runs of each config contribute
their behavioural readouts and no fidelity.

**7 — 2026-09-29, before the shake-out. Check 2 has an unmet precondition, and it
is recorded before the window rather than discovered inside it.**

Check 2 re-presents each logged `pick` and meta move with resampled numbers and
records whether the declared rule predicts the choice. **That requires the log to
hold the information set the agent was actually presented**, and it does not.

**What is in place.** `quixote/log.py`'s `InformationSet` carries a `shown` field
for the `(label, value)` pairs revealed, and its `as_context()` is documented as
the fixed template a re-interrogation rebuilds from, "so it cannot drift between
the original session and a re-interrogation". The slot and the contract exist.

**What is missing.** `quixote/agent_adapter.py` calls `session.propose(move)` with
**no `shown` argument**, and `Session.propose`'s `shown` defaults to empty — so
`shown` is `()` on **every agent-driven move**. Verified on a reasoned-pick-shaped
session: a `pick` offered 10 candidates records `as_context() = {'step': 1,
'support': [[25, -1.0]], 'score': 0.583…, 'shown': []}`. The count of candidates is
kept; **the values are not**. Nothing anywhere populates `shown`.

**Why a count is not enough, and why re-deriving is not either.** A fidelity
measurement asks whether the declared rule predicts the choice *given what was in
front of the agent*. Re-deriving the candidate values from the panel afterwards
would score today's numbers against yesterday's choice, and any change to the
scorer, the basis or the class table between the run and the measurement would
silently become a fidelity signal.

**Registered as the test it must pass**:
`tests/test_agent_cell.py::test_every_pick_and_meta_move_stores_the_information_set_presented`,
marked `xfail(strict=True)` so it becomes a hard failure the moment it starts
passing and the marker has to come off deliberately.

**Two design questions this leaves open, to be registered before the tool is
built, not after:**

1. **What `shown` records for each move kind.** For a `pick`, one pair per
   candidate in `among` is the obvious reading. For a meta move the natural
   content is the trigger state it was evaluated on (`step`, `best`, `failures`,
   `last_gain`, `budget_left`), which is a different shape from `(label, value)`
   pairs.
2. **What "resampled numbers" resamples** — the candidate values only, or the
   whole information set — and whether re-presentation is **stateless** (a fresh
   context per presentation) or continues a session. These change what is being
   measured, so they are registered rather than chosen at implementation time.

**Settled 2026-09-29, with amendment 8: what the information set for a decision
IS.**

> **The information set for decision `k` is the prompt plus `shown[0..k-1]`.**

A decision's context is everything the agent had received **before** it made that
decision, and nothing it received as a consequence of making it.

**A `pick`'s own `shown` is post-execution.** The adapter computes the candidate
statistics before calling `propose`, but it renders them in the **tool result** —
which the agent receives only **after** the pick has executed. So `shown[k]` did
not inform decision `k`; it informs decision `k + 1`, and belongs to that
decision's context. The same holds for every move kind: `_shown_for` reads the
state before the move and the payload is returned after it.

Getting this backwards would inflate measured fidelity in the one direction that
looks like success: re-presenting decision `k` with `shown[k]` in view hands the
agent the answer to the question it is being asked, since the candidate statistics
are exactly what the declared rule ranks by. A rule would then "predict" a choice
the agent could read off the context, and the rate would approach 1 for reasons
having nothing to do with the agent.

**Still open, and belonging to the tool rather than to this definition:** what
"resampled numbers" resamples — the candidate values only, or the whole
information set — and whether re-presentation is **stateless** (a fresh context per
presentation) or continues a session. Both are registered before the tool is built.

**Consequence, stated plainly: check 2 cannot be read from runs made today.** The
reasoned-pick arm may still run — its behavioural readouts under check 3 do not
depend on `shown` — but **any fidelity rate would be computed from a log that did
not record what the agent saw**, and `prereg/agent-cell.md`'s own licensing then
follows: check 2 is what licenses fidelity-driven pricing, so that flag stays off
and unlicensed regardless of what the cell returns.

**8 — 2026-09-29, before the shake-out. `shown` is the verbatim payload, and the
round trip is an invariant.**

Amendment 7 recorded that check 2's precondition was unmet. It is now met, and
this registers what is stored and the guarantee attached to it.

**`shown` is the verbatim payload the adapter rendered to the agent at that
step**, as `(label, value)` pairs, for **every move kind**:

- **`pick`** — one pair per **candidate**, labelled `<feature><sign>`, carrying the
  value of **the statistic the move named**. Note the count: the declared class is
  signed, so five named features yield ten candidates, and the pairs match the
  candidate count rather than `len(among)`.
- **meta moves (`stop`, `restart`)** — the **trigger state** the rule was evaluated
  on: `step`, `best`, `failures`, `last_gain`, and `budget_left` where a budget was
  declared.
- **every other content move** — the state the move was proposed from, in the same
  form.

**The invariant, registered: re-rendering a stored `shown` reproduces the payload
that was sent, BYTE FOR BYTE.** One function, `quixote.log.render_shown`, both
builds the text the agent receives and reproduces it afterwards; the adapter
appends `| shown: <rendered>` to every tool result and stores the same pairs in the
record. Held by `tests/test_agent_cell.py`, against the payloads the adapter
actually returned and again after a JSON round trip, because the agent receives
`ToolResult.to_json()` and not the dataclass.

Why an invariant and not a convention: a fidelity measurement re-presents a
decision and asks whether the declared rule predicts the choice. If the adapter
formatted the payload one way and the re-presentation another, the agent would be
scored against numbers **it never saw in that form**, and the difference would read
as infidelity. The two directions therefore cannot be allowed to drift apart, and
sharing the renderer is what stops them.

**This changes what the `pick` tool renders, and the change is the point.** Before
this the tool returned the outcome alone: an agent named a candidate set and
learned only which one the rule selected, never the candidates' statistics. A
fidelity measurement would then have had to **re-derive** those values afterwards —
scoring today's numbers against yesterday's choice, with any later change to the
scorer, the basis or the class table silently becoming a fidelity signal. The
candidates and their statistic are now in the payload, so the numbers the agent saw
are the numbers it is measured against.

**What it costs, recorded rather than waved past:** the pick tool's result is
longer, and tool-result length is the one lever on per-turn cost
(`quixote/agent_adapter.py`). A pick over five features in a signed class adds ten
`label=value` pairs. It also changes the **agent's information**: an agent that can
see candidate statistics may choose differently from one that cannot, so the
reasoned-pick arm's behaviour is not comparable with the pilot's picks — of which
there were none, so nothing already measured moves.

**`tests/test_agent_cell.py::test_every_pick_and_meta_move_stores_the_information_set_presented`
is no longer `xfail`.** Amendment 7's two open questions — what "resampled numbers"
resamples, and whether re-presentation is stateless — **stay open**, and belong to
the tool, which is built after the cell.

**9 — 2026-09-29, before the shake-out. Cell 1's validity rule covers the
reasoned-pick arm on `s0`.**

Cell 1 registered its validity rule for the **orientation arm against the
replay-gate arm**. It now applies, unchanged in form, to the **reasoned-pick arm
on `s0`** as well.

**Why it has to.** Amendment 8 made a `pick` render **every candidate's statistic**
into the payload, and the reasoned-pick arm is **the only arm that reliably
picks** — its prompt asks for one, which is why it exists
(`prereg/AGENT_PROMPTS_REAL.md` amendment 3), and the pilot recorded **0 picks in
5 runs** when picks were merely permitted. So that arm is the one where the agent
sees the most of the data per run, by a wide margin, and it is the arm most able to
convert what it sees into a false certification. An arm whose data exposure was
increased by an amendment cannot inherit a validity reading taken on arms that
never picked.

**The rule, stated in full rather than by reference:**

> **The reasoned-pick arm on `s0` fails high iff the LOWER end of the Wilson 95%
> interval for its rejection rate exceeds nominal**, at α = 0.05 and α = 0.01.
> - *Predicted: unchanged.* Revealing a candidate's statistic after the move is
>   information about features, not about returns, and `s0`'s features are
>   independent of its returns by construction.
> - *If liberal:* **the arm is withdrawn**, and the **adapter is audited for a
>   returns leak in the rendered payload before anything else is concluded** — the
>   same order cell 1 uses, and for the same reason: on `s0` a leak is the only way
>   this outcome can happen. **No behavioural readout from a liberal arm is
>   reported as a finding**, which includes the fidelity rate check 2 takes from
>   this arm.
> - *If conservative:* reported, and compared with the replay-gate arm's rate on
>   the same panel.

**Detectability at the registered n = 20, computed and stated so a pass is not
read as a calibration claim.** The rule fires at **3 or more rejections of 20** at
α = 0.05 (15%; Wilson [0.0524, 0.3604]) and at **2 or more of 20** at α = 0.01
(10%; [0.0279, 0.3010]). At 2 of 20 and α = 0.05 the interval is [0.0279, 0.3010]
and the rule does **not** fire. **This detects gross leakage and nothing finer.**
The scripted arms of `prereg/unfaithful-searchers.md` carry the calibration claim;
this rules out a hole.

**What it does not extend to.** The orientation arm's own rule is unchanged, and
nothing here is read on `s3`, where the null is not true and a rejection rate is
not a size.

**10 — 2026-09-30, after shake-out attempt 2 and before the cell. The agent's
budget is the harness's turn limit, written at session open.**

Attempt 2 (`prereg/agent-pilot.md`) triggered condition 4 on its longest run: the
integrity check reported a **structural failure** while the support and the score
agreed to **exactly zero**, and the action sequences differed only in **length** —
11 replayed against 13 realized. The cause was a bound, not a divergence. No agent
declares a budget, so `LoggedPolicy` fell back to `searchers.meta_adaptive.BUDGET =
12`, and that log held 14 records.

**Registered:**

> **The harness writes `MAX_TURNS` into the log at session open as the declared
> budget.** `LoggedPolicy` reads the budget from the log. **An agent log without one
> raises**, and there is **no fallback to `meta_adaptive.BUDGET` on the agent
> path.**

**Why the turn limit is the right bound, and not an arbitrary one.** An agent's
procedure ends at **a declared trigger or at the harness's turn limit**, whichever
comes first. The limit is therefore *part of the procedure* — the search genuinely
cannot continue past it — so a null that runs the same procedure must run to the
same bound. 7.1's cap of 12 is a different searcher's bound and belongs to a
different procedure; substituting it prices a search nobody ran.

**Why NOT bounding by the realized length, which is the tempting alternative.**
Taking the bound from how long the log happened to be would make **the bound a
function of the realized data** — a longer search on a lucky draw would license a
longer null, and a replicate would be allowed exactly as many steps as the realized
run took because the realized run took them. That is the **data-dependent-length
error**, and it is the same mistake `SCOPE.md`'s obliviousness condition forbids in
the choice of menu: the bound must be measurable with respect to a σ-field
independent of the return-generating randomness. `MAX_TURNS` is a constant fixed
before any data is seen; the realized length is not.

**Why it raises rather than defaulting.** A log whose bound cannot be recovered
cannot be replayed, and a replay that silently substitutes some other bound produces
a number that looks like a p-value and is not one. Attempt 2's run is the
demonstration: had the check not been structural, a 12-step replay of a 14-step
search would have been priced and reported. **The two short runs of attempt 2 passed
only because they happened to stay under 12 records**, which is not a property any
future run has.

**Runs written before this amendment.** Their budget is **reconstructed** as
`MAX_TURNS`, because the turn limit was in force during them even though it was not
written down. `experiments/regrade_pilot.py` reports which of the two it used —
`"read from the log"` or `"reconstructed"` — because a reconstructed bound is a
weaker claim than a read one, and a reader should not have to assume.

**Also registered: the change history is serialized.** Attempt 2 recorded its
absence as a gap. `log.trigger_changes` now reaches the run file **with its
timestamps**, alongside the committed rules. A change is a data-dependent decision
and its **timing** is the whole reason the verdict prices it, so the timing belongs
in the artifact rather than in a boolean.

**Related work on re-running agents, added by the 2026-09-30 literature search.**
Rewolinski, Zane, Huang, Singh, Wang, Gao & Yu (2026), *Sanity Checks for Agentic
Data Science* (arXiv:2604.11003), re-run agentic pipelines under perturbations of
the data to screen whether the agent can tell signal from noise, and find
self-reported confidence poorly calibrated to the empirical stability of the
conclusions. It is the nearest neighbour to the twins here and to this file's
prediction slot. **The hypothesis differs:** theirs concerns **stability** under
perturbation, and this project's concerns **trial count** and whether a logged
candidate set suffices when the search is adaptive. Read-level: abstract and
listing metadata read 2026-09-30, full text not opened
(`docs/RELATED_WORK_2026.md`).

**11 — 2026-09-30, before any number from the s0 replay arm is seen. Check 1's
type-I rate is a false-certification rate over all 80 runs.**

The s0 replay-gate arm completed 80 runs. **20 of them carry no certifying-null
p-value**, because `quixote/certify.py` does not price that null on a run with a
logged trigger change: the pre-change rule is what replays, so the search after the
change is a decision the null cannot price, and the verdict is
`DEPENDS_ON_JUDGMENT` with the bracket reported instead. The reader refused to read
check 1, correctly, because check 1's wording asked for a **position** for every
run and only 60 runs have one.

**What broke is the wording, not the rule.** Check 1's rule is a validity rule about
**false certification**. It was written assuming every run carries a position,
because when it was drafted nothing suggested a quarter of runs would be bracketed.
The assumption is what the 25% bracket rate broke.

**Registered, before any number is seen:**

> **Check 1's type-I rate is the false-certification rate over all n = 80 runs.** A
> run **rejects** at α iff it **issued a certificate** at α — that is, it carries a
> certifying-null p-value and that p-value is below α. A run that issued no
> certificate counts as a **non-rejection**: `DEPENDS_ON_JUDGMENT`, `UNDECIDABLE`,
> or any run with no position certified nothing, **which is what it does in
> deployment**. The denominator is 80.
>
> The rule is unchanged in form: it **fails high iff the LOWER end of the Wilson 95%
> interval for that rate exceeds nominal**, at α = 0.05 and α = 0.01. **The n = 80
> detectability statement stands for the rate** — it detects a true rate near 13% or
> worse, and rules out gross leakage and no more.

This is the quantity the cell was always about. A gate that brackets a run has not
certified it, and a reader asking "how often does this gate certify noise" must count
that run as a non-certification rather than drop it. Dropping it would condition the
answer on agent behaviour; counting it as a rejection would charge the gate for a
certificate it refused to issue.

**The KS and per-kind readouts need a position, and are read on the 60 that have
one — as descriptive shape readouts, with the conditioning stated.** They are not
the rule and they gate nothing. What they describe is **the distribution of positions
among runs that did not change a trigger**, and every report of them says so. A
uniformity statement about 60 selected runs is not a uniformity statement about the
arm, and the difference is recorded rather than smoothed over.

**One descriptive readout is added, on all 80: the declared-class p-value's rejection
rate at α = 0.05 and 0.01.** It is the bracket's **upper** end, it exists for **every
run** whatever the agent declared or changed, and it is **expected conservative** —
the class tier charges the class maximum whatever route reached it, so it is the one
null that needs no position and no cooperation from the log. Descriptive, no
threshold, no branch.

**Not yet computed, and that is stated rather than implied.** The 80 recorded verdicts
carry `p_frozen` but **no `p_upper`**: `experiments/agent_backend.py`'s
`_certify_run` never passed a declared-class p-value, so the declared-class null was
never computed for this arm. The readout therefore requires a **local computation** on
the simulated panel — no model, no seat — and until it is done the reader reports it as
unavailable rather than silently omitting it.

**The 25% bracket rate is a check-3 readout, not a check-1 problem.** How often an
agent changes a declared rule is behaviour, and check 3 is where behaviour is
reported. It is noted here only because it is what exposed check 1's wording.

#### Check 1, read once, 2026-09-30 — HOLDS

Read under amendment 11 by `experiments/agent_cell_read.py`; output at
`runs/agent_cell_s0_replay/check1_read.txt`. The refusal produced before amendment 11
is kept beside it as `check1_read_REFUSED_pre_amendment11.txt`, so the correction is
visible rather than silent.

**The rule — false certification over all 80 runs:** 2 of 80 = 0.0250 at α = 0.05,
Wilson [0.0069, 0.0866]; 1 of 80 = 0.0125 at α = 0.01, Wilson [0.0022, 0.0675].
Neither lower end exceeds nominal. **VERDICT: HOLDS.** Twenty runs counted as
non-rejections, all `DEPENDS_ON_JUDGMENT` with a logged trigger change.

**Detectability at n = 80, as registered:** the rule fires at 8 or more of 80 at
α = 0.05 and at 3 or more at α = 0.01. It detects a true rate near 13% or worse and
**rules out gross leakage and no more**; the scripted arms carry the calibration
claim and this pass is not a calibration result.

**Descriptive, positions only (60 runs, conditioning stated):** KS against U(0,1)
gives D = 0.1065, p = 0.4724 — no rejection; positions run from 0.0050 to 1.0000
with a median of 0.5746.

**Two limitations of the per-kind readout, recorded because they are structural and
not a property of this draw.** All four kinds present among the priced runs —
`init`, `extend_best`, `refine`, `stop` — appear in **every** priced run, so their
lowest-decile fractions are computed on the same 60 runs and are **identical by
construction** (5/60 each). And `swap_worst` and `restart` appear **only in runs that
issued no certificate**, so **no position exists for them at all** and the readout is
blind to exactly the two kinds a reader would most want it to examine. The per-kind
readout therefore names no suspect kind here, and could not have.

**Still pending:** the declared-class readout amendment 11 registers. `p_upper` was
never computed for this arm, so it is reported as unavailable; it needs a local
computation on the simulated panel, with no model and no seat.

#### Amendment 11's declared-class readout, computed 2026-09-30

`experiments/agent_cell_class_p.py`, locally — no model, no seat. B = 200 per run,
matching each run's certifying null so the granularity is the same; the class-maximum
null and the submitted specification are both computed on the panel's **base feature
columns**, so observed and replicate statistics share one basis. Output at
`runs/agent_cell_s0_replay/class_p_readout.txt`, per-run values in `class_p.json`.

**The readout, descriptive, all 80 runs:** **3 of 80 = 0.0375** at α = 0.05, Wilson
[0.0128, 0.1045]; **2 of 80 = 0.0250** at α = 0.01, Wilson [0.0069, 0.0866].
`p_upper` runs from 0.0050 to 1.0000, median 0.5522. No variance-floor or Sharpe-cap
guard fired on any run.

**It is not conservative relative to the certifying null, and the reason is a finding
about the searcher rather than about the tiers.** On the 60 runs carrying both,
`p_upper − p_certifying` has mean **+0.0002**, median **0.0000**, maximum **+0.0050**,
and the two are **exactly equal on 58 of 60**.

**Why: the agent submitted the class maximum in 80 of 80 runs.** Not approximately —
the submitted score equals `full_class_observed_max` to within 1e-9 on every run, and
on five runs checked by **support** rather than by score the submitted specification
**is** the argmax over all 82,240 members. So both tiers price the same statistic, and
the bracket collapses to a point.

**What this means for the cell, stated plainly.** On `s0` the replay tier buys
**nothing** over the declared-class tier, because this searcher **saturates the
declared class**: greedy `init` → `extend_best` → `extend_best` → `refine` at depth 3
reaches the global argmax every time on this panel. Consequences that follow and are
not optional:

- **Check 4's power comparison is predetermined on this arm.** CERTIFIED rate under
  replay against PASS rate under the class gate cannot differ when the statistic and
  the maxima coincide. Any difference that appears would be bootstrap noise, and the
  check is read that way or not at all.
- **Check 1's pass is weaker than it looks.** It says the gate does not certify noise
  often — but against a searcher whose submission the class tier already prices
  exactly, which is the easiest case for the gate, not a hard one.
- **It does not invalidate anything.** No rule referred to a gap between the tiers,
  and 7.0 already measured replay and class as indistinguishable at matched actual
  size (+0.0003, straddling zero). This is the mechanism behind that, seen directly.
- **It is a property of this class and this panel**, not of agents: at `max_size = 3`
  over `K = 40` a greedy path with `refine` is evidently enough. A deeper class, or
  one where the objective is less nearly modular, would separate the tiers — and
  whether it does is a question for a later experiment, not a repair to this one.

**12 — 2026-09-30, registered before the remaining arms run. The per-kind decile
readout is replaced.**

Check 1's per-kind lowest-decile readout was **structurally blind on the s0 replay
arm**, for two reasons recorded with that read: all four kinds present among the
priced runs appeared in **every** priced run, so their fractions were identical by
construction; and `swap_worst` and `restart` appeared **only** in runs that issued no
certificate, so no position existed for them at all. It named no suspect kind and
could not have.

**Registered in its place, for the remaining arms:**

> **Spearman rank correlation of the position with, per run, (i) the count of each
> move kind and (ii) the number of trigger changes** — computed on the runs that
> carry a position, reported with the correlation, its two-sided p-value and n, one
> row per move kind plus one for trigger changes.

**Why this is the right shape.** A decile fraction asks whether *runs containing a
kind* skew low, which is a question about **presence**; when a kind is present in every
run the question is empty. A rank correlation asks whether *more of a kind* goes with a
**lower position**, which is a question about **dose**, and it survives a kind being
ubiquitous — indeed it is at its most informative there. It is also the natural
readout for the trigger-change count, which is a number rather than a presence.

**Descriptive, no threshold, no branch, and it gates nothing.** The conditioning is
stated wherever it is reported: these are positions among runs that issued a
certificate-eligible position, which is not the whole arm. A kind with too few
distinct counts to rank is reported as **unmeasured with its count**, never as a null
result. **Sign convention, fixed now:** a **negative** correlation means more of that
kind goes with a smaller p-value, which is the direction that would indicate leakage.
