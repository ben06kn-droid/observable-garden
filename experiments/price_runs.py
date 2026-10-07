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

**Planted panels (7.5 stage 2, build item 4).** A run whose `start` event names panel
`planted` carries its `level`, and its supports are in the MASKED indices the agent saw
(`environments/planted_view.py`). The panel is rebuilt from the seed: `load_base()`
loads the pinned X and refuses a mismatch, `make_draw` regenerates the draw, and
`agent_view` re-applies the mask. **One pass over the masked panel** then builds the
run's class table in memory (82,240 streams, about 2 GB, so allow about 2.5 GB a
worker), and with it each member's overlap with the planted weights. From that pass:
- the **class tier**: `class_p_etf`'s computation on that table, so the replicates are
  the certifying null's own, as on the ETF panel;
- the **replay-tier verdict**, through `certify_log` with the same table. Both tiers run
  at `PLANTED_B` = 1,000 (`prereg/planted-edge.md`, "The nulls");
- the **population truths**, written to a `planted_truth` record: the submission's
  in-sample population Sharpe (the closed form, as the scripted driver computes it) and
  holdout population and realized Sharpe; the planted member and the population-best
  member, with recovery of each; the realized class argmax; and the feature mask. Every
  support in the record is in TRUE indices.
For a planted directory the readout gives counts only. The class-p rates are a rule
quantity, and they are read by the registered reader after the results are committed,
not printed at pricing time.
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
    # the content-move cap a capped arm ran under (7.5's unsaturable arm): the replay
    # null enforces it, so a run priced from its file must carry it
    cap = events_of(d, "content_cap")
    log.content_cap = (None if not cap or cap[0].get("cap") is None
                       else int(cap[0]["cap"]))
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


def replicate_rows(sandbox, seed: int, B: int):
    """The certifying null's replicate rows, as `quixote.certify.three_nulls` draws
    them: the block length chosen on the demeaned base columns, `default_rng(seed)`,
    one `stationary_bootstrap_indices` call per replicate, in order. Every tier priced
    from a run's file uses these rows, so its p-values share their resamples."""
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices

    base = np.asarray(sandbox.base_feature_columns(), dtype=float)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(seed)
    return [stationary_bootstrap_indices(base.shape[0], L, rng) for _ in range(B)], L


ALPHA_PRIOR, ALPHA_SEARCH = 0.04, 0.01      # prereg/prior-weighted-alpha.md


def prior_weighted(sandbox, table, seed: int, short_list, support, B: int,
                   p_search: float) -> dict:
    """The prior-weighted arm's two routes, on the class tier's own replicates.

    - **The list route:** Reality Check over the short list's own members. The
      submission's Sharpe is compared with the maximum over the LIST of the demeaned
      replicate Sharpe, at alpha_prior = 0.04. It applies only when the submission is
      on the list; the verdict attaches to the submission, as the registered prompt
      says ("anything you submit is admissible either way").
    - **The search route:** the class tier's p (`p_search`), at alpha_search = 0.01.

    The run certifies if either route rejects, and `route` says which. Total size is
    at most 0.05 by the union bound, given that the list preceded every evaluation,
    which the tool enforces.
    """
    from environments.class_table import ClassTable, canonical
    lst = [canonical(tuple((int(k), float(sg)) for k, sg in sup)) for sup in short_list]
    sub = canonical(tuple((int(k), float(sg)) for k, sg in support)) if support else None
    on_list = sub is not None and sub in lst
    if not lst:                                   # an explicit decline: no list route
        search_ok = p_search < ALPHA_SEARCH
        return {"short_list": [], "declined": True, "on_list": False, "p_prior": None,
                "alpha_prior": ALPHA_PRIOR, "p_search": float(p_search),
                "alpha_search": ALPHA_SEARCH,
                "status": "CERTIFIED" if search_ok else "FAIL",
                "route": "search" if search_ok else None, "B": B,
                "list_null_max_mean": None}
    rows, _ = replicate_rows(sandbox, seed, B)
    mini = ClassTable(streams=np.stack([table.stream(m) for m in lst]), members=lst,
                      index={m: i for i, m in enumerate(lst)},
                      panel_hash=table.panel_hash, periods_per_year=table.periods_per_year)
    N_b = mini.null_max(rows)
    S = table.sharpe(sub) if sub is not None else float("-inf")
    p_prior = (1 + int(np.sum(N_b >= S))) / (B + 1) if on_list else None
    prior_ok = p_prior is not None and p_prior < ALPHA_PRIOR
    search_ok = p_search < ALPHA_SEARCH
    route = ("both" if prior_ok and search_ok else "list" if prior_ok
             else "search" if search_ok else None)
    return {"short_list": [[list(x) for x in m] for m in lst], "declined": False,
            "on_list": on_list,
            "p_prior": p_prior, "alpha_prior": ALPHA_PRIOR,
            "p_search": float(p_search), "alpha_search": ALPHA_SEARCH,
            "status": "CERTIFIED" if route else "FAIL", "route": route, "B": B,
            "list_null_max_mean": float(N_b.mean())}


