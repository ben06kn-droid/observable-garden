"""The agent cell's collector and pricing on a MADE-UP precompute and made-up logs only: the
class tier and the supplied-streams tier on the UNWEIGHTED statistic with the W2 values beside,
L90, EB on a toy, the selection-aware line (the class envelope, and the joint null of the
session's replayed search and the model stream on shared draws), the model-stream-look flag,
refusals (incomplete session, tampered manifest, member order, arm A shown an L90), and the
replay tier computed on a logged grammar session."""
import hashlib
import json

import numpy as np
import pytest

from experiments import agent_cell_etf_recent_collect as C
from experiments import agent_cell_etf_recent_price as PR

T, B = 12, 200


@pytest.fixture(scope="module")
def members():
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    return members_in_order(CLS, 40)


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture()
def pre_dir(tmp_path, members):
    rng = np.random.default_rng(723160)
    d = tmp_path / "precompute"
    d.mkdir()
    N = len(members)
    np.save(d / "class_scored.npy", rng.standard_normal((N, T)) * 0.01)
    S_w, S_u = rng.normal(0, 0.3, N), rng.normal(0, 0.3, N)
    S_w[5], S_u[5] = 1.3, 1.1
    null_w2 = np.sort(rng.normal(0.9, 0.15, B))
    argmax = rng.integers(0, N, B)
    argmax_u = rng.integers(0, N, B)
    np.savez(d / "class_stats.npz", S_w=S_w, S_unw=S_u, null_w2_max=null_w2, null_unw_max=null_w2 - 0.1,
             null_unw_argmax=argmax, null_unw_S_at_argmax=S_u[argmax] + 9.0,       # demeaned: must NOT enter EB
             null_unw_undemeaned_argmax=argmax_u, null_unw_undemeaned_S_at_argmax=S_u[argmax_u] + 0.25,
             joint_unw_max=null_w2 - 0.05, seed=721002, members_sha256=PR.members_sha256(members))
    np.savez(d / "sancho_d1.npz", stream=rng.standard_normal(T), earned_dates=np.array(["x"] * T), turnover_mean=0.2,
             S_w=0.8, S_unw=0.7, null_w2=rng.normal(0.3, 0.15, B), null_unw=rng.normal(0.25, 0.15, B), seed=721000)
    man = {"sha256": {f: _sha(d / f) for f in ("sancho_d1.npz", "class_scored.npy", "class_stats.npz")}}
    (d / "manifest.json").write_text(json.dumps(man))
    return d


def _log(path, run_id, arm, kind, support, *, model_first=False, L90=None, S_w=None, done=True, submit=True):
    ev = [{"kind": "start", "arm": arm, "seed": 7, "index": 0}]
    ev += [{"kind": "tool_result", "tool": "init", "ok": True}, {"kind": "tool_result", "tool": "extend_best", "ok": True}]
    if model_first:
        ev += [{"kind": "baseline_model_call"}, {"kind": "tool_result", "tool": "baseline_model", "ok": True}]
    if submit:
        ev += [{"kind": "candidate", "candidate_kind": kind, "support": support},
               {"kind": "submit", "submission": {"arm": arm, "kind": kind, "support": support,
                                                 "predict": {"mean": 0.4, "sd": 0.3, "note": ""},
                                                 "candidate_S_w": S_w, "candidate_S_unw": None, "L90_shown": L90}}]
    else:
        ev += [{"kind": "no_submit", "detail": "ended without confirm"}]
    if done:
        ev += [{"kind": "end"}]
    path.write_text(json.dumps({"run_id": run_id, "events": ev}))


