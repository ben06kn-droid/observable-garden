"""Outcome-free design quantities for the chosen Binance variant at d = 0 (author,
2026-10-09): the signal at the close of bar t, the fill at that close, the position earning
bar t+1, and the trade costed iff bar t is live. Laptop; the PINNED d = 0 inputs
(`environments.binance_pins`, delay 0).

Under the adopted rules: the cost rule, the whole-window block length, and the
dead-contract closure (the freed gross is not redeployed). Reported:
- the stream's bars at 95%, 96%, 97.5% and 99% (B 5,000, seed 695058), with net and gross
  Sharpe needed at 80% power;
- drag, turnover per unit gross, cost per year, dead share, block length;
- the class tier's bars at d = 0 (the fast kernel's tables are rebuilt for this panel;
  seed 695059);
- leak tests at d = 0 (seeds 695060 learner, 695061 blocks): the learner's book, and every block builder (X on returns and on
  the market, V on volume, taker and count, F on funding, the groups);
- the bit-for-bit repeat (positions, in a separate process).
The d = 1 figures are those of `runs/binance_design_chosen/2026-10-09` (`7f0e2c9`), shown
beside.

**Never computed, printed or stored:** a mean return, a Sharpe, a p-value or any
certification.

    OMP_NUM_THREADS=1 python -m experiments.binance_design_d0 --out runs/binance_design_d0/2026-10-09 --workers 3
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from experiments import binance_design_chosen as C
from experiments import binance_design_v2 as D
from experiments import binance_design_v2_4h as E

NAME = "4h-2021-01"
LAG = 1
SEED, SEED_CLASS, SEED_LEAK, SEED_BLOCK_LEAK = 695058, 695059, 695060, 695061
D1 = Path("runs/binance_design_chosen/2026-10-09/design.json")


def pinned_raw_d0():
    from environments import binance_pins as Pn
    raw = E.raw_4h(NAME, lag=LAG)
    X = Pn.load("X", delay=0)
    if X.shape != raw["panel"].features.shape:
        raise SystemExit("pinned X shape differs from the build")
    raw["panel"] = dataclasses.replace(raw["panel"], features=X)
    return raw, Pn.load("v2", delay=0), Pn.load("costs", delay=0)


def inputs_d0(raw, v2, costs):
    from learn2 import learner as Ln
    panel = dataclasses.replace(raw["panel"], cost_rate=np.asarray(costs["rates"], float))
    inp = Ln.from_panel(panel, blocks={"X": v2["X"], "V": v2["V"], "F": v2["F"]}, groups=v2["G"])
    if inp.d != 0:
        raise SystemExit(f"the panel's delay is {inp.d}, not 0")
    return panel, inp


def job_main() -> dict:
    D.configure("4h")
    C.SEED, C.SEED_CLASS = SEED, SEED_CLASS
    raw, v2, costs = pinned_raw_d0()
    panel, inp = inputs_d0(raw, v2, costs)
    book, first, meta = D.book_of(inp)
    T, ppy = inp.earned.shape[0], inp.ppy
    rows = np.arange(first, T)
    alive = np.array([raw["info"][s]["alive_earned"] for s in panel.meta["symbols"]]).T
    closed = E.close_dead(book, alive)
    out = {"rows": int(len(rows)), "years": len(rows) / ppy, "first_scored_row": int(first),
           "first": panel.meta["earned_opens"][rows[0]], "last": panel.meta["earned_opens"][rows[-1]],
           "seconds_per_fit": meta["seconds_per_fit"], "book_sha256": D.sha(book),
           "as_is": C.figures(book, panel, inp, rows, alive, ppy, len(rows) / ppy),
           "closed": C.figures(closed, panel, inp, rows, alive, ppy, len(rows) / ppy)}
    return out


def job_class() -> dict:
    C.SEED, C.SEED_CLASS = SEED, SEED_CLASS
    raw, v2, costs = pinned_raw_d0()
    panel, _ = inputs_d0(raw, v2, costs)
    return C.class_figures(panel)


def job_leak() -> dict:
    from learn2 import leak as Lk
    from learn2 import learner as Ln
    from learn2 import timing
    D.configure("4h")
    raw, v2, costs = pinned_raw_d0()
    _, inp = inputs_d0(raw, v2, costs)
    first = Ln.FIRST + timing.embargo(D.H, inp.d)
    t = first + (inp.earned.shape[0] - first) // 2
    hashes = []

    def fn(i):
        b = D.book_of(i)[0]
        hashes.append(D.sha(b))
        return b
    return {"leak_view": Lk.leak_view(fn, inp, [t], seed=SEED_LEAK), "base_book_sha256": hashes[0], "t": t}


def job_block_leak() -> dict:
    raw = E.raw_4h(NAME, lag=LAG)
    E.SEED_LEAK["4h-2021-01"] = SEED_BLOCK_LEAK
    return E.job_block_leak("4h-2021-01", raw)


JOBS = {"main": job_main, "leak": job_leak, "class": job_class, "block_leak": job_block_leak}


def run_job(kind):
    t0 = time.time()
    r = JOBS[kind]()
    r["job_seconds"] = time.time() - t0
    return kind, r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design.json").exists():
        raise SystemExit("exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    res = {}
    with ProcessPoolExecutor(a.workers) as ex:
        for kind, r in ex.map(run_job, ("main", "leak", "class", "block_leak")):
            res[kind] = r
            print(f"{kind} done ({r['job_seconds']:.0f} s; {time.time() - t0:.0f} s elapsed)", flush=True)
    d1 = json.loads(D1.read_text())
    m, lk, cl, bl = res["main"], res["leak"], res["class"], res["block_leak"]["block_leak"]
    L = [f"Chosen Binance variant {NAME}, version 2, d = 0 beside d = 1 (outcome-free; pinned inputs; cost rule; "
         "whole-window block length; closure)", f"platform {platform.system()} {platform.machine()}", "=" * 100]
    L.append(f"d = 0: first scored row {m['first_scored_row']}; scored {m['rows']} rows, {m['years']:.2f} years "
             f"({m['first'][:16]} .. {m['last'][:16]}); seconds per fit " +
             ", ".join(f"{k} {v:.0f}" for k, v in m["seconds_per_fit"].items()))
    lv = lk["leak_view"][0]
    L.append(f"leak (learner, t = {lv['t']}): identical up to t {lv['identical_up_to_t']}, change visible {lv['changed_after_t']}")
    L.append("leak (blocks): " + "; ".join(f"{k} {x[0]['identical_up_to_t']}/{x[0]['changed_after_t']}" for k, x in bl.items()))
    L.append(f"bit-for-bit repeat (positions, separate process): {m['book_sha256'] == lk['base_book_sha256']}")
    leak_ok = lv["identical_up_to_t"] and lv["changed_after_t"] and all(
        x[0]["identical_up_to_t"] and x[0]["changed_after_t"] for x in bl.values())
    L.append("LEAK TESTS: " + ("ALL PASS" if leak_ok else "A LEAK TEST FAILED: STOP"))
    L += ["", f"{'':<6} {'rows':>5} {'years':>5} {'L':>3} {'bar95':>6} {'net95':>6} {'gross95':>7} {'bar96':>6} "
          f"{'net96':>6} {'gross96':>7} {'drag':>6} {'turn':>7} {'cost/y':>7} {'deadsh':>7} {'vol':>6} {'gross_mean':>10}"]
    d1c = d1["schemes"]["rule"]["closed"]
    for lab, f, rows, yrs in (("d = 1", d1c, d1["rows"], d1["years"]), ("d = 0", m["closed"], m["rows"], m["years"])):
        b5, b6 = f["bars"]["0.95"], f["bars"]["0.96"]
        L.append(f"{lab:<6} {rows:>5} {yrs:>5.2f} {f['block_length']:>3} {b5['bar']:>6.3f} {b5['net_80']:>6.3f} "
                 f"{b5['gross_80']:>7.3f} {b6['bar']:>6.3f} {b6['net_80']:>6.3f} {b6['gross_80']:>7.3f} "
                 f"{f['cost_drag_sharpe']:>6.3f} {f['turnover_per_unit_gross']:>7.4f} {f['cost_per_year']:>7.4f} "
                 f"{f['dead_gross_share']:>7.4f} {f['ann_vol']:>6.3f} {f['mean_gross']:>10.3f}")
    L.append(f"d = 0 before closure: dead share {m['as_is']['dead_gross_share']:.4f}, drag {m['as_is']['cost_drag_sharpe']:.3f}")
    L.append("stream bars at d = 0 (closed): " + "; ".join(f"{float(q):.3f}: {b['bar']:.3f} -> {b['net_80']:.3f} [{b['gross_80']:.3f}]"
                                                          for q, b in m["closed"]["bars"].items()))
    c1 = d1["schemes"]["rule"]["class"]
    for lab, c in (("d = 1", c1), ("d = 0", cl)):
        L.append(f"class {lab} ({c['rows']} rows, {c['years']:.2f} y, L {c['block_length']}): " +
                 "; ".join(f"{float(q):.3f}: {b['bar']:.3f} -> {b['net_80']:.3f}" for q, b in c["bars"].items())
                 + f"  (cache {c['seconds_build']:.0f} s, null {c['seconds_null']:.0f} s)")
    L.append(f"wall {time.time() - t0:.0f} s")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(res, indent=1, default=float))
    print("\n".join(L))
    return 0 if leak_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
