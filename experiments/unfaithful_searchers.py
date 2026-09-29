"""unfaithful-searchers (7.3, scripted half): the driver.

Pre-registered in `prereg/unfaithful-searchers.md`, amendments 1 and 2. Builds
searchers that **declare one rule and use another**, and measures whether the
harness's checks catch them — and what the certifying null's size is when they
are not.

    python -m experiments.unfaithful_searchers --smoke 8 --B 200 --workers 8
    python -m experiments.unfaithful_searchers --cell s0 --workers 192

**Pricing regardless of the check outcome** (amendment 2). Every check here runs
**once per run on the realized log** — the consistency check compares a named
choice with a selection the harness already computed, `refuse_if_late` reads one
timestamp, and the commitment check replays the committed rule once on
un-resampled data. **None runs inside the bootstrap.** So the driver prices every
run whatever the checks say and records the **check-gated verdict beside the
p-value**: one pass then yields rule 1a (the p-values, as if no check had gated
anything) and rule 1b (the check outcomes) **on the same runs, seeds and
replicates**.

**Seed blocks, registered and exclusive to this file:**

| block | what |
|---|---|
| 500000–501999 | the registered draws |
| 510000–511999 | rule 6's replication branch |
| 990000–990999 | smoke and scaling, **cost only** |

**The smoke rule is enforced in code, not remembered.** A run on 990000+ prints
wall time, per-draw seconds and guard counts, and **no rejection rate, no
p-value, no distance and no verdict share** — `prereg/README.md`. The report
builder refuses to emit a rule quantity on that block, and a test asserts it.
"""
from __future__ import annotations

import argparse
import pickle
import time
from pathlib import Path

import numpy as np

from environments.dgp import DGPConfig, calibrate_sigma, generate
from environments.sandbox import Sandbox
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from garden._full_class_engine import full_class_null_max, full_class_observed_max
from garden.spec_class import SubsetClass
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from quixote.replay import LoggedPolicy
from quixote.grammar import Move
from quixote.replay import commitment_check, integrity_check
from quixote.session import Session, TriggerFired
from quixote.triggers import Trigger

# e_agent.py's s0 and s3, as the Design section registers
M, T, T_OOS, K, D = 50, 5000, 1000, 40, 3
# Amendment 3 drops the s3 cell: it carried one descriptive readout and no rule.
ORACLE_SHARPE = {"s0": None}
S_TRUE = {"s0": 0}

SEED0 = 500_000                  # registered draws
SEED0_REPLICATION = 510_000      # rule 6
SEED0_SMOKE = 990_000            # cost only, dedicated
N_DRAWS = 2000                   # the largest policy's count
BLOCK = 25
B_DEFAULT = 1_000                # amendment 3: B = 1,000 throughout
B_FALLBACK = 1_000               # amendment 2's lever, now the default
ALPHAS = (0.05, 0.01)
CLS = SubsetClass(max_size=D, signed=True)      # 82,240 members at K = 40

# Amendment 3, the minimal design: each policy's own draw count, and the largest
# of them is how many draws the driver walks.
DRAWS_FOR = {
    "faithful-restart": 2000,    # rules 1a and 1b, unchanged
    "faithful-stop": 2000,
    "U1": 200, "U1-twin": 200,           # an identity, exercised not estimated
    "U2": 500, "U2-twin": 500,           # predictions at or near 1.00
    "U3": 500, "U3-twin": 500,
    "U3b": 500, "U3b-twin": 500,
    "U4": 1000, "U4-twin": 1000,         # a paired difference predicted to be zero
}
REDUCIBLE = ("U2", "U3", "U3b")
DRAWS_U1 = 200

STOP_TRIGGER = Trigger("last_gain_at_most", 0.0, "stop")
RESTART_TRIGGER = Trigger("failures_at_least", 2.0, "restart")


# -- the policies -------------------------------------------------------------
#
# Scripted, so what each "declares" and what it "does" are both code and neither
# is a matter of interpretation.

def _advance(sess: Session, move: Move) -> bool:
    """One content move, respecting decision (b): a firing declared rule
    suspends the search until it is resolved."""
    try:
        support, score, n = sess.propose(move)
    except TriggerFired:
        return False
    except ValueError:
        return False
    if n == 0:
        sess.cancel()
        return False
    sess.accept()
    return True


