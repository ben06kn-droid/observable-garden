"""Design measurements for fixed-sequence-replay (7.1) amendment 6.

    python -m experiments.fsr_design --what inertness --seeds 10 --B 200 --workers 6

NOT 7.1 draws. These run on the DESIGN seed block 960000-960999, disjoint from
7.1's registered 300000-301999, at 7.1's registered data configuration (K=40,
M=50, T=5,000, rho=0, s0), and exist to choose and justify the searchers and
their parameters before the driver is written. They are recorded in the
amendment the way the earlier unit-fixture numbers were.

The resampling mirrors `estimator.trigger_replay.replay_nulls` exactly: the
realized search on the columns as they are, replicates from the demeaned columns
by the stationary bootstrap at the selected block length, one RNG per seed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices

DESIGN_SEED0 = 960_000
M, T, T_OOS, K = 50, 5000, 1000, 40


def panel(seed: int):
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    return sb.base_feature_columns(), float(np.sqrt(cfg.periods_per_year))


def random_anchor_class():
    """The candidate redesign for amendment 6, defined here for design
    measurement only; it moves into searchers/ after the amendment is committed.

    Identical to `RestartAfterKFailures` except where anchors come from: a
    permutation of the features fixed by the searcher's seed, not the ranking by
    score. The order does not depend on the data, so it is oblivious and a
    replicate uses the same one; but the first anchor is no longer the best
    single feature, so the first path is not near-optimal and a restart can
    matter."""
    from searchers.meta_adaptive import Move, RestartAfterKFailures, Trace

    class RandomAnchorRestart(RestartAfterKFailures):
        name = "random-anchor-restart"

        def _search(self, K, single, support_score, frozen=None, meta_steps=None):
            self._K = K
            order = [int(k) for k in np.random.default_rng(self.seed).permutation(K)]
            anchor = 0
            support = [(order[anchor], 1.0)]
            best = float(single(order[anchor]))
            best_support = list(support)
            trace = Trace(policy=self.name)
            failures, last_gain = 0, float("inf")
            for step in range(self.budget):
                state = {"step": step, "support": tuple(support), "best": best,
                         "failures": failures, "last_gain": last_gain, "n_features": K}
                if frozen is not None:
                    if step >= len(frozen):
                        break
                    action, trigger, value = frozen[step], "frozen", float("nan")
                elif meta_steps is not None and step >= meta_steps:
                    action, trigger, value = "continue", "fill", float("nan")
                else:
                    action, trigger, value = self._decide(state)
                if action == "stop":
                    trace.moves.append(Move(step, "stop", trigger, value, tuple(support), best))
                    break
                if action == "restart":
                    anchor += 1
                    if anchor >= K:
                        trace.moves.append(Move(step, "stop", "exhausted", float(anchor),
                                                tuple(support), best))
                        break
                    support = [(order[anchor], 1.0)]
                    a_score = float(single(order[anchor]))
                    if a_score > best:        # a random anchor can itself be a new best
                        best, best_support = a_score, list(support)
                    failures, last_gain = 0, float("inf")
                    trace.moves.append(Move(step, "restart", trigger, value, tuple(support), best))
                    continue
                filling = trigger == "fill"
                chosen = (self._fill_move(support, K, support_score) if filling
                          else self._extend(support, K, support_score))
                if chosen is None:
                    trace.moves.append(Move(step, "stop", "exhausted", 0.0, tuple(support), best))
                    break
                gain_score, kind, new_support = chosen
                cur = float(support_score(support))
                last_gain = gain_score - cur
                if gain_score > cur:          # improve on the CURRENT path, not the global best
                    support = list(new_support)
                    failures = 0
                    if gain_score > best:
                        best, best_support = float(gain_score), list(support)
                else:
                    failures += 1
                trace.moves.append(Move(step, "continue", trigger, value, tuple(support), best))
            trace.support, trace.score = tuple(best_support), best
            return trace

    return RandomAnchorRestart


BAR_SE = 3.5      # candidate stop bar, in Sharpe standard errors at T


def cleared_restart_classes():
    """Candidate redesign 2: restart after k failures AND stop once the best
    clears a bar. Without a stop the restart searchers always run to the budget,
    so the trigger null never runs past the realized length and nulls 2 and 3
    coincide by construction. Both anchor rules, for comparison."""
    from searchers.meta_adaptive import RestartAfterKFailures
    RA = random_anchor_class()

    def decide(self, state):
        if state["best"] > self.bar:
            return "stop", "best_so_far > bar", state["best"] - self.bar
        return (("restart" if state["failures"] >= self.k else "continue"),
                f"failures >= {self.k}", float(state["failures"]))

    class ClearedRestart(RestartAfterKFailures):
        name = "cleared-restart"
        def __init__(self, k=2, bar=0.0, seed=0):
            super().__init__(k=k, seed=seed); self.bar = float(bar)
        _decide = decide

    class ClearedRandomRestart(RA):
        name = "cleared-random-restart"
        def __init__(self, k=2, bar=0.0, seed=0):
            super().__init__(k=k, seed=seed); self.bar = float(bar)
        _decide = decide

    return ClearedRestart, ClearedRandomRestart


def continuation_classes():
    """Amendment 6's two added searchers, both stopping at the 3.5 se bar so that
    replicates run past the realized length and the fill engages. Their
    continuations differ from greedy extension in opposite directions."""
    from searchers.meta_adaptive import StopWhenCleared

    class LookaheadStopWhenCleared(StopWhenCleared):
        """Width-2 beam over extend and swap. The beam moves every step; the
        reported support and best move only on improvement, so a beam path can
        pass through a non-improving step and finish above one-step greedy --
        the case where the fill (best single step) can be LIBERAL."""
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
                        key = tuple(ns)
                        if key not in cands or sc > cands[key][0]:
                            cands[key] = (sc, kind, ns)
            if not cands:
                return None
            ranked = sorted(cands.values(), key=lambda c: (c[0], c[1], c[2]), reverse=True)
            self._beam = [list(c[2]) for c in ranked[:2]]
            return ranked[0]

    class RandomExtendStopWhenCleared(StopWhenCleared):
        """Extends by the next feature, not in the support, of a permutation fixed
        by the searcher's seed; taken only if it improves. The fill (best single
        step) dominates it, so the predicted direction is CONSERVATIVE."""
        name = "random-extend-stop-when-cleared"

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
            return (score(ns), "extend", ns)

    return LookaheadStopWhenCleared, RandomExtendStopWhenCleared


def own_continuation(cls):
    """The searcher with 7.1's fill replaced by its OWN continuation, and no stop
    past the realized length. Trigger replay on it gives null 2': it differs from
    null 2 only in what the continuation adds, so null 2 against null 2' is the
    fill's content choice with the meta dimension held fixed."""
    class Own(cls):
        def _fill_move(self, support, K, score):
            return self._extend(support, K, score)
    Own.name = cls.name + "+own-fill"
    return Own


