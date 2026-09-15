# Open questions

Logged rather than pursued. The gate certifies one thing well; these are
the places where improvising would be worse than saying no.

## Certifying more than one specification

The gate certifies a single submitted specification. "Which of these
specifications beat the null" is a stepwise multiple-testing problem
(Romano & Wolf 2005, *Stepwise Multiple Testing as Formalized Data
Snooping*, Econometrica 73(4)). It needs its own procedure, and running the
single-specification gate once per candidate is not that procedure.

## Which statistic for menus containing sparse strategies

SCOPE.md §11: Sharpe re-estimated in every replicate is fragile when a menu
contains rules that rarely trade. Detection and refusal belong in v1. Whether
the gate should also offer a statistic whose denominator cannot collapse,
White's mean return or Hansen's studentization by a full-sample standard
deviation, is a v2 question; Phase 2's SPA will answer part of it.

The detection thresholds are not finished either. e14 chose a support
threshold of 50, the largest value in its pre-registered grid, so a larger
one might separate broken from sound critical values slightly better.
Testing that needs a new run on fresh seeds, and it is deliberately not
being pursued before SPA.

## Search-level power

The gate prints power for a single pre-specified strategy. That is neither
an upper nor a lower bound on the power of the search that produced the
transcript (SCOPE.md §13): a search too narrow to reach the edge detects
less often, one broad enough to reach specifications carrying it detects
more often. Which applies depends on where the edge sits in the menu, which
a transcript does not reveal. Open: whether any transcript-only estimate of
search-level power exists.

## Unequal-length return streams

Joint row resampling needs every specification evaluated on one shared time
index. Transcripts where specifications cover different subsamples (rules
with different warm-up periods, assets with different listing dates) are
rejected by the loaders rather than silently aligned. Truncating to the
common window discards data; resampling calendar time and evaluating each
column on its own support changes what "the same replicate" means across
columns. Neither has been validated.
