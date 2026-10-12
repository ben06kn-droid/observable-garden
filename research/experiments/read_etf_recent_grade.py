"""The reader for the ETF recent panel's grading of its three objects
(`prereg/etf-recent-panel.md`, sections g and i, amendments 1-2; the grades from
`experiments/etf_recent_grade.py`). Reads `grades.json` once and writes `read.txt` and
`decision.json` beside it. The agent cell's submissions are read by
`experiments/read_agent_cell_etf_recent.py`.

    python -m experiments.read_etf_recent_grade --dir runs/etf_recent_grade/<date>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

WINDOW = "the holdout"
LIMITS = ("limits: W2's size is checked by simulation, not proved; overshoots of about 10% are not reliably "
          "detected; the class checks are weak. Item 3 of section b is NOT verified; the list of 40 was named in "
          "2026 from survivors; costs are an assumption.")
WEAK = ("weak: 1.76 years -- one realised Sharpe has a standard error of about 0.75; 'held' and 'did not hold' "
        "are weak evidence either way. A second grading is fixed for 2028-01-03.")
LABEL = {"stream_d1": "(1) the Sancho stream, d = 1",
         "stream_d0": "(2) the Sancho stream, d = 0, NOT IMPLEMENTABLE",
         "class_member": "(3) the class's weighted best member, d = 1"}


def branch(o: dict) -> str:
    x, L, name = o["realized"], o["L90_weighted"], LABEL[o["id"]]
    cert = o["certified"]
    rel = "≥" if o["held"] else "<"
    if cert.get("96%") or cert.get("90%"):
        lvl = "96% level" if cert.get("96%") else "90% level, labelled"
        head = f"{name}: certified in-sample under the recency weights (W2) at the registered weight ({lvl})"
        verb = "held" if o["held"] else "did not hold"
        return f"{head}; its weighted lower bound {verb} on {WINDOW} (realised {x:+.3f} {rel} bound {L:+.3f})."
    return (f"{name}: refused in-sample; consistent with the registered detection floor. "
            f"Graded: realised {x:+.3f} {rel} its weighted lower bound {L:+.3f}.")


def read(d: Path) -> str:
    d = Path(d)
    if (d / "read.txt").exists():
        raise SystemExit("read.txt exists; the grading is read once")
    g = json.loads((d / "grades.json").read_text())
    objs = [i for i in g["items"] if i["type"] == "object"]
    L = [f"ETF RECENT PANEL, HOLDOUT GRADING OF ITS THREE OBJECTS ({g['label']}); {g['first_holdout_date']} .. "
         f"{g['last_date']}, {g['n_periods']} periods; block length {g['block_length']}, B {g['B']}, seed {g['seed']}",
         "=" * 92, WEAK, LIMITS, ""]
    dec = {}
    for o in objs:
        L.append(branch(o))
        L.append(f"   realised unweighted net Sharpe {o['realized']:+.3f}, 90% interval [{o['ci90'][0]:+.3f}, "
                 f"{o['ci90'][1]:+.3f}]; net return {o['net_return']:+.4f}")
        s26 = o["only_2026"]
        L.append(f"   2026 only ({s26['rows']} rows; descriptive, never deciding): "
                 + ("n/a" if s26["realized"] is None else f"{s26['realized']:+.3f}"))
        dec[o["id"]] = {"held": o["held"], "realized": o["realized"], "L90_weighted": o["L90_weighted"],
                        "certified": o["certified"]}
    text = "\n".join(L)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(dec, indent=1))
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    print(read(Path(a.dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
