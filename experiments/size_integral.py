"""The winner-anchored size integral by quadrature: a cross-check of `experiments/limit_model.py`
(which evaluates the same limit by Monte Carlo) for THEORY.md's breadth table (P4).

In the Gaussian limit, Z_i = sqrt(w) f + sqrt(1 - w) e_i (equicorrelation w), the pair statistic
is g(a, b) = (a + b) / sqrt(2 + 2w), and the winner-anchored search submits
max(Z_(1), g(Z_(1), Z_(2))). With
    A(f) = (x - sqrt(w) f) / sqrt(1 - w),   B(f) = (sqrt(2 + 2w) x - 2 sqrt(w) f) / sqrt(1 - w),
its process null is
    F_P(x) = integral phi(f) G_K(A(f), B(f)) df,
    G_K(A, B) = K * integral_{-inf}^{A} phi(u) Phi(min(u, B - u))^(K-1) du,
and the realized-menu null (anchor frozen at one index; P4') is, directly,
    F_C(x) = integral phi(f) integral_{-inf}^{A} phi(v) Phi(min(A, B - v))^(K-1) dv df,
which P4' says equals the rank mixture (1/K) sum_k F_P(k); `rank_mixture` computes that too,
as a check. The limit type-I at level alpha is 1 - F_P(F_C^{-1}(1 - alpha)).

    python -m experiments.size_integral
"""
from __future__ import annotations

from math import comb

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

ALPHA = 0.05
CELLS = ((0.0, 10), (0.0, 20), (0.0, 40), (0.0, 80), (0.3, 10), (0.3, 20), (0.3, 40), (0.3, 80))
THEORY_LIMIT = {(0.0, 10): 0.100, (0.0, 20): 0.156, (0.0, 40): 0.241, (0.0, 80): 0.359,
                (0.3, 10): 0.073, (0.3, 20): 0.092, (0.3, 40): 0.113, (0.3, 80): 0.137}


GH_X, GH_W = np.polynomial.hermite_e.hermegauss(96)      # probabilists' Gauss-Hermite over f
GH_W = GH_W / np.sqrt(2 * np.pi)
GL_X, GL_W = np.polynomial.legendre.leggauss(96)
LOW = -10.0


def _segments(a: float, b: float, kink: float):
    """Gauss-Legendre nodes and weights on [a, b], split at `kink` if it lies inside."""
    cuts = [a] + ([kink] if a < kink < b else []) + [b]
    xs, ws = [], []
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        xs.append(0.5 * (hi - lo) * GL_X + 0.5 * (hi + lo))
        ws.append(0.5 * (hi - lo) * GL_W)
    return np.concatenate(xs), np.concatenate(ws)


def _AB(x, w, f):
    s = np.sqrt(1 - w)
    return (x - np.sqrt(w) * f) / s, (np.sqrt(2 + 2 * w) * x - 2 * np.sqrt(w) * f) / s


def _outer(fn, w):
    if w == 0.0:
        return fn(0.0)
    return float(sum(wf * fn(f) for f, wf in zip(GH_X, GH_W)))


def F_P(x: float, K: int, w: float, k: int = 1) -> float:
    """The rank-k anchor's process null; k = 1 is the winner (the note's G_K)."""
    def inner(f):
        A, B = _AB(x, w, f)
        if A <= LOW:
            return 0.0
        u, wu = _segments(LOW, A, B / 2)
        if k == 1:
            g = norm.cdf(np.minimum(u, B - u)) ** (K - 1)
        else:
            lo = norm.cdf(np.minimum(B - u, u))
            mid = norm.cdf(u) - lo
            g = sum(comb(K - 1, j) * mid ** j * lo ** (K - 1 - j) for j in range(k - 1))
        return K * float(np.sum(wu * norm.pdf(u) * g))
    return _outer(inner, w)


def F_C(x: float, K: int, w: float) -> float:
    """The realized-menu null, directly (anchor frozen at one index)."""
    def inner(f):
        A, B = _AB(x, w, f)
        if A <= LOW:
            return 0.0
        v, wv = _segments(LOW, A, B - A)
        return float(np.sum(wv * norm.pdf(v) * norm.cdf(np.minimum(A, B - v)) ** (K - 1)))
    return _outer(inner, w)


def rank_mixture(x: float, K: int, w: float) -> float:
    """P4': (1/K) sum_k F_P(k), for checking F_C."""
    return float(np.mean([F_P(x, K, w, k) for k in range(1, K + 1)]))


def type1(K: int, w: float, alpha: float = ALPHA) -> tuple[float, float]:
    q = brentq(lambda x: F_C(x, K, w) - (1 - alpha), 0.5, 7.0, xtol=1e-9)
    return 1.0 - F_P(q, K, w), q


def main() -> int:
    print("Winner-anchored limit type-I by quadrature, against THEORY.md's limit column (Monte Carlo, limit_model.py)")
    worst = 0.0
    for w, K in CELLS:
        rate, q = type1(K, w)
        diff = rate - THEORY_LIMIT[(w, K)]
        worst = max(worst, abs(diff))
        print(f"  w {w:.1f}  K {K:3d}  quadrature {rate:.4f}  THEORY.md {THEORY_LIMIT[(w, K)]:.3f}  difference {diff:+.4f}  (q {q:.4f})")
    print(f"  largest |difference| {worst:.4f} (THEORY.md rounds to 0.001; Monte Carlo se at 2e6 draws about 0.0002-0.0003)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
