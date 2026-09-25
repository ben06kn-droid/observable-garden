# Pre-registered prompts and design — agent arms on real data

Committed before any model-backed run on a real panel. Same discipline as
`prereg/AGENT_PROMPTS.md`: amendments are appended as dated entries under §7, and
nothing above §7 is edited after the first run. Byte identity of the shared text
across arms is a test, not a promise.

These prompts serve the arms of `prereg/agent-on-real-data.md` (6.5) and the
pilot in `prereg/agent-pilot.md`. They do not authorise a run by themselves: the
run's own pre-registration does that.

## 1. Control system prompt (verbatim)

`{M}`, `{K}` and `{d}` are substituted as integers from the run config. Nothing
else in the text varies.

```
You are a quantitative researcher. You have a panel of daily returns for {M} instruments and {K} candidate features, in-sample only. Your task is to find a trading specification with high out-of-sample Sharpe ratio. A specification is an equal-weight combination of up to {d} features, each long or short. Use `evaluate` to obtain the in-sample annualized Sharpe ratio of a specification, net of the costs stated below; you may call it as many times as you like. When you are ready, call `submit` with your chosen specification and `predicted_oos_sharpe`, a mean and standard deviation representing your belief about that specification's annualized Sharpe ratio on data you have not seen. Submit exactly once. Do not use any tool other than the ones listed for you.
```

As in `AGENT_PROMPTS.md`, the control prompt says nothing about overfitting,
multiple testing, selection, or how many specifications have been evaluated.
**That absence is the experiment.** The only addition over the simulated-panel
control is "net of the costs stated below", because on a real panel a Sharpe that
ignored costs would not be the quantity the gate grades.

**Cost sentence, appended to every arm** (from `agent-on-real-data.md`,
Execution), byte-identical across arms:

```
Every Sharpe you see is net of 5 bps one-way per unit of turnover, 50 bps a year borrow on short notional, and one full day of implementation lag: the signal is computed at the close of day t and the position is held from the close of t+1 to the close of t+2.
```

## 2. Arms

Each arm is the control prompt plus the cost sentence plus exactly what is stated
here.

**control** — tools `evaluate`, `submit`. Nothing appended. This is the
unconstrained baseline: the agent searches and submits, and no certifier is
named to it.

**prior-weighted α** — tools `short_list`, `evaluate`, `submit`. Appended:

```
Before your first `evaluate` call you may call `short_list` once, naming up to 5 specifications you believe in for reasons that do not depend on this data. A short list named after any `evaluate` call is refused. Specifications on the list are tested at a more forgiving threshold than the ones you find by searching; anything you submit is admissible either way.
```

The cap of 5 is `prereg/prior-weighted-alpha.md`'s registered cap, read from the
pre-registration rather than written into the agent. The thresholds themselves
(α_prior = 0.04, α_search = 0.01) are **not** stated to the agent: what is
registered is that the list is treated more forgivingly, not the numbers, so the
agent cannot reverse-engineer a decision boundary.

**replay gate** — tools `pick_prior`, `init`, `extend_best`, `swap_worst`,
`flip`, `refine`, `pick`, `stop`, `restart`, `predict`, `submit`, via
`quixote/agent_adapter.py`. `pick_prior` is there by amendment 1. Appended:

```
You do not build specifications yourself. You name a move and the harness performs it: `init` anchors on the best single feature, `extend_best` adds the feature that most improves what you hold, `swap_worst` replaces the weakest one, `flip` reverses the sign of a feature you name, `refine` re-fits the signs, and `pick` chooses among candidates you name by a statistic you name. Each move reports what it did and the Sharpe that resulted.

Before your first move you must call `declare_triggers`, naming the stopping rules you will search under: each is one of `best_so_far_above`, `failures_at_least` or `last_gain_at_most`, with its parameter and whether it stops or restarts. To stop or to restart you then call `stop` or `restart` naming one of those rules. The harness evaluates it on the state of your search and performs the move only if it fires. A rule you did not declare is refused, and a rule that does not fire is refused.

While one of your declared rules is firing, the harness will not perform any further move: it tells you which rule fired and what it licenses, and waits. You then take that move, or change the rule.

You may change a declared rule later with `change_trigger`, naming the new rule and your reason. That is allowed, and it is recorded: a rule chosen after seeing results is a decision about the data, so the rule in force before the change is what your search is replayed under, and every move after the change is reported as not replayable.

Before your first move you may call `pick_prior` once, naming one specification you believe in for reasons that do not depend on this data, with your reason. A `pick_prior` named after any move is refused.

The statistic a `pick` names must be one of `sharpe`, `volatility`, `autocorr_1`, `autocorr_5`, or `corr_with_best`. Anything else is refused.
```

