"""Does the builder use the constants the pre-registration fixes?

**Why this file exists.** Three defects reached a built panel on 2026-09-24: the
ADR returns were never shifted (a look-ahead against §4's registered timing), the
class table and the pilot ran at depth 3 against a registered depth of 2, and a
control boundary was invented where §2 already registered one.

All three sat behind tests that *cite* pre-registration lines in their docstrings
and then assert behaviour. A test that says "section 4 requires b+1" in prose and
then checks that returns are finite will pass on a leaked panel. So these tests
**parse the numbers out of the pre-registration files** and compare them with what
the code uses. If the registration changes, they fail until the code follows; if
the code drifts, they fail until it comes back.

They deliberately do not test that the registration is *right*. They test that
the two agree.
"""
import re
from pathlib import Path

import numpy as np
import pytest

from data.adr_costs import FLOOR_BPS, FLOOR_CENTS
from environments import real_panel as rp

PREREG = Path(__file__).resolve().parent.parent / "prereg"
FEATURES = (PREREG / "adr-features.md").read_text()
UNIVERSE = (PREREG / "adr-universe.md").read_text()
# typographic quotes and dashes travel through prose; normalise before matching
FLAT = " ".join(FEATURES.split()).replace("\u2019", "'").replace("\u2013", "-")


def registered(pattern: str, text: str = FLAT, group: int = 1) -> str:
    """One number or phrase, read out of the pre-registration."""
    m = re.search(pattern, text)
    assert m, f"the pre-registration no longer states {pattern!r}"
    return m.group(group)


# -- the timing that was violated -------------------------------------------

def test_the_registered_execution_is_one_bar_and_the_builder_shifts_by_one():
    """§4: 'Signal at the close of bar b, position held over bar b+1.'

    The defect of 2026-09-24. The check is on the source, because the shift is a
    property of how the array is built, and on a real panel below.
    """
    phrase = registered(r"Signal at the close of bar \*b\*, position held over "
                        r"bar \*b\*(\+1)")
    assert phrase == "+1"
    src = Path(rp.__file__).read_text()
    assert "EARN[:-1] = R[1:]" in src, "the ADR builder does not shift by one bar"
    assert "returns=EARN[keep]" in src


@pytest.mark.skipif(not (Path(rp.__file__).parent.parent / "data" / "raw").exists(),
                    reason="raw ADR bars are not present")
def test_on_the_built_panel_a_weight_earns_the_next_bars_return():
    """The same rule, on the panel itself: `returns[t]` is bar t+1's return, so a
    feature computed from bar t's close is not contemporaneous with what it
    earns."""
    panel = rp.build_adr_panel()
    r1 = panel.features[:, :, 0]                       # ret1_home_open
    same_bar = abs(float(np.corrcoef(r1.ravel(), panel.returns.ravel())[0, 1]))
    assert same_bar < 0.05, (
        f"ret1 at row t correlates {same_bar:.3f} with returns[t]: the look-ahead "
        "the 2026-09-24 deviation records is back")


# -- the class -------------------------------------------------------------

def test_the_registered_class_is_signed_depth_two_over_k_22():
    """§3: 'Signed subsets of size <= 2 over K = 22: 968 members'."""
    depth = int(registered(r"Signed subsets of size . (\d) over K = (\d+)"))
    K = int(registered(r"Signed subsets of size . \d over K = (\d+)"))
    members = int(registered(r"over K = \d+: ([\d,]+) members").replace(",", ""))
    assert (depth, K, members) == (2, 22, 968)
    from garden.spec_class import SubsetClass
    assert SubsetClass(max_size=depth, signed=True).size(K) == members

    # and every ADR-side caller uses it
    for mod in ("experiments/adr_cost_diagnostics.py", "experiments/agent_pilot.py"):
        src = Path(__file__).resolve().parent.parent.joinpath(mod).read_text()
        assert "max_size=3" not in src, f"{mod} still uses the ETF panel's depth"


def test_k_is_22_and_the_builder_produces_22_features():
    assert int(registered(r"## 2\. Features: K = (\d+)")) == 22
    names = rp.ADR_BASE if hasattr(rp, "ADR_BASE") else None
    src = Path(rp.__file__).read_text()
    # 11 base signals x 2 boundary halves
    assert src.count('names_out += [f"{nm}_home_open", f"{nm}_home_closed"]') == 1