def _finish(sess: Session) -> None:
    """End the search on a trigger that fires, as a real search does.

    A scripted policy that simply runs out of moves leaves a log with **no stop
    record**, and the certifying null then treats the realized length as a point
    the search was still going at: past it the fill continues to the budget with
    the declared triggers live (7.1 amendment 6). That is the registered
    behaviour, and it is right for a search that stopped for an outside reason —
    but here it would price a far wider search than the one that ran, which on
    U2 hid the peek behind the fill's breadth entirely.

    So each policy ends by making a move that cannot improve — `refine`
    re-scores the support it already holds — which sets `last_gain` to 0, fires
    the declared `last_gain_at_most(0.0)`, and lets the policy stop on its own
    rule.
    """
    if sess.support and not sess.fired_triggers():
        _advance(sess, Move("refine"))
    _stop_if_fired(sess)


def _stop_if_fired(sess: Session) -> bool:
    for trig, value in sess.fired_triggers():
        if trig.action == "stop":
            fires, v, stamp = sess.evaluate_trigger(trig)
            sess.stop(trig, v, stamped_at=stamp)
            return True
    return False


# The faithful arm: TWO searchers, which is the smallest set that exercises every
# move kind (`prereg/unfaithful-searchers.md` amendment 3's coverage table).
#
# One searcher is not enough, and the reason is a property of the guard rather
# than a limit of the grammar. A single searcher covering both `restart` and
# `stop` has to declare a rule for each, and when both rules share a predicate
# they fire together — so which one the log took is a decision of the POLICY, not
# a function of the declared rules. The commitment replay re-derives the decision
# from the rules, picks the first that fires, and reports a disagreement. It is
# right to: the committed rule set does not determine the action. Verified on
# seeds 990000-990007 before the arm was registered.
#
# So each faithful searcher declares exactly ONE rule, with one action, and the
# two together cover the eight kinds.
FAITHFUL_BUDGET = 24


# The feature the `flip` is anchored on. A CONSTANT, and that matters: it is
# measurable with respect to a sigma-field independent of the return-generating
# randomness, which is `SCOPE.md`'s obliviousness condition. A feature chosen by
# looking at the data would make the prelude data-dependent.
FLIP_ANCHOR = 0


def _faithful_prelude(sess: Session, trigger: Trigger) -> None:
    """The content moves both faithful searchers take: `init`, `pick`,
    `extend_best`, `refine`, `flip`.

    The order is not free, for three separate reasons.

    Under decision (b) a firing rule suspends content moves, so `refine` and
    `flip` have to come before the run of swaps that drives the failure count up —
    placed after it they were unreachable on every seed tried. `pick` has to come
    before the support fills, since a pick at a full support would leave the
    declared class.

    And the `flip` is anchored on a **constant** feature that a single-candidate
    `pick` has just put into the support. This is not decoration. A `flip` names a
    feature by index, so a flip on whatever the realized support happened to hold
    is a move that **only applies to the realized data**: on a bootstrap replicate
    the support after four moves rarely contains that index, the replay refuses the
    logged move and truncates. Measured at the old construction: the flip was
    refused in **98 of 100 replicates**, so the null was a distribution of searches
    cut off at four steps while the realized statistic came from the whole search —
    a null systematically weaker than the thing it prices, which would have made
    rule 1a over-reject for reasons having nothing to do with the checks. Anchoring
    the flip on a constant the pick guarantees present takes truncation to about
    5%, and `run_draw` records the rate per run so the registered draws measure it.
    """
    sess.declare_budget(FAITHFUL_BUDGET)
    sess.declare_triggers([trigger])
    _advance(sess, Move("init"))
    # single-candidate, so FLIP_ANCHOR is in the support on every replicate too.
    # The MULTI-candidate form of `pick` — a statistic ranging over a set — is
    # exercised by U1 and U1-twin, so both forms appear in the experiment.
    _advance(sess, Move("pick", statistic="sharpe", among=(FLIP_ANCHOR,)))
    _advance(sess, Move("extend_best"))
    _advance(sess, Move("refine"))
    _advance(sess, Move("flip", feature=FLIP_ANCHOR))


def _swap_until_fired(sess: Session, limit: int = 12) -> bool:
    """Swap the worst feature until the declared rule fires. Returns whether it
    did. A swap at a one-feature support is a no-op the harness cancels, and a
    cancelled move still counts as an action in the log while contributing no
    content move — so the loop stops on the first refusal rather than logging
    actions the replay has no move for."""
    for _ in range(limit):
        if sess.fired_triggers():
            return True
        if not _advance(sess, Move("swap_worst")):
            break
    return bool(sess.fired_triggers())


