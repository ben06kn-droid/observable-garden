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
    assert us.N_DRAWS == 2000                # the largest policy's count
    assert us.B_DEFAULT == 1_000             # amendment 3: B = 1,000 throughout
    assert us.REDUCIBLE == ("U2", "U3", "U3b")
    # amendment 3's per-policy counts, which is how the design was made minimal
    assert us.DRAWS_FOR == {
        "faithful-restart": 2000, "faithful-stop": 2000,
        "U1": 200, "U1-twin": 200,
        "U2": 500, "U2-twin": 500, "U3": 500, "U3-twin": 500,
        "U3b": 500, "U3b-twin": 500,
        "U4": 1000, "U4-twin": 1000,
    }
    assert set(us.S_TRUE) == {"s0"}           # amendment 3 drops the s3 cell


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
    assert len([n for n in names if n.startswith("faithful-")]) == 2
    for u in ("U1", "U2", "U3", "U3b", "U4"):
        assert u in names and f"{u}-twin" in names, u
    assert len(names) == 12


def test_the_faithful_arm_covers_every_move_kind_in_the_grammar():
    """Amendment 3 registers the faithful arm as the SMALLEST set that uses every
    move kind. If a kind stops being reached, the arm no longer answers rule 1b
    for that kind and the claim in the prereg's coverage table is false."""
    from collections import Counter

    from environments.sandbox import Sandbox
    from quixote.session import Session

    seen = Counter()
    for name in ("faithful-restart", "faithful-stop"):
        for seed in (us.SEED0_SMOKE, us.SEED0_SMOKE + 1, us.SEED0_SMOKE + 3):
            data, cfg = us.make_panel("s0", seed)
            sb = Sandbox(data, periods_per_year=cfg.periods_per_year,
                         spec_class=us.CLS)
            sess = Session.on_sandbox(sb, us.CLS, name_prefix="c")
            us.policies(seed)[name][0](sess)
            seen.update(r.move.kind for r in sess.log.records)
    assert set(seen) == {"init", "pick", "extend_best", "refine", "flip",
                         "swap_worst", "restart", "stop"}, sorted(seen)


def test_both_faithful_searchers_take_the_same_content_moves():
    """Amendment 4, item (1): the pair differs in exactly one thing, the action its
    declared rule names. If one of them stops taking `pick` or `flip`, the pair is
    no longer matched and rule 1a is comparing two different searches."""
    from collections import Counter

    from environments.sandbox import Sandbox
    from quixote.session import Session

    content = {}
    for name in ("faithful-restart", "faithful-stop"):
        data, cfg = us.make_panel("s0", us.SEED0_SMOKE)
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=us.CLS)
        sess = Session.on_sandbox(sb, us.CLS, name_prefix="m")
        us.policies(us.SEED0_SMOKE)[name][0](sess)
        # the PRELUDE: everything up to the first meta move. Past it the two
        # necessarily differ — a restart empties the support, so `faithful-restart`
        # takes one further `extend_best` that `faithful-stop` has no need of.
        recs = list(sess.log.records)
        cut = next((i for i, r in enumerate(recs) if r.move.is_meta), len(recs))
        content[name] = Counter(r.move.kind for r in recs[:cut])
    assert content["faithful-restart"] == content["faithful-stop"], content
    assert {"init", "pick", "extend_best", "refine", "flip", "swap_worst"} <= set(
        content["faithful-restart"])


def test_U2_submits_the_class_maximum_exactly():
    """Amendment 4, item (3). U2's declared-class statistic is `max_theta SR_theta`
    — 6.1 arm D's quantity — which is what lets arm D's exactness transfer instead
    of the rate being re-estimated here. If U2 stops reaching the class argmax the
    class-side claim is void, so this is checked rather than assumed."""
    import numpy as np

    from environments.sandbox import Sandbox
    from garden._full_class_engine import full_class_observed_max
    from quixote.replay import LoggedPolicy
    from quixote.session import Session

    for seed in (us.SEED0_SMOKE, us.SEED0_SMOKE + 1, us.SEED0_SMOKE + 2):
        data, cfg = us.make_panel("s0", seed)
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=us.CLS)
        sess = Session.on_sandbox(sb, us.CLS, name_prefix="u")
        us.policies(seed)["U2"][0](sess)
        base = sb.base_feature_columns()
        ann = float(np.sqrt(cfg.periods_per_year))
        got = LoggedPolicy(sess.log, us.CLS).trace(base, ann).score
        want, _, _, _ = full_class_observed_max(base, us.CLS, annualization=ann)
        assert got == pytest.approx(want, abs=1e-12), (seed, got, want)


def test_two_statistics_are_priced_against_one_null():
    """Amendment 5, item (1). Rule 1a reads the PROCEDURE score's p; the submitted
    score's p is descriptive. Both come from the same replicates, so a searcher
    that ended under its rule has them exactly equal — not merely close, which is
    what two separate bootstraps would give."""
    row = _draw()
    for name in us.MEMBERS:
        r = row[name]
        assert r["procedure_score"] == r["realized_score"], name
        if r["ended_under_its_rule"]:
            assert r["procedure_score"] == pytest.approx(
                r["submitted_score"], abs=1e-12), name
            assert r["p_replay"] == r["p_submitted"], name
        assert r["procedure_minus_submitted"] == pytest.approx(
            r["procedure_score"] - r["submitted_score"]), name


