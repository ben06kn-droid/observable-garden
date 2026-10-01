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

#### Cells 1–2 and checks 3–4, read once, 2026-09-30

Output at `runs/agent_cell_read_cells12_checks34.txt`. Quantities follow amendment
11. **Cell 3 is not readable: the ETF arm has not run.**

**CELL 1 — HOLDS for both arms.** Orientation s0 **0/20 = 0.0000** at both levels,
Wilson [0.0000, 0.1611]; reasoned-pick s0 **1/20 = 0.0500**, [0.0089, 0.2361].
Neither lower end exceeds nominal, so neither arm is withdrawn and no audit is
triggered. Comparator: replay gate s0 0.0250 at α = 0.05. At n = 20 the rule fires
at 3 or more of 20 at α = 0.05 — **gross leakage and nothing finer**.

**CELL 2 — A DIFFERENCE, read as priming.** On s3, orientation against replay gate:
moves to submit 5.10 against 5.70 (U p = 0.0376), `pick_prior` used 0.05 against
0.325 (p = 0.0191), trigger changes 0.10 against 0.775 (p = 0.0091). No difference in
accepted picks (both zero), `trigger_is_firing` refusals (p = 0.0529) or engagement
(p = 0.3585). At `rho = 0` the table carries **no information**, so this is
**priming by the paragraph** and it **bounds how much of any ETF effect is priming**;
the ETF readout is reported net of it. At 20 against 40 only a large difference is
visible, which is stated rather than read as equivalence.

**CHECK 3 — behaviour, descriptive.** The reasoned-pick arms are the outliers:
**accepted picks 5/20 on s0 and 6/20 on s3** (zero in every other arm), trigger
changes averaging 2.50 and 2.95 per run against 0.39–0.78 elsewhere, and the lowest
engagement (0.708, 0.671 against 0.83–0.99). They are also the only arms producing
`pick` and `flip` moves. Control engagement is 0.990 with no grammar. **Amendment
12's Spearman readout is almost entirely UNMEASURED**: nearly every move kind has a
single distinct count across the priced runs, so there is no dose to correlate. Only
`trigger changes` on s0 reasoned-pick was measurable — ρ = +0.5226, p = 0.1212,
n = 10 — and positive is the opposite of the leakage direction. The replacement
readout is therefore **no more informative than the decile readout it replaced**, for
the same underlying reason: these searches are too uniform in shape to carry a dose.

**CHECK 4 — the gap is the bracket, not tier power.** At matched actual size 0.05
(thresholds replay 0.0647, class 0.0597, both at s0 actual size 0.0375): s3 power
**replay 13/40 = 0.3250** [0.2008, 0.4798] against **class 26/40 = 0.6500**
[0.4951, 0.7787]. At 0.01 both are 0/40.

**That difference is not a statistical deficit, and the decomposition says so.** The
agent submitted the class maximum **exactly** in 80 of 80 s0 runs and **40 of 40** s3
runs, verified by support and not only by score, so both tiers price the **same
statistic** against near-identical nulls — p-values equal on 58 of 60 s0 runs and 19
of 21 s3 runs. On the **21 s3 runs both tiers price, replay certifies 13 and class
12**; the class tier's extra 14 rejections are **all** on the 19 runs the replay tier
declines to certify because the agent changed a declared rule. So the measured gap is
**the price of the bracket** — the power the replay tier forgoes by refusing a run
whose rule changed — and it is consistent with 7.0's finding that the two tiers are
indistinguishable at matched actual size, which held on runs both tiers priced.

#### Check 3 headline, and two readouts added 2026-09-30

**HEADLINE: trigger changes bound on 25% of s0 runs and 47.5% of s3 runs.**
20 of 80 on the s0 replay arm, 19 of 40 on s3 — the rate **nearly doubles** when there
is signal to find. That is the single most consequential behavioural number in the
cell: it is the share of runs the replay tier declines to certify, it is what check 4's
apparent power gap turned out to be made of, and it is the agent behaviour that
`prereg/bracketed-verdicts.md` amendment 1 and the ROADMAP's tier rule are written
against.

**Stated precisely, because two rates differ and the smaller one is not the headline.**
The 25% / 47.5% figures are **changes that BOUND** — the commitment check fails, so the
committed rule does not reproduce the search that ran. The share of runs with **any
logged change** is 26.3% on s0 and 37.5% on s3. On s3 the bound rate **exceeds** the
logged-change rate, which is not a contradiction and is the next finding.