def class_p_etf(sandbox, table, seed: int, support, B: int) -> dict:
    """The declared-class p on the ETF panel, from the class table.

    Replicate rows are drawn exactly as `quixote.certify.three_nulls` draws them:
    the block length chosen on the demeaned base columns, `default_rng(seed)`, one
    `stationary_bootstrap_indices` call per replicate in order.
    """
    rows, L = replicate_rows(sandbox, seed, B)
    M_b = table.null_max(rows)
    class_max, _ = table.max_sharpe()
    sr = table.sharpe(support) if support else float("-inf")
    p = (1 + int(np.sum(M_b >= sr))) / (B + 1)
    from quixote.confidence import confidence
    conf = (confidence(float(sr), M_b, ppy=float(table.periods_per_year),
                       tier="declared class") if support else None)
    from quixote.confidence import render
    return {"seed": seed, "p_upper": p, "submitted_score": float(sr),
            "confidence": conf,
            # P_H printed only beside a certified run (prereg/confidence-output.md,
            # 2026-10-05); stored in `confidence` either way
            "confidence_text": render(conf, certified=p < CLASS_ALPHA),
            "class_max": float(class_max), "block_length": L,
            "null_max_mean": float(M_b.mean()), "B": B,
            "basis": "class table (stored net streams)",
            "guard_floor": None, "guard_cap": None}


# Verdict fields added after runs were priced in-line: `--check` compares a re-price
# with what a stored run CAN carry, so a field the run predates is not a difference.
ADDED_SINCE = ("confidence",)

PLANTED_B = 1_000         # prereg/planted-edge.md: both tiers at B = 1,000


def planted_level(d: dict) -> float:
    start = events_of(d, "start")
    if not start or "level" not in start[0]:
        raise ValueError(f"{d.get('run_id')}: a planted run's `start` event must carry "
                         "its `level`")
    return float(start[0]["level"])


def planted_basis(seed: int, beta: float):
    """`(base, draw, view, mask)`: the run's planted panel, rebuilt from its seed on
    the pinned X, and the masked view its agent searched."""
    from environments import planted_panel as pp
    from environments.planted_view import agent_view
    base = pp.load_base()                  # the pinned X; refuses a mismatch
    draw = pp.make_draw(base, seed, beta)
    view, mask = agent_view(draw.in_sample, seed)
    return base, draw, view, mask


def planted_table(base, draw, view, mask, inv: dict | None = None):
    """One pass over the masked view: the run's class table, in memory, and every
    member's population Sharpe at this draw's scale.

    Members are enumerated in the view's indices. The panel-invariant moments are
    per TRUE member, so they are mapped through the mask; the overlap moments come
    from the pass itself, as in the scripted driver.
    """
    from environments import planted_panel as pp
    from environments.class_table import (CHUNK, ClassTable, _panel_hash, canonical,
                                          members_in_order)
    T, _, K = view.features.shape
    members = members_in_order(pp.CLS, K)
    N = len(members)
    streams = np.empty((N, T))
    Ea, Ea2, Eak = np.empty(N), np.empty(N), np.empty(N)
    for s in range(0, N, CHUNK):
        X, Ea[s:s + CHUNK], Ea2[s:s + CHUNK], Eak[s:s + CHUNK] = \
            pp.streams_with_overlap(view, members[s:s + CHUNK], draw.w_star_is)
        streams[s:s + len(X)] = X
    table = ClassTable(streams=streams, members=members,
                       index={canonical(m): i for i, m in enumerate(members)},
                       panel_hash=_panel_hash(view),
                       periods_per_year=float(view.periods_per_year))
    inv = pp.invariants_for(base) if inv is None else inv
    true_ix = {canonical(m): i for i, m in enumerate(base.members)}
    order = np.array([true_ix[canonical(mask.to_true(m))] for m in members])
    inv_v = {k: np.asarray(v)[order] for k, v in inv.items()}
    pop = pp.population_from_moments(Ea, Ea2, Eak, inv_v, draw.c, view.periods_per_year)
    return table, pop


