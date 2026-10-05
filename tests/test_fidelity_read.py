"""Check 2's rule reader, on SYNTHETIC presentation logs only."""
import json

import pytest

from experiments import fidelity_read as fr


def _rows(kind, n_dec, n_pres, agree_frac, none_frac=0.0):
    out = []
    for d in range(n_dec):
        for p in range(n_pres):
            i = d * n_pres + p
            total = n_dec * n_pres
            none = i < int(none_frac * total)
            agree = (not none) and (i < int((agree_frac + none_frac) * total))
            out.append({"run_id": f"r{d}", "step": d, "kind": kind,
                        "options": ["a", "b"], "raw": None if none else {"choice": "a"},
                        "answer": None if none else ("a" if agree else "b"),
                        "predicted": "a"})
    return out


def _f(tmp_path, rows):
    f = tmp_path / "fidelity_live_presentations.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return f


def test_the_three_branches(tmp_path):
    rows = (_rows("pick", 12, 20, 0.90) + _rows("stop", 10, 20, 0.70)
            + _rows("restart", 9, 20, 1.0))
    text = fr.read(fr.load(_f(tmp_path, rows)))
    line = {l.split()[0]: l for l in text.splitlines()[4:]}
    assert "NOT priced locally" in line["pick"] and " 0.9000" in line["pick"]
    assert "PRICED LOCALLY" in line["stop"] and " 0.7000" in line["stop"]
    assert "UNMEASURED (9 decisions)" in line["restart"]


def test_agreement_is_recomputed_and_no_answer_disagrees(tmp_path):
    rows = _rows("pick", 10, 20, 0.80, none_frac=0.10)
    text = fr.read(fr.load(_f(tmp_path, rows)))
    line = next(l for l in text.splitlines() if l.strip().startswith("pick"))
    assert "   160         20  0.8000" in line and "NOT priced locally" in line
    rows = _rows("pick", 10, 20, 0.79)                        # just below
    assert "PRICED LOCALLY" in fr.read(fr.load(_f(tmp_path, rows)))


def test_it_refuses_a_file_that_is_not_a_live_log(tmp_path):
    with pytest.raises(SystemExit, match="missing"):
        fr.load(tmp_path / "nope.jsonl")
    bad = _rows("pick", 1, 1, 1.0)
    del bad[0]["raw"]
    with pytest.raises(SystemExit, match="lacks"):
        fr.load(_f(tmp_path, bad))
    bad = _rows("pick", 1, 1, 1.0)
    bad[0]["answer"] = "zzz"
    with pytest.raises(SystemExit, match="outside its options"):
        fr.load(_f(tmp_path, bad))


def test_it_reads_what_fidelity_live_writes(tmp_path):
    """The log format is fidelity.py's LiveResponder's, field for field."""
    from experiments import fidelity as fd
    resp = fd.LiveResponder(lambda dec: "sys", client=lambda req: {"choice": req["options"][0]})
    dec = {"run_id": "r", "step": 3, "kind": "stop", "prefix": [], "declared": [],
           "shown_self": []}
    resp(dec, [("step", 3.0), ("best", 1.0)])
    rows = fr.load(_f(tmp_path, [json.loads(json.dumps(r, default=str)) for r in resp.log]))
    assert rows[0]["kind"] == "stop" and rows[0]["answer"] == "continue"
