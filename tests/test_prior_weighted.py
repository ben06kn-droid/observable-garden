"""The prior-weighted arm: its tool surface, its two routes, and planted dry runs."""
import asyncio
import json

import numpy as np
import pytest

from environments import planted_panel as pp
from experiments import price_runs as pr
from experiments.agent_backend import RunRecord, prior_weighted_tools
from tests.test_planted_panel import _panel


def _surface(K=5):
    base = pp.base_from(_panel(K=K))
    from environments.real_sandbox import RealSandbox
    sb = RealSandbox(base.in_sample, spec_class=pp.CLS)
    rec = RunRecord(run_id="pw", arm="prior-weighted", seed=1)
    by = {h.name: h for h in prior_weighted_tools(sb, rec, K, pp.CLS)}
    call = lambda n, a: asyncio.run(by[n].handler(a))["content"][0]["text"]
    return rec, call, by


def _sl(*specs):
    return {"supports": [{"features": f, "signs": g} for f, g in specs]}


def test_the_list_is_accepted_once_before_any_evaluate():
    rec, call, by = _surface()
    assert set(by) == {"short_list", "evaluate", "submit"}
    assert "recorded" in call("short_list", _sl(([0], [1]), ([1, 2], [1, -1])))
    ev = [e for e in rec.events if e["kind"] == "short_list"]
    assert ev and ev[0]["supports"] == [[[0, 1.0]], [[1, 1.0], [2, -1.0]]]
    assert "Rejected" in call("short_list", _sl(([3], [1])))           # a second list
    assert [r["tool"] for r in rec.refusals] == ["short_list"]


def test_a_list_after_any_evaluate_is_refused_even_a_refused_one():
    rec, call, _ = _surface()
    call("evaluate", {"features": [9], "signs": [1]})                  # refused: K = 5
    assert "after an evaluate" in call("short_list", _sl(([0], [1])))


@pytest.mark.parametrize("specs,why", [
    ((([0], [1]),) * 6, "1 to 5"),
    ((([0, 1, 2, 3], [1, 1, 1, 1]),), "outside the declared class"),
    ((([0, 0], [1, 1]),), "at most once"),
])
def test_a_malformed_list_is_refused(specs, why):
    rec, call, _ = _surface()
    assert why in call("short_list", _sl(*specs))
    assert not [e for e in rec.events if e["kind"] == "short_list"]


@pytest.fixture(scope="module")
def priced_parts():
    import tempfile
    base = pp.base_from(_panel(K=5))
    from environments.planted_view import agent_view
    from environments.real_sandbox import RealSandbox
    draw = pp.make_draw(base, 640905, 1.0)
    view, mask = agent_view(draw.in_sample, 640905)
    inv = pp.invariants_for(base, cache_dir=tempfile.mkdtemp())
    table, _ = pr.planted_table(base, draw, view, mask, inv=inv)
    return RealSandbox(view, spec_class=pp.CLS), table


def test_the_list_route_is_reality_check_over_the_list_on_the_class_tiers_rows(priced_parts):
    sb, table = priced_parts
    lst = [[[0, 1.0]], [[1, -1.0], [2, 1.0]], [[3, 1.0]]]
    sub = lst[1]
    B = 60
    cp = pr.class_p_etf(sb, table, 640905, sub, B)
    out = pr.prior_weighted(sb, table, 640905, lst, sub, B, cp["p_upper"])
    rows, _ = pr.replicate_rows(sb, 640905, B)
    S = table.sharpe(tuple(tuple(x) for x in sub))
    brute = []
    for r in rows:                                  # max over the list, demeaned, on r
        vals = []
        for m in lst:
            x = table.stream(tuple(tuple(p) for p in m))
            x = (x - x.mean())[r]
            vals.append(x.mean() / x.std(ddof=1) * table.annualization)
        brute.append(max(vals))
    p_brute = (1 + sum(v >= S for v in brute)) / (B + 1)
    assert out["on_list"] and out["p_prior"] == pytest.approx(p_brute, abs=1e-12)
    assert out["p_prior"] <= cp["p_upper"]          # the list is inside the class


def test_off_the_list_only_the_search_route_can_certify(priced_parts):
    sb, table = priced_parts
    out = pr.prior_weighted(sb, table, 640905, [[[0, 1.0]]], [[4, 1.0]], 30, 0.005)
    assert not out["on_list"] and out["p_prior"] is None
    assert out["route"] == "search" and out["status"] == "CERTIFIED"
    out = pr.prior_weighted(sb, table, 640905, [[[0, 1.0]]], [[4, 1.0]], 30, 0.02)
    assert out["route"] is None and out["status"] == "FAIL"     # 0.02 >= 0.01


def test_a_planted_dry_run_is_priced_on_both_routes(monkeypatch, tmp_path):
    from experiments import planted_agent as pa
    from experiments.real_prompts import read_prompts
    base = pp.base_from(_panel(K=5))
    monkeypatch.setattr(pp, "load_base", lambda: base)
    inv = pp.invariants_for(base, cache_dir=tmp_path / "inv")
    monkeypatch.setattr(pp, "invariants_for", lambda b, **kw: inv)
    rec = pa.run_one("prior-weighted", 640906, 1.0, 0, prompts=read_prompts(),
                     dry_run=True, base=base)
    d = json.loads(json.dumps(rec.to_json(), default=str))
    f = tmp_path / f"{d['run_id']}.json"
    f.write_text(json.dumps(d))
    r = pr.price_one((str(f), False, 40))
    pw = r["class_p"]["prior_weighted"]
    assert pw["alpha_prior"] == 0.04 and pw["alpha_search"] == 0.01
    assert pw["status"] in ("CERTIFIED", "FAIL") and len(pw["short_list"]) == 2
    t = r["planted_truth"]
    assert len(t["short_list_true"]) == 2 and isinstance(t["short_list_contains_m_star"], bool)
    assert "verdict" not in r                       # no session, no replay verdict
