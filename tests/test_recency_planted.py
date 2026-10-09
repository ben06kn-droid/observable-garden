"""The recency planted runner on a SYNTHETIC pool (no planted seed is used): the long-panel
row draw, the profiles and shifts, the class aggregation to pool rows against the direct
computation, and one task per arm end to end."""
import json

import numpy as np
import pytest

from estimator import recency as Rc
from experiments import recency_planted as P


def test_pool_rows_cover_the_pool_in_blocks():
    i = P.pool_rows(5000, 300, 7, np.random.default_rng(1))
    assert len(i) == 5000 and i.min() >= 0 and i.max() < 300
    runs = np.mean(np.diff(i) % 300 == 1)
    assert 0.8 < runs < 0.9                       # about 1 - 1/7 of steps continue a block


def test_profiles_and_shifts():
    p = {k: P.profile(k, 5040) for k in ("null", "constant", "decaying", "emerging")}
    assert p["decaying"][0] == 1 and p["decaying"][-1] == 0 and p["emerging"][2519] == 0 and p["emerging"][-1] == 1
    rng = np.random.default_rng(2)
    Z = rng.standard_normal((40000, 3))
    V = P.shift("NV40", Z)
    assert np.allclose(V[:30000], 2 * Z[:30000]) and np.array_equal(V[30000:], Z[30000:])
    A = P.shift("NA40", Z)
    assert np.array_equal(A[:30000], Z[:30000])
    rec = A[30000:]
    assert abs(rec.var() - 1.0) < 0.05 and abs(rec.mean()) < 0.03
    lag1 = np.corrcoef(rec[1:, 0], rec[:-1, 0])[0, 1]
    assert 0.3 < lag1 < 0.5                       # (0.3 + 0.09) / 1.18 = 0.33


@pytest.mark.parametrize("seed", [3, 4])
def test_the_class_aggregation_equals_the_direct_computation(seed):
    rng = np.random.default_rng(seed)
    N, n_pool, T, L, Bn = 30, 60, 700, 3, 50
    G = rng.standard_normal((N, n_pool)) * 0.01
    G -= G.mean(axis=1, keepdims=True)
    i = P.pool_rows(T, n_pool, 7, rng)
    agg = P.class_tests(G, i, L, 99, Bn, chunk=7)
    X = G[:, i]
    for cen in ("unweighted", "weighted_superseded"):
        obs, M = Rc.class_null([X[:11], X[11:]], T, L, P.PPY, Bn, 99, P.H, centring=cen)
        S = float(obs.max())
        assert agg[cen]["S"] == pytest.approx(S, rel=1e-10)
        assert agg[cen]["p"] == (1 + int(np.sum(M >= S))) / (Bn + 1)


@pytest.fixture
def fake_pool(tmp_path, monkeypatch):
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    N = len(members_in_order(CLS, 40))
    rng = np.random.default_rng(5)
    G = rng.standard_normal((N, 40)).astype(np.float64) * 0.01
    G -= G.mean(axis=1, keepdims=True)
    BC = rng.standard_normal((40, 40)) * 0.01
    np.save(tmp_path / "G.npy", G)
    np.save(tmp_path / "BC.npy", BC - BC.mean(axis=0))
    np.save(tmp_path / "sd.npy", G.std(axis=1, ddof=1))
    (tmp_path / "manifest.json").write_text(json.dumps({"T_pool": 40, "N": N, "sha256": {}}))
    monkeypatch.setattr(P, "POOL_DIR", tmp_path)
    return tmp_path


def test_one_task_per_arm_records_the_registered_fields(fake_pool):
    for arm, seed in (("N20", 705900), ("C20", 705901), ("NA40", 705902)):
        r = P.one((arm, seed), Bn=20)
        assert r["arm"] == arm and r["T"] == P.YEARS[arm] * 252 and r["block_length"] >= 1
        assert "block_length_last_neff" in r and r["n_eff_rows"] in (3208, 3607)
        assert set(r["stream"]) == ({"unweighted", "weighted", "weighted_superseded"} if arm == "N20"
                                    else {"unweighted", "weighted"})
        assert ("class" in r) == (arm == "N20")
    s = P.one(("N40", 705903), Bn=20, smoke=True)
    assert set(s) == {"arm", "seed", "T", "seconds"} and "class_both_centrings" in s["seconds"]


def test_the_task_lists_and_the_smoke_seeds():
    t = P.tasks()
    assert len(t) == 5200 and len(set(t)) == 5200
    assert {a for a, _ in P.smoke_tasks()} == set(P.SEEDS) and all(705900 <= s <= 705909 for _, s in P.smoke_tasks())
    assert P.refusals("0" * 40)