def test_ended_under_its_rule_is_structural_not_a_score_comparison():
    """Amendment 5: `faithful-restart` declares no stop rule and ends by
    submitting, and its two statistics can still coincide when the extra procedure
    steps fail to improve. So the flag must read the LOG, not the scores — an
    earlier version compared scores and called it 'ended under its rule'."""
    row = _draw()
    assert row["faithful-restart"]["ended_under_its_rule"] is False
    assert row["faithful-restart"]["declares_stop_rule"] is False
    assert row["faithful-stop"]["ended_under_its_rule"] is True
    assert row["faithful-stop"]["declares_stop_rule"] is True


def test_the_faithful_prelude_does_not_truncate_its_own_replicates():
    """Amendment 5, item (3), the defect that would have broken rule 1a.

    The prelude's `flip` used to name whatever feature the realized support held,
    which is a move that applies only to the realized data: on a replicate the
    support rarely contains that index, so the replay refused the logged move and
    the null became a distribution of searches cut off at four steps — weaker than
    the statistic it prices. It was refused in 98 of 100 replicates.

    Anchoring the flip on a constant that a single-candidate `pick` places in the
    support takes truncation to well under half. The bound here is deliberately
    loose: what must never return is a null dominated by truncation.
    """
    row = us.run_draw("s0", us.SEED0_SMOKE, B=100)
    for name in ("faithful-restart", "faithful-stop"):
        assert row[name]["truncation_rate"] < 0.5, (name, row[name])
        assert row[name]["replicates_truncated"] == pytest.approx(
            row[name]["truncation_rate"] * 100)


def test_the_fill_counter_sees_a_searcher_that_runs_past_its_log():
    """Amendment 5, item (2). `faithful-restart` declares no stop rule, so its
    replicates run past the logged length onto the fill. The counter read 0 for
    exactly this case before the fix, which contradicted the prose describing it."""
    row = us.run_draw("s0", us.SEED0_SMOKE, B=100)
    assert row["faithful-restart"]["fill_engaged"] > 50
    # and the anchor feature is a constant, not read off the data
    assert us.FLIP_ANCHOR == 0


def test_the_two_descriptive_readouts_are_recorded_per_run():
    """Amendment 4, item (4): both readouts, on every policy, with no gate. They
    are descriptive, so the test checks they EXIST and are on the scales claimed,
    not that they take any particular value."""
    row = _draw()
    for name in us.MEMBERS:
        r = row[name]
        assert -1.0 <= r["p_class_minus_p_replay"] <= 1.0, name
        assert r["p_class_minus_p_replay"] == pytest.approx(
            r["p_class"] - r["p_replay"]), name
        assert r["submitted_minus_fill"] == pytest.approx(
            r["submitted_score"] - r["fill_score"]), name
        assert 0.0 < r["p_class"] <= 1.0, name


def test_the_faithful_pair_differs_on_whether_the_priced_score_is_the_submitted_one():
    """Amendment 4, item (1), the asymmetry it registers. `faithful-stop` ends on
    its own declared rule, so the replay prices exactly what the session submitted.
    `faithful-restart` declares no stop rule, so the replay runs on under the fill
    to its budget and may price MORE than was submitted. Registering that means
    holding the mechanism in place, not just the sentence."""
    row = _draw()
    stop = row["faithful-stop"]
    assert stop["realized_score"] == pytest.approx(stop["submitted_score"])
    # and never less than submitted: the fill can only add
    r = row["faithful-restart"]
    assert r["realized_score"] >= r["submitted_score"] - 1e-9


def test_each_faithful_searcher_declares_exactly_one_rule():
    """Why the arm needs two searchers and not one. Two rules sharing a predicate
    fire together, so WHICH action the log took is a decision of the policy rather
    than a function of the declared rules — and the commitment replay, which
    re-derives the decision from the rules, refuses it. One rule per searcher
    keeps the replay determinate."""
    from environments.sandbox import Sandbox
    from quixote.session import Session

    for name in ("faithful-restart", "faithful-stop"):
        data, cfg = us.make_panel("s0", us.SEED0_SMOKE)
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=us.CLS)
        sess = Session.on_sandbox(sb, us.CLS, name_prefix="d")
        us.policies(us.SEED0_SMOKE)[name][0](sess)
        assert len(sess.log.declared_trigger_records) == 1, name
        # and a declared budget, or the replay falls back to 7.1's default of 12
        # steps — below this arm's own length, which reads as a disagreement the
        # search never had
        assert sess.log.budget == us.FAITHFUL_BUDGET, name


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
    us.policies(us.SEED0_SMOKE)["faithful-restart"][0](sess)
    base = sb.base_feature_columns()

    p, realized, _p_sub, _eng, _tr = us._trigger_null(
        sess.log, base, ann, B=25, seed=3)
    nulls, _ = three_nulls(sess.log, us.CLS, base, ann, B=25, seed=3)
    expected = (1 + np.sum(np.asarray(nulls.trigger) >= nulls.realized_score)) / 26
    assert p == pytest.approx(expected)
    assert realized == pytest.approx(float(nulls.realized_score))
