"""Planted non-linear rules (`prereg/ml-pipeline-exploratory-2026-10-07.md`, c and the
decisions of 2026-10-07). EXPLORATORY.

A rule's position path is planted exactly as the generator plants a member: returns are
the resampled residual plus c times the rule's positions, in-sample and holdout, each
segment's positions built from that segment's own features (and, for the gate, its own
residual market). `c` is `planted_panel.planted_scale`, which targets the plant's NET
population Sharpe over all days.

Rules, on z (the features standardised across assets each day):
  U        z_a^2
  corner   1[z_a > 0.8 and z_b > 0], a and b from different families
  product  z_a z_b, a and b from different families
  gated    z_a, on only when the volatility state exceeds its expanding median; off days
           are zero positions, on days unit gross; trades into and out of the gate are
           costed like any other
Each is demeaned across assets and scaled to unit gross on the days it is on.

Features are drawn uniformly over all 40, seeded from the seed's planted-member child, as
`planted_panel.planted_member` draws; nothing is excluded. A rule is "fast" if its path's
turnover (sum |change| / sum gross) exceeds 0.5, else "slow" (fixed at c356992).
"""
from __future__ import annotations

import bisect
import dataclasses

import numpy as np

from environments import planted_panel as pp
from learn import inputs as I

RULES = ("U", "corner", "product", "gated")
# Version 2's three shapes (`prereg/ml-v2-exploratory-2026-10-08.md`, H). They are drawn and
# built by separate branches below; the four shapes above are untouched.
RULES_V2 = ("leadlag", "volcond", "regime")
REGIMES_GATED = ("vol_high", "vol_low", "mkt_up", "mkt_down", "disp_high", "disp_low")
N_X = 10
CORNER_A = 0.8
FAST_TURNOVER = 0.5


@dataclasses.dataclass
class RuleDraw:
    seed: int
    beta: float
    c: float
    rule: dict                 # {"shape", "a", "b"}
    in_sample: object
    holdout: object
    w_star_is: np.ndarray
    w_star_ho: np.ndarray
    idx_is: np.ndarray
    idx_ho: np.ndarray
    m_star: None = None        # a rule is not a class member


def draw_features_v2(seed: int, shape: str, n_v: int = 2, K: int = 40) -> dict:
    """Features for a version-2 shape, from the seed's planted-member child, as
    `draw_features` draws. leadlag: an X column; volcond: a P column a and a V column b;
    regime: a P column a and one of the six gated regimes."""
    rng = np.random.default_rng(pp.children(seed)[1])
    if shape == "leadlag":
        return {"shape": shape, "x": int(rng.integers(N_X))}
    if shape == "volcond":
        return {"shape": shape, "a": int(rng.integers(K)), "b": int(rng.integers(n_v))}
    if shape == "regime":
        return {"shape": shape, "a": int(rng.integers(K)),
                "g": REGIMES_GATED[int(rng.integers(len(REGIMES_GATED)))]}
    raise ValueError(shape)


def rule_positions_v2(features: np.ndarray, rule: dict, residual_returns, v2: dict) -> np.ndarray:
    """Positions for a version-2 shape on one segment. `v2` holds that segment's pinned X and
    V (real-data inputs, `environments.etf_v2_inputs`)."""
    shape = rule["shape"]
    if shape == "leadlag":
        return I.unit(v2["X"][:, :, rule["x"]])
    za = I.zscore_features(features)[:, :, rule["a"]]
    if shape == "volcond":
        vb = v2["V"][:, :, rule["b"]]
        active = vb > np.median(vb, axis=1, keepdims=True)
        n = active.sum(axis=1, keepdims=True)
        mu = np.where(n > 0, (za * active).sum(axis=1, keepdims=True) / np.maximum(n, 1), 0.0)
        s = np.where(active, za - mu, 0.0)
        g = np.abs(s).sum(axis=1, keepdims=True)
        return np.where(g > 0, s / np.where(g > 0, g, 1.0), 0.0)
    if shape == "regime":
        from learn2.states import market_states, regime_gates
        on = regime_gates(market_states(residual_returns, 1))[rule["g"]]
        return I.unit(za) * on[:, None]
    raise ValueError(shape)


def draw_features(seed: int, shape: str, family_of=None) -> dict:
    fam = I.FAMILY_OF if family_of is None else np.asarray(family_of)
    K = len(fam)
    rng = np.random.default_rng(pp.children(seed)[1])
    a = int(rng.integers(K))
    b = None
    if shape in ("corner", "product"):
        b = int(rng.choice([k for k in range(K) if fam[k] != fam[a]]))
    return {"shape": shape, "a": a, "b": b}


