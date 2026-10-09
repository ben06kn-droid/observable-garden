"""The French missing-flag counter on SYNTHETIC text: counts only; rows from 2008-12-29 skipped."""
from data import count_french_missing as C


def _text():
    rows = ["19260701,-99.99,0.10,0.20", "19260702,-99.99,-999,0.30", "19270103,0.1,0.2,0.3",
            "19270104,0.2,-99.99,0.1", "19270105,0.2,0.1,0.1", "20081229,-99.99,-99.99,-99.99"]
    return "\n".join(["header", "  Average Value Weighted Returns -- Daily", ",A,B,C"] + rows +
                     ["", "  Average Equal Weighted Returns -- Daily"])


def test_counts_by_year_and_industry():
    r = C.counts(_text())
    assert r["years"]["1926"] == {"rows": 2, "missing": {"A": 2, "B": 1, "C": 0}}
    assert r["years"]["1927"] == {"rows": 3, "missing": {"A": 0, "B": 1, "C": 0}}
    assert "2008" not in r["years"]
    assert r["first_date_all_present"] == "19270103"
    assert r["present_without_later_gap_from"] == {"A": "19270103", "B": "19270105", "C": "19260701"}