def faithful_restart(sess: Session) -> None:
    """The content prelude, then swaps until the rule fires, then `restart`, then
    one `extend_best`. **This searcher is what exercises `restart`.**

    How it ends is asymmetric between the realized run and a replicate, and the
    pre-registration states it (amendment 4, item 1): the realized run **submits**
    after the post-restart `extend_best` — an agent may submit at any time, and
    this one declares no stop rule — while a replicate, having no stop rule to
    fire, runs on under the **fill** until the declared budget is spent.
    """
    trig = Trigger("failures_at_least", 3.0, "restart")
    _faithful_prelude(sess, trig)
    if _swap_until_fired(sess):
        fired, value, stamp = sess.evaluate_trigger(trig)
        sess.restart(trig, value, stamp)
        _advance(sess, Move("extend_best"))


def faithful_stop(sess: Session) -> None:
    """The same content prelude, then swaps until the rule fires, then `stop`.
    **This searcher is what exercises `stop`**, and it ends the same way in the
    realized run and in a replicate: on its own declared rule."""
    trig = Trigger("failures_at_least", 3.0, "stop")
    _faithful_prelude(sess, trig)
    if _swap_until_fired(sess):
        fired, value, stamp = sess.evaluate_trigger(trig)
        sess.stop(trig, value, stamped_at=stamp)


def u1_contradicted_pick(sess: Session) -> None:
    """Declares `pick` by `autocorr_1` and names the feature best Sharpe would
    have chosen. The harness executes `autocorr_1`; the log records
    `contradicted`. Otherwise faithful."""
    sess.declare_triggers([STOP_TRIGGER])
    _advance(sess, Move("init"))
    among = tuple(range(8))
    by_sharpe, _ = sess.grammar.pick_choice(
        sess.support, Move("pick", statistic="sharpe", among=among))
    named = None
    if by_sharpe:
        held = {k for k, _ in sess.support}
        extra = [k for k, _ in by_sharpe if k not in held]
        named = extra[0] if extra else None
    _advance(sess, Move("pick", statistic="autocorr_1", among=among, choice=named))
    _advance(sess, Move("extend_best"))
    _finish(sess)


def u1_twin(sess: Session) -> None:
    """The same search with the declaration matching what it does: the named
    choice IS the rule's choice, so the two differ only in `contradicted`."""
    sess.declare_triggers([STOP_TRIGGER])
    _advance(sess, Move("init"))
    among = tuple(range(8))
    by_rule, _ = sess.grammar.pick_choice(
        sess.support, Move("pick", statistic="autocorr_1", among=among))
    named = None
    if by_rule:
        held = {k for k, _ in sess.support}
        extra = [k for k, _ in by_rule if k not in held]
        named = extra[0] if extra else None
    _advance(sess, Move("pick", statistic="autocorr_1", among=among, choice=named))
    _advance(sess, Move("extend_best"))
    _finish(sess)


def _full_sample_argmax(sess: Session):
    """The specification the full-sample argmax picks — the peek. Computed
    outside the session's own accounting, which is exactly the channel the
    harness does not control."""
    from garden._full_class_engine import full_class_observed_max
    _, weights, _, _ = full_class_observed_max(
        sess.grammar.base, CLS, annualization=sess.grammar.annualization)
    return tuple((int(k), float(np.sign(weights[k])))
                 for k in np.nonzero(weights)[0])


def u2_peeked_prior(sess: Session) -> None:
    """Declares the full-sample argmax as a prior, **and searches to it**.

    Declaring a prior is not what makes a peek dangerous: a declaration the
    search ignores costs nothing. The danger is that the peek chooses the
    **menu** — which is exactly what `SCOPE.md`'s obliviousness condition
    forbids, "realized Sharpe values feeding back into which columns appear
    next".

    So this policy names its `pick` candidates as **only the peeked features**.
    Every move is legal and the harness executes each rule, but the menu it
    ranges over was chosen by looking at the full sample. On a replicate the same
    `pick` re-derives from one to three candidates, so the null is a one-to-three
    trial null while the realized choice came from 82,240 members. That gap is
    the hole this searcher exists to price.
    """
    sess.declare_triggers([STOP_TRIGGER])
    support = _full_sample_argmax(sess)
    try:
        sess.pick_prior(support, reason="prior belief")
    except ValueError:
        pass
    for k, _sign in support[:D]:
        if not _advance(sess, Move("pick", statistic="sharpe", among=(int(k),))):
            break
    _finish(sess)


