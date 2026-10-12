"""Round 2's runner on a SYNTHETIC pool (no planted seed): the NAREV40 shift, the class null
under W2 aggregated to pool rows against the direct computation, one task per arm."""
import json

import numpy as np
import pytest

from estimator import recency as Rc
from experiments import recency_planted as P1
from experiments import recency_planted_2 as P2


def test_narev40_shifts_only_the_oldest_rows():
    Z = np.random.default_rng(1).standard_normal((40000, 2))
    Y = P2.shift("NAREV40", Z)
    assert np.array_equal(Y[30000:], Z[30000:]) and np.array_equal(Y[:2], Z[:2])
    assert abs(Y[2:30000].var() - 1) < 0.05
    assert 0.3 < np.corrcoef(Y[3:30000, 0], Y[2:29999, 0])[0, 1] < 0.4


@pytest.mark.parametrize("seed", [2, 3])
def test_the_class_w2_aggregation_equals_the_direct_computation(seed):
    rng = np.random.default_rng(seed)
    N, n_pool, T, L, Bn = 20, 50, 600, 3, 40
    G = rng.standard_normal((N, n_pool)) * 0.01
    G -= G.mean(axis=1, keepdims=True)
    i = P1.pool_rows(T, n_pool, 7, rng)
    agg = P2.class_w2(G, i, L, 77, Bn, chunk=6)
    X = G[:, i]
    w = Rc.weights(T, P2.H)
    pi, q = Rc.w2_pi_q(w, L)
    r = np.random.default_rng(77)
    idx = [Rc.w2_indices(T, L, pi, q, r) for _ in range(Bn)]
    obs = np.array([Rc.weighted_sharpe(x, w, P2.PPY) for x in X])
    M = np.array([max(Rc.weighted_sharpe((x - q @ x)[I], w, P2.PPY) for x in X) for I in idx])
    assert agg["S"] == pytest.approx(obs.max(), rel=1e-10)
    assert agg["p"] == (1 + int(np.sum(M >= obs.max() - 1e-12))) / (Bn + 1)


@pytest.fixture
def fake_pool(tmp_path, monkeypatch):
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    N = len(members_in_order(CLS, 40))
    rng = np.random.default_rng(5)
    G = rng.standard_normal((N, 40)) * 0.01
    G -= G.mean(axis=1, keepdims=True)
    BC = rng.standard_normal((40, 40)) * 0.01
    np.save(tmp_path / "G.npy", G)
    np.save(tmp_path / "BC.npy", BC - BC.mean(axis=0))
    np.save(tmp_path / "sd.npy", G.std(axis=1, ddof=1))
    (tmp_path / "manifest.json").write_text(json.dumps({"T_pool": 40, "N": N, "sha256": {}}))
    monkeypatch.setattr(P1, "POOL_DIR", tmp_path)
    return tmp_path


def test_one_task_per_kind_records_the_registered_fields(fake_pool):
    for arm, seed in (("NA40", 714900), ("NAREV40", 714901), ("E20", 714902)):
        r = P2.one((arm, seed), Bn=15)
        assert set(r["stream"]) == {"W2", "R15", "fixed", "unweighted"}
        assert ("class" in r) == (arm in P2.CLASS_ARMS) and r["T"] == P2.YEARS[arm] * 252
    s = P2.one(("N40", 714903), Bn=15, smoke=True)
    assert set(s) == {"arm", "seed", "T", "seconds"} and "class_W2" in s["seconds"]


def test_task_lists():
    assert len(P2.tasks()) == 6200 and len(P2.SEEDS["NA40"]) == 2000 and {a for a, _ in P2.smoke_tasks()} == set(P2.SEEDS)
    assert all(714900 <= s <= 714909 for _, s in P2.smoke_tasks()) and P2.refusals("0" * 40)


def test_the_dry_checker(fake_pool, tmp_path):
    from experiments import check_recency_planted_2_dry as C
    out = tmp_path / "dry"
    out.mkdir()
    rows = [P2.one(t, Bn=15) for t in P2.smoke_tasks()]
    (out / "results.jsonl").write_text("\n".join(json.dumps(r, default=float) for r in rows))
    (out / "provenance.json").write_text(json.dumps({"platform": "x", "dry_run": True}))
    assert C.check(out)[1]
    (out / "results.jsonl").write_text("\n".join(json.dumps(r, default=float) for r in rows[1:]))
    assert not C.check(out)[1]
