#!/bin/sh
# Sample outputs for the viewer, made by the package's own commands on small inputs (seconds, no heavy fit):
#   result.json                      quixote audit --json on examples/logs/scripted_session.json (B 500, seed 0): FAIL
#   result_planted.json              the same on examples/logs/planted_session.json and tiny_panel_planted.npz: PASS
#   sancho_out/sancho.json           quixote sancho, a tailored config (first scored row 300, 5 rounds: the recipe of
#                                    tests/test_sancho_model.py) on a seeded synthetic panel of 700 rows x 6 assets
#   sancho_registered_out/sancho.json quixote sancho with the registered config on a seeded synthetic panel of 1,200
#                                    rows x 6 assets (config first_scored_row 756; this run scored from 763)
# The panels are random numbers (synthetic_*.npz): the figures mean nothing; they exercise the viewer.
#   sh scripts/make_viewer_fixtures.sh [PYTHON]      (run from app/web; PYTHON needs numpy, lightgbm 4.7.0)
set -eu
PY=${1:-python3}
ROOT=$(cd ../.. && pwd)
OUT=scripts/fixtures/viewer
mkdir -p "$OUT"
cd "$OUT"
PYTHONPATH="$ROOT" "$PY" - <<'EOF'
import json, numpy as np
from sancho import config as C
def panel(path, T, M=6, K=5, seed=3):
    rng = np.random.default_rng(seed)
    np.savez(path, returns=0.01 * rng.standard_normal((T, M)), features=rng.standard_normal((T, M, K)),
             periods_per_year=252, feature_names=np.array([f"f{k}" for k in range(K)]))
panel("synthetic_700.npz", 700)
panel("synthetic_1200.npz", 1200)
v = C.load().values
v["first_scored_row"], v["trees"]["rounds"] = 300, 5
open("tailored_config.json", "w").write(json.dumps(v))
EOF
PYTHONPATH="$ROOT" "$PY" -m quixote.cli sancho --panel synthetic_700.npz --config tailored_config.json --out sancho_out
PYTHONPATH="$ROOT" "$PY" -m quixote.cli sancho --panel synthetic_1200.npz --out sancho_registered_out
# the audit's exit code is its verdict (FAIL is not 0), so it is not an error here
PYTHONPATH="$ROOT" "$PY" -m quixote.cli audit "$ROOT/examples/logs/scripted_session.json" --panel "$ROOT/examples/data/tiny_panel.npz" \
  --class "$ROOT/examples/class.json" --B 500 --seed 0 --json > result.json || true
PYTHONPATH="$ROOT" "$PY" -m quixote.cli audit "$ROOT/examples/logs/planted_session.json" --panel "$ROOT/examples/data/tiny_panel_planted.npz" \
  --class "$ROOT/examples/class.json" --B 500 --seed 0 --json > result_planted.json || true
rm -f synthetic_700.npz synthetic_1200.npz
ls -la . sancho_out sancho_registered_out