def gain_stop_random_extend():
    """Random extension with a gain-based stop, so it stops early enough for
    replicates to run past (at the 3.5 se bar it never stopped)."""
    RE = continuation_classes()[1]

    class RandomExtendWhileImproving(RE):
        name = "random-extend-while-improving"
        def __init__(self, min_gain=0.0, seed=0):
            super().__init__(bar=float("inf"), seed=seed); self.min_gain = float(min_gain)
        def _decide(self, state):
            gain = state["last_gain"]
            return (("stop" if gain <= self.min_gain else "continue"),
                    f"last_gain > {self.min_gain}", float(gain))
    return RandomExtendWhileImproving


def _content_seed(args):
    name, params, seed, B = args
    from searchers.meta_adaptive import ExtendBySecondBest, SwapWorstWhileImproving
    cls = {"lookahead": continuation_classes()[0], "random_extend_gain": gain_stop_random_extend(),
           "swap": SwapWorstWhileImproving, "second": ExtendBySecondBest}[name]
    extra = {"seed": seed} if "random" in name else {}
    s, own = cls(**params, **extra), own_continuation(cls)(**params, **extra)
    base, ann = panel(seed)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(seed)
    n = s.trace(base, ann).n_moves
    n2, n2own, eng = [], [], 0
    for _ in range(B):
        R = S0[stationary_bootstrap_indices(T, L, rng), :]
        t = s.trace(R, ann, meta_steps=n)
        eng += int(any(m.trigger == "fill" for m in t.moves))
        n2.append(t.score)
        n2own.append(own.trace(R, ann, meta_steps=n).score)
    return {"n2": n2, "n2own": n2own, "engaged": eng}