The trigger list in the prompt is the library in `quixote/triggers.py` and is
generated from it in the test, so prompt and library cannot drift.

**replay gate (reasoned pick)** — tools as the replay gate. Added by amendment 3
for 7.3's fidelity measurement, which has no data without picks. Appended after
the replay block:

```
At least once during your search, use `pick`: name the candidate features you are choosing between, name the statistic that decides among them, and state in one sentence why that statistic is the right one for that choice. The harness will perform the rule you named and tell you whether the feature you expected is the one it selected.
```

**orientation** — tools as the replay gate. Added by amendment 6 for
`prereg/agent-cell.md`'s orientation arm. The replay block, then this paragraph,
which is delivered with the table already substituted into it:

```
Before you begin, here is a summary of the structure of the features you will be working with. It describes the features only: it contains no information about returns, and nothing in it says which features predict anything. Reading it costs you nothing — it is not an evaluation, it does not count against anything, and no part of your search has started yet. Take as long over it as you find useful.

{orientation_table}
```

**declared-class gate** — tools as control. Nothing appended, and the gate is
not described to the agent. It is a certification route applied by the harness
after the run, not an arm the agent can see, so its prompt is byte-identical to
control's; the two differ only in what is done with the submission.

### What the arms cannot tell apart, and why it is stated here

**The replay arm's tool surface is not control's.** A grammar arm names moves; a
control arm builds specifications. So any difference in *search behaviour*
between them — depth reached, number of evaluations, submitted Sharpe — is
confounded with the surface and **is not evidence about the certifier**. Two
consequences, fixed now:

- the certifier comparison at matched search behaviour is `gate-comparison`'s
  (7.0) job, on scripted searchers where the search is held fixed by
  construction;
- what the replay arm here measures is whether a **model-driven** search can be
  certified by process replay at all — its engagement with the grammar, its
  refusal rate, and the verdict — not whether replay beats the class gate.

Any write-up that reads an arm difference as a certifier difference is reading
this design wrong, and this paragraph exists to be cited against it.

## 3. Pinned values

- Model string: `claude-sonnet-5`. A run whose usage log reports any other
  string is excluded from analysis and noted.
- Extended thinking: off. Default sampling settings.
- Declared class: **signed subsets of size ≤ 3**, fixed by run config and opened
  by the harness. Not an agent tool, on the same grounds as
  `AGENT_PROMPTS.md` §3: the class must be fixed before anything is seen (THEORY.md P3).
- `max_turns = 60`. A run that reaches it without submitting is recorded as
  `no_submit` and kept in the run count.
- `evaluate` returns the net in-sample annualised Sharpe and the number of
  observations, as one line. A grammar move returns one line: what the move did,
  the resulting support in masked labels, its Sharpe, the best so far, and the
  number of candidates the harness considered.
- Out-of-sample data is held by the sandbox and exposed by no tool. The agent
  runs with `tools=[]` and `setting_sources=[]`, as `searchers/llm_agent.py`
  records, so there is nothing on disk to read either.
- The panel is fixed before the first run and is the same panel for every run of
  an arm.

## 4. Masking: opaque labels and four structural fields

**This resolves the masking question `prereg/twin-calibration.md` left to 7.4,
and fixes it for every real-data arm.** The tension recorded there is that
memorised history breaks exchangeability, while a theory-driven `pick_prior`
needs to know something about the instrument. The resolution:

- **Every instrument is an opaque label** — `A000`, `A001`, … — assigned by a
  seeded permutation, so the labels carry no ordering either. No ticker, name,
  ISIN, exchange, country or date range crosses the mask.
- **Exactly four structural fields may cross**, and no others:
  `has_home_market`, `home_close_et`, `sector`, `liquidity_band`
  (`Masking.ALLOWED_FIELDS` in `quixote/twins.py`, which **refuses** metadata
  carrying anything else rather than filtering it).
- **A field that does not apply to a panel is absent, not null.** On an ETF
  panel `has_home_market` and `home_close_et` are meaningless and are omitted; on
  the ADR panel all four are populated. An omitted field is not evidence about
  the instrument.
- **The mapping back is the harness's.** `Masking.unmask` exists for grading and
  is not reachable from any tool; the agent-facing view holds no reverse map.
- **Dates are masked too**: the agent sees period indices, not calendar dates, so
  a remembered market event cannot be located in the panel.