**A second class of divergence, found while checking the headline: 15 runs across four
arms fail the commitment check with NO logged change at all.** s3 replay 4 of 40,
s0 orientation 1 of 20, **s3 orientation 8 of 20**, s3 reasoned-pick 2 of 20. All 15
are `UNDECIDABLE` rather than `DEPENDS_ON_JUDGMENT`, so none was priced and none
entered any rate — **the readings of cells 1–2 and checks 1 and 4 stand unchanged.**

**RETRACTED 2026-09-30, pending diagnosis.** This paragraph previously read that the
agent had "searched past its own declared rule without declaring a change" and that
this was "U3's unfaithfulness occurring naturally". **That attribution was premature.**
The observation is only that the committed-rule replay diverges from the realized
search: s3 replay run 19 replays as `[continue, stop]` against a realized
`[continue, continue, continue, stop]`. Whether the cause is the AGENT departing from
its rule or the two TRIGGER EVALUATORS — the live session's and `LoggedPolicy`'s —
disagreeing on the same state was not established, and a divergence between evaluators
would be a harness defect rather than agent behaviour. The diagnosis is below; nothing
is claimed about the agent until it concludes. It is recorded as a
check-3 behavioural readout, and it means the honest statement of how often an agent
departs from its committed rule on s3 is **19 bound changes plus 4 silent
divergences**, not 15 logged changes.

**(4) Two readouts added.**

**The orientation arm's s3 CERTIFIED rate under replay, beside the replay-gate arm's:**
orientation **7/20 = 0.3500**, replay gate **12/40 = 0.3000**, reasoned-pick
**2/20 = 0.1000**. The orientation arm is not lower, so on s3 the paragraph does not
cost power; the reasoned-pick arm's 0.10 is the arm that brackets most (18 of 20), and
is low for that reason rather than for a statistical one. Descriptive, no rule — s3
carries signal, so these are power readouts and not size.

**Pick and meta-move decisions in the registered fidelity subsample** — the first 10
runs of each config in seed order (amendment 6):

| config | subsample | `pick` decisions | meta-move decisions | total |
|---|---|---|---|---|
| s0 reasoned-pick | 10 runs | **3** | 12 | **15** |
| s3 reasoned-pick | 10 runs | **3** | 15 | **18** |

**Three picks per config is the number check 2 would have to work with.** At ~20
re-presentations each that is 60 presentations per config for the kind whose fidelity
the cell exists to measure, and a per-kind rate on 3 instances is below what
`prereg/README.md`'s low-n rule permits to be reported. **Recorded now, before the tool
is built**, so the measurement's unit count is known in advance rather than discovered
after the seat is spent: on this evidence check 2 would report `pick` fidelity as
**unmeasured with its count**, which is the branch amendment 4 already registers for a
kind with too few instances.

## CLOSED — the 7.3 agent cell, 2026-09-30

240 runs, seven arms, the registered sizing. Harness integrity clean on all 240:
240/240 submitted, zero errors, zero unregistered refusals, the pinned model served on
every run, every arm recording HEAD's design hashes with `dirty=False`.

| item | status |
|---|---|
| **Check 1** calibration | **READ — HOLDS.** 2/80 = 0.0250 at α = 0.05, 1/80 = 0.0125 at α = 0.01; neither lower Wilson end above nominal |
| **Cell 1** s0 validity | **READ — HOLDS** for orientation (0/20) and reasoned-pick (1/20); no arm withdrawn, no audit |
| **Cell 2** s3 placebo | **READ — A DIFFERENCE** on 3 of 6 measures, read as priming by the paragraph; it bounds how much of any ETF effect is priming |
| **Check 3** behaviour | **READ.** Headline: trigger changes bound on 25% of s0 and 47.5% of s3 runs, plus 15 silent divergences |
| **Check 4** power | **READ**, with the caveat that the gap is the bracket's price and not tier power |
| **Check 2** fidelity | **PENDING THE TOOL.** The re-presentation tool does not exist (amendment 7), and the subsample holds only 3 pick decisions per config |
| **Cell 3** ETF behaviour | **PENDING 6.5.** That arm has not run; the holdout opens once |