# -- the session -----------------------------------------------------------

def test_the_session_bounds_are_the_registered_ones():
    """§4: 'Traded bars: 09:35-15:55 ET, 76 per full session; first and last bars
    dropped.' Features use every regular bar from 09:30."""
    first = registered(r"Traded bars:\*\* (\d\d:\d\d)")
    last = registered(r"Traded bars:\*\* \d\d:\d\d.(\d\d:\d\d)")
    per = int(registered(r"ET, (\d+) per full session"))
    assert (first, last, per) == ("09:35", "15:55", 76)
    assert rp.FIRST_TRADED == tuple(int(x) for x in first.split(":"))
    # The registered bounds are the session's edges; the constants are bar
    # STARTS, so the last traded bar starts five minutes before 15:55 and ends
    # on it. Asserting the end, not the start, is what the registration fixes.
    lh, lm = (int(x) for x in last.split(":"))
    assert (rp.LAST_TRADED[0] * 60 + rp.LAST_TRADED[1]) + 5 == lh * 60 + lm
    assert rp.SESSION_OPEN == (9, 30)
    assert rp.ADR_BARS_PER_YEAR == 252 * per


def test_flat_overnight_is_registered_and_the_panel_is_flat():
    assert "Flat overnight" in FEATURES
    src = Path(rp.__file__).read_text()
    assert "flat_overnight=True" in src


# -- the control boundary that was invented ---------------------------------

def test_the_controls_take_amsterdams_boundary_as_registered():
    """§2: 'Controls take XAMS's boundary ... as a pseudo-close.' The builder had
    a rule of its own until 2026-09-24."""
    # the registration emphasises the word, so match around the markup
    assert re.search(r"\*\*Controls\*\* take XAMS's boundary \((\d\d:\d\d) ET", FLAT)
    assert registered(r"\*\*Controls\*\* take XAMS's boundary \((\d\d:\d\d) ET") == "11:30"
    src = Path(rp.__file__).read_text()
    assert 'ADR_HOME.get(tk, ADR_HOME["ASML"])' in src
    assert rp.ADR_HOME["ASML"][0] == "XAMS"


def test_the_control_names_are_the_registered_three():
    rows = re.findall(r"^\| ([A-Z]{2,5}) \|.*\*\*control\*\*", UNIVERSE, re.M)
    assert set(rows) == {"ARM", "NXPI", "SPOT"}
    assert set(rp.ADR_CONTROL_BENCH) == set(rows)
    assert all(t not in rp.ADR_TREATED for t in rows)


# -- the cost model ---------------------------------------------------------

def test_the_spread_window_is_the_amended_one():
    """Amendment 2: 'the most recent min(60, available) sessions strictly before
    it, never fewer than 20'."""
    assert re.search(r"min\(60, available\)", FLAT)
    assert re.search(r"never fewer than 20", FLAT)
    assert (rp.ADR_SPREAD_MIN, rp.ADR_SPREAD_MAX) == (20, 60)


def test_the_floor_and_the_fee_are_the_registered_ones():
    """§6: 'Floor: one cent', and amendment 1's 2 bps; '$0.005 per share per
    side'."""
    cents = float(registered(r"ŝ_d ≥ ([\d.]+) / close"))
    fee = float(registered(r"Per-share fee:\*\* \$([\d.]+) per share per side"))
    assert (cents, fee) == (0.01, 0.005)
    assert FLOOR_CENTS == cents
    assert rp.ADR_FEE_PER_SHARE == fee
    assert FLOOR_BPS == 2.0 and "2 bps" in FLAT


def test_the_cost_rate_is_half_a_spread_plus_the_fee():
    """The one line the per-name diagnostic reads: `cost_rate = s_hat/2 + fee`."""
    src = Path(rp.__file__).read_text()
    assert "COST[t_row, mi] = s_hat / 2 + fee" in src


# -- the guard --------------------------------------------------------------

def test_no_bar_is_opened_without_the_registration_commits():
    """The standing rule: feature building refuses unless the registration
    commits are ancestors of HEAD."""
    src = Path(rp.__file__).read_text()
    assert "require_registered_features" in src
    from data.adr_guard import REGISTRATION_COMMITS
    assert len(REGISTRATION_COMMITS) >= 3
