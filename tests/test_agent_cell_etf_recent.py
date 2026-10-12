"""The agent cell's tool layer and launcher on a SYNTHETIC precompute (full class, tiny T): tool
outputs, arm B's line only in B, byte-identical prompts, refusals, resumption, the seed schedule,
no_submit, and the leak tests of `prereg/agent-cell-etf-recent.md` section 5. No model is called."""
import builtins
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest

from experiments import agent_cell_etf_recent as E
from experiments.agent_backend import RunRecord

N, T, B = 82240, 60, 50


def _write_pre(d: Path, last=dt.date(2024, 12, 31), seed=7):
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((N, T)) * 0.01
    np.save(d / "class_scored.npy", X)
    S_unw = X.mean(1) / X.std(1, ddof=1) * np.sqrt(252)
    np.savez(d / "class_stats.npz", S_w=0.9 * S_unw, S_unw=S_unw, null_w2_max=rng.normal(1.5, 0.2, B),
             null_unw_max=rng.normal(1.4, 0.2, B), null_unw_argmax=rng.integers(0, N, B),
             null_unw_S_at_argmax=rng.normal(1.4, 0.2, B), null_unw_undemeaned_argmax=rng.integers(0, N, B),
             null_unw_undemeaned_S_at_argmax=rng.normal(1.6, 0.2, B), joint_unw_max=rng.normal(1.45, 0.2, B),
             members_sha256="synthetic", seed=721002)
    ed = [str(last - dt.timedelta(days=T - 1 - i)) for i in range(T)]
    np.savez(d / "sancho_d1.npz", stream=rng.standard_normal(T) * 0.01, earned_dates=np.array(ed),
             turnover_mean=0.123, S_w=0.8, S_unw=0.7, null_w2=rng.normal(0.4, 0.2, B),
             null_unw=rng.normal(0.3, 0.2, B), seed=721000)
    man = {"registration": "synthetic", "T_scored": T, "N": N, "B": B, "first_earned": ed[0], "last_earned": ed[-1],
           "sha256": {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in E.FILES}}
    (d / "manifest.json").write_text(json.dumps(man))
    return d


@pytest.fixture(scope="module")
def pre_dir(tmp_path_factory):
    return _write_pre(tmp_path_factory.mktemp("pre") / "precompute")


@pytest.fixture(scope="module")
def pre(pre_dir):
    return E.Precompute(pre_dir)


SCRIPT = [("declare_triggers", {"triggers": [{"trigger": "failures_at_least", "param": 2, "action": "stop"}]}),
          ("init", {}), ("extend_best", {}), ("swap_worst", {}), ("refine", {}),
          ("pick", {"among": [1, 2, 3], "statistic": "sharpe"}), ("flip", {"feature": 99}),
          ("baseline_model", {}), ("baseline_model", {})]


def _session(pre, arm, kind="rule"):
    rec = RunRecord(run_id="t", arm=arm, seed=1)
    cell = E.CellSession(pre, arm, rec)
    for name, kw in SCRIPT:
        cell.call(name, **kw)
    cell.call("submit_candidate", kind=kind)
    cell.call("init")                                     # refused: the candidate is fixed
    cell.call("predict", mean=0.4, sd=0.3, note="n")
    cell.call("confirm")
    return cell, rec


def _submission(rec):
    return [e for e in rec.events if e["kind"] == "submit"][-1]["submission"]