**What the cell establishes.** The identity checks do not harm an honest agent arm, at
the resolution n = 20 and n = 80 allow — gross leakage and nothing finer. A bracketed
run issues no certificate and that is the right accounting, registered before any
number was seen (amendment 11).

**What it found that nobody registered a rule for, and which matters more than the
rules it passed.** The agent reached the **class argmax in 120 of 120 runs** across both
panels. So on this class the replay tier is **redundant**: both tiers price the same
statistic against near-identical nulls, and they differ only in what they **refuse**.
Every localising diagnostic the cell registered came back structurally uninformative
for the same underlying reason — the per-kind decile fractions, then amendment 12's
Spearman replacement — because these searches are too uniform in shape to carry a dose.
That is a finding about the arm design, not about the agents, and it is the thing to fix
before a cell like this is run again: a deeper class, or a panel where the Sharpe
objective is less nearly modular, would separate the tiers and give the diagnostics
something to resolve.

**What it licenses.** `p_upper` and the two pricing flags were 7.3's to license.
**Check 2 has not reported, so fidelity-driven pricing stays OFF and unlicensed** — as
`prereg/agent-cell.md`'s own "What these two license" requires. The local-max conjecture
was 7.3's scripted half and is unaffected. The tier-selection rule and the no-fall-through
rule are registered in `ROADMAP.md` and `prereg/bracketed-verdicts.md` on this cell's
evidence, and they make **6.5's headline a class-tier verdict**.

#### The diagnosis of the 15, 2026-09-30 — a harness defect, and it is not repairable retroactively

**Checked in the registered order.** (i) *Refused proposals counted as failures on one
side only* — not the cause; no run among the 15 carries a rejected proposal at the
divergence. (ii) **Declaration text parsed differently by the live evaluator and
`LoggedPolicy` — THIS IS THE CAUSE.** (iii) *`last_gain` over different move kinds* —
not reached; the divergence is explained before it.

**The defect.** `Session.active_trigger_records` built its dict keyed by **action
alone**:

    active = {r.get("action", "stop"): dict(r) for r in declared_trigger_records}

Every rule sharing an action therefore **overwrote the previous one**, and the live
session ran under the **last** rule declared. Run 19 declared three stop rules —
`best_so_far_above(1.2)`, `failures_at_least(3.0)`, `last_gain_at_most(0.02)` — and
the live evaluator held **one**: `last_gain_at_most(0.02)`. `LoggedPolicy` reads
`log.declared_triggers()` and held all **three**.

**The first divergence, named.** Run 19's live trace crosses `best = 1.2312` at record
step 2, so `best_so_far_above(1.2)` is firing from that point. Decision (b) should have
suspended content moves there. It did not, because the live evaluator could not see
that rule, and the search took two further moves (`extend_best`, `refine`) before
stopping on `last_gain = 0.0`. The replay, seeing all three rules, stops at step 2 —
hence replayed `[continue, stop]` against realized
`[continue, continue, continue, stop]`. The eight s3 orientation runs are the same
shape: three stop rules declared, one evaluated.

**Which evaluator was wrong: the LIVE one.** A declared rule that is never evaluated is
not a declaration. `LoggedPolicy` was correct throughout.

**Fixed:** `active_trigger_records` is keyed by **(kind, action)**, so distinct
predicates survive and a `change_trigger` still *replaces* the rule it names rather
than adding to it. Verified live: a session declaring those same three rules now shows
`last_gain_at_most` firing to the live evaluator where it previously did not.
`tests/test_pre_agent_cell.py` requires the session and the replay to fire **identically
on a shared state for every predicate in the registered library**, and asserts the test
covers all of `PREDICATES` so a new predicate cannot be dropped unnoticed.

**0 of the 15 become PASS on re-grade, and that is the correct outcome rather than a
disappointment.** The defect was in **execution**, not in grading: re-grading replays a
stored log against the full declaration, which is what already happened. Those 15 logs
are faithful records of searches that **were allowed to continue past a rule the agent
had declared**, because the harness never evaluated it. Nothing retroactive can undo
that, and the commitment check is right to refuse them.

**What this means for the retracted claim.** The retraction stands and is now
explained: these 15 are **not** U3's unfaithfulness occurring naturally. The agent
declared three rules and obeyed the one it was held to; **the harness is responsible
for the divergence**. No statement about agent fidelity rests on them.