def gate(residual_returns: np.ndarray) -> np.ndarray:
    """On where the volatility state exceeds its expanding median (rows <= t)."""
    v = I.market_states(residual_returns)[:, 0]
    on = np.zeros(len(v), bool)
    hist: list[float] = []
    for t, x in enumerate(v):
        bisect.insort(hist, float(x))
        n = len(hist)
        med = hist[n // 2] if n % 2 else 0.5 * (hist[n // 2 - 1] + hist[n // 2])
        on[t] = x > med
    return on


def rule_positions(features: np.ndarray, rule: dict, residual_returns=None) -> np.ndarray:
    z = I.zscore_features(features)
    za = z[:, :, rule["a"]]
    shape = rule["shape"]
    if shape == "U":
        s = za ** 2
    elif shape == "corner":
        s = ((za > CORNER_A) & (z[:, :, rule["b"]] > 0)).astype(float)
    elif shape == "product":
        s = za * z[:, :, rule["b"]]
    elif shape == "gated":
        s = za
    else:
        raise ValueError(shape)
    w = I.unit(s)
    if shape == "gated":
        w = w * gate(residual_returns)[:, None]
    return w


def turnover(w: np.ndarray) -> float:
    """sum over days of |change in position| / sum over days of gross (c356992, 92f7ea1)."""
    g = np.abs(w).sum()
    return float(np.abs(np.diff(w, axis=0)).sum() / g) if g > 0 else 0.0


def speed(w: np.ndarray) -> str:
    return "fast" if turnover(w) > FAST_TURNOVER else "slow"


def make_draw_rule(base, seed: int, beta: float, shape: str, rule: dict | None = None,
                   block_length: int = pp.BLOCK_LENGTH) -> RuleDraw:
    from dataclasses import replace
    from estimator.bootstrap import stationary_bootstrap_indices
    if shape in RULES_V2:
        return make_draw_rule_v2(base, seed, beta, shape, rule, block_length)
    rule = rule or draw_features(seed, shape)
    ch = pp.children(seed)
    idx_is = stationary_bootstrap_indices(base.E_is.shape[0], block_length,
                                          np.random.default_rng(ch[0]))
    idx_ho = stationary_bootstrap_indices(base.E_ho.shape[0], block_length,
                                          np.random.default_rng(ch[2]))
    E_is, E_ho = base.E_is[idx_is], base.E_ho[idx_ho]
    w_is = rule_positions(base.in_sample.features, rule, E_is)
    w_ho = rule_positions(base.holdout.features, rule, E_ho)
    c = pp.planted_scale(base.in_sample, base.Sigma_is, w_is, beta)
    return RuleDraw(seed=seed, beta=beta, c=c, rule=rule,
                    in_sample=replace(base.in_sample, returns=E_is + c * w_is),
                    holdout=replace(base.holdout, returns=E_ho + c * w_ho),
                    w_star_is=w_is, w_star_ho=w_ho, idx_is=idx_is, idx_ho=idx_ho)


def make_draw_rule_v2(base, seed: int, beta: float, shape: str, rule: dict | None = None,
                      block_length: int = pp.BLOCK_LENGTH, v2: dict | None = None) -> RuleDraw:
    """A version-2 shape planted as every rule is: residuals resampled by the seed's
    children, c net-targeted to `beta`. `v2` = {"is": ..., "ho": ...} segment inputs; by
    default the pinned real-ETF inputs sliced to the base's segments."""
    from dataclasses import replace
    from estimator.bootstrap import stationary_bootstrap_indices
    if v2 is None:
        from environments import etf_v2_inputs as E2
        pinned = E2.load()
        v2 = {"is": E2.for_segment(base.in_sample, pinned), "ho": E2.for_segment(base.holdout, pinned)}
    rule = rule or draw_features_v2(seed, shape, n_v=v2["is"]["V"].shape[2],
                                    K=base.in_sample.features.shape[2])
    ch = pp.children(seed)
    idx_is = stationary_bootstrap_indices(base.E_is.shape[0], block_length,
                                          np.random.default_rng(ch[0]))
    idx_ho = stationary_bootstrap_indices(base.E_ho.shape[0], block_length,
                                          np.random.default_rng(ch[2]))
    E_is, E_ho = base.E_is[idx_is], base.E_ho[idx_ho]
    w_is = rule_positions_v2(base.in_sample.features, rule, E_is, v2["is"])
    w_ho = rule_positions_v2(base.holdout.features, rule, E_ho, v2["ho"])
    c = pp.planted_scale(base.in_sample, base.Sigma_is, w_is, beta)
    return RuleDraw(seed=seed, beta=beta, c=c, rule=rule,
                    in_sample=replace(base.in_sample, returns=E_is + c * w_is),
                    holdout=replace(base.holdout, returns=E_ho + c * w_ho),
                    w_star_is=w_is, w_star_ho=w_ho, idx_is=idx_is, idx_ho=idx_ho)


def gross_population_sharpe(panel, Sigma, w_m, w_star, c) -> float:
    d = c * np.einsum("tm,tm->t", w_m, w_star)
    v = float(np.einsum("tm,mn,tn->t", w_m, Sigma, w_m).mean() + d.var())
    return float(d.mean() / np.sqrt(v) * np.sqrt(panel.periods_per_year))


def plant_record(base, draw: RuleDraw) -> dict:
    """c, the plant's population gross and net Sharpe (in-sample and holdout), its turnover
    and its fast/slow label."""
    return {"c": draw.c, "rule": draw.rule,
            "net": {"in_sample": pp.population_sharpe(base.in_sample, base.Sigma_is,
                                                      draw.w_star_is, draw.w_star_is, draw.c),
                    "holdout": pp.population_sharpe(base.holdout, base.Sigma_ho,
                                                    draw.w_star_ho, draw.w_star_ho, draw.c)},
            "gross": {"in_sample": gross_population_sharpe(base.in_sample, base.Sigma_is,
                                                          draw.w_star_is, draw.w_star_is, draw.c),
                      "holdout": gross_population_sharpe(base.holdout, base.Sigma_ho,
                                                        draw.w_star_ho, draw.w_star_ho, draw.c)},
            "turnover": turnover(draw.w_star_is), "speed": speed(draw.w_star_is)}


def truth_positions(base, draw, w_is: np.ndarray | None, w_ho: np.ndarray | None) -> dict:
    """The population net Sharpe of any position path under the draw's DGP (a member's or a
    rule's), in-sample and holdout. A None segment gives None."""
    return {"in_sample": (pp.population_sharpe(base.in_sample, base.Sigma_is, w_is,
                                               draw.w_star_is, draw.c) if w_is is not None else None),
            "holdout": (pp.population_sharpe(base.holdout, base.Sigma_ho, w_ho,
                                             draw.w_star_ho, draw.c) if w_ho is not None else None)}
