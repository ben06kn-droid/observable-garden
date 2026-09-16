"""The Gaussian limit model behind the note's Propositions 3-5, and every limit number in its tables.

Setting (THEORY.md P4-P5, the note's §2): under the familywise null and exchangeable scoring,
sqrt(T) times the K single-feature Sharpe ratios converges to Z ~ N(0, Omega) with Omega equicorrelated
at omega. An equal-weight size-m subset's limiting statistic is (sum of its z) / sqrt(m(1 + (m-1)omega)),
so a pair is g(x, y) = (x + y) / sqrt(2 + 2 omega).

Two nulls, both sampled here:

  F_C  the realized-menu null: the anchor's index is frozen at its value on the real data, and by
       exchangeability its rank in a replicate is uniform, so ONE F_C serves every anchor rule
       (the note's Proposition 4).
  F_P  the process null of a given rule: each replicate re-picks the anchor by that rule.

Naive type-I at level alpha is then P(M_P > q_{1-alpha}(M_C)), and the note also reports the Kolmogorov
distance sup|F_P - F_C|, which is the uniform p-value distortion of Lopez de Prado & Porcu eq. (12).

Usage: python -m experiments.limit_model [--draws N]
"""
from __future__ import annotations

import argparse

import numpy as np

ALPHA = 0.05
DRAWS = 2_000_000
CHUNK = 250_000
RANKS = (1, 2, 3, 5, 10, 20)
TAUS = (-np.inf, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0, np.inf)
GRID_KS = (10, 20, 40, 80)
GRID_OMEGAS = (0.0, 0.3)
DEPTHS = (2, 3, 4)


def draw_z(rng, n, K, omega):
    """Z ~ N(0, equicorrelated(omega)), via one common factor: no K x K matmul."""
    return np.sqrt(omega) * rng.standard_normal((n, 1)) + np.sqrt(1 - omega) * rng.standard_normal((n, K))


def pair(a, b, omega):
    return (a + b) / np.sqrt(2 + 2 * omega)


def realized_menu_max(Z, omega):
    """M_C: the anchor's index is frozen (index 0; any fixed index has the same law under exchangeability)."""
    best_single = Z.max(axis=1)
    best_pair = pair(Z[:, [0]], Z[:, 1:], omega).max(axis=1)
    return np.maximum(best_single, best_pair)


def process_max_by_rank(Z, omega):
    """M_P(k) for every rank k: the rank-k anchor's best pair is with the winner (rank 1 pairs with the
    runner-up), so the search submits max(Z_(1), g(Z_(k), Z_(1)))."""
    S = -np.sort(-Z, axis=1)
    top = S[:, 0]
    out = {1: np.maximum(top, pair(S[:, 0], S[:, 1], omega))}
    for k in range(2, Z.shape[1] + 1):
        out[k] = np.maximum(top, pair(S[:, k - 1], top, omega))
    return out


def process_max_gumbel(Z, omega, tau, rng):
    """M_P for GumbelAnchored(tau): each replicate picks its own anchor with probability proportional to
    exp(tau * z standardized). tau = +inf is the winner rule, -inf the loser rule."""
    S = -np.sort(-Z, axis=1)
    top = S[:, 0]
    if tau == np.inf:
        return np.maximum(top, pair(S[:, 0], S[:, 1], omega))
    if tau == -np.inf:
        return np.maximum(top, pair(S[:, -1], top, omega))
    spread = Z.std(axis=1, keepdims=True)
    zs = (Z - Z.mean(axis=1, keepdims=True)) / np.where(spread > 0, spread, 1.0)
    anchor = np.argmax(tau * zs + rng.gumbel(size=Z.shape), axis=1)
    z_a = np.take_along_axis(Z, anchor[:, None], axis=1)[:, 0]
    is_winner = z_a >= top
    partner = np.where(is_winner, S[:, 1], top)
    return np.maximum(top, pair(z_a, partner, omega))


def greedy_vs_lattice(Z, omega, depth):
    """P5: r_m = (sum of top m)/c_m. The lattice maximum over subsets of size <= depth is max_m r_m;
    greedy with early stopping takes the first local maximum of r_1..r_depth."""
    S = -np.sort(-Z, axis=1)[:, :depth]
    cum = np.cumsum(S, axis=1)
    r = np.column_stack([cum[:, m - 1] / np.sqrt(m * (1 + (m - 1) * omega)) for m in range(1, depth + 1)])
    lattice = r.max(axis=1)
    greedy = r[:, 0].copy()
    alive = np.ones(len(r), dtype=bool)
    for m in range(1, depth):
        improves = alive & (r[:, m] > greedy)
        greedy = np.where(improves, r[:, m], greedy)
        alive &= improves                      # stop as soon as a step fails to improve
    unimodal_break = (r[:, 1:] > r[:, :-1]).astype(int)
    not_unimodal = np.any(np.diff(unimodal_break, axis=1) > 0, axis=1) if depth > 2 else np.zeros(len(r), bool)
    return greedy, lattice, not_unimodal