**What does not move.** All 15 were `UNDECIDABLE` and unpriced, so cells 1–2 and checks
1, 3 and 4 are unchanged. The 25% / 47.5% bound-change headline is unchanged, since
those are runs with logged changes. **What is now known to be contaminated** is any
reading of how often an agent departs from its committed rule *without* declaring a
change: on this cell that number is **not measurable**, because the harness was not
enforcing the full declaration. It is a question for a future cell run under the fix.

**11 — amended 2026-09-30. The fidelity pick subsample is every accepted pick.**

Amendment 6 set check 2's subsample at the first 10 runs of each config in seed order.
The cell measured **3 accepted picks per config** in that subsample — too few to report
a per-kind rate under `prereg/README.md`'s low-n rule.

> **For `pick` decisions the subsample is EVERY ACCEPTED PICK in the reasoned-pick
> arm**, both configs, not the first 10 runs' worth. **Meta moves keep the first-10
> rule**, since they are plentiful (12 and 15 in the subsample) and widening them would
> buy nothing.

Taking every accepted pick is **not** selection on an outcome: acceptance is a harness
decision about whether the move was legal in that state, fixed before any fidelity
measurement and independent of what the re-presentation will find. The count is
recorded with the rate either way, and if it remains below what the low-n rule permits
the readout stays **unmeasured with its count**.

#### Check 3, exploratory: the self-enforcement natural experiment (NO CLAIM)

**Provenance, which is the whole caveat.** The pre-2026-09-30 defect enforced only the
last declared rule per action. The others were **declared, logged, and present in the
agent's own prompt** — the harness simply never checked them. That accident is a natural
experiment nobody designed: for each unenforced rule, `experiments/self_enforcement.py`
asks when it *would* have fired on the per-step trigger state the harness stored in each
move's `shown`, and what the agent did at that point.

**Result, across every pre-fix agent run: 345 unenforced rules in 203 runs, of which 28
would have fired. Of those, the agent stopped on 18 and continued on 10** — a
self-enforcement share of **0.64 (18/28)**. By predicate: `best_so_far_above` 12 stopped
against 7 continued; `failures_at_least` 6 against 3. Almost every firing is on **s3**
(25 of 28), which follows from `best_so_far_above` needing a high Sharpe to trigger.

**EXPLORATORY, AND IT CARRIES NO CLAIM.** The population is whatever pre-fix runs exist;
the rules examined are whichever the keying happened to drop; the agent never knew which
of its rules were live; n = 28 firings is far below what `prereg/README.md`'s low-n rule
permits to be read as a rate, and no interval is given for that reason. It is recorded
because the data exists and deleting it would be worse, **not** as evidence that agents
self-enforce. Nothing downstream may cite it.

**What it would take to turn this into a claim**, stated so the gap is visible: an arm
where unenforced rules are *registered* as unenforced in advance, with the agent told
which rules bind, so that continuing is a choice rather than a possibility. That is not
registered and is not proposed here.

#### 13 — 2026-09-30, registered before it runs. A check-3 re-anchor under the fixed harness

Every agent run to date executed under a partially-enforced declaration. Check 3's
behavioural numbers are therefore facts about **those runs**, not about agents under the
harness as it now stands. One arm re-anchors them.

> **20 replay-gate runs on `s0` and 20 on `s3`, under the fixed harness, read ONCE
> against the cell's bound-change rates of 25% (s0) and 47.5% (s3).**
>
> **Prediction, registered before the runs: the rates RISE.** Under the fix every
> declared rule is evaluated, so a rule that previously went unchecked now fires and
> suspends the search; an agent that wants to continue must call `change_trigger`, and a
> change that binds is what the bracket counts. More rules enforced means more firings
> means more changes that bind.
> - *Rates rise:* the cell's figures were an **underestimate**, and the re-anchored
>   numbers replace them for any forward-looking statement. The cell's own readings are
>   not restated — they describe runs made under the old harness and are labelled so.
> - *Rates unchanged or fall:* the prediction is wrong and the reason is investigated
>   before the numbers are used, because the mechanism above says they should rise.
> - *n = 20 per config* detects only a large shift: at 25% the Wilson interval for 20
>   runs is wide, so this re-anchors an order of magnitude and not a second decimal.
>   Stated here so the re-anchored figures are not over-read either.