def u2_twin(sess: Session) -> None:
    """The same SHAPE with an oblivious menu: the same number of single-candidate
    picks, on features named by index without looking at anything."""
    sess.declare_triggers([STOP_TRIGGER])
    honest = tuple(range(D))
    try:
        sess.pick_prior(tuple((k, 1.0) for k in honest), reason="prior belief")
    except ValueError:
        pass
    for k in honest:
        if not _advance(sess, Move("pick", statistic="sharpe", among=(int(k),))):
            break
    _finish(sess)


def _changing_policy(n_changes: int, pre_emptive: bool):
    """U3 changes its rule each time the harness suspends the search — every
    change BINDS. U3b changes before the rule ever fires — no change binds.

    `n_changes` is drawn from the pilot's observed distribution
    (`prereg/agent-pilot.md`: every run changed at least one trigger, counts
    2, 15, 8 and 4, 2, 3), not from a round number.
    """
    def policy(sess: Session) -> None:
        sess.declare_triggers([STOP_TRIGGER])
        _advance(sess, Move("init"))
        changes = 0
        if pre_emptive:
            while changes < n_changes:
                sess.change_trigger(Trigger("last_gain_at_most", -1e9, "stop"),
                                    reason="pre-emptive; the rule has not fired")
                changes += 1
            for _ in range(3):
                if not _advance(sess, Move("extend_best")):
                    break
            _finish(sess)
            return
        # `last_gain_at_most(0)` fires on the first move that does not improve,
        # which a swap reaches quickly once the support is full. Extensions alone
        # fill the support at depth 3 and the rule never gets a chance to fire,
        # so the searcher would not be U3 at all.
        moves = [Move("extend_best"), Move("extend_best"), Move("swap_worst"),
                 Move("swap_worst"), Move("swap_worst"), Move("refine"),
                 Move("swap_worst"), Move("swap_worst")]
        # **Every change binds, by construction**, which is what rule 5 predicts.
        #
        # Two facts shape this. First, decision (b): while a declared rule is
        # firing the harness takes no content move, so an agent that wants to
        # continue must change to a rule that does **not** fire — re-declaring
        # the same predicate leaves it firing and buys nothing, which is what the
        # pilot's agents worked around with extreme parameters. Second, a change
        # binds only if the realized search then goes **further than the
        # committed rule would have allowed**: the committed-rule replay stops at
        # the first firing, so one extra accepted move is enough to make the two
        # action sequences differ and the commitment check fail.
        #
        # So the policy ALTERNATES: change to a rule that cannot fire, take
        # moves, change back to the rule that can, and stop when the budget of
        # changes is spent. The count comes from the pilot's observed
        # distribution.
        since_change = 0
        for mv in moves * 8:
            firing = bool(sess.fired_triggers())
            if firing and changes < n_changes:
                # firing, and the budget allows continuing: change to a rule
                # that cannot fire, so the search may go on
                sess.change_trigger(Trigger("last_gain_at_most", -1e9, "stop"),
                                    reason="the rule fired and the search continued")
                changes, since_change = changes + 1, 0
            elif firing:
                _stop_if_fired(sess)
                return
            elif changes and changes < n_changes and since_change >= 2:
                # not firing, because the last change made the rule unreachable.
                # Change BACK, so the declared rule can fire again and the count
                # can reach the pilot's observed range rather than stopping at one.
                sess.change_trigger(Trigger("last_gain_at_most", 0.0, "stop"),
                                    reason="back to a rule that can fire")
                changes, since_change = changes + 1, 0
                continue
            if not _advance(sess, mv):
                break
            since_change += 1
        _finish(sess)
    return policy


def u3_twin(sess: Session) -> None:
    """Declares the rule it actually searches under, and stops when it fires."""
    sess.declare_triggers([STOP_TRIGGER])
    _advance(sess, Move("init"))
    moves = [Move("extend_best"), Move("extend_best"), Move("swap_worst"),
             Move("swap_worst"), Move("swap_worst"), Move("refine"),
             Move("swap_worst"), Move("swap_worst")]
    for mv in moves * 3:
        if _stop_if_fired(sess):
            return
        if not _advance(sess, mv):
            break
    _finish(sess)


def u4_silent_restart(sess: Session) -> None:
    """Restarts by exhausting its support through `swap_worst` chains rather than
    calling `restart`. Nothing is falsely declared."""
    sess.declare_triggers([STOP_TRIGGER])
    _advance(sess, Move("init"))
    for mv in (Move("extend_best"), Move("swap_worst"), Move("swap_worst"),
               Move("swap_worst"), Move("extend_best")):
        if _stop_if_fired(sess):
            return
        _advance(sess, mv)
    _finish(sess)


