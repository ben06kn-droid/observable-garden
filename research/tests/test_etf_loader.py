"""The loader refuses the sealed holdout copy, its directory, and holdout dates."""
import datetime as dt
from pathlib import Path

import pytest

from data.etf_loader import (HOLDOUT_START, HoldoutRefused, load_insample, load_panel,
                            refuse_sealed_or_quarantined)


@pytest.mark.parametrize("name", ["etf_holdout_2023_2025.tar.gz.enc", "holdout.gpg", "x.asc"])
def test_a_sealed_archive_is_refused_unopened(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"not read")
    with pytest.raises(HoldoutRefused, match="sealed archive"):
        refuse_sealed_or_quarantined(p)
    with pytest.raises(HoldoutRefused):
        load_insample(p)


def test_anything_under_desktop_is_refused():
    desktop = Path.home() / "Desktop"
    with pytest.raises(HoldoutRefused, match="Desktop"):
        refuse_sealed_or_quarantined(desktop / "whatever.csv")
    with pytest.raises(HoldoutRefused, match="Desktop"):
        refuse_sealed_or_quarantined(desktop)


def test_the_real_sealed_copy_is_refused_if_it_is_there():
    """The actual second copy, by name. Skipped if it is not on this machine."""
    p = Path.home() / "Desktop" / "etf_holdout_2023_2025.tar.gz.enc"
    if not p.exists():
        pytest.skip("the sealed copy is not on this machine")
    with pytest.raises(HoldoutRefused):
        refuse_sealed_or_quarantined(p)


def test_a_file_containing_a_holdout_date_is_refused_not_filtered(tmp_path):
    p = tmp_path / "SPY.csv"
    p.write_text("date,adjclose,volume\n2022-12-30,100.0,1000\n2023-01-03,101.0,1000\n")
    with pytest.raises(HoldoutRefused, match="2023-01-03"):
        load_insample(p)


def test_an_in_sample_file_loads(tmp_path):
    p = tmp_path / "SPY.csv"
    p.write_text("date,adjclose,volume\n2005-01-03,100.0,1000\n2022-12-30,200.0,2000\n")
    dates, adj, vol = load_insample(p)
    assert dates == [dt.date(2005, 1, 3), dt.date(2022, 12, 30)]
    assert adj == [100.0, 200.0] and vol == [1000.0, 2000.0]
    assert max(dates) < HOLDOUT_START


def test_the_exported_panel_loads_and_stops_before_the_holdout():
    """The real export, if it has been fetched to this machine."""
    from data.etf_loader import INSAMPLE_DIR
    if not INSAMPLE_DIR.exists() or not any(INSAMPLE_DIR.glob("*.csv")):
        pytest.skip("the in-sample export is not on this machine")
    panel = load_panel()
    assert len(panel) >= 30
    for tk, (dates, adj, vol) in panel.items():
        assert max(dates) < HOLDOUT_START, tk
        assert len(dates) == len(adj) == len(vol) > 4000, tk