def content_only(seeds: int, B: int, workers: int) -> str:
    from estimator.trigger_replay import ReplayNulls
    se = float(np.sqrt(DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0).periods_per_year / T))
    cases = [("lookahead", {"bar": BAR_SE * se}), ("random_extend_gain", {"min_gain": 0.0}),
             ("swap", {"min_gain": 0.0, "min_support": 3}), ("second", {"min_gain": 0.0})]
    lines = ["DESIGN MEASUREMENT -- not a 7.1 draw: null 2 (7.1's fill) against null 2' "
             "(the searcher's own continuation), meta dimension held fixed",
             f"seeds {DESIGN_SEED0}-{DESIGN_SEED0 + seeds - 1}, B={B}; signed KS > 0 means null 2 "
             "is smaller than null 2', i.e. the fill is LIBERAL", ""]
    with ProcessPoolExecutor(workers) as ex:
        for name, params in cases:
            res = list(ex.map(_content_seed, [(name, params, DESIGN_SEED0 + i, B) for i in range(seeds)]))
            n_rep = seeds * B
            differ = sum(int(np.sum(np.array(r["n2"]) != np.array(r["n2own"]))) for r in res)
            eng = sum(r["engaged"] for r in res)
            sk = np.array([ReplayNulls(fixed_sequence=np.array(r["n2own"]), trigger=np.array(r["n2"]),
                                       policy=np.array(r["n2own"]), block_length=1, B=B,
                                       realized_score=0.0, realized_actions=()
                                       ).signed_kolmogorov_distance("trigger", "policy") for r in res])
            higher = sum(int(np.sum(np.array(r["n2own"]) > np.array(r["n2"]))) for r in res)
            lines += [f"{name} {params}",
                      f"  engagement: {eng}/{n_rep} ({100 * eng / n_rep:.2f}%)",
                      f"  null 2 != null 2': {differ}/{n_rep} ({100 * differ / n_rep:.2f}%); "
                      f"own continuation higher on {higher} of them",
                      f"  per-seed signed KS(null 2 vs 2'): positive {int(np.sum(sk > 0))}, "
                      f"zero {int(np.sum(sk == 0))}, negative {int(np.sum(sk < 0))}; median {np.median(sk):+.4f}", ""]
    return "\n".join(lines)


def trigger_fill(cls):
    """Amendment 6's fill, as the gate will build it: past the realized length the
    declared triggers are STILL EVALUATED at every step, and only when they say
    continue is the content move replaced by 7.1's fill (best one-step move over
    extend, swap, flip). Run in policy mode with `fill_from` set to the realized
    length, this is null 2; with `fill_from` unset it is the policy, null 3. The
    two differ in content only."""
    class TriggerFill(cls):
        fill_from = None
        engaged = False

        def _decide(self, state):
            self._cur_step = state["step"]
            return super()._decide(state)

        def _extend(self, support, K, score):
            if self.fill_from is not None and getattr(self, "_cur_step", -1) >= self.fill_from:
                self.engaged = True
                return self._fill_move(support, K, score)
            return super()._extend(support, K, score)
    TriggerFill.name = cls.name
    return TriggerFill


def _fill_seed(args):
    name, params, seed, B = args
    from searchers.meta_adaptive import (ExtendBySecondBest, ExtendWhileImproving,
                                         RestartAfterKFailures, StopWhenCleared,
                                         SwapWorstWhileImproving)
    LA, RE = continuation_classes()
    base_cls = {"stop": StopWhenCleared, "restart": RestartAfterKFailures,
                "cleared_restart": cleared_restart_classes()[0],
                "extend": ExtendWhileImproving, "second": ExtendBySecondBest,
                "swap": SwapWorstWhileImproving, "lookahead": LA, "random_extend": RE,
                "random_extend_gain": gain_stop_random_extend()}[name]
    extra = {"seed": seed} if "random" in name else {}
    s = trigger_fill(base_cls)(**params, **extra)
    base, ann = panel(seed)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(seed)
    s.fill_from = None
    n = s.trace(base, ann).n_moves
    n2, n3, eng = [], [], 0
    for _ in range(B):
        R = S0[stationary_bootstrap_indices(T, L, rng), :]
        s.fill_from, s.engaged = None, False
        n3.append(s.trace(R, ann).score)
        s.fill_from, s.engaged = n, False
        n2.append(s.trace(R, ann).score)
        eng += int(s.engaged)
    s.fill_from = None
    return {"n2": n2, "n3": n3, "engaged": eng, "n_realized": n}


