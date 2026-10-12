"""Reader for the recency planted validation (`prereg/recency-weight-planted.md`, 07fa892;
amendments e48113e and a2fc19f). Committed and tested on made-up rows only before any panel
is drawn. Reads once, in the plan's order (section 4, then amendment 1):

  1-2. size, fixed centring: the stream (N20, N40) and the class (N20, N40), at both levels;
       a rate FAILS iff the lower 95% Wilson end of its certification rate exceeds the level;
  3-4. the superseded centring beside it: its rates, and the paired difference superseded
       - fixed (95% paired bootstrap interval, B 10,000, seed 705999), expected above 0;
  5.   power: paired weighted - unweighted at the 96% level for E20 (expected > 0), D20 and
       C20 (expected < 0); the 90% level's differences reported beside;
  6.   NV40: the weighted rate does not fail at either level (an expectation); the
       unweighted rate beside it;
  7.   NA40: no expectation; both branches; the unweighted rate and the registered and
       last-n_eff block lengths beside it.

    python -m experiments.read_recency_planted --dir runs/recency_planted/<date>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

LEVELS = {"96%": {"stream": 0.04, "class": 0.01}, "90%": {"stream": 0.08, "class": 0.02}}
B_PAIRED, PAIRED_SEED = 10_000, 705999
N_REGISTERED = {"N20": 1000, "N40": 1000, "C20": 400, "D20": 400, "E20": 400, "NV40": 1000, "NA40": 1000}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


def rate_line(label: str, flags: np.ndarray, level: float | None = None) -> tuple[str, dict]:
    k, n = int(flags.sum()), len(flags)
    lo, hi = wilson(k, n)
    fails = bool(lo > level) if level is not None else None
    txt = f"   {label:<44} {k:4d}/{n:<4d} = {k / max(n, 1):.3f}  [{lo:.3f}, {hi:.3f}]"
    if level is not None:
        txt += f"  -> {'FAILS' if fails else 'does not fail'} (level {level})"
    return txt, {"k": k, "n": n, "rate": k / max(n, 1), "wilson": [lo, hi], "fails": fails}


def paired(a: np.ndarray, b: np.ndarray, rng) -> tuple[float, float, float]:
    d = a.astype(float) - b.astype(float)
    idx = rng.integers(0, len(d), size=(B_PAIRED, len(d)))
    lo, hi = np.quantile(d[idx].mean(axis=1), [0.025, 0.975])
    return float(d.mean()), float(lo), float(hi)


def read(rows: list[dict]) -> tuple[str, dict]:
    by = {}
    for r in rows:
        by.setdefault(r["arm"], []).append(r)
    for arm in by:
        by[arm].sort(key=lambda r: r["seed"])
    L = ["RECENCY-WEIGHTED CERTIFICATE ON PLANTED PANELS (plan 07fa892; amendments e48113e, a2fc19f)", "=" * 92]
    out = {"n": {a: len(v) for a, v in by.items()}}
    short = [a for a, n in N_REGISTERED.items() if len(by.get(a, [])) != n]
    if short:
        L.append(f"arms with other than the registered n: {short}: not read. STOP and ask.")
        return "\n".join(L), {"stopped": short}
    cert = lambda arm, tier, test, lvl: np.array([r[tier][test]["p"] < LEVELS[lvl][tier] for r in by[arm]])
    rng = np.random.default_rng(PAIRED_SEED)
    # 1-4. size
    L.append("SIZE (null arms). A rate fails iff its lower 95% Wilson end exceeds the level.")
    for tier in ("stream", "class"):
        for arm in ("N20", "N40"):
            for lvl in ("96%", "90%"):
                lev = LEVELS[lvl][tier]
                t, o = rate_line(f"{tier} {arm} weighted, fixed centring, {lvl} level", cert(arm, tier, "weighted" if tier == "stream" else "unweighted", lvl), lev)
                L.append(t)
                out[f"size {tier} {arm} fixed {lvl}"] = o
                sup = "weighted_superseded"
                t, o = rate_line(f"{tier} {arm} superseded centring (kept beside), {lvl}", cert(arm, tier, sup, lvl), lev)
                L.append(t)
                out[f"size {tier} {arm} superseded {lvl}"] = o
                d = paired(cert(arm, tier, sup, lvl), cert(arm, tier, "weighted" if tier == "stream" else "unweighted", lvl), rng)
                held = bool(d[1] > 0)
                L.append(f"      superseded - fixed {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}] -> "
                         f"{'above 0, as expected' if held else 'not above 0'}")
                out[f"superseded-fixed {tier} {arm} {lvl}"] = {"diff": d, "above_zero": held}
                if tier == "stream":
                    t, o = rate_line(f"stream {arm} unweighted (current), {lvl}", cert(arm, "stream", "unweighted", lvl), lev)
                    L.append(t)
                    out[f"size stream {arm} unweighted {lvl}"] = o
    # 5. power
    L.append("")
    L.append("POWER (edge arms, stream): paired weighted - unweighted certification rate")
    want = {"E20": ("emerging", +1), "D20": ("decaying", -1), "C20": ("constant, the stated cost", -1)}
    for arm, (name, sign) in want.items():
        for lvl in ("96%", "90%"):
            wv, uv = cert(arm, "stream", "weighted", lvl), cert(arm, "stream", "unweighted", lvl)
            d = paired(wv, uv, rng)
            line = (f"   {arm} {name}, {lvl}: weighted {wv.mean():.3f}, unweighted {uv.mean():.3f}; "
                    f"diff {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}]")
            if lvl == "96%":
                held = bool(d[1] > 0 if sign > 0 else d[2] < 0)
                line += f" -> expectation ({'>' if sign > 0 else '<'} 0) {'HOLDS' if held else 'DOES NOT HOLD'}"
                out[f"power {arm}"] = {"diff": d, "holds": held}
            L.append(line)
    # 6-7. non-stationary nulls
    L.append("")
    L.append("NON-STATIONARY NULLS (stream, 40 years)")
    for arm in ("NV40", "NA40"):
        for lvl in ("96%", "90%"):
            lev = LEVELS[lvl]["stream"]
            t, o = rate_line(f"{arm} weighted, fixed centring, {lvl}", cert(arm, "stream", "weighted", lvl), lev)
            L.append(t)
            out[f"{arm} weighted {lvl}"] = o
            t, o2 = rate_line(f"{arm} unweighted (beside), {lvl}", cert(arm, "stream", "unweighted", lvl), lev)
            L.append(t)
            out[f"{arm} unweighted {lvl}"] = o2
        bl = np.array([r["block_length"] for r in by[arm]])
        bt = np.array([r["block_length_last_neff"] for r in by[arm]])
        L.append(f"   {arm} block length: registered rule median {np.median(bl):.0f} [{bl.min()}, {bl.max()}]; "
                 f"last n_eff rows median {np.median(bt):.0f} [{bt.min()}, {bt.max()}]")
        failed = any(out[f"{arm} weighted {lvl}"]["fails"] for lvl in ("96%", "90%"))
        if arm == "NV40":
            L.append(f"   NV40 expectation (does not fail at either level): {'DOES NOT HOLD' if failed else 'HOLDS'}")
        else:
            L.append("   NA40 (no expectation): " + (
                "the weighted rate FAILS: the weighted reads' block-length rule is reopened before any real registration"
                if failed else "the weighted rate does not fail: its size holds under this dependence shift on these panels"))
        out[f"{arm} weighted fails"] = failed
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    d = Path(a.dir)
    prov = json.loads((d / "provenance.json").read_text())
    if prov.get("dry_run") or prov.get("smoke") or prov.get("platform") != "Linux x86_64":
        raise SystemExit("not a box run of the registered task list; not read")
    if (d / "read.txt").exists():
        raise SystemExit("already read")
    rows = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines() if x.strip()]
    text, out = read(rows)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1, default=float))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
