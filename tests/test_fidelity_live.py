"""`fidelity.py --live`, against STUB responders only. No model is ever called here."""
import json
import re

import pytest

from environments import planted_panel as pp
from experiments import fidelity as fd
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture
def run_dir(base, monkeypatch, tmp_path):
    """Two planted dry runs (replay gate, scripted: a pick and a stop), on a synthetic
    base that `load_base` returns."""
    from experiments import planted_agent as pa
    from experiments.real_prompts import read_prompts
    monkeypatch.setattr(pp, "load_base", lambda: base)
    for i, seed in enumerate((640910, 640911)):
        rec = pa.run_one("replay gate", seed, 1.0, i, prompts=read_prompts(),
                         dry_run=True, base=base)
        (tmp_path / f"{rec.run_id}.json").write_text(
            json.dumps(rec.to_json(), indent=1, default=str))
    return tmp_path


def _decs(run_dir, kinds=("pick",)):
    out = []
    for f in sorted(run_dir.glob("cell_*.json")):
        out += fd.decisions_of(f, kinds)
    return out


def test_decisions_carry_the_runs_panel_level_and_arm(run_dir):
    decs = _decs(run_dir, ("pick", "stop"))
    assert {d["kind"] for d in decs} == {"pick", "stop"}
    for d in decs:
        assert d["start"]["panel"] == "planted" and d["start"]["level"] == 1.0
        assert d["arm"] == "replay gate"


def test_planted_resampling_keeps_the_labels_and_moves_the_numbers(run_dir):
    dec = _decs(run_dir)[0]
    a, b = fd.resampled_shown(dec, "planted", 0), fd.resampled_shown(dec, "planted", 1)
    assert [l for l, _ in a] == [l for l, _ in dec["shown_self"]] == [l for l, _ in b]
    assert a == fd.resampled_shown(dec, "planted", 0)          # reproducible per rep
    assert [v for _, v in a] != [v for _, v in b]


def test_a_presentation_is_stateless_and_forced_choice(run_dir):
    dec = _decs(run_dir)[0]
    sp = fd.system_prompt_of(dec)
    r0 = fd.presentation_request(dec, fd.resampled_shown(dec, "planted", 0), sp)
    r1 = fd.presentation_request(dec, fd.resampled_shown(dec, "planted", 1), sp)
    strip = lambda t: re.sub(r"-?\d+\.\d+", "#", t)
    assert strip(r0["user"]) == strip(r1["user"])          # only the numbers differ
    assert r0["system"] == r1["system"] == sp
    assert r0["options"] == [l for l, _ in dec["shown_self"]]
    assert "choose" in r0["user"] and r0["tool"]["name"] == "choose"
    meta = _decs(run_dir, ("stop",))[0]
    assert fd.options_for(meta, []) == ["continue", "stop", "restart"]


@pytest.mark.parametrize("raw,ok", [({"choice": "stop"}, "stop"), ({"choice": "x"}, None),
                                    (None, None), ("stop", None), ({}, None)])
def test_answers_outside_the_options_are_no_answer(raw, ok):
    assert fd.parse_answer(raw, ["continue", "stop", "restart"]) == ok


def test_the_live_responder_with_stubs_measures_agreement_and_no_answer(run_dir):
    decs = _decs(run_dir, ("pick", "stop"))
    seen = []

    def first_option(req):
        seen.append(req)
        return {"choice": req["options"][0]}

    resp = fd.LiveResponder(fd.system_prompt_of, client=first_option, name="stub")
    rows = fd.measure(decs, "planted", 4, resp)
    # expected agreement, computed independently from the same replicates
    for row, dec in zip(rows, decs):
        exp = 0
        for rep in range(4):
            sh = fd.resampled_shown(dec, "planted", rep)
            exp += int(fd.options_for(dec, sh)[0] == fd.rule_choice(dec, sh))
        assert row["agreed"] == exp and row["no_answer"] == 0
    assert len(resp.log) == len(seen) == 4 * len(decs)
    # statelessness: no request carries anything from another presentation
    seen[0]["user"] = "mutated"
    assert all("mutated" not in r["user"] for r in seen[1:])
    assert all("Recorded" not in r["user"] for r in seen)

    silent = fd.LiveResponder(fd.system_prompt_of, client=lambda req: None, name="stub")
    rows = fd.measure(decs, "planted", 3, silent)
    assert all(r["agreed"] == 0 and r["no_answer"] == 3 for r in rows)


def test_main_live_refuses_without_yes_and_writes_the_log_with_a_stub(run_dir, monkeypatch,
                                                                      capsys):
    with pytest.raises(SystemExit, match="--yes"):
        fd.main(["--dir", str(run_dir), "--panel", "planted", "--presentations", "2",
                 "--live"])
    assert "model calls" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="exactly one"):
        fd.main(["--dir", str(run_dir), "--panel", "planted", "--live", "--dry-run"])
    monkeypatch.setattr(fd, "sdk_client", lambda req: {"choice": req["options"][-1]})
    # LiveResponder's default client was bound at definition; main passes sdk_client
    assert fd.main(["--dir", str(run_dir), "--panel", "planted", "--presentations", "2",
                    "--live", "--yes"]) == 0
    text = (run_dir / "fidelity_live.txt").read_text()
    assert text.startswith("check 2 — FIDELITY (LIVE")
    lines = (run_dir / "fidelity_live_presentations.jsonl").read_text().splitlines()
    assert lines and all({"raw", "answer", "predicted", "options"} <= set(json.loads(l))
                         for l in lines)


def test_the_dry_run_still_answers_by_the_rule(run_dir):
    assert fd.main(["--dir", str(run_dir), "--panel", "planted", "--presentations", "2",
                    "--dry-run"]) == 0
    text = (run_dir / "fidelity_dryrun.txt").read_text()
    assert "DRY RUN" in text and "rate 1.0000" in text