def trigger_fill_run(seeds: int, B: int, workers: int) -> str:
    from estimator.trigger_replay import ReplayNulls
    se = float(np.sqrt(DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0).periods_per_year / T))
    bar = BAR_SE * se
    cases = [("lookahead", {"bar": bar}), ("random_extend", {"bar": bar}),
             ("random_extend_gain", {"min_gain": 0.0}), ("swap", {"min_gain": 0.0, "min_support": 3}),
             ("second", {"min_gain": 0.0}), ("extend", {"min_gain": 0.0}), ("stop", {"bar": bar}),
             ("restart", {"k": 2}), ("cleared_restart", {"k": 1, "bar": bar})]
    lines = ["DESIGN MEASUREMENT -- not a 7.1 draw. Fill = best one-step content move with the "
             "declared triggers still evaluated at every filled step (amendment 6).",
             f"seeds {DESIGN_SEED0}-{DESIGN_SEED0 + seeds - 1}, B={B}. null 2 = that fill past the "
             "realized length; null 3 = the policy. Signed KS > 0: null 2 smaller, fill LIBERAL.", ""]
    with ProcessPoolExecutor(workers) as ex:
        for name, params in cases:
            res = list(ex.map(_fill_seed, [(name, params, DESIGN_SEED0 + i, B) for i in range(seeds)]))
            n_rep = seeds * B
            eng = sum(r["engaged"] for r in res)
            a2 = [np.array(r["n2"]) for r in res]; a3 = [np.array(r["n3"]) for r in res]
            differ = sum(int(np.sum(x != y)) for x, y in zip(a2, a3))
            fill_higher = sum(int(np.sum(x > y)) for x, y in zip(a2, a3))
            sk = np.array([ReplayNulls(fixed_sequence=y, trigger=x, policy=y, block_length=1, B=B,
                                       realized_score=0.0, realized_actions=()
                                       ).signed_kolmogorov_distance("trigger", "policy")
                           for x, y in zip(a2, a3)])
            lines += [f"{name} {params}",
                      f"  realized lengths: median {int(np.median([r['n_realized'] for r in res]))}, "
                      f"at budget {sum(r['n_realized'] >= 12 for r in res)}/{seeds}",
                      f"  engagement: {eng}/{n_rep} ({100 * eng / n_rep:.2f}%)",
                      f"  null 2 != null 3: {differ}/{n_rep} ({100 * differ / n_rep:.2f}%); "
                      f"fill higher on {fill_higher}, policy higher on {differ - fill_higher}",
                      f"  per-seed signed KS: positive {int(np.sum(sk > 0))}, zero {int(np.sum(sk == 0))}, "
                      f"negative {int(np.sum(sk < 0))}; median {np.median(sk):+.4f}", ""]
    return "\n".join(lines)


def _phase_gain(trace, kind: str, min_support: int = 3) -> tuple[bool, bool]:
    """(phase entered, best improved after it). For restart the phase starts at
    the first restart; for swap, at the step the support first reaches
    `min_support`, after which every continue-move is a swap."""
    marker = None
    for m in trace.moves:
        if kind == "restart" and m.action == "restart":
            marker = m.score
            break
        if kind == "swap" and m.action == "continue" and len(m.support) >= min_support:
            marker = m.score
            break
    if marker is None:
        return False, False
    return True, trace.score > marker


