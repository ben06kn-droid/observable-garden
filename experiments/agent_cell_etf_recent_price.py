"""The agent cell on the ETF recent panel (`prereg/agent-cell-etf-recent.md`, section 6): PRICING,
from committed session logs and the pinned precompute only. Nothing is refitted and no holdout
value exists here.

The precompute (`<run>/precompute/`, written by the BOX-ETF read) is checked file by file
against its manifest's SHA-256 before anything is read:
- `sancho_d1.npz`: Sancho's d = 1 scored stream, its turnover, S_w, S_unw, and its W2 null;
- `class_scored.npy`: (N, T_scored) net streams of the 82,240 members, in
  `members_in_order(CLS, 40)` order;
- `class_stats.npz`: every member's S_w and S_unw, the class's W2 null maxima, the unweighted
  null maxima with each replicate's argmax m_b and S*_b(m_b), the members' SHA-256;
- `base_columns.npy` (optional): the scored rows' base feature columns, which the replay tier
  needs. Without it the replay tier is "not computed", with that reason.

Per submission (section 6's table):
- raw in-sample net Sharpe, weighted (W2) and unweighted;
- the W2 certificate: a rule on the **class tier**, p = (1 + #{class W2 maxima >= S_w}) / (B + 1),
  96% iff p < 0.01 (90% iff p < 0.02, labelled); Sancho's stream on the **supplied-streams
  tier**, p against its own W2 null, 96% iff p < 0.03 (90% iff p < 0.06, labelled);
- the weighted L90 = S_w - the null's 0.90 quantile;
- EB of `prereg/point-estimate.md` (rules only; unweighted; descriptive): S_unw - mean_b[S*_b(m_b)
  - S_unw(m_b)], with m_b and S*_b(m_b) the class argmax and its Sharpe on the UN-DEMEANED unweighted
  replicates (`null_unw_undemeaned_*`, seed 721002);
- for Sancho's stream, beside and descriptive, "selection-aware (approximate, independent
  draws)": p of S_w against max(class W2 maxima_b, Sancho's W2 null_b). The two nulls were drawn
  with different seeds (721002 and 721000), so this is an approximation, not a joint null;
- the replay tier (6.5's trigger replay through `experiments.agent_backend.certify_log`) on the
  session's logged grammar search, where the class is tabulated (the precompute) and the base
  columns are present; a session that called `sancho()` before a rule submission is flagged
  "non-grammar look (Sancho) taken";
- the session's search length: grammar moves, and candidates seen.

    python -m experiments.agent_cell_etf_recent_price --logs runs/agent_cell_etf_recent/sessions \\
        --precompute runs/etf_recent/<D>/precompute --submissions runs/agent_cell_etf_recent/submissions.json \\
        --out runs/agent_cell_etf_recent/priced.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import types
from pathlib import Path

import numpy as np

ALPHA = {"rule": (0.01, 0.02), "sancho": (0.03, 0.06)}
GRAMMAR = {"pick_prior", "declare_triggers", "change_trigger", "init", "extend_best", "swap_worst", "flip",
           "refine", "pick", "stop", "restart"}       # experiments/agent_cell_etf_recent.py, GRAMMAR_TOOLS
CERTIFY_B = 1000


class PricingRefused(RuntimeError):
    pass


# -- the precompute -----------------------------------------------------------------------

def members_sha256(members) -> str:
    """The SHA-256 the precompute records for the member order, by the runner's own expression
    (`experiments.etf_recent_read`): JSON of [[float(k), float(sign)], ...] per member."""
    return hashlib.sha256(json.dumps([[list(map(float, kv)) for kv in m] for m in members]).encode()).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def load_precompute(d: Path, members=None) -> dict:
    d = Path(d)
    man = json.loads((d / "manifest.json").read_text())
    for f, h in man["sha256"].items():
        if not (d / f).exists() or sha_file(d / f) != h:
            raise PricingRefused(f"precompute file {f} is missing or not its manifest SHA-256")
    for f in ("sancho_d1.npz", "class_scored.npy", "class_stats.npz"):
        if f not in man["sha256"]:
            raise PricingRefused(f"the manifest does not pin {f}")
    if members is None:
        from environments.class_table import members_in_order
        from environments.planted_panel import CLS
        members = members_in_order(CLS, 40)
    sn = dict(np.load(d / "sancho_d1.npz", allow_pickle=False))
    cs = dict(np.load(d / "class_stats.npz", allow_pickle=False))
    if str(cs["members_sha256"]) != members_sha256(members):
        raise PricingRefused("the precompute's member order is not members_in_order(CLS, 40)")
    base = np.load(d / "base_columns.npy") if "base_columns.npy" in man["sha256"] else None
    return {"manifest": man, "manifest_sha256": sha_file(d / "manifest.json"), "sancho": sn, "stats": cs,
            "scored": np.load(d / "class_scored.npy", mmap_mode="r"), "base": base, "members": members}


def index_of(members) -> dict:
    from environments.class_table import canonical
    return {canonical(m): j for j, m in enumerate(members)}


# -- logs ---------------------------------------------------------------------------------

def events_of(d: dict, kind: str) -> list[dict]:
    return [e for e in d.get("events", []) if e.get("kind") == kind]


def tool_name(e: dict) -> str:
    return str(e.get("tool") or e.get("name") or "").split("__")[-1]


def last_submission(d: dict) -> dict:
    return events_of(d, "submit")[-1].get("submission") or {}


def search_length(d: dict) -> dict:
    """Grammar moves the harness answered (`tool_result` events of grammar tools), and the
    candidates the grammar session recorded."""
    moves = [e for e in events_of(d, "tool_result") if tool_name(e) in GRAMMAR]
    sl = events_of(d, "session_log")
    cands = None
    if sl:
        seen = set()
        for r in sl[0].get("records", []):
            for c in r.get("candidates", []) or []:
                seen.add(json.dumps(c, sort_keys=True))
        cands = len(seen) if seen else len(sl[0].get("records", []))
    return {"moves": len(moves), "candidates_seen": cands}


def sancho_look_before_submit(d: dict) -> bool:
    """A `sancho()` call before the candidate was fixed (the `candidate` event)."""
    evs = d.get("events", [])
    at = next((i for i, e in enumerate(evs) if e.get("kind") == "candidate"),
              next((i for i, e in enumerate(evs) if e.get("kind") == "submit"), len(evs)))
    return any(e.get("kind") == "sancho_call" or (e.get("kind") == "tool_result" and tool_name(e) == "sancho")
               for e in evs[:at])


# -- one submission -----------------------------------------------------------------------

def tier_p(S: float, null: np.ndarray) -> float:
    null = np.asarray(null, float)
    return float((1 + int(np.sum(null >= S))) / (null.size + 1))


def price(sub: dict, pre: dict, idx: dict) -> dict:
    from environments.class_table import canonical
    st, sn = pre["stats"], pre["sancho"]
    kind = sub["kind"]
    out = {"session": sub["session"], "arm": sub["arm"], "kind": kind, "support": sub["support"],
           "predict": sub["predict"]}
    if kind == "rule":
        key = canonical(sub["support"])
        if key not in idx:
            raise PricingRefused(f"session {sub['session']}: support {key} is not a class member")
        j = idx[key]
        S_w, S_u = float(st["S_w"][j]), float(st["S_unw"][j])
        null = np.asarray(st["null_w2_max"], float)
        if "null_unw_undemeaned_argmax" not in st:
            raise PricingRefused("the precompute holds no un-demeaned argmax (point-estimate.md's m_b)")
        m_b = np.asarray(st["null_unw_undemeaned_argmax"], np.int64)
        eb = S_u - float(np.mean(np.asarray(st["null_unw_undemeaned_S_at_argmax"], float)
                                 - np.asarray(st["S_unw"], float)[m_b]))
        out.update({"member_index": j, "tier": "class (W2)",
                    "EB": {"value": eb, "label": "EB of prereg/point-estimate.md (m_b and S*_b(m_b) on the "
                                                 "un-demeaned unweighted replicates, seed 721002); unweighted, descriptive"}})
    else:
        S_w, S_u = float(sn["S_w"]), float(sn["S_unw"])
        null = np.asarray(sn["null_w2"], float)
        both = np.maximum(np.asarray(st["null_w2_max"], float), null)
        out.update({"tier": "supplied streams (W2)", "EB": None,
                    "selection_aware": {"p": tier_p(S_w, both),
                                        "label": "selection-aware (approximate, independent draws): the class W2 "
                                                 "maxima (seed 721002) and Sancho's W2 null (seed 721000) were not "
                                                 "drawn on shared index sets; descriptive, not a certificate"},
                    "turnover_mean": float(sn["turnover_mean"])})
    p = tier_p(S_w, null)
    a96, a90 = ALPHA[kind]
    out.update({"S_w": S_w, "S_unw": S_u, "p": p,
                "certified": {"96%": bool(p < a96), "90%": bool(p < a90)},
                "alphas": {"96%": a96, "90%": a90, "90% label": "90% level, labelled"},
                "L90": S_w - float(np.quantile(null, 0.90))})
    return out


def replay(d: dict, sub: dict, pre: dict, B: int = CERTIFY_B) -> dict:
    """6.5's trigger replay on the session's logged grammar search, or the reason it is not
    computed. Never invented."""
    if sub["kind"] != "rule":
        return {"status": "not applicable", "reason": "a Sancho submission is not a class search"}
    if pre["base"] is None:
        return {"status": "not computed", "reason": "the precompute holds no base_columns.npy, which certify needs"}
    try:
        from experiments.price_runs import rebuild_session_log
        log = rebuild_session_log(d)
    except Exception as e:                                        # noqa: BLE001
        return {"status": "not computed", "reason": f"the log could not be rebuilt: {type(e).__name__}: {e}"}
    if log is None:
        return {"status": "not computed", "reason": "the log holds no grammar session_log"}
    from environments.class_table import ClassTable
    from environments.planted_panel import CLS
    from experiments.agent_backend import certify_log
    table = ClassTable(streams=pre["scored"], members=pre["members"], index=index_of(pre["members"]),
                       panel_hash="etf-recent-precompute", periods_per_year=252.0)
    base = np.asarray(pre["base"], float)
    sandbox = types.SimpleNamespace(base_feature_columns=lambda: base, periods_per_year=252.0)
    st = events_of(d, "start")
    rec = types.SimpleNamespace(seed=int(st[0].get("seed", 0)) if st else 0, verdict=None,
                                certifying_null_computable=None, notes=[])
    rec.log = lambda kind, **kw: rec.notes.append({"kind": kind, **kw})
    certify_log(rec, log, sandbox, CLS, table=table, B=B)
    if not rec.certifying_null_computable:
        return {"status": "not computed", "reason": "certify raised", "notes": rec.notes}
    return {"status": "computed", "verdict": rec.verdict}


def price_all(log_dir: Path, pre: dict, submissions: dict, B: int = CERTIFY_B) -> dict:
    idx = index_of(pre["members"])
    logs = {}
    for p in sorted(Path(log_dir).glob("*.json")):
        if p.name == "run_config.json":
            continue
        d = json.loads(p.read_text())
        from experiments.agent_cell_etf_recent_collect import session_id
        logs[session_id(p, d)] = d
    rows = []
    for sub in submissions["submissions"]:
        d = logs.get(sub["session"])
        if d is None:
            raise PricingRefused(f"session {sub['session']} has no committed log")
        r = price(sub, pre, idx)
        last = last_submission(d)
        r["log_consistency"] = {
            "S_w_matches": last.get("candidate_S_w") is None or abs(float(last["candidate_S_w"]) - r["S_w"]) < 5e-4,
            "S_unw_matches": last.get("candidate_S_unw") is None or abs(float(last["candidate_S_unw"]) - r["S_unw"]) < 5e-4,
            "L90_shown_matches": (last.get("L90_shown") is None) or abs(float(last["L90_shown"]) - r["L90"]) < 5e-4}
        if sub["arm"] == "A" and last.get("L90_shown") is not None:
            raise PricingRefused(f"session {sub['session']}: arm A was shown an L90")
        r["search"] = search_length(d)
        r["flags"] = ["non-grammar look (Sancho) taken"] if sub["kind"] == "rule" and sancho_look_before_submit(d) else []
        r["replay"] = replay(d, sub, pre, B)
        rows.append(r)
    st, sn = pre["stats"], pre["sancho"]
    return {"precompute_manifest_sha256": pre["manifest_sha256"], "n_sessions": submissions["sessions"],
            "no_submit": submissions["no_submit"], "priced": rows,
            "nulls": {"class_w2_max": np.asarray(st["null_w2_max"], float).tolist(),
                      "class_unw_max": np.asarray(st["null_unw_max"], float).tolist(),
                      "sancho_w2": np.asarray(sn["null_w2"], float).tolist()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True)
    ap.add_argument("--precompute", required=True)
    ap.add_argument("--submissions", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists; pricing is written once")
    try:
        sub_path = Path(a.submissions)
        submissions = json.loads(sub_path.read_text())
        pre = load_precompute(Path(a.precompute))
        rec = price_all(Path(a.logs), pre, submissions)
    except PricingRefused as e:
        raise SystemExit(f"REFUSED: {e}")
    rec["submissions_sha256"] = sha_file(sub_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1, default=float))
    print(f"priced {len(rec['priced'])} submissions ({len(rec['no_submit'])} no_submit) -> {out}; "
          f"SHA-256 {sha_file(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
