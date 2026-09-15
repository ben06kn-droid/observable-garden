# Open questions

## The "no new estimator variants" rule and its carve-outs

The project plan freezes estimator variants after SPA. Two planned additions
are recorded here so the rule stays honest, because neither is a variant: the
full-class null is the Reality Check run on an enumerated matrix of every
specification a declared class contains, and `GumbelAnchored` is a new
searcher, not a new null.

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

## Is the coupling effect graded per anchor, or a step near the top?

E17 (SCOPE.md §16) answered the question across rules: naive type-I rises
with how strongly an anchor rule tracks performance (pre-registered trend
test, p = 0.0001). An exploratory breakdown of the same draws suggests the
inflation comes from anchors among the top few features, while anchors
ranked sixth or lower behave like the loser rule. If so, the winner-chasing
audit should summarize a transcript by how often it anchors near the top,
not by mean κ. Testing that needs anchors fixed at the k-th best single
feature, k = 1, 2, 3, 5, 10, so that rank is set by design rather than
selected by conditioning, on fresh seeds and pre-registered, before the
audit is calibrated. The correlation-based neighbor rule under heterogeneous
correlation is still untested (THEORY.md P6, E19(b)).

## Does re-anchoring at depth inflate a little?

At depth 3, a search that picks its round-2 anchor at random still builds
round 3 on its round-2 winner. E18 (SCOPE.md §17) registered this as not
detectably inflated: 5.3% naive type-I at n=1,000, below the 6.9% that test
could detect. An independent draw of the same rule gave 6.4%. Within both,
the naive p-value was at most the recursive one on 99.9% of draws. A
one-point inflation is plausible; resolving it needs about 3,000 draws per
rule for 80% power against 6%. It affects how the note words depth, not the
gate, which treats any adaptive search without a declared class as
UNDECIDABLE.

## Classes that cannot be enumerated from base returns

Transcript format v2 registers one class, equal-weight feature subsets up to
size d, because it is the only one whose members can be built from base
returns. Threshold and lookback grids, like E20's, are not sums of base
columns. A v3 `spec_class="explicit"`, where the supplier provides returns for
the whole class directly, would give such searches a valid full-class verdict
(the Sullivan–Timmermann–White setup). Everything else stays "none", which is
UNDECIDABLE unless a rerun is provided.

## The degeneracy check on the full-class path

On the full-class path, the degeneracy check (SCOPE.md §11) still runs on the
logged specifications, not on the whole class. A class containing sums of
rarely-trading base columns could have degenerate members the search never
logged. Extending the support screen to class members needs each member's
distinct active periods per replicate, which the moments engine does not
compute.

## Unequal-length return streams

Joint row resampling needs every specification evaluated on one shared time
index. Transcripts where specifications cover different subsamples (rules
with different warm-up periods, assets with different listing dates) are
rejected by the loaders rather than silently aligned. Truncating to the
common window discards data; resampling calendar time and evaluating each
column on its own support changes what "the same replicate" means across
columns. Neither has been validated.
