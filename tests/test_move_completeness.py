"""Every accepted move carries every parameter its re-execution needs.

Registered 2026-09-28 in `quixote/README.md`, implemented after 7.3 scripted.

The agent pilot's logs recorded `move.kind` and not the move's parameters, so a
`flip` without its feature and a `pick` without its statistic and candidate list
are **different moves on re-execution**. Three ADR seat runs could not be re-graded
at all when the replay indexing was corrected (`prereg/agent-pilot.md`, the
2026-09-28 re-grade), and the ETF runs were re-gradable only because their moves
happened to be parameterless.

The serializer was fixed. This test is what keeps it fixed, and it is written on
the **accepted-move path** rather than against one writer of one format: a move
that reaches a log must carry what re-executing it needs, whoever writes it out
afterwards.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden.spec_class import SubsetClass
from quixote.grammar import Move
from quixote.session import Session

# What each move kind needs in order to be re-executed. A kind absent here needs
# nothing beyond its own name, which is itself the claim being made.
REQUIRED = {
    "flip": ("feature",),
    "pick": ("statistic", "among"),
    "refine": (),
    "init": (),
    "extend_best": (),
    "swap_worst": (),
}


def _session(seed=11, K=10):
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    cls = SubsetClass(max_size=K, signed=True)
    return Session.on_sandbox(sb, cls), sb, cls, float(np.sqrt(cfg.periods_per_year))


def _take(sess, move):
    try:
        _s, _sc, n = sess.propose(move)
    except (ValueError, Exception) as exc:       # noqa: BLE001
        if type(exc).__name__ == "TriggerFired":
            return False
        if isinstance(exc, ValueError):
            return False
        raise
    if n == 0:
        sess.cancel()
        return False
    sess.accept()
    return True


def _missing(move) -> list[str]:
    out = []
    for field in REQUIRED.get(move.kind, ()):
        value = getattr(move, field, None)
        if value is None or (isinstance(value, (tuple, list)) and len(value) == 0):
            out.append(field)
    return out


def test_every_accepted_move_carries_what_its_re_execution_needs():
    """The accepted-move path, over every kind the grammar offers."""
    sess, _sb, _cls, _ann = _session()
    assert _take(sess, Move("init"))
    assert _take(sess, Move("pick", statistic="autocorr_1", among=(0, 1, 2, 3)))
    assert _take(sess, Move("extend_best"))
    assert _take(sess, Move("refine"))
    held = sess.support[0][0]
    assert _take(sess, Move("flip", feature=held))
    _take(sess, Move("swap_worst"))

    kinds = set()
    for rec in sess.log.records:
        if rec.move.note == "rejected":
            continue
        kinds.add(rec.move.kind)
        missing = _missing(rec.move)
        assert not missing, (
            f"accepted {rec.move.kind} at step {rec.step} is missing "
            f"{missing}: it cannot be re-executed from its own record")
    # the test is only meaningful if the parameterised kinds were actually taken
    assert {"pick", "flip"} <= kinds, kinds


def test_a_move_missing_its_parameter_cannot_even_be_CONSTRUCTED():
    """Stronger than refusing it at the moment of the move: the grammar refuses a
    `flip` with no feature in `Move.__post_init__`, so such a move never reaches a
    log, a serializer or a replay. The failure this guards against is a move being
    accepted and only failing much later, on a replay, with the session gone."""
    with pytest.raises(ValueError, match="flip names the feature"):
        Move("flip")
    # and a well-formed one is fine
    assert Move("flip", feature=2).feature == 2


def test_the_completeness_rule_covers_every_kind_the_grammar_offers():
    """If the grammar grows a kind, this file must say what that kind needs.
    Otherwise a new parameterised move silently inherits 'needs nothing', which is
    exactly how `flip` and `pick` came to be serialized without their parameters."""
    from quixote.grammar import MOVE_KINDS

    content = {k for k in MOVE_KINDS if k not in ("stop", "restart")}
    missing = content - set(REQUIRED)
    assert not missing, (
        f"these move kinds have no completeness rule in REQUIRED: {sorted(missing)}. "
        "Add what each needs for re-execution, or state that it needs nothing.")