def _one_seed(args):
    name, params, seed, B = args
    from searchers.meta_adaptive import (ExtendBySecondBest, ExtendWhileImproving,
                                         RestartAfterKFailures, StopWhenCleared,
                                         SwapWorstWhileImproving)
    cls = {"restart": RestartAfterKFailures, "swap": SwapWorstWhileImproving,
           "stop": StopWhenCleared, "extend": ExtendWhileImproving,
           "second": ExtendBySecondBest, "random_restart": random_anchor_class(),
           "cleared_restart": cleared_restart_classes()[0],
           "cleared_random_restart": cleared_restart_classes()[1],
           "lookahead": continuation_classes()[0],
           "random_extend": continuation_classes()[1]}[name]
    s = cls(**params, **({"seed": seed} if "random" in name else {}))
    base, ann = panel(seed)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(seed)
    realized = s.trace(base, ann)
    n = realized.n_moves
    kind = "swap" if name == "swap" else "restart"
    out = {"realized_actions": realized.actions(),
           "realized_phase": _phase_gain(realized, kind),
           "rep_phase": [], "rep_actions": [], "differ_23": 0, "differ_13": 0,
           "engaged": 0, "n2": [], "n3": [], "seconds": 0.0}
    import time
    for _ in range(B):
        R = S0[stationary_bootstrap_indices(T, L, rng), :]
        t0 = time.perf_counter()
        pol = s.trace(R, ann)
        trig_t = s.trace(R, ann, meta_steps=n)
        fixed = s.replay_fixed_sequence(R, realized.actions(), annualization=ann)
        out["seconds"] += time.perf_counter() - t0
        trig = trig_t.score
        out["engaged"] += int(any(m.trigger == "fill" for m in trig_t.moves))
        out["differ_23"] += int(trig != pol.score)
        out["differ_13"] += int(fixed != pol.score)
        out["n2"].append(trig); out["n3"].append(pol.score)
        out["rep_phase"].append(_phase_gain(pol, kind))
        out["rep_actions"].append(pol.actions())
    return out


def inertness(seeds: int, B: int, workers: int, cases=None) -> str:
    cases = cases or [("restart", {"k": 2}), ("swap", {"min_gain": 0.0, "min_support": 3})]
    lines = ["DESIGN MEASUREMENT -- not a 7.1 draw", f"seeds {DESIGN_SEED0}-{DESIGN_SEED0 + seeds - 1}, "
             f"B={B} replicates each, K={K} M={M} T={T} s0", ""]
    with ProcessPoolExecutor(workers) as ex:
        for name, params in cases:
            res = list(ex.map(_one_seed, [(name, params, DESIGN_SEED0 + i, B)
                                          for i in range(seeds)]))
            n_rep = seeds * B
            entered = sum(p[0] for r in res for p in r["rep_phase"])
            gained = sum(p[1] for r in res for p in r["rep_phase"])
            r_entered = sum(r["realized_phase"][0] for r in res)
            r_gained = sum(r["realized_phase"][1] for r in res)
            d23 = sum(r["differ_23"] for r in res)
            d13 = sum(r["differ_13"] for r in res)
            label = "swap phase" if name == "swap" else "restart"
            from estimator.trigger_replay import ReplayNulls
            sk = []
            for r in res:
                rn = ReplayNulls(fixed_sequence=np.array(r["n3"]), trigger=np.array(r["n2"]),
                                 policy=np.array(r["n3"]), block_length=1, B=B,
                                 realized_score=0.0, realized_actions=())
                sk.append(rn.signed_kolmogorov_distance("trigger", "policy"))
            sk = np.array(sk)
            eng = sum(r["engaged"] for r in res)
            secs = sum(r["seconds"] for r in res) / n_rep
            lines += [f"{name} {params}",
                      f"  realized runs: {label} entered {r_entered}/{seeds}, "
                      f"best beaten after it {r_gained}/{seeds}",
                      f"  replicates (policy path): {label} entered {entered}/{n_rep}, "
                      f"best beaten after it {gained}/{n_rep} ({100 * gained / n_rep:.2f}%)",
                      f"  nulls 2 and 3 differ on {d23}/{n_rep} replicates ({100 * d23 / n_rep:.2f}%)",
                      f"  nulls 1 and 3 differ on {d13}/{n_rep} replicates ({100 * d13 / n_rep:.2f}%)",
                      f"  engagement (trigger replay runs past the realized length): {eng}/{n_rep} "
                      f"({100 * eng / n_rep:.2f}%)",
                      f"  per-seed signed KS(null 2 vs 3): positive {int(np.sum(sk > 0))}, zero "
                      f"{int(np.sum(sk == 0))}, negative {int(np.sum(sk < 0))}; median {np.median(sk):+.4f}",
                      f"  single-core cost: {secs * 1000:.1f} ms per replicate for the three nulls",
                      ""]
    return "\n".join(lines)


