"""The French long-history read end to end on a SYNTHETIC panel (never the real file): the
repeat, the two W2 streams with the unweighted beside, the class under W2, the performance
line, the block lengths; the input loader's refusals; the runner refuses while not live."""
import datetime as dt

import numpy as np
import pytest

from experiments import french_long_read as FL


@pytest.fixture(scope="module")
def synth():
    rng = np.random.default_rng(717000)
    T, M = 1400, 8
    R = 0.01 * rng.standard_normal((T, M))
    R[:150, 6] = np.nan                             # a late industry
    d0 = dt.date(1926, 7, 1)
    dates = [d0 + dt.timedelta(days=k) for k in range(T)]
    return dates, [f"N{j}" for j in range(M)], R


def test_the_read_on_a_synthetic_panel(synth, tmp_path, monkeypatch):
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    monkeypatch.setattr(FL, "B", 120)
    dates, names, R = synth
    rec = FL.run_read(dates, names, R, "b1", members_in_order(CLS, 40)[:128], workers=2,
                      cache_dir=tmp_path, cache_name="synthetic-long")
    assert rec["repeat_bit_identical"] == {"d1": True, "d0": True}
    t1, t2, t3 = rec["test1_stream_d1"], rec["test2_stream_d0"], rec["test3_class_d1"]
    assert t1["alphas"] == {"96%": 0.03, "90%": 0.06} and t2["alphas"] == {"96%": 0.01, "90%": 0.02}
    assert "NOT IMPLEMENTABLE" in t2["test"] and t2["n_rows"] == t1["n_rows"] + 2
    for t in (t1, t2, t3):
        assert 0 < t["weighted_W2"]["p"] <= 1 and t["unweighted"]["label"] == FL.UNWEIGHTED_LABEL
    assert set(t1["performance_line"]["lines"]) == {"252", "756"} and "block_length_last_neff" in t1
    assert t3["N"] == 128 and len(t3["weighted_W2"]["best_member"]["features"]) >= 1
    assert rec["entry_dates"]["N6"] == str(dates[150])


def test_the_loader_refuses_late_rows_and_disorder(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("date,A,B\n1989-12-29,0.1,\n1990-01-02,0.2,0.3\n")
    with pytest.raises(SystemExit, match="after the read's end"):
        FL.load("b1", [p])
    q = tmp_path / "b.csv"
    q.write_text("date,A,B\n1926-07-01,0.1,\n1926-07-02,0.2,0.3\n")
    d, n, R = FL.load("b1", [q])
    assert np.isnan(R[0, 1]) and R[1, 0] == pytest.approx(0.002)
    with pytest.raises(SystemExit, match="strictly increasing"):
        FL.load("b1", [q, q])


def test_the_runner_refuses_while_not_live():
    assert any("not live" in b for b in FL.refusals("0" * 40, None))