**What this costs, stated rather than discovered later.** A theory-driven prior
over *named* instruments is impossible under masking, by design. What remains
possible is a prior over structure — "cross-sectional reversal is stronger in
instruments whose home market has already closed" is expressible through
`has_home_market` and `home_close_et` without knowing which instrument is which.
If an arm's engagement with `pick_prior` or `short_list` turns out to be zero,
masking is the first suspect and the result is reported as such rather than as a
finding about priors.

**Feature names are not masked.** The features are the researcher's own
constructions, committed in the feature-list commit, and their names (`ret1_z`,
`vol20_rank`, …) describe arithmetic rather than identity. Masking them would
make a reasoned `pick` impossible while hiding nothing an agent could memorise.

**The contaminated feature.** `agent-on-real-data.md` records that the
researcher observed `ret1_z`'s in-sample statistic on 2026-09-24, which makes a
**human**-declared specification involving `ret1` inadmissible for the short
list. **The agent's declarations are unaffected**, for the reason recorded
there: the agent never saw that number, and its short list is declared inside its
own session before its first `evaluate`. Nothing in these prompts mentions
`ret1`, and the prompts are checked for that by test.

## 5. What is deliberately absent

- **No arm tells the agent its own statistic's null distribution**, a critical
  value, or a p-value. `AGENT_PROMPTS.md`'s `gate` and `pushed` arms do that on
  the simulated panel; carrying them here would cross two changes at once (real
  data and a new arm) and neither would be readable.
- **No `status` tool.** Same reason.
- **No count and no budget sentence.** Both are deferred in
  `AGENT_PROMPTS.md` and stay deferred here.
- **No twin arm.** `twin-calibration`'s per-dataset twins are reserved for 7.4,
  where the dataset is the question.

## 6. Tests that hold this file to the code

In `tests/test_agent_prompts_real.py`:

1. the control prompt and the cost sentence are byte-identical across every arm
   that uses them;
2. the arm-appended text is exactly what this file states, read from this file;
3. the replay arm's tool list is the adapter's grammar tools, and its trigger
   list is `quixote/triggers.py`'s library, generated from it;
4. no prompt names a certifier's threshold, an α, a p-value or a critical value;
5. no prompt mentions `ret1`;
6. the masked view carries only the four allowed fields and no identifier, and
   the reverse map is unreachable from the tool surface.

## 7. Amendments

Dated entries are appended here; nothing above is edited after the first run.

**1 — 2026-09-24, before any model-backed run on any real panel. `pick_prior`
joins the replay arm.**

`prereg/agent-pilot.md` measures "how many runs use `pick_prior`", and §2's
replay-arm tool list did not contain it, so that measurement had no tool to
read. The tool exists in `quixote/agent_adapter.py` and the session already
refuses a late declaration; only the arm's list and its prompt sentence were
missing. Both are added above, before any run, and the design md5 moves with
them — which is why this is done now rather than after.

**What `pick_prior` can and cannot test on the ADR panel, recorded so a zero is
not over-read.** §4 says that if declaration usage is zero, masking is the first
suspect. That is right for a panel whose instruments the agent can name. On the
**ADR panel it does not apply**: a specification is a combination of *features*,
no tool exposes an asset label or a calendar date, and the feature names are
arithmetic (`ret1_home_open`, `rel3_home_closed`). So masking constrains nothing
an agent could act on there, and a zero on that panel is evidence about the
prompt or the model, **not** about masking. On a panel where instruments are
nameable, §4's reading stands unchanged.


**2 — 2026-09-24, after the first pilot attempt and before its re-run. The
`pick` statistic library is named in the prompt.**

§2's replay block names the trigger library explicitly but said only "a statistic
you name" for `pick`. An agent in the first pilot attempt supplied prose — "in-sample
Sharpe with [1+,0+,x]" — and the harness refused it, so `pick` was attempted once in
five runs and never succeeded. That is `prereg/agent-pilot.md` rule 2's branch: the
prompt is the suspect, not the model.

The block above now names the five statistics of `quixote/statistics.py`, exactly as
it already names the three triggers, and a test generates the list from the module so
the two cannot drift. **IC stays absent**, as `quixote/statistics.py` records: it needs
the panel a replicate does not have.


**3 — 2026-09-24, before any 7.3 run. A fourth arm, because fidelity has no data
without picks.**

`prereg/agent-pilot.md`'s reading records that **`pick` was used in 0 of 5 runs**
once the harness allowed it and the prompt named the statistic library. The
replay arm's prompt *permits* a reasoned choice; it does not *ask* for one, and
five runs chose simpler moves.

ROADMAP 7.3's fidelity measurement re-presents a **single decision** to the agent
about twenty times with resampled numbers and records how often the declared rule
predicts the choice. Its unit of analysis is a `pick`. With no picks there is
nothing to re-present, so 7.3's agent cell would measure fidelity on an empty
sample.

