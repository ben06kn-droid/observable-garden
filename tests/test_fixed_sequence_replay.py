"""The 7.1 driver: its nulls are replay_nulls' nulls, and its smoke prints no rules."""
import numpy as np

from estimator.bootstrap import select_block_length
from estimator.trigger_replay import replay_nulls
from experiments import fixed_sequence_replay as fsr
from searchers.meta_adaptive import registered_71


def test_driver_nulls_equal_replay_nulls():
    """Two implementations of one resampling drift unless held equal. Same seed,
    same block length: nulls 1-3 must be array-equal, for every searcher."""
    seed = fsr.SEED0_SMOKE
    base, ann, se = fsr.panel(seed)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    for s, s_ref in zip(registered_71(seed, se), registered_71(seed, se)):
        s.scoring = s_ref.scoring = "moments"
        realized, n1, n2, n3, engaged = fsr.nulls_for(s, base, S0, L, ann, 6, seed)
        ref = replay_nulls(base, s_ref, B=6, block_length=L, annualization=ann, seed=seed)
        np.testing.assert_array_equal(n1, ref.fixed_sequence, err_msg=s.name)
        np.testing.assert_array_equal(n2, ref.trigger, err_msg=s.name)
        np.testing.assert_array_equal(n3, ref.policy, err_msg=s.name)
        assert realized.score == ref.realized_score
        assert engaged.dtype == bool and engaged.size == 6


def test_smoke_block_is_disjoint_and_cost_report_prints_no_rule_quantity():
    blocks = {"registered": range(fsr.SEED0, fsr.SEED0 + 2000),
              "replication": range(fsr.SEED0_REPLICATION, fsr.SEED0_REPLICATION + 2000),
              "smoke": range(fsr.SEED0_SMOKE, fsr.SEED0_SMOKE + 1000)}
    names = list(blocks)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not set(blocks[a]) & set(blocks[b]), (a, b)
    data = fsr.run(1, fsr.SEED0_SMOKE, 3, None, None)
    text = fsr.cost_report(data)
    for forbidden in ("p_", "reject", "ks", "KS", "differ", "engaged", "rate"):
        assert forbidden not in text, forbidden
    assert "COST ONLY" in text
