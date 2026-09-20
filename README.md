# observable-garden

**How much of a reported backtest is search rather than signal — and a gate
that turns the answer into a verdict.**

## What it's for

A backtest that looks good may only be the best of many tries. Correcting for
that has been possible since White's Reality Check in 2000, but it needs to
know how wide the search was, and for human research nobody does: the
discarded attempts are never written down.

For an agent, they are. Every specification it evaluates, kept or thrown away,
sits in a log. This project asks what that log licenses you to conclude. It
builds the search's null distribution from the log itself — no assumed
independence, no invented trial count — and wraps it in a tool that returns a
verdict:

| verdict | what it means | exit |
|---|---|---|
| **PASS** | the result clears the bar once the search behind it is priced in | 0 |
| **FAIL** | the search could have certified an edge, and this result did not clear it | 1 |
| **INADMISSIBLE** | the search was too broad to certify anything, so not clearing the bar says nothing | 2 |
| **UNDECIDABLE** | the log alone does not license a correction, because the menu was not fixed in advance | 3 |
| **DEGENERATE** | the statistic broke on this menu, so the critical value measures near-empty resamples | 4 |

The distinction that matters most is FAIL against INADMISSIBLE: one is a real
negative result, the other is a non-result, and conflating them is how a
search that never could have proved anything gets read as evidence of
absence.

Everything is validated against simulated data where the right answer is known
by construction, before any claim about real backtests.

## Quickstart

```
pip install -e .
garden audit --example null_grid     # FAIL          exit 1
garden audit --example real_edge     # PASS          exit 0
garden audit --example overwide      # INADMISSIBLE  exit 2
```

Three bundled searches over moving-average rules on simulated prices: one with
no edge anywhere, one with a real edge, one so broad it could not have
certified an edge if it had found one. Every verdict prints its critical
value, power, and a reason per check, so it can be argued with.

Size a search before running it with `garden preflight`, and audit your own
with `garden audit run.npz`. `garden explain menu` walks through the question
the whole tool turns on: was your candidate list fixed before you saw any
results?

## What it found

- **Searching adaptively breaks the standard correction.** When a search
  builds its next candidate out of its own best result so far, applying the
  Reality Check to the log understates the correction — and the gap widens the
  more candidates there are. In the worst case tested, over a third of
  searches across pure noise clear a nominal 5% bar.
- **It is specifically *chasing winners* that does the damage.** Searches that
  branch from a random or unrelated candidate stay honest. The distortion
  grows with how strongly the anchor tracks performance, along a curve that
  the order statistics predict in advance — and it survives when the
  assumptions behind that prediction are broken, including for trading rules
  whose scoring is not a weighted sum at all, though it is much smaller there.
- **Two repairs hold.** Replaying the search inside each resample, or
  declaring in advance the whole class of specifications it could have
  produced, both stay correctly calibrated everywhere they have been tested —
  including moving-average rules, which cannot be written as sums of anything
  and so defeat the first repair entirely. The second needs no re-execution,
  only an honest declaration, and it is conservative: it buys validity at some
  cost in power.
- **Declare the tightest class your searcher's grammar can actually reach.**
  Most of the second repair's cost in power turns out to be class mismatch
  rather than conservatism. Moving `Adaptive` from the 10,700-member class it
  can reach to the 82,240-member signed class it cannot took its actual size
  from the neighbourhood of nominal down to 1.35% at a nominal 5% — while a
  searcher that submits the maximum of its declared class comes in exactly
  calibrated, and searching sub-optimally *within* a reachable class costs
  almost nothing.
- **Breadth is not free, and a lucky pass is worse than no pass.** Holding the
  reported result fixed, every extra specification makes an edge harder to
  certify. Results that scrape past an underpowered search overstate the edge
  badly, so the gate refuses to certify rather than handing back a number that
  flatters.
- **The Sharpe ratio itself is fragile here.** Over rules that rarely trade,
  resampling can make the statistic explode, and the correction then measures
  near-empty resamples rather than the breadth of the search. The gate detects
  this and refuses.