**The arm above is registered now**, before 7.3 is written, so that the
requirement precedes the design rather than being added once the cell comes back
empty. Its sentence asks for one `pick` with a named statistic and a stated
reason; it names no statistic in particular, so which rule the agent chooses is
still the agent's. **7.3's fidelity cell runs this arm**, and a 7.3 that reports
fidelity from any other arm has to say why.

**What it costs, recorded:** an arm that asks for a move is not the arm that
merely permits one, so the pilot's engagement numbers do not transfer to it, and
a `pick` made because the prompt asked is weaker evidence about what an agent
would do unprompted than one made freely. Both readings are available, because
the plain replay arm stays in the file unchanged.

**4 — 2026-09-24, before the next pilot re-run. Triggers are declared before the
first evaluation, with a priced exception.**

`prereg/agent-pilot.md` attempt 4 found that **two of three runs declared a stop
rule their own search does not satisfy**: both named `best_so_far > 100`, both
passed 100 at their second move, and both searched to their tenth. Replayed as a
rule — which is what a declared trigger is — that predicate ends the search eight
moves early, so the identity guard refused the run and nothing could be priced.
The trigger had been named at the moment of stopping: a description offered
afterwards, not a commitment the search ran under, and a log cannot tell those
apart unless the harness separates them.

**The rule, decided.** Triggers join `pick_prior`, `short_list` and
`declare_budget` as declarations fixed **before the first evaluation**, and a
`stop` or `restart` may only fire one already on record.

**The exception, priced rather than forbidden.** An agent may change a declared
trigger mid-search with `change_trigger`. The change is logged with its
timestamp, **the trigger in force before it is what replays**, and every move
after it is recorded as not replayable and reported in the bracket
(`prereg/bracketed-verdicts.md`). A change is a data-dependent decision and is
priced as one; it is not refused, because refusing it would push the same
decision outside the log where nothing can price it.

The block in §2 above states both to the agent. `quixote/session.py` enforces
them (`declare_triggers`, `change_trigger`), and `quixote/agent_adapter.py`
exposes them as tools. A session that declares nothing keeps the old behaviour,
so 7.1's scripted searchers and every log written before today are unaffected.

**5 — 2026-09-25, before the next pilot re-run. A firing rule stops the search
until the agent resolves it.**

Amendment 4 made a declared trigger a commitment on paper. Attempt 5 showed it
was not one in fact: the harness evaluated a declared rule only when the agent
invoked it, while a replay evaluates every declared rule at every step, so a rule
that would have fired early ended the replay where the realized search carried
on, and two verdicts of three were refused by the identity guard for that reason
alone.

**Decided: check and refuse to continue.** Before every content move the harness
evaluates the declared rules. If one fires it **announces which and what it
licenses, and takes no content move** until the agent either performs that move
or calls `change_trigger`. The agent keeps its agency — nothing is done on its
behalf — and every departure from its own rule is priced rather than hidden.

The alternative was to enforce the rule outright, performing the move the trigger
licenses. That makes every log replayable by construction and takes the decision
away from the agent, which is the thing this experiment is trying to observe. It
is recorded here as the option not taken.

**6 — 2026-09-25, committed not live. The orientation paragraph.**

`prereg/agent-cell.md` registers an **orientation arm**: before its first
`evaluate` the agent is handed a summary of the **feature panel's structure and
nothing about returns**, and the question is whether an agent that knows the map
searches better without the gate's false-certification rate moving.

The paragraph is registered verbatim in §2 above. `{orientation_table}` is
substituted with the rendered table from `quixote/orientation.py`, whose builder
takes the feature matrix and has **no parameter through which a return could
arrive**; the delivered table is hashed per run and the hash is stored in the run
config.

**The shared text is byte-identical to the replay-gate arm's**, as §2 requires,
and that identity is a test: the orientation arm is the replay-gate arm plus this
paragraph, nothing else.

**What the paragraph claims, and why each clause is there.** It says the summary
is about features only, that it contains no information about returns, and that
nothing in it says which features predict anything — three statements the
X-only construction makes true, so the agent is not being asked to take anything
on trust that is not enforced in code. It says reading costs nothing, because
orientation consumes no evaluation budget and is not a trial. It does **not**
suggest the summary is useful, recommend a way to use it, or name any feature:
the arm is about whether the agent finds a use, not about being told one.

**Nothing runs on this amendment.** `prereg/agent-cell.md` is committed-not-live,
and its cell 2 exists precisely to measure how much of any effect is the
paragraph rather than the table.