def sample(K, omega, draws, seed, rng_gumbel=None, taus=(), depth=None):
    """One pass: the realized-menu null, the per-rank process nulls, optional per-tau nulls and P5 gaps."""
    rng = np.random.default_rng(seed)
    mc, by_rank, by_tau = [], {k: [] for k in range(1, K + 1)}, {t: [] for t in taus}
    gaps = {"short": 0, "strictly_below": 0, "not_unimodal": 0, "worst": 0.0, "n": 0}
    for start in range(0, draws, CHUNK):
        n = min(CHUNK, draws - start)
        mc.append(realized_menu_max(draw_z(rng, n, K, omega), omega))
        Z = draw_z(rng, n, K, omega)
        for k, v in process_max_by_rank(Z, omega).items():
            by_rank[k].append(v)
        for t in taus:
            by_tau[t].append(process_max_gumbel(Z, omega, t, rng_gumbel or rng))
        if depth is not None:
            greedy, lattice, not_uni = greedy_vs_lattice(Z, omega, depth)
            short = lattice - greedy > 1e-12
            gaps["short"] += int(short.sum())
            gaps["strictly_below"] += int((lattice > greedy + 1e-12).sum())
            gaps["not_unimodal"] += int(not_uni.sum())
            gaps["worst"] = max(gaps["worst"], float((lattice - greedy).max()))
            gaps.setdefault("shortfalls", []).append((lattice - greedy)[short])
            gaps["n"] += n
    return (np.concatenate(mc), {k: np.concatenate(v) for k, v in by_rank.items()},
            {t: np.concatenate(v) for t, v in by_tau.items()}, gaps)


def type1(M_P, q):
    return float(np.mean(M_P > q))


def kolmogorov(M_P, M_C):
    """sup|F_P - F_C|, on the pooled grid of both samples."""
    grid = np.quantile(np.concatenate([M_P, M_C]), np.linspace(0.001, 0.999, 999))
    F_P = np.searchsorted(np.sort(M_P), grid, side="right") / len(M_P)
    F_C = np.searchsorted(np.sort(M_C), grid, side="right") / len(M_C)
    return float(np.abs(F_P - F_C).max())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=DRAWS)
    args = parser.parse_args()
    d = args.draws
    se = np.sqrt(ALPHA * (1 - ALPHA) / d)
    print(f"Gaussian limit model, {d:,} draws per cell (Monte Carlo se on a 5% rate: {se:.4f})\n")

    # --- Proposition 4 and its corollaries: the rank curve at the note's reference cell -------------
    M_C, by_rank, by_tau, _ = sample(20, 0.3, d, seed=11, taus=TAUS)
    q = np.quantile(M_C, 1 - ALPHA)
    # One independently drawn rank per draw. Concatenating blocks of by_rank would not be a mixture:
    # every rank's array comes from the same Z, so the blocks are dependent.
    picks = np.random.default_rng(12).integers(1, 21, size=d)
    mixture = np.take_along_axis(np.column_stack([by_rank[k] for k in range(1, 21)]),
                                 (picks - 1)[:, None], axis=1)[:, 0]
    mix_rate = type1(mixture, q)
    print("Corollary 4.1 (random anchor is exactly calibrated), K=20, omega=0.3")
    print(f"  uniform mixture over ranks: type-I {mix_rate:.4f} +/- {np.sqrt(mix_rate * (1 - mix_rate) / d):.4f} "
          f"(target {ALPHA})\n")
    print("Table 2, rank-graded limit (K=20, omega=0.3)")
    print(f"  {'rank':>6} {'type-I':>8} {'sup|F_P-F_C|':>13}")
    for k in RANKS:
        print(f"  {k:>6} {type1(by_rank[k], q):>8.4f} {kolmogorov(by_rank[k], M_C):>13.4f}")

    print("\nTable 2, rule-graded limit (GumbelAnchored, K=20, omega=0.3)")
    print(f"  {'tau':>6} {'type-I':>8} {'sup|F_P-F_C|':>13}")
    for t in TAUS:
        label = "-inf" if t == -np.inf else ("+inf" if t == np.inf else f"{t:g}")
        print(f"  {label:>6} {type1(by_tau[t], q):>8.4f} {kolmogorov(by_tau[t], M_C):>13.4f}")

    # --- Proposition 5: size of the winner-anchored error across K and omega -----------------------
    print("\nTable 3, winner-anchored limit type-I and Kolmogorov distortion")
    print(f"  {'omega':>6} {'K':>4} {'type-I':>8} {'sup|F_P-F_C|':>13}")
    for omega in GRID_OMEGAS:
        for K in GRID_KS:
            M_C_g, by_rank_g, _, _ = sample(K, omega, d, seed=100 + K)
            q_g = np.quantile(M_C_g, 1 - ALPHA)
            print(f"  {omega:>6.1f} {K:>4} {type1(by_rank_g[1], q_g):>8.4f} "
                  f"{kolmogorov(by_rank_g[1], M_C_g):>13.4f}")

    # --- Proposition 7(b): greedy against the lattice maximum --------------------------------------
    print("\nP5 gap table (K=20, omega=0.3): greedy with early stopping vs the lattice maximum")
    print(f"  {'depth':>6} {'greedy below':>13} {'r not unimodal':>15} {'99.9th pct shortfall':>21}")
    for depth in DEPTHS:
        *_, gaps = sample(20, 0.3, d, seed=200 + depth, depth=depth)
        # A sample maximum is seed-dependent and grows with the draw count, so it cannot reproduce:
        # report a quantile of the shortfall among draws that fall short.
        short = np.concatenate(gaps["shortfalls"]) if gaps.get("shortfalls") else np.zeros(1)
        q999 = float(np.quantile(short, 0.999)) if short.size else 0.0
        print(f"  {depth:>6} {gaps['short'] / gaps['n']:>12.4%} {gaps['not_unimodal'] / gaps['n']:>15.4%} "
              f"{q999:>21.4f}")


if __name__ == "__main__":
    main()