def _firing_seed(seed):
    """Realized null runs on one design seed, for every candidate parameter.
    Returns per-configuration action sequences and best-so-far paths."""
    from searchers.meta_adaptive import (ExtendBySecondBest, ExtendWhileImproving,
                                         RestartAfterKFailures, StopWhenCleared,
                                         SwapWorstWhileImproving)
    RA = random_anchor_class()
    base, ann = panel(seed)
    se = float(np.sqrt(DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0).periods_per_year / T))
    configs = {}
    for c in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
        configs[("stop", f"bar={c}se")] = StopWhenCleared(bar=c * se)
    for k in (1, 2, 3):
        configs[("restart", f"k={k}")] = RestartAfterKFailures(k=k)
        configs[("random_restart", f"k={k}")] = RA(k=k, seed=seed)
    for g in (0.0, 0.1, 0.25, 0.5):
        configs[("extend", f"min_gain={g}se")] = ExtendWhileImproving(min_gain=g * se)
        configs[("second", f"min_gain={g}se")] = ExtendBySecondBest(min_gain=g * se)
        configs[("swap", f"min_gain={g}se,min_support=3")] = SwapWorstWhileImproving(
            min_gain=g * se, min_support=3)
    out = {}
    for key, srch in configs.items():
        t = srch.trace(base, ann)
        out[key] = {"actions": t.actions(), "n": t.n_moves,
                    "phase": _phase_gain(t, "swap" if key[0] == "swap" else "restart")}
    return se, out


def firing(seeds: int, workers: int) -> str:
    with ProcessPoolExecutor(workers) as ex:
        res = list(ex.map(_firing_seed, [DESIGN_SEED0 + 100 + i for i in range(seeds)]))
    se = res[0][0]
    lines = ["DESIGN MEASUREMENT -- not a 7.1 draw",
             f"realized null runs on seeds {DESIGN_SEED0 + 100}-{DESIGN_SEED0 + 99 + seeds}, "
             f"K={K} M={M} T={T} s0; one Sharpe standard error at T={T}: se = {se:.4f}", "",
             f"{'searcher':<16}{'parameter':<26}{'stop fired':>11}{'restart fired':>14}"
             f"{'hit budget':>11}{'median steps':>13}{'phase gain':>11}"]
    for key in res[0][1]:
        runs = [r[1][key] for r in res]
        n = len(runs)
        stop = sum("stop" in r["actions"] and r["n"] < 12 for r in runs)
        rst = sum("restart" in r["actions"] for r in runs)
        budget = sum(r["n"] >= 12 and "stop" not in r["actions"] for r in runs)
        gain = sum(r["phase"][1] for r in runs)
        med = int(np.median([r["n"] for r in runs]))
        lines.append(f"{key[0]:<16}{key[1]:<26}{stop / n:>11.2f}{rst / n:>14.2f}"
                     f"{budget / n:>11.2f}{med:>13d}{gain / n:>11.2f}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", choices=["inertness", "inertness_random", "inertness_cleared",
                                       "all_searchers", "content_only", "trigger_fill", "firing"], required=True)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--B", type=int, default=200)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.what == "trigger_fill":
        print(trigger_fill_run(a.seeds, a.B, a.workers), flush=True)
    elif a.what == "content_only":
        print(content_only(a.seeds, a.B, a.workers), flush=True)
    elif a.what == "firing":
        print(firing(a.seeds, a.workers), flush=True)
    elif a.what == "inertness_cleared":
        se = float(np.sqrt(DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0).periods_per_year / T))
        print(inertness(a.seeds, a.B, a.workers,
                        cases=[(n, {"k": k, "bar": BAR_SE * se})
                               for n in ("cleared_restart", "cleared_random_restart")
                               for k in (1, 2)]), flush=True)
    elif a.what == "all_searchers":
        se = float(np.sqrt(DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0).periods_per_year / T))
        bar = BAR_SE * se
        print(inertness(a.seeds, a.B, a.workers, cases=[
            ("lookahead", {"bar": bar}), ("random_extend", {"bar": bar}),
            ("swap", {"min_gain": 0.0, "min_support": 3}),
            ("stop", {"bar": bar}), ("restart", {"k": 2}),
            ("cleared_restart", {"k": 1, "bar": bar}),
            ("extend", {"min_gain": 0.0}), ("second", {"min_gain": 0.0})]), flush=True)
    elif a.what == "inertness_random":
        print(inertness(a.seeds, a.B, a.workers,
                        cases=[("random_restart", {"k": k}) for k in (1, 2)]), flush=True)
    else:
        print(inertness(a.seeds, a.B, a.workers), flush=True)


if __name__ == "__main__":
    main()