def test_collect_and_price(tmp_path, pre_dir, members):
    logs = tmp_path / "logs"
    logs.mkdir()
    rule = [[int(k), float(s)] for k, s in members[5]]
    pre = PR.load_precompute(pre_dir, members)
    st, sn = pre["stats"], pre["sancho"]
    _log(logs / "a.json", "a", "A", "rule", rule, model_first=True, S_w=1.3)
    _log(logs / "b.json", "b", "B", "baseline_model", None, L90=0.7 - float(np.quantile(sn["null_unw"], 0.90)))
    _log(logs / "c.json", "c", "A", "rule", None, submit=False)
    rec = C.collect(sorted(logs.glob("*.json")))
    assert rec["sessions"] == 3 and rec["no_submit"] == ["c"] and len(rec["submissions"]) == 2
    assert rec["submissions"][1]["support"] == "baseline_model"
    assert set(rec["submissions"][0]) == {"session", "arm", "kind", "support", "predict"}
    out = PR.price_all(logs, pre, rec)
    a, b = out["priced"]
    # a rule: the class tier on the UNWEIGHTED statistic, the W2 beside, labelled
    nu, nw = st["null_unw_max"], st["null_w2_max"]
    assert a["tier"] == "class (unweighted)" and a["S"] == pytest.approx(1.1) and a["S_w"] == pytest.approx(1.3)
    assert a["p"] == (1 + int(np.sum(nu >= 1.1))) / (B + 1)
    assert a["certified"]["96%"] == (a["p"] < 0.01) and a["certified"]["90%"] == (a["p"] < 0.02)
    assert a["L90"] == pytest.approx(1.1 - float(np.quantile(nu, 0.90)))
    assert a["p_w2"] == (1 + int(np.sum(nw >= 1.3))) / (B + 1)
    assert a["L90_w2"] == pytest.approx(1.3 - float(np.quantile(nw, 0.90)))
    assert a["w2_label"] == a["S_w_label"] == "recency-weighted, descriptive"
    assert a["EB"]["value"] == pytest.approx(1.1 - 0.25)                 # toy: S*_b(m_b) - S(m_b) = 0.25, un-demeaned
    assert "un-demeaned" in a["EB"]["label"] and "unweighted" in a["EB"]["label"]
    assert a["flags"] == [PR.MODEL_LOOK_FLAG] and a["search"]["moves"] == 2
    assert a["replay"]["status"] == "not computed" and "base_columns" in a["replay"]["reason"]
    # the model stream: the supplied-streams tier, unweighted; arm B was shown the unweighted L90
    assert b["kind"] == "baseline_model" and b["tier"] == "supplied streams (unweighted)" and b["EB"] is None
    assert b["alphas"]["96%"] == 0.03 and b["p"] == (1 + int(np.sum(sn["null_unw"] >= 0.7))) / (B + 1)
    assert b["L90"] == pytest.approx(0.7 - float(np.quantile(sn["null_unw"], 0.90)))
    assert all(b["log_consistency"].values()) and b["replay"]["status"] == "not applicable"
    sa = b["selection_aware"]                                          # no base columns: the class envelope
    assert sa["basis"] == "class envelope, not the session's own search" and "base_columns" in sa["reason"]
    assert sa["p"] == (1 + int(np.sum(st["joint_unw_max"] >= 0.7))) / (B + 1)
    assert set(out["nulls"]) == {"class_unw_max", "model_unw", "class_w2_max", "model_w2"}
    assert "sancho" not in json.dumps(out["priced"]).lower()


def test_refusals(tmp_path, pre_dir, members):
    logs = tmp_path / "logs"
    logs.mkdir()
    _log(logs / "a.json", "a", "A", "rule", [[0, 1.0]], done=False)
    with pytest.raises(C.CollectRefused, match="incomplete"):
        C.collect(sorted(logs.glob("*.json")))
    _log(logs / "a.json", "a", "A", "rule", [[0, 1.0]], L90=0.2)
    rec = C.collect(sorted(logs.glob("*.json")))
    pre = PR.load_precompute(pre_dir, members)
    with pytest.raises(PR.PricingRefused, match="arm A was shown an L90"):
        PR.price_all(logs, pre, rec)
    with pytest.raises(PR.PricingRefused, match="member order"):
        PR.load_precompute(pre_dir, members[::-1])
    with open(pre_dir / "class_scored.npy", "ab") as fh:
        fh.write(b"x")
    with pytest.raises(PR.PricingRefused, match="class_scored.npy"):
        PR.load_precompute(pre_dir, members)
    out = tmp_path / "subs.json"
    C.write(rec, out)
    with pytest.raises(C.CollectRefused, match="written once"):
        C.write(rec, out)


def _grammar_precompute(tmp_path, members):
    """A synthetic precompute covering the full class, with base columns (the replay needs them)."""
    rng = np.random.default_rng(723170)
    N, Tn = len(members), 80
    d = tmp_path / "pre"
    d.mkdir()
    base = rng.standard_normal((Tn, 40)) * 0.01 + 0.0004 * np.arange(40)[None, :] / 40
    W = np.zeros((N, 40))
    for j, m in enumerate(members):
        for k, s in m:
            W[j, k] = s / len(m)
    scored = (W @ base.T)
    np.save(d / "class_scored.npy", scored)
    np.save(d / "base_columns.npy", base)
    S_u = scored.mean(axis=1) / scored.std(axis=1, ddof=1) * np.sqrt(252.0)
    null = np.sort(rng.normal(2.5, 0.3, B))
    am = rng.integers(0, N, B)
    np.savez(d / "class_stats.npz", S_w=S_u * 0.9, S_unw=S_u, null_w2_max=null, null_unw_max=null,
             null_unw_argmax=am, null_unw_S_at_argmax=S_u[am], null_unw_undemeaned_argmax=am,
             null_unw_undemeaned_S_at_argmax=S_u[am] + 0.1, joint_unw_max=null,
             seed=721002, members_sha256=PR.members_sha256(members))
    np.savez(d / "sancho_d1.npz", stream=rng.standard_normal(Tn) * 0.01, earned_dates=np.array(["2024-12-31"] * Tn),
             turnover_mean=0.2, S_w=0.8, S_unw=0.7, null_w2=rng.normal(0.3, 0.15, B),
             null_unw=rng.normal(0.25, 0.15, B), seed=721000)
    files = ("sancho_d1.npz", "class_scored.npy", "class_stats.npz", "base_columns.npy")
    (d / "manifest.json").write_text(json.dumps({"sha256": {f: _sha(d / f) for f in files}}))
    return d


