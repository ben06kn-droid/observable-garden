"""Rehearse 6.9's grading path on an in-sample split that stands in for the holdout
(`prereg/holdout-grading.md`). No holdout file is decrypted, opened or read.

The stand-in: the real in-sample CSVs (2005-2022), hash-checked against the fetch
manifest, are split at 2020-01-01. 2005-2019 plays in-sample and 2020-2022 plays the
holdout. A rehearsal manifest records the split files' hashes when they are written.
`grade_real.run_grading` then runs in its registered order, with only two substitutions,
both printed:
- the window is 2020-01-01..2022-12-31;
- the platform pin is this machine's.

S and G are both HEAD.

Also checked:
- the one-build features over 2005-2022 equal `build_etf_panel`'s, and how they differ
  from the pinned X;
- grading each submission over the full in-sample window reproduces the in-sample
  score the agent saw (`submitted_sharpe`).

    python -m experiments.rehearse_holdout_grading --out runs/holdout_grading_rehearsal
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from experiments import grade_real as gr

DIRS = ("runs/etf_control", "runs/etf_declared_class", "runs/etf_replay",
        "runs/etf_orientation")
SPLIT = dt.date(2020, 1, 1)
STANDIN_END = dt.date(2022, 12, 31)


def main(argv=None) -> int:
    from data.etf_loader import INSAMPLE_DIR, load_panel
    from environments.real_panel import build_etf_panel
    from experiments.collect_submissions import submissions_for
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L: list[str] = []

    def P(s=""):
        L.append(s)
        print(s, flush=True)
    head = subprocess.run(["git", "-C", str(gr.REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    P("REHEARSAL of the 6.9 grading path — an in-sample split stands in for the holdout")
    P("=" * 92)
    P(f"  HEAD {head[:12]} (stands in for both S and G); platform {gr.platform_now()}")
    P(f"  SUBSTITUTIONS: window {SPLIT}..{STANDIN_END} (registered 2023-01-01..2025-12-31); "
      f"platform pin {gr.platform_now()} (registered {gr.PINNED_PLATFORM})")
    P("  no holdout file is decrypted, opened or read")
    P("")

    # 1. the submissions, as step 1 of the sequence writes them
    subs = submissions_for(list(DIRS), 40)
    tmp = Path(tempfile.mkdtemp(prefix="og_rehearsal_"))
    subs_path = tmp / "submissions.json"
    subs_path.write_text(json.dumps(subs))
    subs_sha = gr.sha256_file(subs_path)
    P(f"1. submissions: {len(subs)} collected from {len(DIRS)} arms; sha256 {subs_sha[:16]}...")

    # 2. the real in-sample inputs against the fetch manifest
    manifest = json.loads(gr.MANIFEST.read_text())
    n = gr.require_manifest_hashes(INSAMPLE_DIR, "insample", manifest)
    P(f"2. the real in-sample CSVs: {n} files match data/etf_manifest.json")

    # 3. the split, and a rehearsal manifest of the split files
    ins, sho = tmp / "insample_part", tmp / "standin_holdout"
    ins.mkdir(), sho.mkdir()
    rman = {"derived": {}}
    for p in sorted(Path(INSAMPLE_DIR).glob("*.csv")):
        lines = p.read_text().splitlines(keepends=True)
        head_line, rows = lines[0], lines[1:]
        a_rows = [r for r in rows if dt.date.fromisoformat(r.split(",")[0]) < SPLIT]
        b_rows = [r for r in rows if dt.date.fromisoformat(r.split(",")[0]) >= SPLIT]
        (ins / p.name).write_text(head_line + "".join(a_rows))
        (sho / p.name).write_text(head_line + "".join(b_rows))
        rman["derived"][p.stem] = {"insample": {"sha256": gr.sha256_file(ins / p.name)},
                                   "holdout": {"sha256": gr.sha256_file(sho / p.name)}}
    rman_path = tmp / "rehearsal_manifest.json"
    rman_path.write_text(json.dumps(rman))
    P(f"3. split at {SPLIT}: {len(rman['derived'])} tickers; rehearsal manifest written")
    P("")

    # 4. the grading path itself
    P("4. grade_real.run_grading:")
    res = gr.run_grading(ins, sho, subs_path, subs_sha, head, head, rman_path,
                         tmp / "grades.json", window=(SPLIT, STANDIN_END),
                         expected_platform=gr.platform_now())
    P("")

    # 5. one build equals build_etf_panel on the real in-sample data; the pinned X
    panel = build_etf_panel()
    prices = {t: (v[0], np.asarray(v[1])) for t, v in load_panel(INSAMPLE_DIR).items()}
    dates, tickers, F, earn = gr.build_span(prices)
    T = len(dates)
    same_F = np.array_equal(F[gr.WARM:T - 2], panel.features, equal_nan=True)
    same_r = np.array_equal(np.nan_to_num(earn[gr.WARM:T - 2]), panel.returns)
    P(f"5. one build over 2005-2022 equals build_etf_panel(): features {same_F}, "
      f"returns {same_r}")
    try:
        from environments.planted_panel import pinned_features
        X = pinned_features(shape=panel.features.shape)
        diff = ~np.isclose(X, panel.features, rtol=0, atol=0, equal_nan=True)
        cols = sorted({int(k) for k in np.argwhere(diff)[:, 2]}) if diff.any() else []
        P(f"   against the pinned X (7.5): {int(diff.sum())} of {diff.size} entries differ"
          + (f", in feature columns {cols}" if cols else ""))
    except Exception as e:                                  # reported, not fatal
        P(f"   against the pinned X: not compared ({type(e).__name__}: {e})")

    # 6. grading over the full in-sample window reproduces what each agent saw
    full = gr.grade_span(subs, dates, F, earn, dates[gr.WARM + 2], dates[T - 1],
                         costs_bps=(5.0,))
    seen = {}
    for d in DIRS:
        for f in Path(gr.REPO / d).glob("cell_*.json"):
            x = json.loads(f.read_text())
            if x.get("submitted_support") and x.get("submitted_sharpe") is not None:
                seen[x["run_id"]] = float(x["submitted_sharpe"])
    diffs = [abs(r["net_sharpe_5bps"] - seen[r["name"]]) for r in full if r["name"] in seen]
    bad = sum(d > 1e-9 for d in diffs)
    P(f"6. full in-sample window, net at 5 bps, against each run's submitted_sharpe: "
      f"{len(diffs)} compared, max |diff| {max(diffs):.2e}, {bad} above 1e-9")

    # 7. what the stand-in grades look like (in-sample data, so printing them is harmless)
    g = res["grades"]
    for key in ("gross_sharpe", "net_sharpe_5bps", "net_sharpe_10bps"):
        v = np.array([r[key] for r in g])
        q = np.percentile(v, [25, 50, 75])
        P(f"7. stand-in {key:<17} n {len(v)}  q25 {q[0]:+.3f}  med {q[1]:+.3f}  "
          f"q75 {q[2]:+.3f}")
    P(f"   periods graded per submission: {sorted({r['n_periods'] for r in g})}; "
      f"first earned {g[0]['first_earned']}, last {g[0]['last_earned']}")
    (out / "rehearsal.txt").write_text("\n".join(L) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