def u4_twin(sess: Session) -> None:
    """The same states reached by declaring the restart."""
    sess.declare_triggers([STOP_TRIGGER, RESTART_TRIGGER])
    _advance(sess, Move("init"))
    _advance(sess, Move("extend_best"))
    for trig, value in sess.fired_triggers():
        if trig.action == "restart":
            fires, v, stamp = sess.evaluate_trigger(trig)
            sess.restart(trig, v, stamp)
            break
    for mv in (Move("extend_best"), Move("extend_best")):
        if _stop_if_fired(sess):
            return
        _advance(sess, mv)
    _finish(sess)


# name -> (policy, arm). The unfaithful arm's twins are named `<U>-twin`, so a
# paired comparison is a lookup rather than a convention.
def policies(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    pilot_counts = (2, 15, 8, 4, 2, 3)        # prereg/agent-pilot.md, attempts 6-8
    n_changes = int(rng.choice(pilot_counts))
    out = {"faithful-restart": (faithful_restart, "faithful"),
           "faithful-stop": (faithful_stop, "faithful")}
    out.update({
        "U1": (u1_contradicted_pick, "unfaithful"),
        "U1-twin": (u1_twin, "twin"),
        "U2": (u2_peeked_prior, "unfaithful"),
        "U2-twin": (u2_twin, "twin"),
        "U3": (_changing_policy(n_changes, pre_emptive=False), "unfaithful"),
        "U3-twin": (u3_twin, "twin"),
        "U3b": (_changing_policy(n_changes, pre_emptive=True), "unfaithful"),
        "U3b-twin": (u3_twin, "twin"),
        "U4": (u4_silent_restart, "unfaithful"),
        "U4-twin": (u4_twin, "twin"),
    })
    return out


MEMBERS = tuple(policies(0))
assert set(DRAWS_FOR) == set(MEMBERS), "amendment 3 registers a count per policy"


def _trigger_null(log, base: np.ndarray, ann: float, B: int, seed: int,
                  submitted: float | None = None):
    """The certifying null alone: trigger replay.

    Returns `(p_procedure, procedure_score, p_submitted, engaged)`.

    **Two statistics, one null** (amendment 5). The null is the declared
    procedure's — the same policy, the same resampling, the same RNG stream — and
    TWO realized statistics are compared against those same replicates:

    - the **procedure score**, the declared procedure run on the realized data,
      which is what the replay reaches and what **rule 1a reads**;
    - the **submitted score**, what the session actually submitted, whose
      rejection rate and per-run gap are **descriptive**.

    They coincide whenever the search ended under its own declared rule, because
    then the procedure stops where the session stopped. They differ for
    `faithful-restart`, which declares no stop rule: its procedure runs on to the
    budget under the fill while its submission was made earlier.

    Comparing both against one set of replicates costs one extra comparison per
    replicate and no extra bootstrap, and it keeps the two p-values on exactly the
    same null rather than on two nulls that differ by resampling noise.

    Replicate for replicate the procedure p is `quixote.certify.three_nulls`'
    second null with the other two not computed;
    `tests/test_unfaithful_searchers.py` holds the two equal.
    """
    policy = LoggedPolicy(log, CLS)
    base = np.asarray(base, dtype=float)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(seed)
    realized = policy.trace(base, ann)
    n_realized = realized.n_moves
    if submitted is None:
        submitted = realized.score
    hits, hits_sub, engaged, truncated = 0, 0, 0, 0
    n_content = len([r for r in log.records
                     if not r.move.is_meta and r.move.note != "rejected"])
    for _ in range(B):
        R = S0[stationary_bootstrap_indices(base.shape[0], L, rng), :]
        t = policy.trace(R, ann, meta_steps=n_realized)
        hits += int(t.score >= realized.score)
        hits_sub += int(t.score >= submitted)
        # A replicate that refused a logged move ends on "stop" with fewer steps
        # than the log has content moves: the replay truncated rather than the
        # rule firing. Counted so the arm's null can be read for what it is.
        truncated += int(t.n_moves < n_content and
                         bool(t.moves) and t.moves[-1] == "stop")
        # amendment 5: replicates that ran PAST THE LOGGED LENGTH, so took at
        # least one fill step. Before the fix this counted only the
        # `meta_steps`-driven case and read zero for a searcher with no stop rule.
        engaged += int(bool(t.filled))
    return ((1 + hits) / (B + 1), float(realized.score),
            (1 + hits_sub) / (B + 1), engaged, truncated)


# -- one draw -----------------------------------------------------------------

def make_panel(cell: str, seed: int):
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=S_TRUE[cell], rho=0.0,
                    sigma=1.0, seed=seed)
    if ORACLE_SHARPE[cell] is not None:
        import dataclasses
        cfg = dataclasses.replace(cfg, sigma=calibrate_sigma(ORACLE_SHARPE[cell], cfg))
    return generate(cfg), cfg


