"""Certification: pricing a logged search against the null 7.1 selected.

**The certifying null is trigger replay** (`fixed-sequence-replay`, read
2026-09-24): the logged search re-executed on each resample with its declared
triggers re-evaluated at every step. Its rejection rate came in at or below
nominal for all six registered searchers, 3.45-4.70% at a nominal 5% and
0.35-0.90% at 1%, so it is valid to certify with; the rates sit *under* nominal
as P2 predicts for a searcher submitting less than its class maximum, and **no
exactness is claimed**.

The other two nulls are computed and reported beside it:

- **fixed-sequence replay** is the bracket's lower end. 7.1's rule 2 licenses
  that: freezing the meta decisions is liberal (+0.0120 at alpha = 0.05 for the
  searchers that stop at a bar), so its p-value is a lower bound on the
  certifying one. This is the field `prereg/bracketed-verdicts.md` left for part
  two, and it is filled in here.
- **policy replay** is exact for a scripted policy and has no agent counterpart;
  it is reported when available as the reference the other two are read against.

**The fill.** Where a replicate runs past the realized length, the declared
triggers still decide, and a step they let continue takes the best one-step
content move over extend, swap and flip. 7.1 measured that move's direction, and
`FILL_NOTE` states it on **every verdict whose replicates used it**.

The upper end of the bracket stays the declared-class p-value and is not
computed here: 7.3 has not confirmed local-max pricing.
"""
from __future__ import annotations

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from estimator.trigger_replay import ReplayNulls
from quixote.pricing import DEFAULT as NO_PRICING
from quixote.pricing import PricingOptions, steps_to_price
from quixote.replay import LoggedPolicy, identity_check
from quixote.verdict import QuixoteVerdict

CERTIFYING_NULL = "trigger replay (fixed-sequence-replay, read 2026-09-24)"

FILL_NOTE = (
    "This verdict's null used the fill: on {engaged:,} of {B:,} replicates "
    "({share:.1%}) the search ran past its realized length and took the best "
    "one-step content move, with the declared triggers still evaluated. 7.1 "
    "measured that move's direction against a width-2 beam: LIBERAL, positive on "
    "1,506 of 1,507 draws where the two differ. It moved no verdict there "
    "(type-I 0.0440 under both nulls at alpha = 0.05, no discordant draws, "
    "McNemar p = 1.0000), so strengthening the fill is optional rather than "
    "required. Continuations stronger than a width-2 beam are untested.")

NO_FILL_NOTE = ("The fill was never used: no replicate ran past the realized "
                "length, so nulls 2 and 3 can only differ by chance in the "
                "bootstrap, not by the fill's choice.")


def three_nulls(log, spec_class, base: np.ndarray, annualization: float = 1.0,
                B: int = 10_000, block_length: int | None = None,
                seed: int | None = None,
                pricing: PricingOptions = NO_PRICING,
                table=None) -> tuple[ReplayNulls, np.ndarray]:
    """Nulls 1-3 for a logged search, plus the per-replicate engagement flag.

    The resampling is `estimator.trigger_replay.replay_nulls`', replicate for
    replicate: the realized search on the columns as they are, replicates from
    the demeaned columns by the stationary bootstrap, one RNG seeded by `seed`.
    `tests/test_quixote_certify.py` holds the two equal. It is repeated here only
    because `replay_nulls` returns scores and this needs the engagement flag too.
    """
    priced, _ = steps_to_price(log, pricing)
    policy = LoggedPolicy(log, spec_class, locally_priced=priced)
    base = np.asarray(base, dtype=float)
    T = base.shape[0]
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0)) if block_length is None else int(block_length)
    rng = np.random.default_rng(seed)

    # With a class table the resampling is over ROWS of the table, and every
    # score - realized and replicate alike - is a lookup into the stored
    # net-of-cost streams (`environments/class_table.py`). Without one the
    # replicate is a resampled base matrix, which is the simulated-panel path and
    # is unchanged.
    def scorers(rows):
        return None if table is None else table.scorer(rows, demeaned=True)

    realized = policy.trace(base, annualization,
                            score_fn=None if table is None else table.scorer(None))
    acts, n = realized.actions(), realized.n_moves
    n1, n2, n3 = np.empty(B), np.empty(B), np.empty(B)
    engaged = np.zeros(B, dtype=bool)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        R = S0[idx, :]
        sf = scorers(idx)
        n1[b] = policy.trace(R, annualization, frozen=acts, score_fn=sf).score
        t2 = policy.trace(R, annualization, meta_steps=n, score_fn=sf)
        n2[b], engaged[b] = t2.score, bool(t2.filled)
        n3[b] = policy.trace(R, annualization, score_fn=sf).score
    return ReplayNulls(fixed_sequence=n1, trigger=n2, policy=n3, block_length=L, B=B,
                       realized_score=realized.score,
                       realized_actions=tuple(acts)), engaged


