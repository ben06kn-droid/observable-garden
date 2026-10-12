"""A run can be re-graded from its manifest row alone.

`runs/<batch>/runs.csv` carries `submitted_features` and `submitted_signs` so a
run can be re-graded offline -- net of trading costs, or under a shifted
out-of-sample panel -- without unpacking `raw.tar.gz`. That is worth nothing
unless the reconstruction is exact, so this pins it end to end: rebuild the
weight vector from the manifest, regenerate the panel from the run's own DGP
seed, recompute the gross out-of-sample Sharpe, and require it to equal the
number the harness stored at submit time.

This is a test rather than a check inside an analysis script because every
re-grade built on the manifest inherits it. If the seed derivation, the sigma
round-trip through config.json, or the weight reconstruction ever drifts, the
re-grades would still produce plausible numbers and quietly be wrong.

One run per batch, not all 661: the property is about the reconstruction path,
and each `generate` draws a (T, M, K) panel.
"""
import csv
import json
import math
import pathlib

import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
pytest.importorskip(
    "claude_agent_sdk",
    reason="searchers.llm_agent imports the agent SDK at module level. Agent runs\ngo through the seat on the laptop and never on EC2, so the SDK is absent there\nand these tests skip rather than failing collection for the whole suite.")

from searchers.llm_agent import spec_from

# CONFIGS and dgp_seeds are the authoritative run configuration and seed
# derivation, so they are imported rather than restated -- reimplementing them
# here would duplicate the thing under test. They live in experiments.e_agent,
# which imports claude_agent_sdk at module level, so this module cannot be
# collected on a machine without the SDK (an EC2 box running scripted work, for
# instance). Moving them would shift the harness fingerprint, since e_agent.py
# is inside code_state.CODE_PATHS. Skipping is the cheaper honest answer: the
# re-grades this gates are local work, and run where the SDK is installed.
from experiments.e_agent import CONFIGS, dgp_seeds  # noqa: E402

RUNS = pathlib.Path(__file__).resolve().parent.parent / "runs"
# s0 (sigma pinned at 1) and both s3 batches (sigma solved for, amendment 9),
# so the sigma round-trip is covered in both regimes and across two models.
BATCHES = ("b1-baseline", "b4-s3-recal", "b5-opus")


def _rows(batch: str) -> list[dict]:
    p = RUNS / batch / "runs.csv"
    if not p.exists():
        pytest.skip(f"no manifest at {p}; run experiments.build_manifest")
    with p.open(newline="") as fh:
        rd = csv.reader(fh)
        fields = next(rd)
        return [{k: json.loads(v) for k, v in zip(fields, row)} for row in rd]


def _a_graded_run(batch: str) -> dict:
    """The first run in the batch that submitted and was graded. Deterministic:
    the manifest is committed and ordered by seed."""
    for r in _rows(batch):
        if r["graded"] and r["submitted_features"] and r["oos"] is not None:
            return r
    pytest.skip(f"{batch} holds no graded run carrying a submission")


def _config_for(r: dict) -> DGPConfig:
    """Exactly what experiments/e_agent.py built for this run, with sigma taken
    from the manifest rather than recomputed: amendment 9 solves sigma from the
    oracle target, and the solved value is what the run actually used."""
    cfg = CONFIGS[r["config"]]
    return DGPConfig(M=cfg["M"], T=cfg["T"], T_oos=cfg["T_oos"], K=cfg["K"],
                     s=cfg["s"], rho=0.0, sigma=r["sigma"],
                     seed=int(dgp_seeds()[r["seed_index"]]))


@pytest.mark.parametrize("batch", BATCHES)
def test_submitted_spec_agrees_with_its_structured_form(batch):
    """`submitted_spec` is "<column>:<name>" as the verdict recorded it. The name
    must be what `spec_from` builds from the features and signs stored beside it,
    or the two columns describe different specifications."""
    r = _a_graded_run(batch)
    spec = spec_from(r["submitted_features"], r["submitted_signs"],
                     CONFIGS[r["config"]]["K"])
    assert r["submitted_spec"].split(":", 1)[1] == spec.name


@pytest.mark.parametrize("batch", BATCHES)
def test_gross_oos_recomputes_from_the_seed_and_the_spec(batch):
    """The gate for every offline re-grade.

    Reproduces `Sandbox.oos_sharpe_for_grading`: the position path is
    `x_oos @ weights`, the portfolio return is its cross-sectional mean against
    `r_oos`, and the Sharpe is annualized by `periods_per_year`."""
    r = _a_graded_run(batch)
    dgp = _config_for(r)
    data = generate(dgp)

    weights = spec_from(r["submitted_features"], r["submitted_signs"], dgp.K).weights
    signal = data.x_oos @ weights
    R = (signal * data.r_oos).mean(axis=1)
    recomputed = float(R.mean() / R.std(ddof=1) * math.sqrt(dgp.periods_per_year))

    assert recomputed == pytest.approx(r["oos"], rel=1e-9, abs=1e-12), (
        f"{r['run_id']}: re-grade {recomputed} != stored {r['oos']}")


@pytest.mark.parametrize("batch", BATCHES)
def test_turnover_is_computable_from_the_same_reconstruction(batch):
    """What 6.2 needs on top of the gross path: a position series it can charge
    a cost against. Positions are bounded and finite, and turnover is the mean
    absolute change across assets, so a cost model is a subtraction away."""
    r = _a_graded_run(batch)
    dgp = _config_for(r)
    data = generate(dgp)

    weights = spec_from(r["submitted_features"], r["submitted_signs"], dgp.K).weights
    signal = data.x_oos @ weights
    turnover = np.abs(np.diff(signal, axis=0)).mean(axis=1)

    assert signal.shape == (dgp.T_oos, dgp.M)
    assert turnover.shape == (dgp.T_oos - 1,)
    assert np.all(np.isfinite(turnover))
    assert turnover.mean() > 0
