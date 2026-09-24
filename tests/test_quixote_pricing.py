"""7.2 part two (c): local-max and fidelity-driven pricing, off until 7.3 licenses them.

The thing to pin is mostly the *absence* of an effect: with the flags off, which
is the default, these rules change no null and no verdict. With a flag on, the
verdict says the pricing is unlicensed and names what would license it.
"""
from dataclasses import replace as dc_replace

import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden.spec_class import SubsetClass
from quixote.certify import certify, three_nulls
from quixote.drivers import stop_when_cleared
from quixote.pricing import DEFAULT, LICENSED_BY, PricingOptions, steps_to_price
from quixote.session import Session


def _session(seed=0, s=0, K=10, T=600, bar=0.5):
    cfg = DGPConfig(M=20, T=T, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    cls = SubsetClass(max_size=K, signed=False)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    sess = Session.on_sandbox(sb, cls)
    stop_when_cleared(sess, bar=bar)
    return sess, cls, sb.base_feature_columns(), float(np.sqrt(cfg.periods_per_year))


def _mark_unreplayable(log, i=1):
    i = min(i, len(log.records) - 1)
    log.records[i] = dc_replace(log.records[i], replayable=False)
    return i


def test_nothing_is_licensed_yet():
    """7.3 has not reported, so nothing licenses either rule."""
    assert LICENSED_BY is None
    assert DEFAULT.local_max is False and DEFAULT.fidelity is False
    assert DEFAULT.enabled is False


def test_the_default_prices_no_step_even_with_an_unreplayable_move():
    sess, cls, base, ann = _session()
    _mark_unreplayable(sess.log)
    steps, reasons = steps_to_price(sess.log, DEFAULT)
    assert steps == frozenset() and reasons == []


def test_the_default_leaves_the_nulls_identical(sub=None):
    """The flags off must be the same computation as before they existed."""
    sess, cls, base, ann = _session(seed=2)
    _mark_unreplayable(sess.log)
    a, _ = three_nulls(sess.log, cls, base, ann, B=80, seed=3)
    b, _ = three_nulls(sess.log, cls, base, ann, B=80, seed=3, pricing=DEFAULT)
    for which in ("fixed_sequence", "trigger", "policy"):
        np.testing.assert_array_equal(getattr(a, which), getattr(b, which))


def test_local_max_pricing_prices_the_unreplayable_step_and_says_it_is_unlicensed():
    sess, cls, base, ann = _session(seed=4)
    _mark_unreplayable(sess.log, 1)
    opts = PricingOptions(local_max=True)
    steps, reasons = steps_to_price(sess.log, opts)
    assert steps == frozenset({1})
    assert reasons and "NOT LICENSED" in reasons[0] and "7.3" in reasons[0]

    v_off = certify(sess.log, cls, base, ann, B=120, seed=6)
    v_on = certify(sess.log, cls, base, ann, B=120, seed=6, pricing=opts)
    assert v_off.locally_priced_steps == () and v_off.pricing_licensed is None
    assert v_on.locally_priced_steps == (1,) and v_on.pricing_licensed is False
    assert any("NOT LICENSED" in r for r in v_on.reasons)
    assert not any("NOT LICENSED" in r for r in v_off.reasons)


def test_a_priced_step_takes_the_best_move_over_the_whole_grammar():
    """The mechanism, checked directly: at a priced step the replay takes the
    argmax over extend, swap and flip, not the logged continuation."""
    from searchers.meta_adaptive import MetaAdaptive
    from quixote.grammar import Grammar
    from quixote.replay import LoggedPolicy
    sess, cls, base, ann = _session(seed=5, bar=1e9)
    priced_records = {1, 2, 3}                     # log record indices
    t = LoggedPolicy(sess.log, cls,
                     locally_priced=frozenset(priced_records)).trace(base, ann)
    assert t.locally_priced == len(priced_records)
    g = Grammar(cls, base, ann)
    anchor, _, _ = g.anchor(0)                     # the loop starts from the anchor
    for rec in sorted(priced_records):
        step = rec - 1                             # record 0 is the anchor
        before = list(t.supports[step - 1]) if step else list(anchor)
        cands = MetaAdaptive._grammar(before, g.K, lambda ns: g.score(tuple(ns)))
        best = max(cands)
        # the step took the local max, or kept its support because the local max
        # did not improve on the best so far
        assert tuple(t.supports[step]) in (tuple(best[2]), tuple(before))


def test_pricing_a_greedy_continuation_is_a_no_op_and_that_is_structural():
    """For a searcher whose continuation is greedy extension the local max IS its
    move: at a greedily reached support a swap cannot beat the best single and a
    flip of an unsigned feature is strictly worse. So the nulls do not move, and
    the flag is not thereby decoration -- it bites on continuations the local max
    does not dominate, which is what 7.3 exercises. 7.1 found the same about the
    fill (`prereg/fixed-sequence-replay.md` amendment 6(c))."""
    sess, cls, base, ann = _session(seed=5, bar=1e9)
    for i in range(1, len(sess.log.records)):
        _mark_unreplayable(sess.log, i)
    off, _ = three_nulls(sess.log, cls, base, ann, B=150, seed=8)
    on, _ = three_nulls(sess.log, cls, base, ann, B=150, seed=8,
                        pricing=PricingOptions(local_max=True))
    np.testing.assert_array_equal(off.policy, on.policy)
    assert np.all(on.policy >= off.policy)


def test_fidelity_pricing_hits_the_kinds_below_the_tolerance_only():
    """7.3's check 2: a move type whose declared rule predicts the agent's choice
    at or below the tolerance is priced locally from its first occurrence."""
    sess, cls, base, ann = _session(seed=1, bar=1e9)
    kinds = [r.move.kind for r in sess.log.records]
    assert "extend_best" in kinds
    opts = PricingOptions(fidelity=True, fidelity_rates={"extend_best": 0.4, "stop": 0.9},
                          fidelity_tolerance=0.5)
    steps, reasons = steps_to_price(sess.log, opts)
    assert steps == frozenset(i for i, k in enumerate(kinds) if k == "extend_best")
    assert "extend_best" in reasons[0] and "NOT LICENSED" in reasons[0]
    # a tolerance below every rate prices nothing
    lenient = PricingOptions(fidelity=True, fidelity_rates={"extend_best": 0.4},
                             fidelity_tolerance=0.1)
    assert steps_to_price(sess.log, lenient)[0] == frozenset()


def test_both_flags_together_price_the_union_and_report_both():
    sess, cls, base, ann = _session(seed=7, bar=1e9)
    _mark_unreplayable(sess.log, 2)
    opts = PricingOptions(local_max=True, fidelity=True,
                          fidelity_rates={"extend_best": 0.1}, fidelity_tolerance=0.5)
    steps, reasons = steps_to_price(sess.log, opts)
    assert 2 in steps
    assert len(reasons) == 2 and all("NOT LICENSED" in r for r in reasons)


def test_no_module_claims_the_conjecture_holds():
    """The conservatism of local-max pricing is 7.3's question. Nothing here may
    assert it, and the module must say who tests it."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "quixote" / "pricing.py").read_text()
    assert "conjecture" in src and "7.3" in src
    for claim in ("is conservative.", "proved", "guarantees"):
        assert claim not in src, claim
