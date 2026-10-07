"""The 6.5 holdout grading reader, on synthetic grades and re-priced records."""
import json

import numpy as np
import pytest

from experiments import holdout_grading_read as hr
from quixote.confidence import confidence

ARMS = ("control", "declared-class gate", "replay gate", "orientation")


def _make(tmp_path, n=8, T=300, drift=0.0, L_shift=0.0, mu_shift=0.0, seed=0):
    rng = np.random.default_rng(seed)
    grades, dates = [], [f"2023-01-{1 + i % 28:02d}" for i in range(T)]
    rep = tmp_path / "repriced"
    runs = tmp_path / "runs"
    rep.mkdir(parents=True), runs.mkdir(parents=True)
    for i in range(n):
        name = f"cell_etf_{i}_x_{i}"
        g = drift / np.sqrt(252) * 0.01 + rng.normal(0, 0.01, T)
        n5, n10 = g - 0.0001, g - 0.0002
        sr = lambda x: float(x.mean() / x.std(ddof=1) * np.sqrt(252))
        grades.append({"name": name, "gross_sharpe": sr(g), "net_sharpe_5bps": sr(n5),
                       "net_sharpe_10bps": sr(n10), "n_periods": T,
                       "stream": {"gross": g.tolist(), "net_5bps": n5.tolist(),
                                  "net_10bps": n10.tolist()}})
        M = rng.normal(0.8, 0.15, 1000)
        S = 0.4 + L_shift
        conf = confidence(S, M, tier="declared class")
        cp = {"submitted_score": S, "null_max_draws": M.tolist(), "null_max_mean": float(M.mean()),
              "confidence": conf, "p_upper": 0.9, "status": "FAIL", "B": 1000}
        verdict = ({"status": "FAIL", "confidence": confidence(S, M - 0.1, tier="trigger replay")}
                   if i % 2 else None)
        (rep / f"{name}.json").write_text(json.dumps(
            {"run_id": name, "class_p": cp, "verdict": verdict,
             "superseded": {"class_p": {"status": "FAIL", "B": 200},
                            "verdict": {"status": "FAIL"} if verdict else None}}))
        (runs / f"{name}.json").write_text(json.dumps(
            {"run_id": name, "arm": ARMS[i % 4], "submitted_support": [[1 if i else 3, 1.0]],
             "prediction": {"mean": 0.3 + mu_shift + 0.01 * i, "sd": 0.2} if i else None}))
    gp = tmp_path / "grades.json"
    gp.write_text(json.dumps({"grades": grades, "graded_dates": dates}))
    return gp, rep, runs


def _read(tmp_path, **kw):
    gp, rep, runs = _make(tmp_path, **kw)
    g, rows = hr.load(gp, rep, [runs])
    return hr.read(g, rows, B=400)


def test_it_prints_the_five_readouts_in_order_and_nothing_else(tmp_path):
    text = _read(tmp_path)
    heads = [ln for ln in text.splitlines() if not ln.startswith(" ")]
    assert heads == ["(1) REGISTERED BY 6.5",
                     "(2) H1 — THE GATE'S LOWER BOUNDS AGAINST REALIZED",
                     "(3) H2 — THE AGENTS' STATED EXPECTATIONS AGAINST REALIZED",
                     "(4) DESCRIPTIVE",
                     "(5) RELATIVE READOUTS — DESCRIPTIVE, NO RULE"]
    assert "no PASS" in text and "exact from the stored M_b" in text


def test_h1_fails_low_when_the_bounds_sit_far_above_realized_and_holds_otherwise(tmp_path):
    hi = _read(tmp_path / "a", L_shift=3.0)      # L_0.90 far above any realized Sharpe
    assert "FAILS LOW" in hi
    lo = _read(tmp_path / "b", L_shift=-3.0)
    assert "holds: not shown to overstate on this holdout" in lo.split("(3)")[0]


def test_h2_fails_high_when_the_stated_means_sit_far_above_realized(tmp_path):
    assert "FAILS HIGH" in _read(tmp_path / "a", mu_shift=3.0)
    assert "FAILS HIGH" not in _read(tmp_path / "b", mu_shift=-3.0)