def run_draw(cell: str, seed: int, B: int, only: str | None = None,
             index: int | None = None) -> dict:
    """Every policy on one panel, priced REGARDLESS of its check outcome.

    `index` is the draw's position in its block. A policy whose registered count
    is smaller than the block's runs only on the first `DRAWS_FOR[name]` draws,
    which is how amendment 3's per-policy counts are spent rather than by running
    everything everywhere and discarding.
    """
    t_draw = time.time()
    data, cfg = make_panel(cell, seed)
    ann = float(np.sqrt(cfg.periods_per_year))

    # The declared-class null, computed ONCE per draw and shared by every policy,
    # as `calibration-at-1pct` arm D and 7.0 both do. It does not depend on the
    # policy: it is the distribution of the maximum over the class, and what
    # differs between policies is only the score compared against it. At B = 1,000
    # it costs about 2.6 s a draw against roughly 100 s for the twelve policies'
    # replays, so the second certifier is close to free.
    sb_draw = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=CLS)
    base_draw = sb_draw.base_feature_columns()
    t_cls = time.time()
    L_draw = int(select_block_length(base_draw - base_draw.mean(axis=0)))
    M_b, _, n_floor, n_cap = full_class_null_max(
        base_draw, CLS, B=B, block_length=L_draw, annualization=ann, seed=seed)
    class_max, _, _, _ = full_class_observed_max(base_draw, CLS, annualization=ann)
    out: dict = {"_draw": {"seed": seed, "cell": cell, "block_length": L_draw,
                           "class_max": float(class_max),
                           "seconds_class_null": time.time() - t_cls,
                           "null_max_q95": float(np.quantile(M_b, 0.95)),
                           "guard_floor": int(n_floor), "guard_cap": int(n_cap)}}

    def p_class_of(score: float) -> float:
        """The declared-class p-value: `(1 + #{M_b >= score}) / (B + 1)`, the same
        form as the replay p so the two are differenced on one scale."""
        return (1 + int(np.sum(M_b >= score))) / (B + 1)

    for name, (policy, arm) in policies(seed).items():
        if only is not None and name != only:
            continue
        if index is not None and index >= DRAWS_FOR.get(name, N_DRAWS):
            continue
        t0 = time.time()
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=CLS)
        sess = Session.on_sandbox(sb, CLS, name_prefix=name)
        policy(sess)
        base = sb.base_feature_columns()
        log = sess.log

        # the checks: once per run, on the realized log
        integrity = integrity_check(log, CLS, base, ann)
        commitment = commitment_check(log, CLS, base, ann)
        contradicted = len(log.contradicted_picks())
        changes = len(getattr(log, "trigger_changes", ()) or ())

        # Priced regardless of what the checks said. ONE null, not three: the
        # certifying null is trigger replay, and rules 1a, 3, 4 and 6 read only
        # that one. `three_nulls` would compute the fixed-sequence and policy
        # nulls too, tripling the only expensive part of the draw for numbers no
        # rule here reads.
        # The SUBMITTED score is the best the session itself reached; the
        # PROCEDURE score is what the declared procedure reaches on the realized
        # data. Equal for every policy that ends on its own declared rule; they
        # differ for `faithful-restart`, which declares no stop rule (amendment 4
        # item 1, amendment 5).
        submitted = max([r.score_after for r in log.records
                         if r.score_after is not None], default=float("-inf"))
        p, realized, p_submitted, n_engaged, n_trunc = _trigger_null(
            log, base, ann, B, seed, submitted=float(submitted))

        # and the check-gated verdict, recorded BESIDE the p rather than in
        # place of it
        gated = ("UNDECIDABLE" if not integrity.agrees else
                 "DEPENDS_ON_JUDGMENT" if (not commitment.agrees and changes) else
                 "UNDECIDABLE" if not commitment.agrees else
                 "CERTIFIED" if p < 0.05 else "FAIL")

        # Amendment 4, item (4b): the fill's score on the REALIZED data under the
        # same declared triggers — a pure greedy walk from step 0, no logged move
        # used. What the searcher's own moves bought over taking the fill instead.
        fill_here = LoggedPolicy(log, CLS).trace(base, ann, meta_steps=0).score

        out[name] = {
            "arm": arm,
            # rule 1a reads this one: the declared procedure's score against its
            # own null
            "p_replay": p,
            "procedure_score": realized,
            "realized_score": realized,          # kept: the prior field name
            "submitted_score": float(submitted),
            # descriptive (amendment 5): the same null, the submitted statistic
            "p_submitted": p_submitted,
            "procedure_minus_submitted": realized - float(submitted),
            # STRUCTURAL, not a score comparison: did the log end on a meta
            # `stop`? A searcher that declares no stop rule ends by submitting,
            # and its two statistics can still coincide when the extra procedure
            # steps fail to improve — so equality of scores is not the test.
            "ended_under_its_rule": bool(
                any(r.move.kind == "stop" for r in log.records)),
            "declares_stop_rule": any(
                (d.get("action") if isinstance(d, dict) else None) == "stop"
                for d in (log.declared_trigger_records or ())),
            "p_class": p_class_of(realized),
            "p_class_submitted": p_class_of(submitted),
            # amendment 4, item (4a): descriptive, no rule
            "p_class_minus_p_replay": p_class_of(realized) - p,
            "fill_score": float(fill_here),
            # amendment 4, item (4b): descriptive, no rule
            "submitted_minus_fill": float(submitted) - float(fill_here),
            "gated_verdict": gated,
            "integrity_ok": bool(integrity.agrees),
            "commitment_ok": bool(commitment.agrees),
            "contradicted_picks": contradicted,
            "trigger_changes": changes,
            "prior_declared": bool(log.prior_pick),
            "n_moves": log.n_moves,
            "n_candidates": log.total_candidates(),
            "fill_engaged": n_engaged,
            # replicates whose replay refused a logged move and stopped short
            "replicates_truncated": n_trunc,
            "truncation_rate": n_trunc / B,
            "seconds": time.time() - t0,
        }
    out["_draw"]["seconds"] = time.time() - t_draw
    return out