- **Correcting by an "effective number of trials" double-counts.** Shrinking
  the trial count for correlation, when the closed-form deflated Sharpe
  already absorbs it, leaves real overfitting standing.
- **One case makes the size of the problem concrete.** With uncorrelated
  trials and a thousand of them, a search reports a Sharpe of **2.03** —
  double what the data-generating process can actually deliver — when the
  truth is **0.21**. Reading nothing but the transcript, the bootstrap calls
  that decay to within **0.017**.

The first three are plotted in `figures/`: `headline_breadth.png` (the
correction degrading as the candidate set widens), `headline_anchor_rank.png`
(inflation tracking how closely the search follows its own winner, against a
prediction fixed beforehand) and `headline_dose_response.png` (the same effect
as the search narrows around its own results). Regenerate them with
`python -m experiments.plot_headline_figures`.

Every number, caveat and diagnostic behind these is in **`SCOPE.md`**; the
propositions and proofs are in **`THEORY.md`**; each experiment was
pre-registered before it ran; EXPERIMENTS.md gives the commit.

## Relationship to prior work

The verdict engine is White's Reality Check (2000). That correction is
twenty-six years old and is the right tool; nothing here replaces it. What
this project adds sits inside that framework:

- **Where a logged transcript is enough.** White's asymptotics hold the
  specification set fixed as the sample grows, while treating those
  specifications as the products of a search. They do not say what "fixed"
  requires when the specifications were themselves chosen from the evaluation
  data. This project makes that condition explicit — the menu must be
  data-oblivious — shows what fails without it, and supplies two repairs that
  restore validity when it does not hold.
- **Sizing a search before running it.** A pre-flight power calculation tells
  you, in advance, whether the breadth you intend can certify anything at all.
  Most of the searches that return INADMISSIBLE should never have been run at
  that width.
- **The case the correction could not reach.** An instrumented sandbox for
  searchers whose trial count is observable for the first time: an agent's
  every evaluation, kept or discarded, is in a log.

`SCOPE.md`, Prior art, places this against Sullivan–Timmermann–White (1999), Hansen
(2005), Romano & Wolf (2005) and the deflated Sharpe ratio literature.

## How it works

A search evaluates candidates against a sandbox that logs every return stream,
used or not, then submits one. The estimator imposes the null by demeaning
every logged column, resamples one time index across all of them jointly so
their correlation is preserved, and reads off the distribution of the best
result such a search would produce with nothing to find.

**What the null says.** By default it is *zero return*: the verdict asks
whether the result beats not trading, once the search is priced in. It does
not ask whether the result beats owning the asset. On a long-only grid over a
rising market that distinction decides the verdict — a rule can clear a
breadth-corrected bar on the benchmark's own return, with no timing edge at
all. Pass `--benchmark series.csv` to `garden audit` and the series is
subtracted from every logged column before demeaning, making the null *zero
excess return over a declared benchmark*. `garden preflight --benchmark` sizes
a search against the same question and checks the series length against
`--periods`. A benchmark cannot be combined with a class enumerated from
`base_returns`, where a specification is a weighted sum of features: the gate
refuses rather than deduct the benchmark once per feature.

The correction is valid whenever the candidate list was fixed before any
results were seen. When it was not, the log alone cannot say what the search
*would* have tried on other data — hence UNDECIDABLE, and the two repairs
above.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Layout

```
garden/         the gate: transcript format, audit, preflight, explain, CLI
environments/   simulated data, the sandbox contract, price worlds
searchers/      scripted, dose-response, crossover and diagnostic searchers
estimator/      naive, recursive and procedure-level bootstraps; closed-form baseline
experiments/    one module per experiment, named in EXPERIMENTS.md; parallel runner
prereg/         the agent-arm design, and any experiment not yet reported
cloud/          EC2 setup and detached-run scripts
tests/, figures/
```
