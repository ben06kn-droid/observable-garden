"""Meta-adaptive searchers for 7.1: searches whose *meta* choices are data driven.

The distinction 7.1 turns on (ROADMAP 7.1, THEORY.md P4):

- **Content choices** — which feature to extend by — are rules. They are
  functions of the sample, so a bootstrap replicate re-executes them exactly.
- **Meta choices** — when to stop, when to restart, whether to take another move
  at all — were made *after seeing results*. Freezing them at their realized
  positions is the realized-menu error one level up, and stop-when-cleared is
  the winner-anchored case of it.

Each searcher here records both: the move sequence, and the **trigger** behind
every meta choice, as a predicate that can be re-evaluated on a replicate. That
is what makes the trigger-replay null of `estimator/trigger_replay.py` possible,
and what 7.1 measures against fixed-sequence replay and full policy replay.

Every searcher shares one core loop between `run`, `replay` and both replay
forms, for the reason `searchers/scripted.py` gives: two implementations of one
decision rule drift, and the replay nulls are only valid while they agree.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from environments.sandbox import Distribution, Sandbox, Specification
from estimator.bootstrap import sharpe
from searchers.base import Searcher

BUDGET = 12          # hard cap on moves, so a replicate can never run away


def _signed_sum(K: int, support) -> np.ndarray:
    """Weights from a list of (feature, sign) pairs."""
    w = np.zeros(K)
    for k, s in support:
        w[k] = float(s)
    return w


def _support_name(support) -> str:
    return "[" + ",".join(f"{k}{'+' if s > 0 else '-'}" for k, s in support) + "]"


def _column_sharpe(column: np.ndarray, annualization: float = 1.0) -> float:
    return float(sharpe(column[:, None], axis=0, annualization=annualization)[0])


def _moment_sharpe(mean: float, var: float, annualization: float = 1.0) -> float:
    """The Sharpe of a stream from its mean and sample variance, with the same
    guards as `estimator.bootstrap.sharpe` (a zero-variance stream scores 0; the
    cap applies), counted in the same GUARD_COUNTS."""
    from estimator.bootstrap import GUARD_COUNTS, SHARPE_CAP
    if not var > 0.0:
        GUARD_COUNTS["zero_variance"] += 1
        return 0.0
    sr = mean / np.sqrt(var) * annualization
    if abs(sr) > SHARPE_CAP:
        GUARD_COUNTS["sharpe_cap"] += 1
        return float(np.sign(sr) * SHARPE_CAP)
    return float(sr)


@dataclass
class Move:
    """One step of a search, with the meta decision that preceded it.

    `action` is the meta choice made *before* this move, given everything
    already seen: "continue" takes another extension, "restart" abandons the
    current support for a fresh anchor, "stop" ends the search. `trigger` names
    the predicate that produced it and `trigger_value` is what that predicate
    saw, so a replicate can re-evaluate the same predicate on its own state.
    """
    step: int
    action: str                      # "continue" | "restart" | "stop"
    trigger: str                     # the predicate's name
    trigger_value: float             # what the predicate evaluated to
    support: tuple[int, ...] = ()    # the support after the move ( () if stopped )
    score: float = float("-inf")     # best-so-far after the move
    filled: bool = False             # the continuation was 7.1's fill (amendment 6)


@dataclass
class Trace:
    """A realized search: its moves, its submission, and the policy that made it."""
    moves: list[Move] = field(default_factory=list)
    support: tuple[int, ...] = ()
    score: float = float("-inf")
    policy: str = ""

    @property
    def n_moves(self) -> int:
        return len(self.moves)

    @property
    def stopped_at(self) -> int:
        for m in self.moves:
            if m.action == "stop":
                return m.step
        return len(self.moves)

    def actions(self) -> list[str]:
        return [m.action for m in self.moves]


class MetaAdaptive(Searcher):
    """Base class: the shared search loop, parameterised by a meta decision.

    Subclasses implement `_decide(state) -> (action, trigger_name, value)` and
    nothing else. `mode` selects how meta choices are made during a replay:

    - "policy"  — re-evaluate the policy, which is exact because the policy is
                  code. This is null 3 in 7.1.
    - "trigger" — re-evaluate each declared predicate on the replicate's own
                  state, but only for as many steps as the realized search took;
                  past that, fill greedily. It agrees with "policy" exactly up to
                  the realized length and can diverge after it.
    - "fixed"   — take the realized action at each step regardless of what the
                  replicate sees. This is null 1, the error being measured.
    """
    budget = BUDGET
    spec_class = None          # None = unbounded by any class; see set_class()

    def set_class(self, spec_class):
        """Restrict every move to a declared class.

        `None` -- the default -- is the behaviour `fixed-sequence-replay`
        registered and runs: bounded only by `budget`, reaching whatever support
        size its trigger takes it to. Amendment 4 records why 7.1 is not capped.

        When a class is given, a move producing a support outside it is
        **refused**, in the realized run and in every replicate alike.
        Membership is a function of the support and the class, not of the data,
        so a replicate refuses exactly the moves the realized run refused --
        which is what amendment 4's licence-transfer argument rests on. 7.0 uses
        capped variants, because that cell scores against the class gate.
        """
        self.spec_class = spec_class
        return self

    def _allowed(self, support) -> bool:
        if self.spec_class is None:
            return True
        return bool(self.spec_class.contains(_signed_sum(self._K, support)))

    def _decide(self, state: dict) -> tuple[str, str, float]:
        raise NotImplementedError

    # -- the continue-move ---------------------------------------------------

    @staticmethod
    def _grammar(support, K, score):
        """Every one-step move of 7.2's content grammar, scored.

        Returns (score, kind, new_support) triples over `extend`, `swap` and
        `flip`. `support` is a list of (feature, sign) pairs, so `flip` is a real
        move rather than a no-op -- which is why supports here carry signs even
        though the extend-only searchers never set one to -1.
        """
        held = {k for k, _ in support}
        remaining = [k for k in range(K) if k not in held]
        out = []
        for j in remaining:                                   # extend
            ns = support + [(j, 1.0)]
            out.append((score(ns), "extend", ns))
        for i in range(len(support)):                         # swap
            for j in remaining:
                ns = support[:i] + [(j, support[i][1])] + support[i + 1:]
                out.append((score(ns), "swap", ns))
        for i in range(len(support)):                         # flip
            ns = support[:i] + [(support[i][0], -support[i][1])] + support[i + 1:]
            out.append((score(ns), "flip", ns))
        return out

    def _grammar_allowed(self, support, K, score):
        """`_grammar` filtered to the declared class. A refused move is simply
        not a candidate, so the policy chooses among what it may actually do."""
        self._K = K
        cands = self._grammar(support, K, score)
        if self.spec_class is None:
            return cands
        return [c for c in cands if self._allowed(c[2])]

    def _fill_move(self, support, K, score):
        """7.1's fill rule, as amended: the best **one-step move across the whole
        content grammar**, not merely the best extension.

        The earlier rule filled with greedy extension only. Greedy extension
        dominates any other single-feature *extension*, so a searcher whose
        continuation was a weaker extension showed a conservative fill almost
        mechanically. It does not dominate `swap` or `flip`, and because a search
        is a path rather than a single step, a locally-best move can still end
        below a swap-based continuation. Widening the fill to the full grammar is
        what makes the comparison informative rather than arithmetical.
        """
        cands = self._grammar_allowed(support, K, score)
        return max(cands) if cands else None

    def _extend(self, support, K, score):
        """This policy's own continue-move. Best *extension* by default."""
        cands = [c for c in self._grammar_allowed(support, K, score) if c[1] == "extend"]
        return max(cands) if cands else None

    # -- the one loop ------------------------------------------------------

    def _search(self, K: int, single: callable, support_score: callable,
                frozen: list[str] | None = None,
                meta_steps: int | None = None) -> Trace:
        """`single(k)` and `support_score(support)` score candidates.

        `frozen` supplies the meta action at each step instead of `_decide`:
        fixed-sequence replay. The realized sequence is the whole search, so when
        it runs out the search is over.

        `meta_steps` is the realized length. Past it the declared triggers are
        STILL evaluated at every step (fixed-sequence-replay amendment 6); only
        when they say continue is the continuation replaced by 7.1's fill, the
        best one-step content move. So a replicate stops or restarts past the
        realized length exactly as the policy would, and the trigger null differs
        from the policy null in content alone."""
        self._K = K
        scores = np.array([single(k) for k in range(K)])
        order = list(np.argsort(-scores))
        anchor = 0
        support = [(int(order[anchor]), 1.0)]
        best = float(scores[order[anchor]])
        # The support that scored `best`. A restart replaces `support` but not
        # `best`, so without this the trace would report one support with
        # another's score (fixed-sequence-replay amendment 5).
        best_support = list(support)
        trace = Trace(policy=self.name)
        failures, last_gain = 0, float("inf")

        for step in range(self.budget):
            state = {"step": step, "support": tuple(support), "best": best,
                     "failures": failures, "last_gain": last_gain,
                     "n_features": K}
            filling = False
            if frozen is not None:
                if step >= len(frozen):
                    break                       # the realized search ended here
                action = frozen[step]
                trigger, value = "frozen", float("nan")
            else:
                action, trigger, value = self._decide(state)
                filling = meta_steps is not None and step >= meta_steps

            if action == "stop":
                trace.moves.append(Move(step, "stop", trigger, value,
                                        tuple(support), best))
                break

            if action == "restart":
                anchor += 1
                if anchor >= K:
                    trace.moves.append(Move(step, "stop", "exhausted", float(anchor),
                                            tuple(support), best))
                    break
                support = [(int(order[anchor]), 1.0)]
                failures, last_gain = 0, float("inf")
                trace.moves.append(Move(step, "restart", trigger, value,
                                        tuple(support), best))
                continue

            # continue: extend the current support by one feature. Which feature
            # depends on whether this step is the policy running (its own
            # continue-move) or the fill running past the realized sequence
            # (greedy, by 7.1's rule). For most searchers these are the same
            # function; the point of ExtendBySecondBest is that they are not.
            chosen = (self._fill_move(support, K, support_score) if filling
                      else self._extend(support, K, support_score))
            if chosen is None:
                trace.moves.append(Move(step, "stop", "exhausted", 0.0,
                                        tuple(support), best))
                break
            gain_score, kind, new_support = chosen
            last_gain = gain_score - best
            if gain_score > best:
                support = list(new_support)
                best = float(gain_score)
                best_support = list(support)
                failures = 0
            else:
                failures += 1
            trace.moves.append(Move(step, "continue", trigger, value,
                                    tuple(support), best, filled=filling))

        trace.support, trace.score = tuple(best_support), best
        return trace

    # -- entry points ------------------------------------------------------

    # "columns" sums base columns and computes each candidate's Sharpe from its
    # stream: O(T) per candidate, and bit-identical to the scripted searchers.
    # "moments" computes the resampled mean vector and covariance ONCE per base
    # matrix and scores every candidate from them: O(|support|^2) per candidate.
    # It agrees with "columns" to ~1e-12, not bit for bit, and is opt-in; its
    # equivalence is asserted in tests/test_meta_adaptive.py.
    scoring = "columns"

    def _scorers_from_columns(self, base: np.ndarray, annualization: float):
        if self.scoring == "moments":
            return self._scorers_from_moments(base, annualization)

        def single(k):
            return _column_sharpe(base[:, k], annualization)

        def support_score(support):
            stream = sum(base[:, k] * s for k, s in support)
            return _column_sharpe(stream, annualization)

        return single, support_score

    def _scorers_from_moments(self, base: np.ndarray, annualization: float):
        cache = getattr(self, "_moment_cache", None)
        if cache is not None and cache[0] is base:
            mu, C = cache[1], cache[2]
        else:
            mu = base.mean(axis=0)
            C = np.cov(base, rowvar=False, ddof=1)
            self._moment_cache = (base, mu, C)

        def single(k):
            return _moment_sharpe(mu[k], C[k, k], annualization)

        def support_score(support):
            idx = [k for k, _ in support]
            sg = np.array([g for _, g in support], dtype=float)
            return _moment_sharpe(float(sg @ mu[idx]),
                                  float(sg @ C[np.ix_(idx, idx)] @ sg), annualization)

        return single, support_score

    def trace(self, base: np.ndarray, annualization: float = 1.0,
              frozen: list[str] | None = None,
              meta_steps: int | None = None) -> Trace:
        single, support_score = self._scorers_from_columns(base, annualization)
        return self._search(base.shape[1], single, support_score,
                            frozen=frozen, meta_steps=meta_steps)

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        """Full policy replay: the policy is code, so this is exact."""
        return self.trace(base_columns, annualization).score

    def replay_fixed_sequence(self, base_columns: np.ndarray, actions: list[str],
                              annualization: float = 1.0) -> float:
        """Fixed-sequence replay: meta choices frozen at the realized sequence,
        content rules re-executed. 7.1's null 1."""
        return self.trace(base_columns, annualization, frozen=actions).score

    def replay_triggers(self, base_columns: np.ndarray, n_realized_moves: int,
                        annualization: float = 1.0) -> float:
        """Trigger replay: every meta choice's predicate re-evaluated on this
        replicate. 7.1's null 2.

        Every declared predicate is evaluated at every step, before and past the
        realized length alike (amendment 6). Past it, a step whose triggers say
        continue takes 7.1's fill -- the best one-step content move -- in place of
        the policy's own continuation.

        The exact invariant, asserted in `tests/test_meta_adaptive.py`: this
        differs from full policy replay **only in content, and only on replicates
        that run past the realized length**. The meta decisions are the policy's
        at every step. So a searcher whose continuation is the fill's move
        (greedy extension over a support the fill cannot improve by swap or flip)
        has nulls 2 and 3 identical, and a searcher whose realized search runs to
        the budget has them identical by construction. `LookaheadStopWhenCleared`
        and `ExtendBySecondBest` are the cases where content can differ, in
        opposite directions.
        """
        return self.trace(base_columns, annualization,
                          meta_steps=n_realized_moves).score

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features

        def single(k):
            return sandbox.evaluate(Specification(
                weights=_signed_sum(K, [(k, 1.0)]), name=f"{self.name}_f{k}")).sharpe

        def support_score(support):
            return sandbox.evaluate(Specification(
                weights=_signed_sum(K, support),
                name=f"{self.name}_{_support_name(support)}")).sharpe

        t = self._search(K, single, support_score)
        self.last_trace = t
        spec = Specification(weights=_signed_sum(K, t.support),
                             name=f"{self.name}_{_support_name(t.support)}")
        sandbox.submit(spec, Distribution.degenerate(t.score))


