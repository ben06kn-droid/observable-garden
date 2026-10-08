"""The factorised kernel (`environments/planted_fast.py`) against the registered code, on
the synthetic base: streams to 1e-12 relative, Sharpes to 1e-10 (1e-9 on the
multi-level path), and class argmax, searcher supports and both p-values identical.
Any flip is a failure."""
from dataclasses import replace

import numpy as np
import pytest

from environments import planted_fast as pf
from environments import planted_panel as pp
from environments.class_table import streams_for
from experiments import planted_edge as pe
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture(scope="module")
def cache(base, tmp_path_factory):
    return pf.build(base.in_sample, base.members, cache_dir=tmp_path_factory.mktemp("fast"))


@pytest.fixture(scope="module")
def inv(base, tmp_path_factory):
    return pp.invariants_for(base, cache_dir=tmp_path_factory.mktemp("inv"))


@pytest.mark.parametrize("beta", [0.0, 1.0, 1.5])
def test_streams_match_streams_for_to_1e12_relative(base, cache, beta):
    d = pp.make_draw(base, 640050, beta)
    F = pf.feature_returns(d.in_sample)
    fast = pf.streams(cache, F, 0, cache.N)
    ref = streams_for(d.in_sample, base.members)
    scale = np.abs(ref).max()
    assert np.abs(fast - ref).max() <= 1e-12 * scale
    ann = np.sqrt(d.in_sample.periods_per_year)
    np.testing.assert_allclose(pf._sharpe_rows(fast, ann), pe._sharpe_rows(ref, ann),
                               rtol=0, atol=1e-10)


def test_the_overlap_matches_streams_with_overlap(base, cache):
    d = pp.make_draw(base, 640051, 1.0)
    _, Ea, Ea2, Eak = pp.streams_with_overlap(d.in_sample, base.members, d.w_star_is)
    a = pf.overlap(cache, np.einsum("tmk,tm->tk", pf.demeaned(d.in_sample), d.w_star_is),
                   0, cache.N)
    k = np.asarray(cache.k)
    np.testing.assert_allclose(a.mean(1), Ea, rtol=0, atol=1e-14)
    np.testing.assert_allclose((a * a).mean(1), Ea2, rtol=0, atol=1e-14)
    np.testing.assert_allclose((a * k).mean(1), Eak, rtol=0, atol=1e-14)


@pytest.mark.parametrize("seed", [640052, 640053, 640054])
def test_run_levels_equals_run_level_on_every_level(base, cache, inv, seed):
    betas = (0.0, 1.0, 1.5)
    B = 60
    fast = pf.run_levels(base, cache, seed, betas, B, inv)
    overlap = None
    for beta, f in zip(betas, fast):
        ref = pe.run_level(base, seed, beta, B, inv, overlap)
        overlap = ref.pop("_overlap")
        for k in ("c", "planted", "block_length_null", "class_argmax", "pop_best",
                  "planted_rank", "null_max_q"):
            if k == "null_max_q":
                for a in ref[k]:
                    assert f[k][a] == pytest.approx(ref[k][a], abs=1e-9), (beta, k)
            else:
                assert f[k] == ref[k], (beta, k)
        for k in ("class_max", "null_max_mean", "pop_best_sr"):
            assert f[k] == pytest.approx(ref[k], abs=1e-9), (beta, k)
        for a, b in zip(f["searchers"], ref["searchers"]):
            assert a["searcher"] == b["searcher"]
            assert a["support"] == b["support"], (beta, a["searcher"])
            assert a["n_moves"] == b["n_moves"], (beta, a["searcher"])
            assert a["p_class"] == b["p_class"], (beta, a["searcher"], "p_class FLIP")
            assert a["p_trigger"] == b["p_trigger"], (beta, a["searcher"], "p_trigger FLIP")
            assert a["score"] == pytest.approx(b["score"], abs=1e-9)
            assert a["truth"]["in_sample"] == pytest.approx(b["truth"]["in_sample"], abs=1e-9)
            assert a["truth"]["holdout"] == b["truth"]["holdout"]


def test_it_refuses_stateful_books(base):
    p = base.in_sample
    bad = replace(p, tradable=np.asarray(p.tradable).copy())
    bad.tradable[5, 2] = False
    with pytest.raises(ValueError, match="untradable"):
        pf.check_panel(bad)
    with pytest.raises(ValueError, match="flat-overnight"):
        pf.check_panel(replace(p, flat_overnight=True))


def test_the_cache_is_built_once_keyed_and_read_only(base, tmp_path):
    c1 = pf.build(base.in_sample, base.members, cache_dir=tmp_path)
    c2 = pf.build(base.in_sample, base.members, cache_dir=tmp_path)
    assert c1.key == c2.key and c1.path == c2.path
    assert not c1.g.flags.writeable and not c1.k.flags.writeable
    other = replace(base.in_sample, cost_rate=np.asarray(base.in_sample.cost_rate) * 2)
    assert pf.build(other, base.members, cache_dir=tmp_path).key != c1.key
    assert len(list(tmp_path.glob("fast_*"))) == 4        # two caches, two lock files
    import json
    man = json.loads((tmp_path / f"fast_{c1.key}" / "manifest.json").read_text())
    import hashlib
    assert man["panel_x_sha256"] == hashlib.sha256(np.ascontiguousarray(
        base.in_sample.features, dtype=np.float64).tobytes()).hexdigest()
    assert "pinned_x_sha256" not in man
