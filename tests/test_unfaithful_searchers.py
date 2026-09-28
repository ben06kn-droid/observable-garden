"""7.3's scripted driver: does it route the registered blocks, and does the
smoke stay cost-only?

`prereg/unfaithful-searchers.md` registers three seed blocks and the standing
rule that a smoke or scaling curve reports cost alone. Both are things a reader
cannot check by reading output — a rule quantity printed on the cost-only block
looks like any other number — so they are checked here.

The searchers themselves are checked against the predictions the amendments
register, because a driver whose U3 never changes a trigger is not running U3.
"""
import numpy as np
import pytest

from experiments import unfaithful_searchers as us

RULE_WORDS = ("rejection", "reject", "p-value", "p_value", "p =", "wilson",
              "type-i", "type i", "power", "certified", "depends_on_judgment",
              "verdict", "distance", "contradicted", "misfire")


# -- seed-block routing -------------------------------------------------------

def test_the_three_registered_blocks_are_the_ones_the_driver_uses():
    assert (us.SEED0, us.SEED0_REPLICATION, us.SEED0_SMOKE) == (500_000, 510_000, 990_000)
    assert us.N_DRAWS == 2000 and us.B_DEFAULT == 10_000
    assert us.B_FALLBACK == 1_000            # amendment 2's second lever
    assert us.DRAWS_U1 == 200                # amendment 1: an identity, not a rate
    assert us.REDUCIBLE == ("U2", "U3", "U3b")   # amendment 2's third lever


def test_each_flag_routes_to_its_own_block():
    """`--smoke` to 990000, `--replication` to 510000, neither to 500000. A
    registered draw taken from the smoke block would be a draw nobody registered."""
    assert us.is_smoke_block(us.SEED0_SMOKE)
    assert us.is_smoke_block(us.SEED0_SMOKE + 999)
    assert not us.is_smoke_block(us.SEED0_SMOKE + 1000)
    for other in (us.SEED0, us.SEED0_REPLICATION):
        assert not us.is_smoke_block(other)
    # the blocks do not overlap, at 2,000 draws each
    assert us.SEED0 + us.N_DRAWS <= us.SEED0_REPLICATION
    assert us.SEED0_REPLICATION + us.N_DRAWS <= us.SEED0_SMOKE


def test_a_registered_run_refuses_an_unregistered_B():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "experiments.unfaithful_searchers",
                        "--cell", "s0", "--B", "3000"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "fallback" in (r.stdout + r.stderr)
    r2 = subprocess.run([sys.executable, "-m", "experiments.unfaithful_searchers",
                         "--smoke", "2", "--replication"], capture_output=True, text=True)
    assert r2.returncode != 0 and "exclusive" in (r2.stdout + r2.stderr)


# -- the smoke prints no rule quantity ----------------------------------------

def _smoke_data(n=2, B=12):
    return us.run("s0", n, us.SEED0_SMOKE, B, None, None)


def test_the_cost_report_carries_no_rule_quantity():
    """`prereg/README.md`: a smoke reports wall time, per-draw seconds and guard
    counts. Not a rejection rate, not a p-value, not a verdict share."""
    text = us.cost_report(_smoke_data()).lower()
    for word in RULE_WORDS:
        assert word not in text, word
    assert "cost only" in text and "per draw" in text


def test_the_cost_report_refuses_a_block_that_is_not_the_cost_only_one():
    """The rule is enforced where it cannot be forgotten: a registered block's
    data cannot be rendered through the cost path at all."""
    data = _smoke_data()
    data["settings"]["seed0"] = us.SEED0
    with pytest.raises(ValueError, match="cost-only block"):
        us.cost_report(data)
    data["settings"]["seed0"] = us.SEED0_REPLICATION
    with pytest.raises(ValueError, match="cost-only block"):
        us.cost_report(data)


def test_a_registered_run_prints_no_reading_at_all(capsys):
    """Not even a summary: the rules are read by the reader, on the registered
    block, once."""
    us.main(["--smoke", "1", "--B", "8", "--workers", "1",
             "--out", "/tmp/us_smoke_test"])
    out = capsys.readouterr().out.lower()
    for word in RULE_WORDS:
        assert word not in out, word


# -- the searchers are the ones the amendments register -----------------------

def _draw(seed=None, B=20):
    return us.run_draw("s0", seed or us.SEED0_SMOKE, B=B)