def _overlaps(sup, ref) -> bool:
    """The scripted driver's two-of-three, for a depth-3 reference."""
    cs = set(sup) if sup else set()
    need = 2 if len(ref) == 3 else len(ref)
    return len(cs & set(ref)) >= need


def planted_truth(base, draw, view, mask, table, pop, support_masked) -> dict:
    """The population truths for one run, every support in TRUE indices."""
    from environments import planted_panel as pp
    from environments.class_table import canonical
    from experiments.planted_edge import StreamCache, _sharpe

    ann = float(np.sqrt(view.periods_per_year))
    star = canonical(draw.m_star)
    star_v = canonical(mask.to_masked(star))
    if draw.beta > 0:
        assert abs(pop[table.column(star_v)] - draw.beta) < 1e-8, \
            "closed form disagrees with the planted scale"
    jp = int(np.argmax(pop))
    plus = canonical(mask.to_true(table.members[jp]))
    cmax, jc = table.max_sharpe()
    argmax = canonical(mask.to_true(table.members[jc]))

    def recovery(sup):
        return {"equals": sup == star if sup else False,
                "two_of_three": _overlaps(sup, star),
                "equals_pop_best": sup == plus if sup else False,
                "two_of_three_pop_best": _overlaps(sup, plus)}

    sup_v = canonical(support_masked) if support_masked else None
    sup = canonical(mask.to_true(sup_v)) if sup_v else None
    rec = {"seed": draw.seed, "level": draw.beta, "c": draw.c,
           "feature_mask": list(mask.perm),
           "submitted_support_true": [list(x) for x in sup] if sup else None,
           "submitted_truth": ({"in_sample": float(pop[table.column(sup_v)]),
                                "holdout": pp.truth(base, draw, sup)["holdout"]}
                               if sup else None),
           "submitted_realized": table.sharpe(sup_v) if sup else None,
           "submitted_holdout_realized": (_sharpe(StreamCache(draw.holdout).get(sup), ann)
                                          if sup else None),
           "submitted_recovery": recovery(sup),
           "planted": [list(x) for x in star],
           "planted_truth": pp.truth(base, draw, star),
           "planted_realized": table.sharpe(star_v),
           "class_max": float(cmax), "class_argmax": [list(x) for x in argmax],
           "class_argmax_recovery": recovery(argmax),
           "pop_best": [list(x) for x in plus], "pop_best_sr": float(pop[jp]),
           "pop_n_positive": int((pop > 0).sum()),
           "planted_rank": int((pop > pop[table.column(star_v)]).sum()) + 1}
    return rec