Descriptive for check 3; it gates nothing and certifies nothing. Rule 5 of
`prereg/agent-pilot.md` does not apply — these are agent-cell runs, not pilot runs — but
no verdict is read from them and the s3 arm carries signal, so its rates are behaviour
and not size.

#### Check 2's tool, built 2026-09-30 — `experiments/fidelity.py`, dry run only

Amendment 7's two open questions are settled in the implementation and recorded here.

**What the resampling resamples: the candidate statistics, recomputed on a stationary
block bootstrap replicate of the streams** — the gate's own bootstrap and block length.
Not noise added to a number: the figures the agent sees are what the *same*
specifications would have produced on a resampled history, so they are jointly plausible
and carry the panel's dependence. A meta move's state has its data-dependent parts
(`best`, `last_gain`) recomputed on the replicate and its counters kept.

**Presentations are stateless**, and the transcript prefix is **byte-identical to the
original except the replaced numbers** — built with `quixote.log.render_shown`, the same
renderer the adapter used, which is why amendment 8's round trip had to exist. A
continuing session would let presentation *k* see presentation *k − 1*, and the
measurement would be of adaptation rather than of fidelity.

**The information set is the prompt plus `shown[0..k-1]`**: a decision's own `shown` is
excluded from its own presentation, because including it would hand the agent the answer
— the candidate statistics are exactly what the declared rule ranks by.

**Subsamples as amended:** every accepted `pick`; meta moves from the first 10 runs in
seed order.

**Dry run on the shake-out and both reasoned-pick arms.** The responder answers **by the
declared rule**, so the rate is 1.0000 by construction and the report says so: it shows
the harness is **consistent**, not that any agent is faithful. Decision counts:

| arm | `pick` | `restart` | `stop` |
|---|---|---|---|
| s0 reasoned-pick | 5 | 5 | 7 |
| s3 reasoned-pick | 6 | 7 | 8 |
| shake-out 2 | 1 | 1 | 1 |

**Every kind is below 10 decisions, so every kind reports UNMEASURED with its count** —
the branch amendment 4 registers. Widening the pick subsample to *every* accepted pick
raised it from 3 to 5 and 6, which is more and still not enough.

**So check 2 cannot be measured on the runs that exist, and this is now a counted fact
rather than an expectation.** `--live` is deliberately not wired: the tool refuses
anything but `--dry-run`, because putting it on the seat is a separate registered
decision and the decision now has a number attached to it — at 20 presentations a config
would cost roughly 100–160 model calls to produce a rate the low-n rule forbids
reporting. **Fidelity-driven pricing stays off and unlicensed.**

#### Amendment 13 read once, 2026-09-30 — the prediction is RIGHT on s0 and WRONG on s3

20 replay-gate runs per config under the fixed harness. Integrity clean on both: 20/20
submitted, zero errors, zero unregistered refusals, pinned model on all 40, self-check
replayable on all 40, one prompt sha per arm, seat throughout, HEAD's design hashes.

**The arms draw from the same registered seed block by index, so the first 20 seeds are
the SAME DRAWS the cell used. The comparison is paired, which is stronger than
registered** and is how it is read:

| config | bound-change rate, old harness | under the fix | paired, same 20 seeds |
|---|---|---|---|
| s0 | 20/80 = 0.2500 | **9/20 = 0.4500** [0.2582, 0.6579] | 6/20 → **9/20** |
| s3 | 19/40 = 0.4750 | **3/20 = 0.1500** [0.0524, 0.3604] | 11/20 → **3/20** |

**s0: the prediction holds.** The rate rises, the old full-arm baseline falls outside the
new interval, and 11 of 20 pairs are discordant.

**s3: the prediction is CONTRADICTED**, and amendment 13's own branch requires the reason
before the numbers are used. **The reason, and it is not seed noise:** the comparison is
paired on identical draws, 11/20 → 3/20, with 8 discordant pairs almost all in the
direction old-had-changes → new-has-none.