class StopWhenCleared(MetaAdaptive):
    """Stops the moment the best-so-far clears a bar fixed before the search.

    The winner-anchored case, and the one P4 says is worst: the stopping time is
    a function of the realized maximum, so freezing it at its realized step
    conditions the replicate on an event that has not happened to it.
    """
    name = "stop-when-cleared"

    def __init__(self, bar: float, seed: int = 0):
        super().__init__(seed=seed)
        self.bar = float(bar)

    def _decide(self, state):
        return (("stop" if state["best"] > self.bar else "continue"),
                "best_so_far > bar", state["best"] - self.bar)


class RestartAfterKFailures(MetaAdaptive):
    """Abandons the current support for the next-best anchor after k consecutive
    extensions that did not improve. The restart point is data driven, so the
    realized sequence of restarts is itself a selected object."""
    name = "restart-after-k-failures"

    def __init__(self, k: int = 2, seed: int = 0):
        super().__init__(seed=seed)
        self.k = int(k)

    def _decide(self, state):
        return (("restart" if state["failures"] >= self.k else "continue"),
                f"failures >= {self.k}", float(state["failures"]))


class ExtendWhileImproving(MetaAdaptive):
    """Keeps extending while the last extension gained more than `min_gain`, and
    stops otherwise. The mildest of the three: the trigger looks at an increment
    rather than at the running maximum."""
    name = "extend-while-improving"

    def __init__(self, min_gain: float = 0.0, seed: int = 0):
        super().__init__(seed=seed)
        self.min_gain = float(min_gain)

    def _decide(self, state):
        gain = state["last_gain"]
        return (("stop" if gain <= self.min_gain else "continue"),
                f"last_gain > {self.min_gain}", float(gain))