def test_the_policy_set_is_the_faithful_arm_plus_four_unfaithful_and_their_twins():
    names = set(us.MEMBERS)
    assert len([n for n in names if n.startswith("faithful-")]) == 6
    for u in ("U1", "U2", "U3", "U3b", "U4"):
        assert u in names and f"{u}-twin" in names, u
    assert len(names) == 16


def test_U1_and_its_twin_price_identically_which_is_rule_3():
    """Amendment 1: they execute identical moves, because the harness executes
    the DECLARED rule. Their p-values are equal, not close — and U1's log differs
    only in `contradicted`."""
    row = _draw()
    assert row["U1"]["p_replay"] == row["U1-twin"]["p_replay"]
    assert row["U1"]["realized_score"] == row["U1-twin"]["realized_score"]
    assert row["U1"]["contradicted_picks"] == 1
    assert row["U1-twin"]["contradicted_picks"] == 0


def test_U2_reaches_the_peeked_specification_and_prices_far_below_its_twin():
    """Rule 4. The peek chooses the MENU — `SCOPE.md`'s "realized Sharpe values
    feeding back into which columns appear next" — so the replay re-derives from
    one to three candidates while the realized choice came from 82,240."""
    row = _draw()
    assert row["U2"]["p_replay"] < row["U2-twin"]["p_replay"]
    assert row["U2"]["prior_declared"] and row["U2-twin"]["prior_declared"]


def test_U3_changes_bind_and_U3b_changes_do_not():
    """Rule 5. U3 changes a rule that has fired, so the committed-rule replay
    stops where the realized search did not: bracketed. U3b changes before the
    rule ever fires, so the change never binds and the run prices normally."""
    row = _draw()
    u3, u3b = row["U3"], row["U3b"]
    assert u3["trigger_changes"] >= 2          # the pilot's observed range
    assert not u3["commitment_ok"]
    assert u3["gated_verdict"] == "DEPENDS_ON_JUDGMENT"
    assert u3b["trigger_changes"] >= 2
    assert u3b["commitment_ok"]
    assert u3b["gated_verdict"] in ("CERTIFIED", "FAIL")


def test_the_faithful_arm_trips_no_check():
    """Rule 1b, registered as 0 misfires. A check that fires on an honest
    searcher makes every unfaithful result unreadable."""
    row = _draw()
    for name in (n for n in us.MEMBERS if n.startswith("faithful-")):
        r = row[name]
        assert r["integrity_ok"] and r["commitment_ok"], name
        assert r["contradicted_picks"] == 0 and r["trigger_changes"] == 0, name


def test_every_run_is_priced_whatever_the_checks_said():
    """Amendment 2: the driver prices every run and records the check-gated
    verdict BESIDE the p, so one pass yields rule 1a and rule 1b on the same
    runs. A bracketed run still has a p-value."""
    row = _draw()
    for name in us.MEMBERS:
        r = row[name]
        assert 0.0 < r["p_replay"] <= 1.0, name
        assert r["gated_verdict"] in ("CERTIFIED", "FAIL", "DEPENDS_ON_JUDGMENT",
                                      "UNDECIDABLE"), name
    assert row["U3"]["gated_verdict"] == "DEPENDS_ON_JUDGMENT"
    assert row["U3"]["p_replay"] > 0          # priced anyway


def test_the_single_null_equals_three_nulls_trigger_replicate_for_replicate():
    """The driver computes the certifying null alone, not all three. It must be
    the same number `quixote.certify.three_nulls` would give for that null, on
    the same RNG stream."""
    from environments.sandbox import Sandbox
    from quixote.certify import three_nulls
    from quixote.session import Session

    data, cfg = us.make_panel("s0", us.SEED0_SMOKE)
    ann = float(np.sqrt(cfg.periods_per_year))
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=us.CLS)
    sess = Session.on_sandbox(sb, us.CLS, name_prefix="t")
    us.policies(us.SEED0_SMOKE)["faithful-mixed"][0](sess)
    base = sb.base_feature_columns()

    p, realized, _ = us._trigger_null(sess.log, base, ann, B=25, seed=3)
    nulls, _ = three_nulls(sess.log, us.CLS, base, ann, B=25, seed=3)
    expected = (1 + np.sum(np.asarray(nulls.trigger) >= nulls.realized_score)) / 26
    assert p == pytest.approx(expected)
    assert realized == pytest.approx(float(nulls.realized_score))
