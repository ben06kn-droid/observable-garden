"""Bundled example transcripts: moving-average crossover searches on
simulated daily prices, the Sullivan-Timmermann-White (1999) setup on data
where the right verdict is known by construction. Shipped as fixed
transcripts in garden/data (data seed 0), so the quickstart is deterministic;
`python -m garden.examples` regenerates them from build().

Rules are long-short or long-only crossovers with no band filter. Band
filters on close windows produce rules that are almost never in the market,
whose bootstrap Sharpes are heavy-tailed enough to dominate the null
maximum (SCOPE.md, Sparse strategies); that pathology would drive the verdicts instead
of search breadth."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from estimator.bootstrap import sharpe
from garden.transcript import Transcript, load_npz

PERIODS_PER_YEAR = 252
DAILY_VOL = 0.01
WARMUP = 200
MENU_SEED = 20_000
EXAMPLE_SEED = 0
DATA_DIR = Path(__file__).parent / "data"

EXAMPLES = {
    "null_grid": "362 MA-crossover rules, 10 years of a random walk, no rule has an edge. Expected: FAIL.",
    "real_edge": "32 MA-crossover rules, 10 years of prices that drift with one rule's signal "
                 "(true Sharpe 1.5). Expected: PASS.",
    "overwide": "10,000 MA-crossover rules, 4 years of prices with a modest edge in one rule "
                "(true Sharpe 0.75). Expected: INADMISSIBLE.",
}


def _grid(fasts, slows):
    return [(f, s, long_only) for f in fasts for s in slows if f < s for long_only in (False, True)]


def _menu(name: str) -> tuple[int, list, tuple[int, int] | None, float]:
    if name == "null_grid":
        rules = _grid((1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50),
                      (10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 175, 200))
        return 2520, rules, None, 0.0
    if name == "real_edge":
        return 2520, _grid((5, 10, 20, 30), (50, 100, 150, 200)), (10, 100), 1.5
    if name == "overwide":
        true_rule = (20, 100, False)
        full = [r for r in _grid(range(1, 51), range(2, 201)) if r != true_rule]
        # Thinned with a fixed seed that never sees returns, so the menu stays data-oblivious.
        keep = np.random.default_rng(MENU_SEED).choice(len(full), 9_999, replace=False)
        return 1000, [true_rule] + [full[i] for i in np.sort(keep)], (20, 100), 0.75
    raise ValueError(f"unknown example {name!r}; choose from {sorted(EXAMPLES)}")


def _simulate(n: int, rng: np.random.Generator, true_rule, true_sharpe: float) -> np.ndarray:
    """Daily log returns. With a true rule, each day's drift takes the sign of that
    rule's crossover signal at the previous close."""
    eps = rng.normal(0.0, DAILY_VOL, n)
    if true_rule is None:
        return eps
    fast, slow = true_rule
    mu = true_sharpe / np.sqrt(PERIODS_PER_YEAR) * DAILY_VOL
    r = np.empty(n)
    log_price = np.empty(n)
    level = 0.0
    for t in range(n):
        drift = 0.0
        if t >= slow:
            drift = mu * np.sign(log_price[t - fast:t].mean() - log_price[t - slow:t].mean())
        r[t] = drift + eps[t]
        level += r[t]
        log_price[t] = level
    return r


def _rule_returns(r: np.ndarray, rules: list) -> np.ndarray:
    """(len(r) - WARMUP, n_rules): each rule's daily return, holding the position its
    moving averages signaled at the previous close."""
    n = len(r)
    cum = np.concatenate([[0.0], np.cumsum(np.cumsum(r))])
    ma = {}
    for w in {w for f, s, _ in rules for w in (f, s)}:
        m = np.full(n, np.nan)
        m[w - 1:] = (cum[w:] - cum[:-w]) / w
        ma[w] = m
    out = np.empty((n - WARMUP, len(rules)))
    for i, (fast, slow, long_only) in enumerate(rules):
        pos = np.sign(ma[fast][WARMUP - 1:-1] - ma[slow][WARMUP - 1:-1])
        if long_only:
            pos = np.maximum(pos, 0.0)
        out[:, i] = pos * r[WARMUP:]
    return out


def build(name: str, seed: int = 0) -> Transcript:
    n_periods, rules, true_rule, true_sharpe = _menu(name)
    r = _simulate(n_periods + WARMUP, np.random.default_rng(seed), true_rule, true_sharpe)
    R = _rule_returns(r, rules)
    ids = [f"ma_{f}_{s}_{'long' if lo else 'ls'}" for f, s, lo in rules]
    best = int(np.argmax(sharpe(R, axis=0)))
    return Transcript(R, ids, ids[best], menu_kind="oblivious", periods_per_year=PERIODS_PER_YEAR)


def path(name: str) -> Path:
    if name not in EXAMPLES:
        raise ValueError(f"unknown example {name!r}; choose from {sorted(EXAMPLES)}")
    return DATA_DIR / f"{name}.npz"


def load(name: str) -> Transcript:
    return load_npz(path(name))


def write_bundled() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for name in EXAMPLES:
        build(name, seed=EXAMPLE_SEED).save(path(name))


if __name__ == "__main__":
    write_bundled()