**The mechanism.** The prediction assumed more rules enforced ⇒ more firings ⇒ more
changes. The missing step is **what the agent wants when a rule fires**. Under the fix
`best_so_far_above` is enforced for the first time and fires first on **3 of 20** s3 runs
(it fired first on **0 of 40** before, being the dropped rule). On a panel with signal,
when that rule fires the agent has **already found something good**, so it **stops** —
and a run that stops changes nothing, so the bound-change rate falls. The logged-change
rate falls with it, 0.375 → 0.150, while log length barely moves (5.70 → 5.10). On `s0`
the opposite: nothing clears the bar, the firing rule is `last_gain_at_most` on a
non-improving move, stopping forfeits a search that has found nothing, and the agent
**changes the rule and continues** — log length rises 6.00 → 7.65 and changes rise.

**So the re-anchored figures are 0.45 on s0 and 0.15 on s3**, and the direction of the
correction depends on the panel. The cell's 25% / 47.5% are **not** uniformly
underestimates: they understated s0 and overstated s3. Any forward-looking statement uses
the re-anchored pair with the mechanism attached, and **not** a single rate across panels.
At n = 20 these re-anchor an order of magnitude, as registered.

**What this says about the bracket's cost.** The fall on s3 means enforcing a declaration
properly makes agents **stop earlier on panels with signal** rather than argue with their
rules — which lowers the bracket rate and therefore the number of runs the replay tier
declines. That is the opposite of the pessimistic reading, and it was not predicted.

#### Check 2 — DEFERRED to the next agent cell, 2026-09-30

**Deferred, not pending.** `experiments/fidelity.py` is built and its dry run counted the
decisions that exist: `pick` **5** on s0 and **6** on s3; `restart` 5 and 7; `stop` 7 and
8 — **every kind below 10**, so every kind reports **unmeasured with its count**, which is
the branch amendment 4 registers. Widening the pick subsample to every accepted pick took
it from 3 to 5 and 6: more, and still not enough.

**The reason is the arm's yield, not the tool.** At these rates a config needs roughly
**40 reasoned-pick runs** to clear 10 pick decisions, and the next agent cell is where an
arm can be sized in **decisions** rather than runs. Measuring it on the seat now would
spend roughly 100–160 model calls per config to produce a rate the low-n rule forbids
reporting.

**Fidelity-driven pricing stays OFF and unlicensed**, as `prereg/agent-cell.md`'s "What
these two license" requires: check 2 is what would license it and check 2 has not
reported. `--live` is not wired in the tool, so the flag cannot be switched on by
accident.

#### Check 4 under the fix, descriptive — the s3 re-anchor's two tiers on the same 20 runs

Computed locally; no model, no seat. Both tiers on the same 20 re-anchor runs, which are
the same seeds as the cell's first 20 s3 draws.

| α | replay CERTIFIED | declared class | difference |
|---|---|---|---|
| 0.05 | **14/20 = 0.7000** [0.4810, 0.8545] | **15/20 = 0.7500** [0.5313, 0.8881] | **−0.0500** |
| 0.01 | 10/20 = 0.5000 [0.2993, 0.7007] | 11/20 = 0.5500 [0.3421, 0.7418] | −0.0500 |

**This is the under-the-fix figure, and it replaces the cell's −0.3250 for any
forward-looking statement.** The gap nearly closes, and the decomposition says why: only
**3 of 20** runs are bracketed under the fix, against 19 of 40 in the cell, and **on the
17 runs both tiers price, both certify 14**. The cell's apparent power gap was the
bracket's cost, and the bracket got cheaper when the harness began enforcing the whole
declaration — the same mechanism amendment 13's s3 fall identified, seen from the other
side.

Saturation is near-total but no longer total: **19 of 20** runs submit the class maximum
exactly, against 40 of 40 in the cell. Descriptive, no rule, and at n = 20 the intervals
are wide enough that only the direction is readable.

#### 6.5's remaining runs: deferred pricing, priced on the compute box, 2026-10-01

**Recorded before the remaining runs are launched.** Cell 3's (6.5's) remaining runs
are executed with `experiments/agent_cell.py --defer-pricing` and priced afterwards,
on the compute box, from their **committed** run files by
`experiments/price_runs.py`. Nothing about what is priced changes; where and when
it is computed does.