def test_the_joint_null_shares_the_replays_draws(tmp_path, members, monkeypatch):
    """A model-stream submission after a logged grammar search: the selection-aware line uses the
    session's replayed trigger null and the model stream's demeaned replicate on the SAME draws.
    The draws regenerated by the pricing equal the ones `three_nulls` drew, element for element."""
    import importlib
    QC = importlib.import_module("quixote.certify")          # the package re-exports the function `certify`
    from experiments import agent_cell_etf_recent as H
    d = _grammar_precompute(tmp_path, members)

    def driver(cell, rec, prompt, prompts):
        for name in ("init", "extend_best", "extend_best"):
            cell.call(name)
        cell.call("baseline_model")
        cell.call("submit_candidate", kind="baseline_model")
        cell.call("predict", mean=0.3, sd=0.5, note="")
        cell.call("confirm")
    rec = H.run_session(H.Precompute(d), "B", seed=13, index=0, prompts={"system": "x"}, driver=driver)
    log = json.loads(json.dumps(rec.to_json(), default=str))
    pre = PR.load_precompute(d, members)
    sub = {"session": "s", "arm": "B", "kind": "baseline_model", "support": "baseline_model",
           "predict": {"mean": 0.3, "sd": 0.5, "note": ""}}
    seen = []
    orig = QC.stationary_bootstrap_indices

    def recording(T, L, rng):
        i = orig(T, L, rng)
        seen.append((T, L, np.array(i)))
        return i
    monkeypatch.setattr(QC, "stationary_bootstrap_indices", recording)
    sa = PR.selection_aware(log, sub, pre, B=30)
    assert sa["basis"].startswith("the session's own search"), sa
    assert len(seen) == 30
    regen = PR.replay_draws(seen[0][0], sa["block_length"], sa["seed"], 30)
    assert all(np.array_equal(a[2], b) for a, b in zip(seen, regen))
    assert all(a[1] == sa["block_length"] for a in seen)
    # the p itself, recomputed from its parts
    from environments.planted_panel import CLS
    from experiments.price_runs import rebuild_session_log
    monkeypatch.setattr(QC, "stationary_bootstrap_indices", orig)
    nulls, _ = QC.three_nulls(rebuild_session_log(log), CLS, np.asarray(pre["base"], float), float(np.sqrt(252.0)),
                              30, None, sa["seed"], table=PR.class_table(pre))
    joint = np.maximum(np.asarray(nulls.trigger, float), PR.model_replicates(pre["sancho"]["stream"], regen))
    assert sa["p"] == PR.tier_p(0.7, joint)


def test_the_replay_tier_is_computed_on_a_logged_grammar_session(tmp_path, members):
    """A real harness session (experiments/agent_cell_etf_recent.py, scripted driver) on a synthetic
    precompute with base_columns.npy: its committed log is priced and the replay tier computes."""
    from experiments import agent_cell_etf_recent as H
    d = _grammar_precompute(tmp_path, members)

    def driver(cell, rec, prompt, prompts):
        for name, kw in (("init", {}), ("extend_best", {}), ("extend_best", {}), ("swap_worst", {})):
            cell.call(name, **kw)
        cell.call("submit_candidate", kind="rule")
        cell.call("predict", mean=0.5, sd=0.4, note="")
        cell.call("confirm")
    rec = H.run_session(H.Precompute(d), "A", seed=11, index=0, prompts={"system": "x"}, driver=driver)
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / f"{rec.run_id}.json").write_text(json.dumps(rec.to_json(), default=str))
    subs = C.collect(sorted(logs.glob("*.json")))
    assert len(subs["submissions"]) == 1 and subs["submissions"][0]["kind"] == "rule"
    out = PR.price_all(logs, PR.load_precompute(d, members), subs, B=50)
    r = out["priced"][0]
    assert r["replay"]["status"] == "computed", r["replay"]
    v = r["replay"]["verdict"]
    assert v["n_moves"] >= 1 and v["B"] == 50 and "status" in v
    assert r["search"]["moves"] == 4 and r["flags"] == []


def test_collect_and_price_240_sessions(tmp_path, pre_dir, members):
    """Amendment 2: 120 per arm. The collector and pricing take 240 committed logs."""
    logs = tmp_path / "logs240"
    logs.mkdir()
    pre = PR.load_precompute(pre_dir, members)
    for i in range(240):
        arm = "A" if i % 2 == 0 else "B"
        if i % 3 == 0:
            _log(logs / f"s{i}.json", f"s{i}", arm, "baseline_model", None)
        else:
            _log(logs / f"s{i}.json", f"s{i}", arm, "rule", [[int(k), float(s)] for k, s in members[i % 50]])
    rec = C.collect(sorted(logs.glob("*.json")))
    assert rec["sessions"] == 240 and len(rec["submissions"]) == 240
    assert sum(s["arm"] == "A" for s in rec["submissions"]) == 120
    priced = PR.price_all(logs, pre, rec)
    assert len(priced["priced"]) == 240
