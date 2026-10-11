"""The agent cell's collector and pricing on a MADE-UP precompute and made-up logs only: the
class tier and the supplied-streams tier, L90, EB on a toy, the selection-aware line, the
Sancho-look flag, refusals (incomplete session, tampered manifest, member order, arm A shown an
L90), and the replay tier's reason when it cannot be computed."""
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
             seed=721002, members_sha256=PR.members_sha256(members))
    np.savez(d / "sancho_d1.npz", stream=rng.standard_normal(T), earned_dates=np.array(["x"] * T), turnover_mean=0.2,
             S_w=0.8, S_unw=0.7, null_w2=rng.normal(0.3, 0.15, B), seed=721000)
    man = {"sha256": {f: _sha(d / f) for f in ("sancho_d1.npz", "class_scored.npy", "class_stats.npz")}}
    (d / "manifest.json").write_text(json.dumps(man))
    return d


def _log(path, run_id, arm, kind, support, *, sancho_first=False, L90=None, S_w=None, done=True, submit=True):
    ev = [{"kind": "start", "arm": arm, "seed": 7, "index": 0}]
    ev += [{"kind": "tool_result", "tool": "init", "ok": True}, {"kind": "tool_result", "tool": "extend_best", "ok": True}]
    if sancho_first:
        ev += [{"kind": "sancho_call"}, {"kind": "tool_result", "tool": "sancho", "ok": True}]
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
    L90_rule = 1.3 - float(np.quantile(pre["stats"]["null_w2_max"], 0.90))
    _log(logs / "a.json", "a", "A", "rule", rule, sancho_first=True, S_w=1.3)
    _log(logs / "b.json", "b", "B", "sancho", None, L90=0.8 - float(np.quantile(pre["sancho"]["null_w2"], 0.90)))
    _log(logs / "c.json", "c", "A", "rule", None, submit=False)
    rec = C.collect(sorted(logs.glob("*.json")))
    assert rec["sessions"] == 3 and rec["no_submit"] == ["c"] and len(rec["submissions"]) == 2
    assert rec["submissions"][1]["support"] == "sancho" and set(rec["submissions"][0]) == {"session", "arm", "kind", "support", "predict"}
    out = PR.price_all(logs, pre, rec)
    a, b = out["priced"]
    null = pre["stats"]["null_w2_max"]
    assert a["tier"] == "class (W2)" and a["p"] == (1 + int(np.sum(null >= 1.3))) / (B + 1)
    assert a["certified"]["96%"] == (a["p"] < 0.01) and a["certified"]["90%"] == (a["p"] < 0.02)
    assert a["L90"] == pytest.approx(L90_rule)
    S_u = pre["stats"]["S_unw"]
    assert a["EB"]["value"] == pytest.approx(1.1 - 0.25)                 # toy: S*_b(m_b) - S(m_b) = 0.25 on the un-demeaned replicates
    assert "point-estimate.md" in a["EB"]["label"] and "un-demeaned" in a["EB"]["label"]
    assert a["flags"] == ["non-grammar look (Sancho) taken"] and a["search"]["moves"] == 2
    assert a["replay"]["status"] == "not computed" and "base_columns" in a["replay"]["reason"]
    assert b["tier"] == "supplied streams (W2)" and b["EB"] is None and b["alphas"]["96%"] == 0.03
    both = np.maximum(null, pre["sancho"]["null_w2"])
    assert b["selection_aware"]["p"] == (1 + int(np.sum(both >= 0.8))) / (B + 1)
    assert "approximate, independent draws" in b["selection_aware"]["label"]
    assert all(b["log_consistency"].values()) and b["replay"]["status"] == "not applicable"
    assert len(out["nulls"]["class_w2_max"]) == B and S_u.shape[0] == len(members)


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


def test_the_replay_tier_is_computed_on_a_logged_grammar_session(tmp_path, members):
    """A real harness session (experiments/agent_cell_etf_recent.py, scripted driver) on a synthetic
    precompute with base_columns.npy: its committed log is priced and the replay tier computes."""
    from experiments import agent_cell_etf_recent as H
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
    ann = np.sqrt(252.0)
    S_u = scored.mean(axis=1) / scored.std(axis=1, ddof=1) * ann
    S_w = S_u * 0.9
    null = np.sort(rng.normal(2.5, 0.3, B))
    am = rng.integers(0, N, B)
    np.savez(d / "class_stats.npz", S_w=S_w, S_unw=S_u, null_w2_max=null, null_unw_max=null,
             null_unw_argmax=am, null_unw_S_at_argmax=S_u[am], null_unw_undemeaned_argmax=am,
             null_unw_undemeaned_S_at_argmax=S_u[am] + 0.1, seed=721002, members_sha256=PR.members_sha256(members))
    np.savez(d / "sancho_d1.npz", stream=rng.standard_normal(Tn), earned_dates=np.array(["2024-12-31"] * Tn),
             turnover_mean=0.2, S_w=0.8, S_unw=0.7, null_w2=rng.normal(0.3, 0.15, B), seed=721000)
    files = ("sancho_d1.npz", "class_scored.npy", "class_stats.npz", "base_columns.npy")
    (d / "manifest.json").write_text(json.dumps({"sha256": {f: _sha(d / f) for f in files}}))

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