**The reason.** On the ETF panel the session and the pricing want different
machines. The session is a seat call and needs almost no local compute; the pricing
needs no model and is almost all compute — the certifying null (B = 200 trigger
replays against the 82,240-member class table) and the declared-class p, which is
the registered certifying tier on this panel (ROADMAP, "What this makes the ETF
verdict") and takes a class maximum over all 82,240 stored net streams on every
replicate. In-line, each worker prices before it can start its next session, so the
seat's throughput is bounded by pricing on an 8 GB laptop against a 2.8 GB table.
Deferred, the sessions run back to back and the pricing runs in parallel where the
cores and the memory are. Committing the logs **before** pricing has a second
benefit: the log a verdict is computed from is fixed in history before the verdict
exists.

**Why this is the same computation and not a second one.**
- `--defer-pricing` writes the complete log — every move with its parameters and
  `shown`, the declared rules, the change history, the declared budget — **and the
  close-time self-check**, then a `pricing_deferred` event in place of the verdict.
  The completion rule is unchanged: `end` is still written last.
- `price_runs` rebuilds the session log from the file and prices it through
  `experiments.agent_backend.certify_log`, **the function the in-line path calls**,
  on the panel rebuilt as the runner builds it. One function, not two copies.
- **Checked on committed s0 logs before use:** `price_runs --check` re-priced all 20
  runs of `runs/reanchor_s0_replay` (priced in-line under the fixed harness; FAIL 10,
  DEPENDS_ON_JUDGMENT 9, CERTIFIED 1) and reproduced **20/20 verdicts identically**,
  field for field, `certifying_null_computable` and the verdict event included.
  `tests/test_price_runs.py` holds the same equality on a scripted run, both ways:
  in-line against `--check`, and in-line against deferred-then-priced.
- A run priced in-line keeps its verdict: `price_runs` writes a verdict only into a
  file carrying `pricing_deferred`, and adds the class p to every complete run.

**The ETF class p.** Computed from the class table on the **certifying null's own
replicates** — the same block length, `default_rng(seed)`, the same draw order — so a
run's replay-tier and class-tier p-values are paired on identical resamples.
`ClassTable.null_max` reads the table once per run and prices all replicates of a
member chunk from a count matrix, as `garden/_full_class_engine.py` does for the
simulated panels. It agrees with `max_sharpe(rows, demeaned=True)` per replicate to
1e-10 relative (`tests/test_class_table.py`), **not bit for bit**: the reduction
order differs.

**A defect found while building this, and what it did to the six ETF runs already
made.** `environments/class_table.build_class_table` wrote its manifest shape as
`[T, N]` and checked it against `[N, T]`, so **the cache never hit**: every ETF run
rebuilt the 2.8 GB table at start, opening the shared file `w+` — which truncates
it — while other `--workers` processes were reading it. Fixed: the shape is read
from the `.npy` header; a build writes a private file and renames it into place, so
a partial table is never visible under its name; a lock makes concurrent callers
build once; a manifest from before the fix is not trusted, so every existing table
is rebuilt once. Found because the table on disk at 15:51 was **half zeros** (rows
41,472–82,239, the tail of the depth-3 members) from a rebuild that never finished.
Rebuilt and verified row for row against direct computation; true class maximum
**0.3159**, `(18, +)(19, −)`.

The six in-line ETF runs in `runs/etf_replay` (uncommitted), audited against the
verified table:

| run | search's recorded scores | in-line verdict | re-priced from log |
|---|---|---|---|
| 0 | **4 records read 0.0000 where the true Sharpe is −0.32 to −1.82** (rows 44, 164, 5241, 7281) | DEPENDS_ON_JUDGMENT | identical |
| 1 | all true | **UNDECIDABLE** | **FAIL**, p = 0.9950 |
| 2–5 | all true | FAIL, DEPENDS, FAIL, FAIL | identical |

- **Run 0's search ran on a truncated table**: it was shown false zeros for four
  supports, so its log is not a record of a search on this panel, although its
  submission is the true class maximum. Its verdict reproduces, which certifies the
  arithmetic and not the search.
- **Run 1's in-line verdict is an artefact**: its integrity check failed against the
  damaged table; against the true one it prices to FAIL.
- **Class p, all six: 1.0000** at B = 200 — every replicate's class maximum exceeds
  the submitted 0.29–0.32, consistent with the preflight bar of 1.14 on this class.

**Disposition of runs 0 and 1 is not decided here.** Recorded so it is decided
before the remaining runs are read, not after.