def test_tool_outputs_and_the_arm_b_line(pre):
    for kind in ("rule", "baseline_model"):
        ca, ra = _session(pre, "A", kind)
        cb, rb = _session(pre, "B", kind)
        sa, sb = _submission(ra), _submission(rb)
        assert sa["kind"] == sb["kind"] == kind and sa["L90_shown"] is None
        assert sb["L90_shown"] == pytest.approx(cb.candidate["L90"])
        assert sa["predict"] == {"mean": 0.4, "sd": 0.3, "note": "n"}
        la = [o for o in ca.outputs if o.startswith("Candidate fixed")][0]
        lb = [o for o in cb.outputs if o.startswith("Candidate fixed")][0]
        assert "L90" not in la and "Gate's 90% lower bound for this candidate: L90 = " in lb
        assert "weighted" not in lb.split("\n")[1]       # the unweighted L90 (section 0)
        assert lb.split("\n")[0] == la                    # B = A plus one line
        assert not any("L90" in o for o in cb.outputs if not o.startswith("Candidate fixed"))
        if kind == "baseline_model":
            assert sa["support"] is None
            assert cb.candidate["L90"] == pytest.approx(0.7 - np.quantile(pre.model["null_unw"], 0.9))
        else:
            i = pre.idx(sa["support"])
            assert cb.candidate["L90"] == pytest.approx(pre.S_unw[i] - np.quantile(pre.class_null_unw, 0.9))
            assert sa["candidate_S_unw"] == pytest.approx(pre.S_unw[i])
    s = [o for o in ca.outputs if o.startswith("Baseline model stream:")]
    assert len(s) == 2 and s[0] == s[1] and "0.700" in s[0] and "0.800" in s[0] and "0.123" in s[0]
    assert any("Sharpe (all years equal)" in o and "Sharpe (recent years weighted)" in o
               for o in ca.outputs if o.startswith("init kept"))
    kinds = {r["kind"] for r in ra.refusals}
    assert "candidate_fixed" in kinds and "UNREGISTERED" not in kinds


def test_the_flow_refusals(pre):
    cell = E.CellSession(pre, "A", RunRecord(run_id="t", arm="A", seed=1))
    assert cell.call("confirm").startswith("Refused: candidate_required")
    assert cell.call("submit_candidate", kind="rule").startswith("Refused: no_candidate")
    assert cell.call("submit_candidate", kind="other").startswith("Refused: bad_kind")
    cell.call("submit_candidate", kind="baseline_model")
    assert cell.call("confirm").startswith("Refused: predict_required")
    assert cell.call("predict", mean=0.1, sd=-1).startswith("Refused: bad_sd")
    assert cell.call("submit_candidate", kind="rule").startswith("Refused: candidate_fixed")
    cell.call("predict", mean=0.1, sd=0.0)
    assert cell.call("confirm") == "confirmed; the session is over"
    assert cell.call("baseline_model").startswith("Refused: after_confirm")
    assert cell.call("evaluate").startswith("Refused")


def test_prompts_byte_identical_and_complete():
    p = E.read_prompts()
    assert E.system_prompt("A", p) == E.system_prompt("B", p)
    assert all(f"tool:{t}" in p for t in E.TOOLS)
    with pytest.raises(ValueError):
        E.system_prompt("C", p)


FORBIDDEN = [r"p-value", r"\bp =", r"\balpha\b", r"critical", r"\bnull\b", r"certif", r"verdict",
             r"\barms?\b", r"\bETFs?\b", r"\b(38|40)\s+(ETFs?|instruments|assets|funds)\b",
             r"\d{4}-\d{2}-\d{2}", r"(?<![\d.])(19|20)\d{2}(?!\d)",
             r"sancho"]                                   # the codename (decision 11), any case


def _all_text(pre):
    p = E.read_prompts()
    texts = [E.system_prompt("A", p)] + [p[f"tool:{t}"] for t in E.TOOLS]
    for arm in ("A", "B"):
        for kind in ("rule", "baseline_model"):
            texts += _session(pre, arm, kind)[0].outputs
        cell = E.CellSession(pre, arm, RunRecord(run_id="r", arm=arm, seed=2))      # refusal texts
        texts += [cell.call("confirm"), cell.call("submit_candidate", kind="rule"),
                  cell.call("submit_candidate", kind="other"), cell.call("predict", mean=0.1, sd=0.1)]
        cell.call("submit_candidate", kind="baseline_model")
        texts += [cell.call("predict", mean=0.1, sd=-1), cell.call("submit_candidate", kind="rule"), cell.call("init")]
        cell.call("predict", mean=0.1, sd=0.1)
        cell.call("confirm")
        texts += [cell.call("baseline_model"), cell.call("evaluate")]
    return texts