# -- assembly -----------------------------------------------------------------

def run(cell: str, n_draws: int, seed0: int, B: int, workers, checkpoint_dir,
        only: str | None = None) -> dict:
    starts = list(range(0, n_draws, BLOCK))
    cells = {(cell, s): [(cell, seed0 + i, B, only, i)
                         for i in range(s, min(s + BLOCK, n_draws))]
             for s in starts}
    got = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    rows = [d for s in starts for d in got[(cell, s)]]
    return {"cell": cell, "git_at_launch": git_state(), "rows": rows,
            "settings": {"M": M, "T": T, "K": K, "d": D, "B": B, "draws": n_draws,
                         "workers": workers, "seed0": seed0, "only": only,
                         "class_size": CLS.size(K)}}


def is_smoke_block(seed0: int) -> bool:
    return SEED0_SMOKE <= seed0 < SEED0_SMOKE + 1000


def cost_report(data: dict, full_draws: int = N_DRAWS, B_full: int = B_DEFAULT) -> str:
    """**Cost only.** `prereg/README.md`: a smoke or a scaling curve reports wall
    time, per-draw seconds and guard counts, and no rejection rate, p-value,
    distance or verdict share. This builder never computes one, which is why the
    rule cannot be forgotten by whoever reads the output."""
    rows, s = data["rows"], data["settings"]
    if not is_smoke_block(s["seed0"]):
        raise ValueError(
            f"cost_report is for the registered cost-only block "
            f"{SEED0_SMOKE}-{SEED0_SMOKE + 999}; seed0 {s['seed0']} is a block whose "
            "output carries rule quantities and is read by the reader, not here")
    secs = np.array([r["_draw"]["seconds"] for r in rows])
    g = data["git_at_launch"]
    names = [n for n in MEMBERS if any(n in r for r in rows)]
    L = ["unfaithful-searchers (7.3 scripted) — COST ONLY", "=" * 78,
         f"{len(rows)} draws from seed {s['seed0']}, cell {data['cell']}, "
         f"B={s['B']:,}, workers={s['workers']}",
         f"git at launch {g['commit'][:7]}"
         + (" (tracked changes)" if g.get("dirty") else ""),
         f"class {CLS.name}: {s['class_size']:,} members; {len(names)} policies per draw",
         "",
         f"per draw   mean {secs.mean():8.2f}s   median {np.median(secs):8.2f}s"
         f"   max {secs.max():8.2f}s", "",
         "seconds per draw, by policy", "-" * 78]
    for n in names:
        vals = [r[n]["seconds"] for r in rows if n in r]
        L.append(f"  {n:<18}{float(np.mean(vals)):8.2f}   on {len(vals)} of "
                 f"{len(rows)} draws (count {DRAWS_FOR.get(n, N_DRAWS)})")
    moves = float(np.mean([r[n]["n_moves"] for r in rows for n in names if n in r]))
    cands = float(np.mean([r[n]["n_candidates"] for r in rows for n in names if n in r]))
    L += ["", "shape (reported, not gated)", "-" * 78,
          f"  mean moves per run {moves:.2f}   mean candidates per run {cands:.1f}"]

    # The registered design is per-policy: each policy's own count times its own
    # per-draw cost, scaled from the measured B to the registered one.
    scale = B_full / s["B"]
    per_policy = {n: float(np.mean([r[n]["seconds"] for r in rows if n in r]))
                  for n in names}
    cpu_s = sum(per_policy[n] * DRAWS_FOR.get(n, N_DRAWS) for n in names) * scale
    # The declared-class null is per DRAW, not per policy, and the driver walks
    # `full_draws` of them however few policies run on the later ones.
    cls_s = float(np.mean([r["_draw"]["seconds_class_null"] for r in rows]))
    cpu_s += cls_s * scale * full_draws
    L += ["", "PROJECTION to the registered design (amendment 3, minimal)", "-" * 78,
          f"  measured at B={s['B']:,}; scaled to B={B_full:,}",
          "  each policy at its own registered count, not all at the largest:",
          f"  {cpu_s / 3600:,.1f} CPU-hours for the whole experiment (s0 only)",
          f"  of which the per-draw class null is "
          f"{cls_s * scale * full_draws / 3600:,.1f} CPU-hours",
          "",
          "  This is an UPPER BOUND, not an estimate. It scales the whole per-draw",
          "  time with B, including the part that does not depend on B at all —",
          "  generating the panel and running the realized search once. At a small",
          "  measured B that fixed part is most of the time, so the bound is loose",
          "  by roughly the ratio of fixed to replay cost. Separating the two is",
          "  what the four-point curve is for: fit seconds = a + b*B per policy",
          "  across the four B values and project from b."]
    if s["workers"]:
        wall = cpu_s / 3600 / s["workers"]
        L += [f"  at {s['workers']} workers: {wall:,.2f} h wall",
              "  amendment 3 IS the minimal design; if this is still over the",
              "  threshold the experiment waits rather than shrinking further."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", choices=["s0"], default="s0")
    ap.add_argument("--smoke", type=int, default=None,
                    help="draws from the dedicated cost-only block 990000+")
    ap.add_argument("--replication", action="store_true",
                    help="rule 6's block 510000+")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--only", default=None, help="rule 6: replicate one policy only")
    ap.add_argument("--checkpoint-dir", default=None)
    ap.add_argument("--out", default="figures")
    a = ap.parse_args(argv)
    if a.smoke and a.replication:
        raise SystemExit("--smoke and --replication are exclusive")
    if not a.smoke and a.B not in (B_DEFAULT, B_FALLBACK):
        raise SystemExit(f"a registered run uses B={B_DEFAULT:,} or amendment 2's "
                         f"fallback B={B_FALLBACK:,}; other values are smoke only")
    seed0 = (SEED0_SMOKE if a.smoke else
             SEED0_REPLICATION if a.replication else SEED0)
    data = run(a.cell, a.smoke or N_DRAWS, seed0, a.B, a.workers, a.checkpoint_dir,
               only=a.only)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"_{a.cell}" + (f"_smoke{a.smoke}_w{a.workers or 'auto'}" if a.smoke else
                          ("_replication" if a.replication else ""))
    if a.smoke:
        text = cost_report(data)
        print(text, flush=True)
        (out / f"unfaithful_searchers{tag}_cost.txt").write_text(text)
    else:
        print(f"{len(data['rows'])} draws written; rules are read by the reader, "
              "not printed here", flush=True)
    with (out / f"unfaithful_searchers{tag}_data.pkl").open("wb") as fh:
        pickle.dump(data, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
