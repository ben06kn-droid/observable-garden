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

SCOPE.md, Sparse strategies: Sharpe re-estimated in every replicate is fragile when a menu
contains rules that rarely trade. Detection and refusal belong in v1. Whether
the gate should also offer a statistic whose denominator cannot collapse,
White's mean return or Hansen's studentization by a full-sample standard
deviation, is a v2 question; Phase 2's SPA will answer part of it.

The detection thresholds are not finished either. degeneracy-recalibration chose a support
threshold of 50, the largest value in its pre-registered grid, so a larger
one might separate broken from sound critical values slightly better.
Testing that needs a new run on fresh seeds, and it is deliberately not
being pursued before SPA.

## Search-level power

The gate prints power for a single pre-specified strategy. That is neither
an upper nor a lower bound on the power of the search that produced the
transcript (SCOPE.md, The cost of breadth): a search too narrow to reach the edge detects
less often, one broad enough to reach specifications carrying it detects
more often. Which applies depends on where the edge sits in the menu, which
a transcript does not reveal. Open: whether any transcript-only estimate of
search-level power exists.

## How should the winner-chasing audit combine anchors across rounds?

anchor-rank (SCOPE.md, Winner-chasing) settled the single-anchor question. Naive inflation
follows the anchor's rank along the Gaussian-limit curve: flat across the
top two ranks, falling through rank 5, and slightly conservative below. Mean
κ is a poor summary of that curve. What is untested is a search with several
data-dependent rounds, some anchored high and some low: whether their
effects on the naive test add, or whether one inflating round dominates. The
curve itself is measured only at K=20, ρ=0.3 and depth 2, with exchangeable
features. feature-count found the winner rule's inflation growing with K at both
correlations tested (SCOPE.md, Winner-chasing); other ranks across K are
untested. The correlation-based neighbor rule was tested under heterogeneous
correlation in unequal-correlation arm (b) (SCOPE.md, Winner-chasing): the recursive bootstrap
stayed calibrated as the correlations separated, but separation was partial
(anchor stability 0.192 against 0.088),
which turns out to be the harder case rather than the easier one. Under exact
ties the recursive bootstrap now has a sketch (THEORY.md P6): the anchor is
asymptotically independent of the Sharpe vector, and non-winners are
exchangeable, so the submitted value has the limit law of a random anchor and
the replicate's bias about the anchor's *identity* does not bias the value's
law. Partial separation breaks both premises at once and has no argument, only
the measurement that it stayed calibrated. Formalizing the sketch, and finding
an argument for the separated case, are the two open tasks.

## Does re-anchoring at depth inflate a little?

At depth 3, a search that picks its round-2 anchor at random still builds
round 3 on its round-2 winner. search-depth (SCOPE.md, Winner-chasing) registered this as not
detectably inflated: 5.3% naive type-I at n=1,000, below the 6.9% that test
could detect. An independent draw of the same rule gave 6.4%. Within both,
the naive p-value was at most the recursive one on 99.9% of draws. A
one-point inflation is plausible; resolving it needs about 3,000 draws per
rule for 80% power against 6%. It affects how the note words depth, not the
gate, which treats any adaptive search without a declared class as
UNDECIDABLE.

## Is the gap between adaptive-powered and search-depth for Adaptive real?

adaptive-powered measured Adaptive's naive type-I at 13.6% (K=25, M=60, T=600, block length
chosen on the transcript). search-depth measured 9.2% (K=20, M=50, T=500, block length
chosen on the base columns). Both runs had n=500. scoring-rule ruled out the scoring
rule (SCOPE.md, Winner-chasing).

A rough calculation, not a test, suggests most of the rest may not be real:

- In the Gaussian limit, for depth-3 greedy search at ρ=0.3, going from K=20
  to K=25 raises naive type-I from 10.5% to 11.6%, about 1.1 points.
- The remaining 3.3 points are small against the sampling error of two n=500
  rates, whose difference has a standard error of about 2.0 points. That is
  roughly 1.6 standard errors.
- M and T do not enter the limit model, so any effect from them would be a
  finite-sample one. The block-length rule is the one candidate the limit
  model says nothing about.