def test_leaks_no_names_dates_arms_verdicts(pre):
    from data.fetch_etf import TICKERS
    from environments.real_panel import ETF_BASE
    texts = _all_text(pre)
    blob = "\n".join(texts)
    for pat in FORBIDDEN:
        assert not re.search(pat, blob, re.I), pat
    for t in TICKERS:
        assert not re.search(rf"\b{re.escape(t)}\b", blob), t
    for nm in ETF_BASE:
        assert nm not in blob, nm
    outs = [t for t in texts[1 + len(E.TOOLS):]]
    assert not any(re.search(r"\b[AB]\b", o) for o in outs)        # no arm label in any tool output


def test_leaks_no_file_outside_the_precompute(pre_dir, monkeypatch):
    opened = []
    real_open, real_load = builtins.open, np.load
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
    monkeypatch.setattr(np, "load", lambda f, *a, **k: (opened.append(str(f)), real_load(f, *a, **k))[1])
    pre = E.Precompute(pre_dir)
    for arm in ("A", "B"):
        _session(pre, arm)
    root = str(Path(pre_dir).resolve())
    assert opened and all(str(Path(f).resolve()).startswith(root) for f in opened), opened


def test_leaks_no_row_after_2024(tmp_path):
    d = _write_pre(tmp_path / "late" / "precompute", last=dt.date(2025, 1, 2))
    with pytest.raises(E.Refused, match="after 2024-12-31"):
        E.Precompute(d)


def test_a_tampered_file_is_refused(tmp_path):
    d = _write_pre(tmp_path / "tamper" / "precompute")
    np.savez(d / "sancho_d1.npz", stream=np.zeros(T), earned_dates=np.array(["2024-01-02"]), turnover_mean=0.0,
             S_w=9.0, S_unw=9.0, null_w2=np.zeros(B), null_unw=np.zeros(B), seed=0)
    with pytest.raises(E.Refused, match="manifest"):
        E.Precompute(d)


def test_launcher_refusals(pre_dir, monkeypatch, tmp_path):
    class R:
        def __init__(self, rc=0, out=""):
            self.returncode, self.stdout = rc, out
    monkeypatch.setattr(E, "_git", lambda *a: R(0, ""))
    # the live constants (set at go-live) and the pinned manifest
    assert E.REGISTRATION == "00c7af167f8ddb9a4874cc29b438926112360fb9"
    assert E.PRECOMPUTE_MANIFEST_SHA256 == "78583e9b2fdadad7ef64bb6cd1b08b0a0ca9879a15ea84f165a20d2e705b0ae2"
    monkeypatch.setattr(E, "REGISTRATION", None)
    monkeypatch.setattr(E, "PRECOMPUTE_MANIFEST_SHA256", None)
    bad = E.refusals(pre_dir, tmp_path / "cell", smoke=False)
    assert any("not live" in b for b in bad) and any("not pinned" in b for b in bad)
    man_sha = E._sha(Path(pre_dir) / "manifest.json")
    monkeypatch.setattr(E, "REGISTRATION", "f" * 40)
    monkeypatch.setattr(E, "PRECOMPUTE_MANIFEST_SHA256", man_sha)
    assert E.refusals(pre_dir, tmp_path / "cell", smoke=False) == []
    assert any("smoke" in b for b in E.refusals(pre_dir, tmp_path / "cell", smoke=True))
    assert any("smoke" in b for b in E.refusals(pre_dir, tmp_path / "cell_smoke", smoke=False))
    assert E.refusals(pre_dir, tmp_path / "cell_smoke", smoke=True) == []
    monkeypatch.setattr(E, "PRECOMPUTE_MANIFEST_SHA256", "0" * 64)
    assert any("pinned SHA-256" in b for b in E.refusals(pre_dir, tmp_path / "cell", smoke=False))
    monkeypatch.setattr(E, "PRECOMPUTE_MANIFEST_SHA256", man_sha)
    monkeypatch.setattr(E, "_git", lambda *a: R(1, "") if a[0] == "merge-base" else R(0, " M x.py"))
    bad = E.refusals(pre_dir, tmp_path / "cell", smoke=False)
    assert any("not an ancestor" in b for b in bad) and any("uncommitted" in b for b in bad)
    with pytest.raises(SystemExit, match="REFUSED"):
        E.main(["--precompute", str(pre_dir), "--runs", "1", "--out", str(tmp_path / "cell")])


