"""garden explain: the methodology and citations behind each verdict path."""
from __future__ import annotations

MENU = """\
Is your candidate menu data-oblivious?

  Did you decide the full set of specifications to evaluate before seeing
  any of their results?
    yes -> oblivious. A seeded random subsample of a fixed grid still
           counts, as long as the seed wasn't picked after looking.
    no  -> Did any result change what you tried next (refining around a
           winner, dropping a losing feature, adding a filter after seeing
           a drawdown)?
             yes      -> adaptive.
             not sure -> unknown. The gate treats it like adaptive.

  A pre-declared grid run in one batch is oblivious, however large.
  A person or agent iterating in a notebook is almost always adaptive.

  Why it matters: the Reality Check treats the set of evaluated
  specifications as fixed. That is exactly true for an oblivious menu,
  at any trial count and any correlation. For an adaptive menu the gate
  returns UNDECIDABLE; see `garden explain undecidable`."""

REALITY_CHECK = """\
The verdict engine is White's Reality Check (White 2000). Every evaluated
specification's return stream is demeaned, imposing the null that none of
them has an edge. The time index is resampled with the stationary bootstrap
(Politis & Romano 1994), using one shared index for every specification so
their correlation is preserved, and the largest Sharpe ratio is recorded in
each replicate. The p-value is the share of replicates whose maximum
reaches the reported Sharpe: the probability that a search of exactly this
shape, over data with nothing to find, produces a best result this good.
The critical value is the Sharpe the reported result must exceed for
p < alpha, printed so the verdict can be checked by eye.

Because specifications are resampled jointly, correlated or duplicated
trials are not over-penalized and no "effective number of trials" is
needed. The correction is valid for any trial count and correlation
structure provided the menu was fixed before results were seen (`garden
explain menu`). It corrects for search breadth only: trading costs, regime
change and look-ahead bias also cause out-of-sample decay and are not
checked.

  White, H. (2000). A Reality Check for Data Snooping. Econometrica 68(5).
  Sullivan, R., Timmermann, A. & White, H. (1999). Data-Snooping, Technical
    Trading Rule Performance, and the Bootstrap. Journal of Finance 54(5).
  Politis, D. & Romano, J. (1994). The Stationary Bootstrap. JASA 89(428).
  Hansen, P.R. (2005). A Test for Superior Predictive Ability. JBES 23(4).
    A higher-powered successor, not yet implemented here."""

INADMISSIBLE = """\
INADMISSIBLE means the search could not have certified a result even if one
existed. The gate asks how often a specification whose true Sharpe equals
the reference would clear this search's critical value, using the submitted
specification's own bootstrap distribution of Sharpe ratios shifted to the
reference, so the data's autocorrelation and tails carry through. When that
power is below the floor (default 20%), not clearing the bar is
uninformative, and the verdict says so instead of reporting FAIL.

The mechanism is unavoidable: holding the reported result fixed, every
added specification makes the null maximum larger, so power falls as
breadth grows. In this project's pinned-selection experiment, power against
a true Sharpe near 1.0 fell from 15% to 6% to 2% as the search grew from 10
to 100 to 1,000 specifications (SCOPE.md §10). The fix is a narrower
search, sized in advance with `garden preflight`. Low power does not weaken
a PASS, because alpha fixes the false-positive rate, but it inflates the
size of passing effects (type-M error), which the gate flags as a warning.

The power figure is for a single pre-specified strategy: the chance that
one specification whose true Sharpe equals the reference clears the bar on
its own. It is not a bound on search power in either direction. A search
that takes the best of many correlated specifications sharing an edge can
pass more often, because its winning in-sample Sharpe stacks the maximum of
the noise on top of the edge: in the bundled `overwide` example
single-strategy power is 7-11%, yet 6 of 20 data seeds pass, with true
Sharpes of 0.13-0.58 reported as deflated Sharpes of 0.65-1.07. A search too
narrow to reach the edge passes less often: at 10 specifications, search
power ran 0.53 below single-strategy power in this project's matched
comparison (SCOPE.md §13).

  Gelman, A. & Carlin, J. (2014). Beyond Power Calculations: Assessing
    Type S (Sign) and Type M (Magnitude) Errors. Perspectives on
    Psychological Science 9(6)."""