def price_planted(d: dict, out: dict, check: bool, class_B: int | None) -> dict:
    """One planted run: verdict, class tier and truths from one pass."""
    from environments import planted_panel as pp
    from environments.real_sandbox import RealSandbox
    from experiments.agent_backend import RunRecord, certify_log

    t0 = time.time()
    seed, beta = int(d["seed"]), planted_level(d)
    base, draw, view, mask = planted_basis(seed, beta)
    sandbox = RealSandbox(view, spec_class=pp.CLS)
    table, pop = planted_table(base, draw, view, mask)
    B = class_B or PLANTED_B
    log = rebuild_session_log(d)
    if log is not None and (out["needs_verdict"] or check):
        rec = RunRecord(run_id=d["run_id"], arm=d["arm"], seed=seed)
        certify_log(rec, log, sandbox, pp.CLS, table, B=B)
        out["certifying_null_computable"] = rec.certifying_null_computable
        out["verdict"] = rec.verdict
        out["verdict_events"] = rec.events
    sup = d.get("submitted_support")
    cp = class_p_etf(sandbox, table, seed, sup, B)
    cp["status"] = "CERTIFIED" if cp["p_upper"] < CLASS_ALPHA else "FAIL"
    cp["alpha"] = CLASS_ALPHA
    cp["tier"] = "declared class"
    cp["basis"] = "planted: in-memory class table of the masked view"
    sl = events_of(d, "short_list")
    if sl:
        cp["prior_weighted"] = prior_weighted(sandbox, table, seed, sl[0]["supports"],
                                              sup, B, cp["p_upper"])
    out["class_p"] = cp
    out["planted_truth"] = planted_truth(base, draw, view, mask, table, pop, sup)
    if sl:
        from environments.class_table import canonical
        star = canonical(draw.m_star)
        lst = [canonical(mask.to_true(tuple((int(k), float(g)) for k, g in m)))
               for m in sl[0]["supports"]]
        out["planted_truth"]["short_list_true"] = [[list(x) for x in m] for m in lst]
        out["planted_truth"]["short_list_contains_m_star"] = star in lst
        out["planted_truth"]["short_list_overlaps_m_star"] = any(
            _overlaps(m, star) for m in lst)
    out["panel"] = "planted"
    out["secs"] = time.time() - t0
    return out


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
    if panel == "planted":
        if "planted_truth" in kinds and "class_p" in kinds and not check:
            out.update(class_p=d["class_p"], planted_truth=d["planted_truth"],
                       panel=panel, secs=0.0)
            return out
        return price_planted(d, out, check, class_B)
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
        sl = events_of(d, "short_list")
        if sl:
            cp["prior_weighted"] = prior_weighted(sandbox, table, seed,
                                                  sl[0]["supports"], sup, B, cp["p_upper"])
    else:
        cp = class_p_on(sandbox, cls, ann, seed, sup, B)
    cp["status"] = "CERTIFIED" if cp["p_upper"] < CLASS_ALPHA else "FAIL"
    cp["alpha"] = CLASS_ALPHA
    cp["tier"] = "declared class"
    out["class_p"] = cp
    out["panel"] = panel
    out["secs"] = time.time() - t0
    return out


REPRICE_NOTE = ("The B = 200 verdict and class_p in the source run file are the registered "
                "6.5 results. The fields re-priced here exist only to supply the confidence "
                "readouts for 6.5 holdout grading (prereg/holdout-grading.md); they supersede nothing in the "
                "registration and never replace the source file's fields.")