def certify(log, spec_class, base: np.ndarray, annualization: float = 1.0,
            alpha: float = 0.05, B: int = 10_000, block_length: int | None = None,
            seed: int | None = None, p_declared_class: float | None = None,
            pricing: PricingOptions = NO_PRICING, table=None) -> QuixoteVerdict:
    """Price a logged search against the trigger-replay null.

    A run whose replay disagrees with itself on the un-resampled data is
    **flagged and not priced** (the identity guard), because there is no
    defensible way to price a search whose own replay is not that search.
    """
    guard = identity_check(log, spec_class, base, annualization,
                           score_fn=None if table is None else table.scorer(None))
    if not guard.agrees:
        return QuixoteVerdict(
            status="UNDECIDABLE", alpha=alpha,
            n_moves=log.n_moves, n_candidates=log.total_candidates(),
            reasons=[guard.reason(),
                     "Not priced: the certifying null would be pricing a search that did "
                     "not run."])

    priced, pricing_reasons = steps_to_price(log, pricing)
    nulls, engaged = three_nulls(log, spec_class, base, annualization, B, block_length,
                                 seed, pricing=pricing, table=table)
    p_trigger = nulls.p_value("trigger")
    n_eng = int(engaged.sum())

    v = QuixoteVerdict(
        status="CERTIFIED" if p_trigger < alpha else "FAIL",
        alpha=alpha,
        p_frozen=nulls.p_value("fixed_sequence"),
        p_upper=p_declared_class,
        bracket_source=("lower end: fixed-sequence replay, licensed by 7.1's rule 2 "
                        "(freezing is liberal, +0.0120 at alpha = 0.05); upper end: "
                        + ("the declared-class p-value" if p_declared_class is not None
                           else "not computed, 7.3 has not confirmed local-max pricing")),
        n_moves=log.n_moves,
        n_candidates=log.total_candidates(),
        unreplayable_decisions=tuple(r.move.kind for r in log.unreplayable()),
        certifying_null=CERTIFYING_NULL,
        p_certifying=p_trigger,
        p_policy=nulls.p_value("policy"),
        realized_score=float(nulls.realized_score),
        fill_engaged=n_eng,
        fill_replicates=B,
        locally_priced_steps=tuple(sorted(priced)),
        pricing_licensed=False if priced else None,
    )
    v.reasons.append(
        f"Certified against {CERTIFYING_NULL}: p = {p_trigger:.4f} against alpha = {alpha}. "
        "7.1 measured this null at or below nominal for all six registered searchers "
        "(3.45-4.70% at a nominal 5%); the rates sit under nominal as P2 predicts, and no "
        "exactness is claimed.")
    v.reasons.append(FILL_NOTE.format(engaged=n_eng, B=B, share=n_eng / B) if n_eng
                     else NO_FILL_NOTE)
    v.reasons.append(
        f"Reported beside it: fixed-sequence replay p = {v.p_frozen:.4f} (the bracket's "
        f"lower end) and policy replay p = {v.p_policy:.4f} (exact for a scripted policy, "
        "with no agent counterpart).")
    v.reasons.extend(pricing_reasons)
    v.reasons.append(guard.reason())
    return v