The economical reading is a small K effect plus noise, with M, T or the
block-length rule contributing at most something modest. If it is worth
closing, the single most informative run is search-depth's configuration with adaptive-powered's
block-length rule. The note avoids the question: it reports only oblivious-calibration's
configuration, and adaptive-powered stays in SCOPE.md with its labels.

## Why do the two class nulls disagree on about 1.5% of draws?

non-additive-scoring (SCOPE.md, Winner-chasing) ran the declared-class test two ways on identical draws:
the stationary bootstrap the gate actually uses, and the class maximum on the
same circular shifts as the procedure-level null. Their rejection decisions
agreed on 98.2% and 98.9% of draws, against a pre-registered threshold of
99%, so that clause failed in both worlds.

Most disagreements are borderline — a median of 0.019 from α, balanced in
direction, so neither null systematically rejects more — and the shift null is
the coarser object, carrying about 489 distinct p-values against the
bootstrap's 1,070. But a handful of disagreements sit far from α (out to 0.25
and 0.62), and those are not explained by boundary effects or resolution. The
two constructions differ in more than granularity, and the pre-registration
assumed they would track each other more closely than they do. Worth knowing
which is closer to the truth before the gate's bootstrap path is relied on for
a class supplied this way.

## Classes that cannot be enumerated from base returns

Transcript format v2 registers one class, equal-weight feature subsets up to
size d, because it is the only one whose members can be built from base
returns. Threshold and lookback grids, like non-additive-scoring's, are not sums of base
columns. A v3 `spec_class="explicit"`, where the supplier provides returns for
the whole class directly, would give such searches a valid full-class verdict
(the Sullivan–Timmermann–White setup). Everything else stays "none", which is
UNDECIDABLE unless a rerun is provided.

## The degeneracy check on the full-class path

On the full-class path, the degeneracy check (SCOPE.md, Sparse strategies) still runs on the
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

## garden watch and explicit classes

**Scheduled as ROADMAP.md 6.4; no longer open.** `watch` prices its bar from a
`SubsetClass` and rejects `ExplicitClass` at open, so an agent whose tool grammar
emits rules rather than equal-weight feature subsets cannot be watched. `audit`
already prices such a class from the supplied `class_returns` and `transcript`
already checks membership by spec id, and the tier argument — the bar is fixed
before any evaluation, and nothing inside the class moves it — does not depend on
which kind of class it is.

## watch's chase rate cannot separate winner-chasing from enumeration order

`garden/watch.py` warns on the chase rate: the fraction of a trailing window
whose candidate support contains the best-so-far's support. It separates the
cases it was built for — a search that always extends its running best scores
exactly 1, a random-anchored one about 1/K, and enumerating singles exactly 0.

It also fires on searches that are not chasing at all. Containment follows from
enumeration order alone: a lattice walked in `itertools.combinations` order emits
every subset before its supersets. Measured across four seeds at K=8,
`LatticeAdaptive` scores 0.4–0.6 and tripped the warning on two of them, despite
generation that is oblivious by construction — it is oblivious-calibration's control for precisely
that property, and `round1_beam` returns the whole feature set with no reference
to realized data.

The warning is informational and never touches the verdict, so this costs
nothing but a misleading label. Two routes if it is worth fixing: require the
chase to be *informative*, counting a step only when the contained best-so-far is
itself high-ranked among evaluated specs (folding κ's rank idea in without
reusing the name); or report the excess over the chase rate the same menu would
show under a shuffled evaluation order, which is zero by construction for any
oblivious enumeration but is heavier to pre-register.

## garden watch is coupled to whatever can build a Sandbox

`watch.open` takes a configured `Sandbox` rather than a base-return matrix,
because `Sandbox.evaluate` computes `x_in @ weights` across assets and needs the
full `(T, M, K)` panel; a `(T, K)` matrix of per-feature returns cannot
reconstruct one. That is the honest signature, but it means watch can only be
pointed at data something can turn into a `DGPData`-shaped panel.

For real data that is a panel loader, which is the public-data notebook's job.
Until one exists, watch runs on simulated panels only — a scope limit of the
entry point, not of the method.