def test_seeds_and_schedule():
    s = E.schedule("both", 40)
    assert len(s) == 80 and [x[0] for x in s[:4]] == ["A", "B", "A", "B"]
    a = [int(v) for v in np.random.default_rng(20261011).integers(0, 2**31 - 1, size=40)]
    b = [int(v) for v in np.random.default_rng(20261012).integers(0, 2**31 - 1, size=40)]
    assert [x[2] for x in s if x[0] == "A"] == a and [x[2] for x in s if x[0] == "B"] == b
    assert E.schedule("A", 3) == [("A", i, a[i]) for i in range(3)]
    sm = E.schedule("both", 5, smoke=True)
    m = [int(v) for v in np.random.default_rng(723100).integers(0, 2**31 - 1, size=5)]
    assert [x[0] for x in sm] == ["A", "B", "A", "B", "A"] and [x[2] for x in sm] == m


def test_resumption(tmp_path):
    out = tmp_path / "cell"
    out.mkdir()
    (a0, i0, s0), (b0, j0, t0) = E.schedule("both", 1)
    (out / f"{E.run_id_for(a0, s0, i0)}.json").write_text(json.dumps({"events": [{"kind": "start"}, {"kind": "end"}]}))
    partial = out / f"{E.run_id_for(b0, t0, j0)}.json"
    partial.write_text(json.dumps({"events": [{"kind": "start"}]}))
    p = E.plan(out, "both", 1)
    assert p["skipped"] == [E.run_id_for(a0, s0, i0)] and p["redone"] == [partial.stem]
    assert p["todo"] == [(b0, j0, t0)] and not partial.exists()


def test_a_session_end_to_end_and_no_submit(pre):
    p = E.read_prompts()

    def scripted(cell, rec, prompt, prompts):
        assert prompt == E.system_prompt(cell.arm, prompts)
        for name, kw in SCRIPT:
            cell.call(name, **kw)
        cell.call("submit_candidate", kind="rule")
        cell.call("predict", mean=0.2, sd=0.4)
        cell.call("confirm")

    rec = E.run_session(pre, "B", 11, 0, p, driver=scripted)
    kinds = [e["kind"] for e in rec.events]
    assert kinds[0] == "start" and kinds[-1] == "end" and "session_log" in kinds and "self_check" in kinds
    assert rec.submitted and not rec.no_submit and _submission(rec)["arm"] == "B"

    def idle(cell, rec, prompt, prompts):                 # spends every turn and never confirms
        cell.call("declare_triggers", triggers=[{"trigger": "failures_at_least", "param": 99, "action": "stop"}])
        for _ in range(60):
            cell.call("init")
        rec.no_submit = True
        rec.log("no_submit", detail="error_max_turns")

    rec2 = E.run_session(pre, "A", 12, 1, p, driver=idle)
    assert rec2.no_submit and not rec2.submitted and rec2.submitted_support is None
    assert "submit" not in [e["kind"] for e in rec2.events] and [e["kind"] for e in rec2.events][-1] == "end"