class ExtendBySecondBest(MetaAdaptive):
    """Continues by adding the **second**-best available extension, not the best.

    Its reason for existing is narrow and structural. For the other three
    searchers the continue-move *is* greedy extension, which is also 7.1's fill
    rule, so past the realized sequence the fill can only diverge from the policy
    in the meta dimension -- when the policy would have stopped or restarted
    there. That happens occasionally and only when the realized sequence is
    short, so it exercises the fill's **content** choice not at all. 7.3 cannot
    exercise it either: an agent has no exact policy null to compare a filled
    trigger replay against.

    Without this searcher the fill's content rule would go into the gate
    untested. Its continuation is deliberately not greedy, so **every** filled
    step adds a different feature from the one the policy would have added.
    Nulls 2 and 3 then separate systematically rather than occasionally, and the
    signed Kolmogorov distance between them says which way the fill errs.

    The meta trigger is the mildest one -- extend while improving -- so that what
    separates the nulls is the continue-move and nothing else.
    """
    name = "second-best-while-improving"

    def __init__(self, min_gain: float = 0.0, seed: int = 0):
        super().__init__(seed=seed)
        self.min_gain = float(min_gain)

    def _decide(self, state):
        gain = state["last_gain"]
        return (("stop" if gain <= self.min_gain else "continue"),
                f"last_gain > {self.min_gain}", float(gain))

    def _extend(self, support, K, score):
        ranked = sorted((c for c in self._grammar_allowed(support, K, score)
                         if c[1] == "extend"), reverse=True)
        if not ranked:
            return None
        return ranked[1] if len(ranked) > 1 else ranked[0]


