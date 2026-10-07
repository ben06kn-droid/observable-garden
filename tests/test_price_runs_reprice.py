"""`price_runs --reprice-to`: re-price already-priced runs at a new B, confidence fields
included, into a new location, never touching the source (`prereg/holdout-grading.md`).

A synthetic s0 run, scripted as in `tests/test_price_runs.py`, priced at a small B that
stands in for 6.5's B = 200, then re-priced at a larger one.
"""
import json

import pytest

import experiments.agent_backend as ab
import experiments.agent_cell as ac
from experiments import price_runs as pr

SEED = 20260929
B_OLD, B_NEW = 20, 40


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(ac, "_drive_model", lambda arm, rec, handlers, *a, **k:
                        ac._scripted(rec, handlers, arm))
    monkeypatch.setattr(ab, "CERTIFY_B", B_OLD)


@pytest.fixture
def priced(tmp_path, scripted):
    rec, _ = ac.run_one("replay gate", "s0", SEED, 0, prompts=ac.read_prompts(),
                        credential="seat", defer_pricing=False)
    src = tmp_path / "runs"
    src.mkdir()
    path = src / f"{rec.run_id}.json"
    path.write_text(json.dumps(rec.to_json(), indent=1, default=str))
    assert pr.main(["--dir", str(src), "--workers", "1", "--B", str(B_OLD)]) == 0
    d = json.loads(path.read_text())
    assert d["class_p"]["B"] == B_OLD and d["verdict"] is not None
    return src, path


def test_it_writes_a_new_record_at_the_new_B_with_confidence_and_leaves_the_source(priced, tmp_path):
    src, path = priced
    before = path.read_bytes()
    dest = tmp_path / "repriced"
    assert pr.main(["--dir", str(src), "--workers", "1", "--B", str(B_NEW),
                    "--reprice-to", str(dest)]) == 0
    assert path.read_bytes() == before, "the source run file must not change"
    out = json.loads((dest / path.name).read_text())
    assert out["B"] == B_NEW
    # s0's class tier (`class_p_on`) carries no confidence fields; the ETF path's does
    # (`class_p_etf`, tests/test_confidence.py), routed by the next test
    assert out["class_p"]["B"] == B_NEW
    assert out["verdict"]["B"] == B_NEW and out["verdict"].get("confidence") is not None
    stored = json.loads(before)
    assert out["superseded"]["class_p"] == stored["class_p"]
    assert out["superseded"]["verdict"] == json.loads(json.dumps(stored["verdict"], default=str))
    assert "registered 6.5 results" in out["note"]
    assert out["source"]["sha256"] == __import__("hashlib").sha256(before).hexdigest()
    assert (dest / "reprice_readout.txt").exists()


def test_it_never_overwrites_and_never_writes_into_the_source(priced, tmp_path):
    src, path = priced
    dest = tmp_path / "repriced"
    assert pr.main(["--dir", str(src), "--workers", "1", "--B", str(B_NEW),
                    "--reprice-to", str(dest)]) == 0
    first = (dest / path.name).read_bytes()
    with pytest.raises(SystemExit, match="nothing is overwritten"):
        pr.main(["--dir", str(src), "--workers", "1", "--B", str(B_NEW),
                 "--reprice-to", str(dest)])
    assert (dest / path.name).read_bytes() == first
    for bad in (src, src / "sub"):
        with pytest.raises(SystemExit, match="new location"):
            pr.main(["--dir", str(src), "--workers", "1", "--B", str(B_NEW),
                     "--reprice-to", str(bad)])


def test_a_run_without_class_p_is_skipped_not_priced(tmp_path, scripted):
    rec, _ = ac.run_one("replay gate", "s0", SEED, 0, prompts=ac.read_prompts(),
                        credential="seat", defer_pricing=True)
    src = tmp_path / "runs"
    src.mkdir()
    path = src / f"{rec.run_id}.json"
    path.write_text(json.dumps(rec.to_json(), indent=1, default=str))
    r = pr.reprice_one((str(path), B_NEW))
    assert "skip" in r and "no class_p" in r["skip"]


def test_it_requires_B_and_excludes_check(priced, tmp_path):
    src, _ = priced
    with pytest.raises(SystemExit, match="needs --B"):
        pr.main(["--dir", str(src), "--reprice-to", str(tmp_path / "x")])


def test_an_etf_run_is_routed_through_class_p_etf_at_the_new_B(priced, monkeypatch):
    """6.5's runs are ETF runs: the class tier must come from `class_p_etf`, the path
    that carries the confidence fields."""
    _, path = priced
    seen = {}
    real_basis = pr._basis

    def spy(sandbox, table, seed, sup, B):
        seen["B"] = B
        return {"p_upper": 0.5, "B": B, "confidence": {"B": B, "C0": 0.5}}
    monkeypatch.setattr(pr, "panel_of", lambda d: "etf")
    monkeypatch.setattr(pr, "_basis", lambda panel, seed: real_basis("s0", seed))
    monkeypatch.setattr(pr, "class_p_etf", spy)
    r = pr.reprice_one((str(path), B_NEW))
    assert seen["B"] == B_NEW
    assert r["record"]["class_p"]["confidence"]["B"] == B_NEW
