# pivotal-interrogation (item 7): ask the agent only where its answer could change the verdict

**DRAFT — committed but not live.** Authorises nothing. Depends on item 1's
bracket. Prior art not yet searched beyond the note at the end.

## Question

Item 1 returns `DEPENDS_ON_JUDGMENT` when the bracket straddles α, and stops
there. Resolving it by re-running the whole agent under the null costs K full
runs. Can the verdict be resolved by asking the agent only at the decision
points where its answer could change the outcome, and how many calls does that
take?

## The decomposition

For a decision the gate cannot replay, item 1 already computes two values in
every null replicate. Comparing both against the submitted Sharpe sorts every
replicate into exactly three groups:

| group | frozen path | upper bound | share |
|---|---|---|---|
| **already exceeds** | clears | clears | `p_frozen` |
| **cannot exceed** | falls short | falls short | `1 - p_upper` |
| **pivotal** | falls short | clears | `p_upper - p_frozen` |

The agent's counterfactual choice can only matter in the **pivotal** group, so

    true p <= p_frozen + (bracket width) x theta

where `theta` is the fraction of pivotal replicates in which the agent's actual
choice would have cleared the bar. `theta` is estimated by sampling pivotal
replicates: rebuild what the agent would have seen at that decision point, put
the decision to it, and replay the rest of the search with its answer.

**Worked example, verified.** Bracket `[0.02, 0.09]`, pivotal mass 0.07. Sample
40 pivotal replicates; the agent's choice clears in 6.

- `theta_hat` = 6/40 = 0.150
- 95% one-sided upper bound (Clopper–Pearson) = **0.2747**
- bound: `p <= 0.02 + 0.07 x 0.2747` = **0.0392**

which resolves to a pass, for 40 short calls.

**Why the pivotal restriction is what makes it cheap.** Bounding the switching
rate uniformly over *all* replicates gives, from zero switches in `n`
presentations, an upper bound near `3/n` (the rule of three). With
`p_frozen = 0.02` and α = 0.05 that needs **n > 100**; with `p_frozen = 0.04` it
needs **n > 300**. Both figures are correct for their case — the cost of the
uniform route scales with how close `p_frozen` already is to α, and the earlier
"roughly 300" corresponds to the harder case. The pivotal route's cost instead
scales with the **bracket's width**, i.e. with how much the verdict actually
rests on judgment. A tight bracket costs nothing; a bracket lying wholly on one
side of α costs nothing.

**Several judgment decisions in one run.** A sampled replicate is walked forward:
the harness executes every rule-based move, the agent is called only at the
judgment points, and each context is built from the path so far. It is a sparse
re-run — code reproduces everything code can reproduce, and the model is
consulted only where it is irreplaceable.

## The assumption, and how it is checked

**The assumption is that the agent asked again behaves like the agent in the
original session.** Twin calibration does not need this; this does.

The rebuilt context is a **synthetic transcript**: the same prompts and tool
calls with the replicate's numbers substituted. The agent's original free-text
reasoning cannot be regenerated for a world that never happened, so **the
template is fixed in advance: tool calls and results only, reasoning stripped.**

Two checks keep it honest.

- **Self-consistency.** Present the real context again several times and record
  how often the agent reproduces its realized choice. This measures the
  decision's intrinsic randomness. **Intrinsic randomness does not break the
  bound**, because pivotal replicates use the agent's actual answer, random or
  not.
- **Twin validation.** On pure-noise runs that have twins, p-values produced this
  way must come out calibrated. **Twins are exact, so they can audit this method;
  this method cannot audit twins.**

## Caveats, registered

- **Conservative grouping.** Replicates in "already exceeds" stay counted even
  though the agent might have switched to something worse. The result is a
  **bound, not an estimate**. Sampling that group too would give an unbiased
  estimate at roughly double the calls, and is not registered.
- **Error budget.** The confidence level on `theta` is charged against α:
  **test at 0.045 with a 0.005 allowance**, registered here.
- **The upper end.** `p_upper` is the **class maximum** until 7.3 confirms the
  local-max conjecture, per item 1.

## Decision rules

1. **Coverage on a scripted judgment searcher (primary).** A scripted searcher
   with a **hidden rule** standing in for judgment, so that full policy replay
   gives the true p-value. Over draws, the bound must cover the true p-value on
   at least 95%. *Read one-sided on the lower Wilson end of coverage; passes
   0.9749 for a correct procedure at n = 2,000.*
   - *Holds:* the bound is sound and its tightness can be reported.
   - *Fails low:* the bound is not a bound. The likely cause is the context
     template changing the agent's decision, which the self-consistency check
     measures. Halt.
   - *Fails high (coverage far above 0.95):* the bound is loose; reported as
     the cost of conservative grouping, not as a defect.
2. **Tightness, reported not gated.** Distribution of `bound − true p`, and the
   share of `DEPENDS_ON_JUDGMENT` runs the method resolves.
3. **Call cost, reported not gated.** Calls per resolved verdict against bracket
   width, to check the claimed scaling.

## Where it sits

An escalation ladder:

| step | cost | exactness |
|---|---|---|
| item 1's bracket | free, always computed | bounds, assumption-light |
| **pivotal interrogation** | tens of calls, only when the bracket straddles α | bound, needs the context assumption |
| item 5's twins | K full runs | exact under exchangeability |

It also produces a behavioural number that stands alone: **in the worlds where it
mattered, how often the agent's judgment followed the data.** That connects
directly to this project's original question about whether agents discount for
their own search.

## Cost

Tens of agent calls per judgment decision, against $0.268 per full run measured
across 661 stored runs. A short single-decision call is a fraction of that; **not
sized**, and sizing needs a smoke on the real template before any go.

## Prior art

Not searched for this item. The nearest neighbour known from the earlier search
is Miao, Pritchard & Zou's agentic bootstrap (arXiv:2607.01507), which re-runs
agents **wholesale on fixed data** rather than querying them at decision points
under a resampled null. No novelty claim is made here.