class SwapWorstWhileImproving(MetaAdaptive):
    """Continues by **swapping**, not extending: once the support reaches
    `min_support`, every continue-move replaces one member with the best
    available replacement.

    This is the searcher the amended fill rule needs. The fill takes the best
    one-step move over the whole grammar, which includes swap, so it dominates
    this policy's move *at each step* -- but a search is a path, and the locally
    best move is not globally optimal, so the filled path can still finish below
    the swap path. Unlike `ExtendBySecondBest`, whose continuation the fill
    dominates by a monotone argument, the direction here is a genuine empirical
    question, which is why rule 3 reads it on this searcher and on
    `RestartAfterKFailures`.
    """
    name = "swap-worst-while-improving"

    def __init__(self, min_gain: float = 0.0, min_support: int = 3, seed: int = 0):
        super().__init__(seed=seed)
        self.min_gain = float(min_gain)
        self.min_support = int(min_support)

    def _decide(self, state):
        gain = state["last_gain"]
        return (("stop" if gain <= self.min_gain else "continue"),
                f"last_gain > {self.min_gain}", float(gain))

    def _extend(self, support, K, score):
        # grow to min_support first; there is nothing to swap out of a support
        # of one that would not simply be a different single feature
        kind = "extend" if len(support) < self.min_support else "swap"
        cands = [c for c in self._grammar_allowed(support, K, score) if c[1] == kind]
        return max(cands) if cands else None


