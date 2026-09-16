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
verdict: **PASS**, **FAIL**, **INADMISSIBLE** (the search was too broad to
prove anything), **UNDECIDABLE** (the log alone is not enough), or
**DEGENERATE** (the statistic broke on this menu).

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
  assumptions behind that prediction are broken.
- **Two repairs hold.** Replaying the search inside each resample, or
  declaring in advance the whole class of specifications it could have
  produced, both stay correctly calibrated everywhere they have been tested.
  The second needs no re-execution, only an honest declaration.
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

The first three are plotted in `figures/`: `headline_breadth.png` (the
correction degrading as the candidate set widens), `headline_anchor_rank.png`
(inflation tracking how closely the search follows its own winner, against a
prediction fixed beforehand) and `headline_dose_response.png` (the same effect
as the search narrows around its own results). Regenerate them with
`python -m experiments.plot_headline_figures`.

Every number, caveat and diagnostic behind these is in **`SCOPE.md`**; the
propositions and proofs are in **`THEORY.md`**; each experiment was
pre-registered in **`prereg/`** before it ran.

## How it works

A search evaluates candidates against a sandbox that logs every return stream,
used or not, then submits one. The estimator imposes the null by demeaning
every logged column, resamples one time index across all of them jointly so
their correlation is preserved, and reads off the distribution of the best
result such a search would produce with nothing to find.

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
experiments/    e1-e20 in the order they ran, with a parallel runner
prereg/         a pre-registration per experiment, committed before it ran
cloud/          EC2 setup and detached-run scripts
tests/, figures/
```
