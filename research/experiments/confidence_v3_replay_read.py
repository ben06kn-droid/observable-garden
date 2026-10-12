"""V3 for the replay tier's P_5 — a declared secondary analysis on data already read.

`prereg/confidence-output.md`, "Replay-tier V3" (LIVE 2026-10-05). **SECONDARY, ON
DATA ALREADY READ.** The V2 read (`afdcb53`) printed V3 for the class tier's P_5. This
prints the same table for the **replay tier's** P_5 (`conf_replay`), on the same file,
with the same bins (deciles), outcomes (realized holdout Sharpe > 0, holdout population
Sharpe > 0), subsets (all submissions, and those certified by the class tier,
`p_class < 0.05`) and Brier score, per level. Descriptive, with no rule.

It refuses any file but `0edab26`'s (SHA-256), through the pinned V2 reader's own
loader, which checks the block, levels and searchers.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

from estimator.metrics import wilson_ci
from experiments.confidence_cell_read import LEVELS, by_level, load

REGISTERED_SHA256 = "d762314a500b7b62e6da21be79e45704c646b4432c8cba29aec9e676c6537357"
CERT_ALPHA = 0.05
FILE = "runs/confidence_cell/draws.jsonl"


def check(path: Path, sha256: str | None = REGISTERED_SHA256) -> None:
    if sha256 is not None and hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise SystemExit(f"{path}: SHA-256 is not the registered {sha256}; refused")


def read(recs, key: str = "conf_replay") -> str:
    L = ["V3 — reliability of P_5, TRIGGER-REPLAY tier — READ ONCE",
         "SECONDARY, ON DATA ALREADY READ (the V2 read, afdcb53, printed the class tier's;",
         "this quantity was not computed in that read). prereg/confidence-output.md.",
         "=" * 78]
    A = L.append
    edges = np.linspace(0, 1, 11)
    for beta in LEVELS:
        subs = [s for lv in by_level(recs, beta) for s in lv["searchers"]
                if s.get(key) is not None]
        A(f"   level {beta:.1f}: {len(subs)} submissions with a replay-tier P_5")
        for label, pick in (("all", subs),
                            ("certified", [s for s in subs if s["p_class"] < CERT_ALPHA])):
            for outcome, f in (("realized holdout > 0", lambda s: s["holdout_realized"] > 0),
                               ("holdout population > 0", lambda s: s["truth"]["holdout"] > 0)):
                P = np.array([s[key]["P_H"] for s in pick])
                y = np.array([f(s) for s in pick], dtype=float)
                if not len(P):
                    A(f"     {label:<10}{outcome:<26} none")
                    continue
                A(f"     {label:<10}{outcome:<26} n {len(P)}, Brier {np.mean((P - y) ** 2):.4f}")
                for i in range(10):
                    m = (P >= edges[i]) & ((P < edges[i + 1]) if i < 9 else (P <= 1))
                    if not m.any():
                        continue
                    k, n = int(y[m].sum()), int(m.sum())
                    lo, hi = wilson_ci(k, n)
                    A(f"       P_5 in [{edges[i]:.1f}, {edges[i + 1]:.1f}{')' if i < 9 else ']'}:"
                      f" mean P {P[m].mean():.3f}, observed {k}/{n} = {k / n:.3f} "
                      f"[{lo:.3f}, {hi:.3f}]")
        A("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=FILE)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    path = Path(a.file)
    check(path)
    text = read(load(path))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