def reprice_one(payload) -> dict:
    """Re-price an ALREADY-priced run (it carries a `class_p`) at `B`, confidence fields
    included, without touching its file. The class tier always; the verdict only where
    the run carries one. Module-level so a process pool can pickle it."""
    import hashlib
    from experiments.agent_backend import RunRecord, certify_log
    from experiments.agent_cell_class_p import class_p_on

    path, B = payload
    path = Path(path)
    raw = path.read_bytes()
    d = json.loads(raw)
    out = {"file": path.name, "run_id": d.get("run_id")}
    kinds = [e.get("kind") for e in d.get("events", [])]
    if "end" not in kinds:
        out["skip"] = "incomplete: no `end` event"
        return out
    if "class_p" not in kinds:
        out["skip"] = "carries no class_p: not an already-priced run"
        return out
    panel, seed = panel_of(d), int(d["seed"])
    if panel == "planted":
        out["skip"] = "planted runs are out of this mode's scope"
        return out
    sandbox, cls, table, ann = _basis(panel, seed)
    t0 = time.time()
    verdict, computable, vevents = None, None, []
    log = rebuild_session_log(d)
    if d.get("verdict") is not None and log is not None:
        rec = RunRecord(run_id=d["run_id"], arm=d["arm"], seed=seed)
        certify_log(rec, log, sandbox, cls, table, B=B)
        verdict, computable, vevents = rec.verdict, rec.certifying_null_computable, rec.events
    sup = d.get("submitted_support")
    if panel == "etf":
        cp = class_p_etf(sandbox, table, seed, sup, B)
        sl = events_of(d, "short_list")
        if sl:
            cp["prior_weighted"] = prior_weighted(sandbox, table, seed,
                                                  sl[0]["supports"], sup, B, cp["p_upper"])
    else:
        cp = class_p_on(sandbox, cls, ann, seed, sup, B)
    cp["status"] = "CERTIFIED" if cp["p_upper"] < CLASS_ALPHA else "FAIL"
    cp["alpha"] = CLASS_ALPHA
    cp["tier"] = "declared class"
    out.update(record={
        "run_id": d.get("run_id"), "arm": d.get("arm"), "seed": seed, "panel": panel,
        "source": {"file": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
        "B": B, "class_p": cp, "verdict": verdict,
        "certifying_null_computable": computable, "verdict_events": vevents,
        "superseded": {"class_p": d.get("class_p"), "verdict": d.get("verdict"),
                       "certifying_null_computable": d.get("certifying_null_computable")},
        "note": REPRICE_NOTE}, secs=time.time() - t0)
    return out


def reprice_dir(src: Path, dest: Path, B: int, workers: int) -> str:
    """Write one re-priced record per already-priced run into `dest`, a NEW location.
    Refuses a destination inside the source directory and any existing output file:
    the B = 200 results are never overwritten, here or anywhere."""
    from experiments.code_state import code_state, platform_info
    src, dest = src.resolve(), dest.resolve()
    if dest == src or src in dest.parents:
        raise SystemExit(f"{dest} is the source directory or inside it; the re-priced "
                         "records go to a new location")
    files = sorted(src.glob("cell_*.json"), key=lambda p: int(p.name.split("_")[2]))
    clash = [f.name for f in files if (dest / f.name).exists()]
    if clash:
        raise SystemExit(f"{len(clash)} output file(s) already exist in {dest} "
                         f"(first: {clash[0]}); nothing is overwritten")
    dest.mkdir(parents=True, exist_ok=True)
    payloads = [(str(f), B) for f in files]
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(reprice_one, payloads))
    else:
        results = [reprice_one(p) for p in payloads]
    cs, pf = code_state(), platform_info()
    written, skipped = 0, []
    for r in results:
        if "skip" in r:
            skipped.append((r["file"], r["skip"]))
            continue
        rec = dict(r["record"], code_state=cs, platform=pf, secs=r["secs"])
        target = dest / r["file"]
        tmp = dest / f".{r['file']}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(rec, indent=1, default=str))
        os.replace(tmp, target)
        written += 1
    L = [f"price_runs --reprice-to — {src} -> {dest}  (B = {B})",
         f"  {len(files)} run file(s); {written} re-priced record(s) written; "
         f"{len(skipped)} skipped; no source file touched; no rate is printed here"]
    L += [f"    skipped {f}: {why}" for f, why in skipped]
    text = "\n".join(L)
    (dest / "reprice_readout.txt").write_text(text + "\n")
    return text


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
    if "planted_truth" in result and not any(e.get("kind") == "planted_truth"
                                             for e in ev):
        d["planted_truth"] = result["planted_truth"]
        new.append({"t": time.time(), "kind": "planted_truth",
                    **result["planted_truth"]})
    if not new:
        return
    new.append({"t": time.time(), "kind": "priced_from_log",
                "by": "experiments/price_runs.py", "code_state": code_state(),
                "platform": __import__("experiments.code_state",
                                       fromlist=["platform_info"]).platform_info(),
                "verdict_written": bool(result.get("needs_verdict")),
                "class_p_written": "class_p" in [e["kind"] for e in new],
                "planted_truth_written": "planted_truth" in [e["kind"] for e in new]})
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
    for k in ADDED_SINCE:                 # fields a run priced before them cannot carry
        if k not in a:
            b.pop(k, None)
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
    ap.add_argument("--reprice-to", default=None,
                    help="re-price ALREADY-priced runs at --B, confidence fields included, "
                         "into this NEW directory; the source files are never touched")
    a = ap.parse_args(argv)
    if a.reprice_to:
        if not a.B or a.check:
            raise SystemExit("--reprice-to needs --B and excludes --check")
        print(reprice_dir(Path(a.dir), Path(a.reprice_to), a.B, a.workers), flush=True)
        return 0

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

    if any(r.get("panel") == "planted" for r in priced):
        # counts only: the class-p rates and the truths are rule quantities, read by
        # the registered reader after the results are committed
        L += ["", f"  planted: {len(priced)} run(s) priced; class tier and truths "
              "written; no rate is printed here"]
        text = "\n".join(L)
        print("\n" + text, flush=True)
        if not a.check:
            (d / "pricing_readout.txt").write_text(text + "\n")
        return 1 if a.check and disagree else 0

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