UNDECIDABLE = """\
UNDECIDABLE means the transcript alone does not license a correction. The
Reality Check treats the evaluated specifications as a fixed set. If the
search chose what to try next from what it had already seen, the bootstrap
keeps re-testing the one path the search took on the real data, not the
paths it would have taken on other data. It underestimates the null maximum
and returns p-values that are too small. In this project's experiments a
nominal 5% test rejected 12.7-13.6% of true nulls for adaptive searchers,
rising steadily with how data-dependent the menu was (SCOPE.md §2-5). This
is the post-selection inference problem.

The gate still shows the Reality Check p-value, labeled as a lower bound,
because the direction of the error is known. Three routes lead to a valid
verdict. Sample splitting (search on one period, evaluate only the chosen
specification on a held-out period) needs no correction. The
procedure-level bootstrap re-runs the whole search on data with the
signal-return link broken; it needs only a re-executable search, via
`garden.audit(transcript, rerun=...)`. The recursive bootstrap re-derives
each selection step algebraically and needs specifications linear in a
fixed base set (`estimator.recursive_bootstrap`).

  Leeb, H. & Pötscher, B. (2005). Model Selection and Inference: Facts and
    Fiction. Econometric Theory 21(1).
  Efron, B. (2014). Estimation and Accuracy after Model Selection. JASA
    109(507)."""

POWER = """\
In `audit`, power comes from the data. The gate records the submitted
specification's Sharpe in every bootstrap replicate, centers that
distribution, shifts it to the reference Sharpe, and reports the fraction
landing above the critical value. That keeps the data's own autocorrelation
and higher moments and costs no extra bootstrap. It is power for a single
pre-specified strategy, assuming a rejection would come from that strategy
alone. A real search can detect more often, when it is broad enough to
reach strategies carrying the edge, or less often, when it is too narrow to
reach them (`garden explain inadmissible`).

In `preflight` there is no data yet, so the gate uses Lo's (2002) standard
error for a Sharpe ratio with serially uncorrelated returns, against the
exact null maximum of independent trials, or equicorrelated trials if you
pass --rho. Independence is the worst case, because correlated trials
behave like fewer trials. Autocorrelation widens the Sharpe's standard
error, which preflight does not model. Power depends jointly on the test,
the data and the search; what transfers is the shape (rising with effect
size, falling with breadth), not the exact thresholds.

  Lo, A. (2002). The Statistics of Sharpe Ratios. Financial Analysts
    Journal 58(4)."""

BREADTH = """\
The gate reports an effective breadth: the participation ratio N^2 / sum of
squared eigenvalues of the trial correlation matrix. It equals N for
uncorrelated trials and 1 for exact duplicates, and shows how much of the
search was really distinct. It is never used in the correction.

Plugging an eigenvalue-based effective N into the closed-form deflated
Sharpe ratio (Bailey & López de Prado 2014) counts correlation twice. The
closed form's variance term, the cross-sectional variance of trial Sharpes,
already shrinks as trials correlate, so shrinking N as well under-deflates:
in this project's grid it left up to 0.94 Sharpe of overfitting standing at
ρ=0.3 (SCOPE.md §10). The bootstrap accounts for correlation once, directly,
by resampling trials jointly."""

DEGENERATE = """\
DEGENERATE means the test statistic broke on this menu. The Reality Check
here re-estimates each specification's Sharpe ratio in every replicate. For
a rule that rarely trades, a resample can catch only a few of its active
periods; its standard deviation can then shrink faster than its mean, and
its Sharpe explodes. When those resamples set the null maximum, the critical
value measures near-empty resamples, not the breadth of the search. On one
10,000-rule menu with band filters the critical value ranged from 2.03 to
155 across 20 simulated price paths (SCOPE.md §11).

The gate flags a replicate's maximum as degenerate when that column's
resample holds too few distinct active periods, or its standard deviation
collapses relative to the full sample. It refuses when too large a share of
replicates take their maximum from a degenerate resample, or when excluding
those resamples would change the verdict, and it prints that share on every
audit. Dropping rules because of how often they traded would make the menu
data-dependent, so the remedies are a menu redefined before looking, or a
statistic whose denominator cannot collapse: White's (2000) mean return, or
Hansen's (2005) studentization by the full-sample standard deviation.

  White, H. (2000). A Reality Check for Data Snooping. Econometrica 68(5).
  Hansen, P.R. (2005). A Test for Superior Predictive Ability. JBES 23(4)."""

TOPICS = {
    "menu": MENU,
    "reality-check": REALITY_CHECK,
    "pass": REALITY_CHECK,
    "fail": REALITY_CHECK,
    "inadmissible": INADMISSIBLE,
    "undecidable": UNDECIDABLE,
    "degenerate": DEGENERATE,
    "power": POWER,
    "breadth": BREADTH,
}


def explain(topic: str | None = None) -> str:
    if topic is None:
        return MENU + "\n\nOther topics: " + ", ".join(t for t in TOPICS if t != "menu")
    return TOPICS[topic]