class ClearedRestart(MetaAdaptive):
    """Restart after k failures, and stop once the best clears a bar: the only
    registered searcher with two declared triggers, the shape of an agent's
    policy that both restarts and stops (amendment 6)."""
    name = "cleared-restart"

    def __init__(self, k: int = 1, bar: float = 0.0, seed: int = 0):
        super().__init__(seed=seed)
        self.k, self.bar = int(k), float(bar)

    def _decide(self, state):
        if state["best"] > self.bar:
            return "stop", "best_so_far > bar", state["best"] - self.bar
        return (("restart" if state["failures"] >= self.k else "continue"),
                f"failures >= {self.k}", float(state["failures"]))


class LookaheadStopWhenCleared(StopWhenCleared):
    """Width-2 beam over extend and swap, stopping at the bar. The beam moves at
    every step; the reported support and best move only on improvement, so a
    beam path can pass through a non-improving step and finish above one-step
    greedy -- the continuation 7.1's fill can be LIBERAL against (amendment 6)."""
    name = "lookahead-stop-when-cleared"

    def _search(self, K, single, support_score, frozen=None, meta_steps=None):
        self._beam = None
        return super()._search(K, single, support_score, frozen, meta_steps)

    def _extend(self, support, K, score):
        beam = self._beam if self._beam else [list(support)]
        cands = {}
        for b in beam:
            for sc, kind, ns in self._grammar_allowed(b, K, score):
                if kind in ("extend", "swap"):
                    # One feature set is one candidate: the beam can reach a set
                    # in two orders, which tie exactly and are then split by float
                    # noise differently on each scoring path. Canonical order.
                    ns = sorted(ns)
                    key = tuple(ns)
                    if key not in cands:
                        cands[key] = (score(ns), kind, ns)
        if not cands:
            return None
        ranked = sorted(cands.values(), key=lambda c: (c[0], c[1], c[2]), reverse=True)
        self._beam = [list(c[2]) for c in ranked[:2]]
        return ranked[0]


