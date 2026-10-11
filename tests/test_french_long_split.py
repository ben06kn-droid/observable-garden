"""The host-side cut on SYNTHETIC zip text: windows, missing cells, counts, entry dates, refusals."""
import pytest

from data import french_long_split as S


def _text():
    rows = ["19260701,-99.99,0.10,0.20", "19260702,-99.99,0.30,0.25", "19260706,0.1,0.2,0.3",
            "19891229,0.2,-99.99,0.1", "19900102,0.5,0.5,0.5", "19951229,0.4,0.4,0.4", "20081226,0.1,0.1,0.1",
            "20200102,9.9,9.9,9.9"]
    return "\n".join(["header", "  Average Value Weighted Returns -- Daily", ",A,B,C"] + rows +
                     ["", "  Average Equal Weighted Returns -- Daily"])


def test_the_b1_cut_counts_and_entry():
    c = S.cut(_text(), *S.CUTS["b1"])
    assert [d for d, _ in c["rows"]] == ["19260701", "19260702", "19260706", "19891229"]
    assert c["rows"][0][1] == ["", "0.10", "0.20"] and c["rows"][3][1][1] == ""
    assert c["counts"]["years"]["1926"]["missing"] == {"A": 2, "B": 0, "C": 0}
    assert c["counts"]["first_date_all_present"] == "19260706"
    assert c["counts"]["entry_rule_ii"] == {"A": "19260706", "B": None, "C": "19260701"}


def test_the_holdout_and_b2_extra_windows_never_reach_2020():
    h = S.cut(_text(), *S.CUTS["b1-holdout"])
    assert [d for d, _ in h["rows"]] == ["19900102", "19951229"]
    e = S.cut(_text(), *S.CUTS["b2-extra"])
    assert [d for d, _ in e["rows"]] == ["19900102", "19951229", "20081226"]
    assert all(not d.startswith("2020") for d, _ in e["rows"])


def test_refuses_until_live(tmp_path):
    with pytest.raises(SystemExit, match="not live"):
        S.main(["--cut", "b1", "--zip", str(tmp_path / "x.zip"), "--out", str(tmp_path / "o.csv")])