def test_the_joint_bootstrap_shares_its_days_and_matches_the_plain_sharpe_at_identity():
    X = np.random.default_rng(1).normal(0, 0.01, (3, 200))
    C = np.ones((200, 1))                        # every day once: the realized sample
    assert np.allclose(hr.boot_sharpes(X, C)[:, 0], hr.sharpe(X))
    C = hr.bootstrap_counts(200, B=50, seed=5)
    assert np.all(C.sum(axis=0) == 200)          # each replicate is 200 days
    assert np.array_equal(C, hr.bootstrap_counts(200, B=50, seed=5))     # seeded
    assert hr.BLOCK_LENGTH == 9 and hr.B_BOOT == 10_000 and hr.SEED_BOOT == 690_000


def test_crps_helpers_agree_with_their_definitions():
    rng = np.random.default_rng(2)
    s = rng.normal(0.3, 0.5, 4001)
    brute = np.abs(s - 1.0).mean() - 0.5 * np.abs(s[:, None] - s[None, :]).mean()
    assert hr.crps_sample(s, 1.0) == pytest.approx(brute, rel=1e-9)
    assert hr.crps_normal(0.3, 0.5, 1.0) == pytest.approx(hr.crps_sample(s, 1.0), abs=0.01)
    assert hr.crps_normal(0.3, 0.0, 1.0) == pytest.approx(0.7)


def test_a_missing_record_refuses(tmp_path):
    gp, rep, runs = _make(tmp_path)
    next(rep.glob("*.json")).unlink()
    with pytest.raises(SystemExit, match="missing"):
        hr.load(gp, rep, [runs])


def test_relative_readouts_match_scipy_and_their_definitions():
    from scipy.stats import spearmanr
    rng = np.random.default_rng(3)
    n, B = 20, 300
    score = rng.normal(size=n)
    real = 0.5 * score + rng.normal(size=n)
    boot = real[:, None] + 0.3 * rng.normal(size=(n, B))
    mu = score + rng.normal(size=n)
    mu[4] = np.nan
    names = [f"r{i:02d}" for i in range(n)]
    out = hr.relative_readouts(score, mu, names, real, boot)
    assert out["R-a"][0] == pytest.approx(spearmanr(score, real).statistic, abs=1e-12)
    has = ~np.isnan(mu)
    assert out["R-b"][0] == pytest.approx(spearmanr(mu[has], real[has]).statistic, abs=1e-12)
    top, bot = hr.halves(score, names)
    assert top.sum() == bot.sum() == 10 and not (top & bot).any()
    assert score[top].min() >= score[bot].max()
    assert out["R-c"][0] == pytest.approx(real[top].mean() - real[bot].mean(), abs=1e-12)
    se = np.std([spearmanr(score, boot[:, b]).statistic for b in range(B)], ddof=1)
    assert out["R-a"][1] == pytest.approx(se, abs=1e-12)
    tmu, bmu = hr.mu_halves(mu)
    assert out["R-d"][0] == pytest.approx(real[tmu].mean() - real[bmu].mean(), abs=1e-12)
    assert out["n"] == {"R-a": 20, "R-b": 19, "R-c": 10, "R-d": (9, 10)}


def test_halves_break_ties_by_name():
    # three tied at 1.0 compete for two top-half places: "a" and "b" win on name
    top, bot = hr.halves(np.array([1.0, 1.0, 1.0, 0.0]), ["c", "b", "a", "d"])
    assert list(top) == [False, True, True, False]
    assert list(bot) == [True, False, False, True]


def test_r_d_splits_at_the_median_with_ties_to_the_bottom():
    top, bot = hr.mu_halves(np.array([0.1, 0.2, 0.2, 0.2, 0.5, np.nan]))
    assert list(top) == [False, False, False, False, True, False]     # median 0.2 -> bottom
    assert list(bot) == [True, True, True, True, False, False]


def test_section_5_prints_r_c_r_d_r_b_r_a_with_the_stand_in_detectable_size(tmp_path):
    text = _read(tmp_path)
    sec = text.split("(5) RELATIVE READOUTS — DESCRIPTIVE, NO RULE")[1].strip().splitlines()
    assert [ln.split()[0] for ln in sec] == ["R-c", "R-d", "R-b", "R-a"]
    for ln, k in zip(sec, ("R-c", "R-d", "R-b", "R-a")):
        assert f"stand-in detectable {2.486 * hr.STANDIN_SE[k]:.3f}" in ln
        assert " SE " in ln and "[" in ln
    assert "near-duplicate" in sec[3] and all("near-duplicate" not in ln for ln in sec[:3])
