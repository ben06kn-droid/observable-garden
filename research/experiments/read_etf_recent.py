"""Reader for the ETF recent panel's in-sample read (`prereg/etf-recent-panel.md`). Tested on
made-up results only. Renders once, in the registered order: the repeat, test 1 (Sancho
d = 1), test 2 (Sancho d = 0, NOT IMPLEMENTABLE), test 3 (the class). For each, the W2
certificate at both levels with its branch sentence and the weighted L90, then the unweighted
statistic labelled "unweighted, descriptive, not the certificate"; for the streams, the
performance line and the 10 bps line; for the class, the weighted best member AND the
unweighted best member beside it (the B1 reader left the latter out; this one does not).

    python -m experiments.read_etf_recent --dir runs/etf_recent/<date>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.read_french_long import LIMITS, branch

PANEL_LIMITS = ("item 3 of section b (ticker, merger or structure changes) NOT verified; the list of 40 "
                "named in 2026 from survivors; costs an assumption")


def render(key: str, t: dict) -> list[str]:
    w, u = t["weighted_W2"], t["unweighted"]
    L = [f"{key}: {t['test']}",
         f"   rows {t['n_rows']}; B {t['B']}, seed {t['seed']}, block length {t['block_length']}"
         + (f" (last n_eff rows: {t['block_length_last_neff']})" if "block_length_last_neff" in t else ""),
         f"   recency-weighted (W2, h 1,260): net Sharpe {w['S']:.3f}; p {w['p']:.4f} "
         f"(96% level iff p < {t['alphas']['96%']}; 90% level iff p < {t['alphas']['90%']}); weighted L90 {w['L90']:+.3f}"]
    if "best_member" in w:
        L.append(f"   best member (weighted): {', '.join(w['best_member']['features'])}")
    for lvl in ("96%", "90%"):
        L.append(f"   -> {lvl} level: {branch(t, lvl)}")
    L.append(f"   [{u['label']}] net Sharpe {u['S']:.3f}; p {u['p']:.4f}; L90 {u['L90']:+.3f}")
    if "best_member" in u:
        L.append(f"   [{u['label']}] best member (unweighted): {', '.join(u['best_member'])}")
    if "cost_10bps_beside" in t:
        c = t["cost_10bps_beside"]
        L.append(f"   [{c['label']}] net Sharpe {c['S']:.3f}")
    if "performance_line" in t:
        pl = t["performance_line"]["lines"]
        L.append("   performance line (unweighted; descriptive; never gates): " + "; ".join(
            f"last {k} rows {v['S']:+.3f} [{v['ci90'][0]:+.3f}, {v['ci90'][1]:+.3f}]" for k, v in pl.items()))
    return L


def read(rec: dict) -> tuple[str, dict]:
    cut = rec.get("cut", {})
    L = [f"ETF RECENT PANEL, IN-SAMPLE READ (registered at {rec.get('registration')}); "
         f"{rec.get('first_date')} .. {rec.get('last_date')}, {rec.get('rows')} rows, {cut.get('n_included')} ETFs; "
         f"platform {rec.get('platform')}",
         "=" * 92, f"limits of the certificate: {LIMITS}", f"limits of the panel: {PANEL_LIMITS}"]
    rep = rec.get("repeat_bit_identical") or {}
    if not (rep.get("d1") and rep.get("d0")) or rec.get("stopped"):
        L.append(f"the bit-for-bit repeat FAILED or the read stopped ({rec.get('stopped')}): nothing priced. STOP and ask.")
        return "\n".join(L), {"stopped": True}
    L.append("bit-for-bit repeat: d = 1 identical, d = 0 identical")
    out = {}
    for key in ("test1_stream_d1", "test2_stream_d0", "test3_class_d1"):
        if key not in rec:
            L.append(f"{key} missing: not read. STOP and ask.")
            return "\n".join(L), {"stopped": True}
        L.append("")
        L += render(key, rec[key])
        out[key] = {lvl: rec[key]["weighted_W2"]["certified"][lvl] for lvl in ("96%", "90%")}
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    d = Path(a.dir)
    if (d / "read.txt").exists():
        raise SystemExit("already read")
    rec = json.loads((d / "results.json").read_text())
    if rec.get("platform") != "Linux x86_64":
        raise SystemExit("not a box run; not read")
    text, out = read(rec)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