class RandomExtendWhileImproving(MetaAdaptive):
    """Extends by the next feature, not yet held, of a permutation fixed by the
    searcher's seed, keeping it only if it improves, and stops once an extension
    gains no more than `min_gain`. The fill dominates its continuation, so it is
    the predicted-CONSERVATIVE case (amendment 6)."""
    name = "random-extend-while-improving"

    def __init__(self, min_gain: float = 0.0, seed: int = 0):
        super().__init__(seed=seed)
        self.min_gain = float(min_gain)

    def _decide(self, state):
        gain = state["last_gain"]
        return (("stop" if gain <= self.min_gain else "continue"),
                f"last_gain > {self.min_gain}", float(gain))

    def _search(self, K, single, support_score, frozen=None, meta_steps=None):
        self._perm = [int(k) for k in np.random.default_rng(self.seed).permutation(K)]
        self._ptr = 0
        return super()._search(K, single, support_score, frozen, meta_steps)

    def _extend(self, support, K, score):
        held = {k for k, _ in support}
        while self._ptr < K and self._perm[self._ptr] in held:
            self._ptr += 1
        if self._ptr >= K:
            return None
        j = self._perm[self._ptr]
        self._ptr += 1
        ns = list(support) + [(j, 1.0)]
        if not self._allowed(ns):
            return None
        return (score(ns), "extend", ns)


def registered_71(seed: int, se: float) -> list:
    """Amendment 6's six searchers with their registered parameters. `se` is one
    Sharpe standard error at the configuration's T, so the stop bar is 3.5 se."""
    bar = 3.5 * se
    return [StopWhenCleared(bar=bar, seed=seed), ExtendWhileImproving(min_gain=0.0, seed=seed),
            ClearedRestart(k=1, bar=bar, seed=seed), LookaheadStopWhenCleared(bar=bar, seed=seed),
            RandomExtendWhileImproving(min_gain=0.0, seed=seed),
            ExtendBySecondBest(min_gain=0.0, seed=seed)]


# The three whose continue-move is greedy extension. They are the clean
# measurement of the fixed-sequence gap, because nulls 2 and 3 coincide for them
# and nothing but the freezing moves. ExtendBySecondBest is deliberately not one
# of them.
GREEDY_CONTINUATION = (StopWhenCleared, RestartAfterKFailures, ExtendWhileImproving)
SEARCHERS = GREEDY_CONTINUATION + (ExtendBySecondBest, SwapWorstWhileImproving)

# Rule 3's informative cases: their continuation is not dominated by the fill's
# best-one-step-over-the-grammar move along the whole path.
INFORMATIVE_FOR_FILL = (RestartAfterKFailures, SwapWorstWhileImproving)
