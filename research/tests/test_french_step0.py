"""French step 0's comparison helpers on synthetic arrays (the script is not run here)."""
import datetime as dt
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import french_step0 as S


def test_feature_diffs_measure_z_and_count_rank_entries():
    names = ["a_z", "a_rank", "b_z", "b_rank"]
    rng = np.random.default_rng(0)
    A = rng.standard_normal((50, 6, 4))
    B = A.copy()
    B[3, 2, 0] += 2e-10                       # a z difference
    B[7, 1, 1] = -B[7, 1, 1] + 1              # two rank entries differ
    B[9, 4, 3] += 0.5
    fd = S.feature_diffs(A, B, names)
    assert fd["z_max_abs"] == pytest.approx(2e-10, rel=1e-6)
    assert fd["rank_differing"] == 2 and fd["rank_total"] == 50 * 6 * 2


def test_refit_diffs_count_penalty_and_stack_changes():
    ref = [{"year": 3, "penalties": [1, 3, 10, 1e6], "stack_weights": [0.5, 0.2]},
           {"year": 5, "penalties": [3, 3, 3, 3], "stack_weights": [0.4, 0.1]}]
    new = [{"year": 3, "penalties": [1, 3, 10, 1e6], "stack_weights": [0.5, 0.2 + 1e-12]},
           {"year": 5, "penalties": [3, 1, 3, 3], "stack_weights": [0.41, 0.1]}]
    assert S.refit_diffs(ref, new) == {"refits": 2, "penalties_differ": 1, "stack_weights_differ": 1}


def test_tolerances_against_the_read_values():
    fd = {"z_max_abs": 5e-10, "rank_differing": 246, "rank_total": 2_465_680}
    t = S.tolerances(fd, {"member_2937": 0.6794, "ridge_stack": 0.5476})
    assert t == {"z_max_abs": True, "rank_entries": True, "sharpe_member_2937": True,
                 "sharpe_ridge_stack": False}
    fd["rank_differing"] = 247
    assert not S.tolerances(fd, {"member_2937": 0.679, "ridge_stack": 0.547})["rank_entries"]


def test_a_panel_reaching_2020_is_refused():
    ok = SimpleNamespace(meta={"earned_dates": [dt.date(2019, 12, 31)]})
    S._guard(ok)
    bad = SimpleNamespace(meta={"earned_dates": [dt.date(2019, 12, 31), dt.date(2020, 1, 2)]})
    with pytest.raises(SystemExit, match="holdout"):
        S._guard(bad)


def test_the_member_is_2937s_support():
    assert S.MEMBER_2937 == ((28, 1.0), (29, -1.0)) and S.READ_SHARPE == {"member_2937": 0.679, "ridge_stack": 0.547}
