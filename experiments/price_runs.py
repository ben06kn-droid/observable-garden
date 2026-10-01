"""Price agent-cell runs from their committed logs: certifying null, class p, verdict.

`experiments/agent_cell.py --defer-pricing` runs the session, writes the complete
log with its close-time self-check, and stops. This prices what it wrote, for a
whole directory, in parallel. **No model, no seat**: everything here is a function
of the run file and the panel.

**The same computation as the in-line path, not a second copy of it.** The session
log is rebuilt from the file's `session_log`, `triggers_predeclared`,
`declared_budget` and `trigger_changes` events, and priced through
`experiments.agent_backend.certify_log` -- the function `_certify_run` calls when a
run prices itself at close -- on the panel rebuilt from the run's own seed (`s0`,
`s3`) or the ETF panel with its class table. `--check` holds that claim to
account: it re-prices runs that were priced in-line, compares field for field
against the verdict they carry, and writes nothing.

    python -m experiments.price_runs --dir runs/reanchor_s0_replay --check
    python -m experiments.price_runs --dir runs/etf_replay --workers 8

**What it writes.** Into each run file that carries a `pricing_deferred` event:
the verdict and `certifying_null_computable` exactly as the in-line path would
have, and the same `verdict` or `certify_error` event, inserted before `end` so
`end` stays the last event. Into **every** complete run file: a `class_p` record
and event (`prereg/agent-cell.md` amendment 11's declared-class p; on the ETF
panel the registered certifying tier, ROADMAP "What this makes the ETF
verdict"). A run already priced in-line keeps its verdict untouched. Beside the
runs: `class_p.json` and `pricing_readout.txt`.

**The class p, by panel.** Simulated: `experiments.agent_cell_class_p.class_p_on`,
unchanged, so these numbers are the ones check 4 read. ETF: the class-maximum
null over the 82,240 stored net streams (`ClassTable.null_max`), the submitted
specification scored from the same table. Its replicates are the certifying
null's own -- the same block length, the same RNG seed, drawn in the same order --
so the two p-values of a run are computed on identical resamples.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

ALPHAS = (0.05, 0.01)
CLASS_ALPHA = 0.05
_ETF: dict = {}          # per process: the ETF panel, sandbox and table, built once


def load_run(path: Path) -> dict:
    return json.loads(path.read_text())


def events_of(d: dict, kind: str) -> list[dict]:
    return [e for e in d.get("events", []) if e.get("kind") == kind]


def panel_of(d: dict) -> str:
    start = events_of(d, "start")
    if not start or "panel" not in start[0]:
        raise ValueError(f"{d.get('run_id')}: no `start` event naming the panel")
    return start[0]["panel"]


def rebuild_session_log(d: dict):
    """The `SessionLog` the run closed with, from the file -- or None for an arm
    with no session (control), which the in-line path does not price either.

    Every field `certify` reads is restored: the records with their moves'
    parameters, `replayable` and `contradicted`; the declared rules as declared;
    the change history; the declared budget; and `agent_driven`, which makes a
    missing budget an error rather than 7.1's cap.
    """
    from experiments.regrade_pilot import rebuild_log

    sl = events_of(d, "session_log")
    if not sl:
        return None
    records = sl[0]["records"]
    budget = events_of(d, "declared_budget")
    log = rebuild_log(records, d.get("triggers_predeclared") or [],
                      budget[0].get("budget") if budget else None,
                      agent_driven=True)
    for rec, r in zip(log.records, records):
        rec.contradicted = bool(r.get("contradicted", False))
    changes = events_of(d, "trigger_changes")
    log.trigger_changes = tuple(
        {"at_step": ch.get("at_step"), "trigger": dict(ch.get("trigger") or {}),
         "reason": ch.get("reason"), "timestamp": ch.get("timestamp")}
        for ch in (changes[0]["changes"] if changes else ()))
    return log


def _basis(panel: str, seed: int):
    """(sandbox, cls, table, annualization) for one run, built as the runner
    builds it."""
    if panel == "etf":
        if not _ETF:
            from experiments.agent_cell import etf_panel
            p, cls, sandbox, table = etf_panel()
            _ETF.update(panel=p, cls=cls, sandbox=sandbox, table=table)
        return _ETF["sandbox"], _ETF["cls"], _ETF["table"], None
    from experiments.agent_cell import simulated_panel
    _data, _cfg, cls, sandbox, dgp = simulated_panel(panel, seed)
    return sandbox, cls, None, float(np.sqrt(dgp.periods_per_year))


def class_p_etf(sandbox, table, seed: int, support, B: int) -> dict:
    """The declared-class p on the ETF panel, from the class table.

    Replicate rows are drawn exactly as `quixote.certify.three_nulls` draws them:
    the block length chosen on the demeaned base columns, `default_rng(seed)`, one
    `stationary_bootstrap_indices` call per replicate in order.
    """
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices

    base = np.asarray(sandbox.base_feature_columns(), dtype=float)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(seed)
    rows = [stationary_bootstrap_indices(base.shape[0], L, rng) for _ in range(B)]
    M_b = table.null_max(rows)
    class_max, _ = table.max_sharpe()
    sr = table.sharpe(support) if support else float("-inf")
    p = (1 + int(np.sum(M_b >= sr))) / (B + 1)
    return {"seed": seed, "p_upper": p, "submitted_score": float(sr),
            "class_max": float(class_max), "block_length": L,
            "null_max_mean": float(M_b.mean()), "B": B,
            "basis": "class table (stored net streams)",
            "guard_floor": None, "guard_cap": None}


def price_one(payload) -> dict:
    """One run. Module-level so a process pool can pickle it; returns what to
    write and writes nothing itself."""
    from experiments.agent_backend import CERTIFY_B, RunRecord, certify_log
    from experiments.agent_cell_class_p import class_p_on

    path, check, class_B = payload
    path = Path(path)
    d = load_run(path)
    out = {"file": path.name, "run_id": d.get("run_id")}
    kinds = [e.get("kind") for e in d.get("events", [])]
    if "end" not in kinds:
        out["skip"] = "incomplete: no `end` event"
        return out
    deferred = "pricing_deferred" in kinds
    out["deferred"] = deferred
    # deferred and not yet priced; a second pass over a directory is a no-op
    out["needs_verdict"] = deferred and not ({"verdict", "certify_error"} & set(kinds))
    panel, seed = panel_of(d), int(d["seed"])
    sandbox, cls, table, ann = _basis(panel, seed)
    t0 = time.time()

    # -- the verdict: only where the in-line path would have produced one ------
    log = rebuild_session_log(d)
    if log is not None and (out["needs_verdict"] or check):
        rec = RunRecord(run_id=d["run_id"], arm=d["arm"], seed=seed)
        certify_log(rec, log, sandbox, cls, table)
        out["certifying_null_computable"] = rec.certifying_null_computable
        out["verdict"] = rec.verdict
        out["verdict_events"] = rec.events          # `verdict` or `certify_error`

    # -- the class p: every complete run, once ---------------------------------
    if "class_p" in kinds and not check:
        out.update(class_p=d["class_p"], panel=panel, secs=time.time() - t0)
        return out
    sup = d.get("submitted_support")
    B = class_B or int((d.get("verdict") or out.get("verdict") or {}).get("B")
                       or CERTIFY_B)
    if panel == "etf":
        cp = class_p_etf(sandbox, table, seed, sup, B)
    else:
        cp = class_p_on(sandbox, cls, ann, seed, sup, B)
    cp["status"] = "CERTIFIED" if cp["p_upper"] < CLASS_ALPHA else "FAIL"
    cp["alpha"] = CLASS_ALPHA
    cp["tier"] = "declared class"
    out["class_p"] = cp
    out["panel"] = panel
    out["secs"] = time.time() - t0
    return out


def _write(path: Path, d: dict, result: dict) -> None:
    """Insert the priced fields, keeping `end` the last event. Atomic."""
    from experiments.code_state import code_state

    ev = d["events"]
    end_at = max(i for i, e in enumerate(ev) if e.get("kind") == "end")
    new = []
    if "verdict" in result and result.get("needs_verdict"):
        d["certifying_null_computable"] = result["certifying_null_computable"]
        d["verdict"] = result["verdict"]
        new += result["verdict_events"]
    if not any(e.get("kind") == "class_p" for e in ev):
        d["class_p"] = result["class_p"]
        new.append({"t": time.time(), "kind": "class_p", **result["class_p"]})
    if not new:
        return
    new.append({"t": time.time(), "kind": "priced_from_log",
                "by": "experiments/price_runs.py", "code_state": code_state(),
                "verdict_written": bool(result.get("needs_verdict")),
                "class_p_written": "class_p" in [e["kind"] for e in new]})
    d["events"] = ev[:end_at] + new + ev[end_at:]
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, indent=1, default=str))
    os.replace(tmp, path)


def compare(stored: dict, result: dict) -> list[str]:
    """Field-for-field differences between an in-line verdict and a re-price."""
    diffs = []
    if stored.get("certifying_null_computable") != result.get("certifying_null_computable"):
        diffs.append(f"certifying_null_computable {stored.get('certifying_null_computable')}"
                     f" != {result.get('certifying_null_computable')}")
    # through JSON, as the stored side went, so a tuple and a list compare equal
    rt = lambda x: json.loads(json.dumps(x, default=str))
    a, b = rt(stored.get("verdict") or {}), rt(result.get("verdict") or {})
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            diffs.append(f"verdict.{k}: {a.get(k)!r} != {b.get(k)!r}")
    ea = [{k: v for k, v in e.items() if k != "t"} for e in stored.get("events", [])
          if e.get("kind") in ("verdict", "certify_error")]
    eb = [{k: v for k, v in e.items() if k != "t"}
          for e in result.get("verdict_events", [])]
    if rt(ea) != rt(eb):
        diffs.append("verdict event differs")
    return diffs


def wilson(k: int, n: int):
    from estimator.metrics import wilson_ci
    return wilson_ci(k, n)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--check", action="store_true",
                    help="re-price runs priced in-line and compare; writes nothing")
    ap.add_argument("--B", type=int, default=None,
                    help="class-p replicates; default the run's certifying B")
    a = ap.parse_args(argv)

    d = Path(a.dir)
    files = sorted(d.glob("cell_*.json"), key=lambda p: int(p.name.split("_")[2]))
    if not files:
        raise SystemExit(f"no cell_*.json in {d}")
    payloads = [(str(f), a.check, a.B) for f in files]

    # The ETF table is opened once in the parent so a missing or legacy cache is
    # rebuilt once, here, rather than raced by every worker (each would wait on
    # the build lock, but the wait is better spent visibly).
    if any(panel_of(load_run(f)) == "etf" for f in files):
        print("  opening the ETF class table (built once if the cache is stale) ...",
              flush=True)
        _basis("etf", 0)

    results = []
    if a.workers <= 1 or len(payloads) <= 1:
        for p in payloads:
            results.append(price_one(p))
            print(f"  {results[-1]['file']} priced", flush=True)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            futs = {pool.submit(price_one, p): p[0] for p in payloads}
            for fut in as_completed(futs):
                results.append(fut.result())
                r = results[-1]
                print(f"  {r['file']} priced ({r.get('secs', 0):.0f}s)", flush=True)
    results.sort(key=lambda r: int(r["file"].split("_")[2]))

    L = [f"price_runs — {a.dir}" + ("  [--check: nothing written]" if a.check else ""),
         "=" * 78]
    skipped = [r for r in results if "skip" in r]
    priced = [r for r in results if "skip" not in r]
    L.append(f"  {len(results)} run files; {len(priced)} complete, "
             f"{len(skipped)} skipped as incomplete")
    for r in skipped:
        L.append(f"    skipped {r['file']}: {r['skip']}")

    if a.check:
        inline = [r for r in priced if not r["deferred"] and "verdict" in r]
        agree, disagree = 0, []
        for r in inline:
            diffs = compare(load_run(d / r["file"]), r)
            if diffs:
                disagree.append((r["file"], diffs))
            else:
                agree += 1
        L += ["", f"  IN-LINE AGAINST FROM-LOG, {len(inline)} runs priced in-line:",
              f"    identical: {agree}/{len(inline)}"]
        for f, diffs in disagree:
            L.append(f"    DIFFERS {f}:")
            L += [f"      {x}" for x in diffs[:8]]
    else:
        n_written = 0
        for r in priced:
            p = d / r["file"]
            before = p.read_bytes()
            _write(p, load_run(p), r)
            n_written += p.read_bytes() != before
        L.append(f"  {sum(1 for r in priced if r['needs_verdict'])} deferred run(s) "
                 f"given a verdict; {n_written} file(s) written")

    # the readout, from the files' verdicts (or the re-prices under --check)
    def verdict_of(r):
        if a.check or r["needs_verdict"]:
            return r.get("verdict")
        return load_run(d / r["file"]).get("verdict")
    status = {}
    for r in priced:
        s = (verdict_of(r) or {}).get("status", "none (no session)")
        status[s] = status.get(s, 0) + 1
    L += ["", "  replay-tier verdicts (certifying null): "
          + ", ".join(f"{k} {v}" for k, v in sorted(status.items()))]
    p = np.asarray([r["class_p"]["p_upper"] for r in priced], dtype=float)
    L += ["", f"  declared-class p, {len(p)} runs, B per run "
          f"{sorted({r['class_p']['B'] for r in priced})}:"]
    for al in ALPHAS:
        k = int((p < al).sum())
        lo, hi = wilson(k, len(p))
        L.append(f"    alpha = {al:<5} {k:>3}/{len(p):<3} = {k / len(p):7.4f}   "
                 f"Wilson [{lo:.4f}, {hi:.4f}]")
    if len(p):
        L.append(f"    p: min {p.min():.4f}  median {np.median(p):.4f}  max {p.max():.4f}")
    text = "\n".join(L)
    print("\n" + text, flush=True)
    if not a.check:
        (d / "pricing_readout.txt").write_text(text + "\n")
        (d / "class_p.json").write_text(json.dumps(
            [{"run_id": r["run_id"], "index": int(r["file"].split("_")[2]),
              **r["class_p"]} for r in priced], indent=1))
    return 1 if a.check and disagree else 0


if __name__ == "__main__":
    raise SystemExit(main())
