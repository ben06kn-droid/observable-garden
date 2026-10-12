"""The agent cell on the ETF recent panel (`prereg/agent-cell-etf-recent.md`, sections 0 and 6):
PRICING, from committed session logs and the pinned precompute only. Nothing is refitted and no
holdout value exists here.

**The primary statistic is the UNWEIGHTED net Sharpe** (section 0): the certificate, L90, EB, the
replay tier and the selection-aware line. Every W2-weighted counterpart is printed beside,
labelled "recency-weighted, descriptive". (The parent panel's scripted certificate stays W2; it
is not priced here.)

The precompute (`<run>/precompute/`, written by the BOX-ETF read) is checked file by file
against its manifest's SHA-256 before anything is read:
- `sancho_d1.npz`: the model stream (d = 1) on the scored rows, its turnover, S_w, S_unw, its
  W2 null `null_w2` and its unweighted null `null_unw` (seed 721000);
- `class_scored.npy`: (N, T_scored) net streams of the 82,240 members, in
  `members_in_order(CLS, 40)` order;
- `class_stats.npz`: every member's S_w and S_unw; the class's W2 and unweighted null maxima;
  the un-demeaned unweighted replicate argmax m_b and S*_b(m_b) (EB); `joint_unw_max`, the
  class's unweighted maxima joint with the model stream's demeaned replicate on the same draws
  (seed 721002);
- `base_columns.npy`: the scored rows' base feature columns, which the replay tier needs.

Per submission (section 6's table):
- S (unweighted, primary) and S_w beside;
- the certificate, unweighted: a rule on the **class tier**, p = (1 + #{null_unw_max >= S}) /
  (B + 1), 96% iff p < 0.01 (90% iff p < 0.02, labelled); the model stream on the
  **supplied-streams tier**, p against its own unweighted null, 96% iff p < 0.03 (90% iff
  p < 0.06, labelled); `p_w2` beside on the W2 nulls;
- `L90` = S - the unweighted null's 0.90 quantile (what arm B was shown, and what is graded);
  `L90_w2` beside;
- EB (rules only; unweighted; descriptive), defined in full in the registration's section 6:
  S - mean_b[S*_b(m_b) - S(m_b)];
- the replay tier (6.5's trigger replay through `experiments.agent_backend.certify_log`) on the
  session's logged grammar search; a rule submitted after a `baseline_model()` call is flagged
  "a non-grammar look (the model stream) was taken";
- for a model-stream submission, the selection-aware line: p of S under the joint null of the
  session's search and the model stream on SHARED day-index draws -- the replayed search's
  trigger null (`quixote.certify.three_nulls`, its draws regenerated from its seed and block
  length) against the model stream's demeaned replicate Sharpe; where no grammar search was
  logged or a trigger was changed, the class envelope `joint_unw_max`, so labelled;
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

REGISTRATION = "00c7af167f8ddb9a4874cc29b438926112360fb9"  # prereg/agent-cell-etf-recent.md, live


def registration_refusals(precompute: Path) -> list[str]:
    """Pricing runs only under the live registration, on the pinned precompute."""
    import subprocess
    from experiments.agent_cell_etf_recent import PRECOMPUTE_MANIFEST_SHA256
    bad = []
    if subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION, "HEAD"], capture_output=True).returncode:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    man = Path(precompute) / "manifest.json"
    if not man.exists() or hashlib.sha256(man.read_bytes()).hexdigest() != PRECOMPUTE_MANIFEST_SHA256:
        bad.append("the precompute manifest is missing or not its pinned SHA-256")
    return bad

ALPHA = {"rule": (0.01, 0.02), "baseline_model": (0.03, 0.06)}
W2_LABEL = "recency-weighted, descriptive"
MODEL_LOOK_FLAG = "a non-grammar look (the model stream) was taken"
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


def model_look_before_submit(d: dict) -> bool:
    """A `baseline_model()` call before the candidate was fixed (the `candidate` event)."""
    evs = d.get("events", [])
    at = next((i for i, e in enumerate(evs) if e.get("kind") == "candidate"),
              next((i for i, e in enumerate(evs) if e.get("kind") == "submit"), len(evs)))
    return any(e.get("kind") == "baseline_model_call"
               or (e.get("kind") == "tool_result" and tool_name(e) == "baseline_model") for e in evs[:at])


# -- one submission -----------------------------------------------------------------------

def tier_p(S: float, null: np.ndarray) -> float:
    null = np.asarray(null, float)
    return float((1 + int(np.sum(null >= S))) / (null.size + 1))


def price(sub: dict, pre: dict, idx: dict) -> dict:
    from environments.class_table import canonical
    st, sn = pre["stats"], pre["sancho"]
    kind = sub["kind"]
    if kind not in ALPHA:
        raise PricingRefused(f"session {sub['session']}: unknown submission kind {kind!r}")
    out = {"session": sub["session"], "arm": sub["arm"], "kind": kind, "support": sub["support"],
           "predict": sub["predict"]}
    if kind == "rule":
        key = canonical(sub["support"])
        if key not in idx:
            raise PricingRefused(f"session {sub['session']}: support {key} is not a class member")
        j = idx[key]
        S_w, S = float(st["S_w"][j]), float(st["S_unw"][j])
        null, null_w2 = np.asarray(st["null_unw_max"], float), np.asarray(st["null_w2_max"], float)
        if "null_unw_undemeaned_argmax" not in st:
            raise PricingRefused("the precompute holds no un-demeaned argmax (EB's m_b)")
        m_b = np.asarray(st["null_unw_undemeaned_argmax"], np.int64)
        eb = S - float(np.mean(np.asarray(st["null_unw_undemeaned_S_at_argmax"], float)
                               - np.asarray(st["S_unw"], float)[m_b]))
        out.update({"member_index": j, "tier": "class (unweighted)",
                    "EB": {"value": eb, "label": "EB (registration section 6): m_b and S*_b(m_b) on the un-demeaned "
                                                 "unweighted replicates, seed 721002; unweighted, descriptive"}})
    else:
        S_w, S = float(sn["S_w"]), float(sn["S_unw"])
        if "null_unw" not in sn:
            raise PricingRefused("the precompute holds no unweighted null for the model stream")
        null, null_w2 = np.asarray(sn["null_unw"], float), np.asarray(sn["null_w2"], float)
        out.update({"tier": "supplied streams (unweighted)", "EB": None, "turnover_mean": float(sn["turnover_mean"])})
    p, p_w2 = tier_p(S, null), tier_p(S_w, null_w2)
    a96, a90 = ALPHA[kind]
    out.update({"S": S, "S_w": S_w, "S_w_label": W2_LABEL, "p": p,
                "certified": {"96%": bool(p < a96), "90%": bool(p < a90)},
                "alphas": {"96%": a96, "90%": a90, "90% label": "90% level, labelled"},
                "L90": S - float(np.quantile(null, 0.90)),
                "p_w2": p_w2, "certified_w2": {"96%": bool(p_w2 < a96), "90%": bool(p_w2 < a90)},
                "L90_w2": S_w - float(np.quantile(null_w2, 0.90)), "w2_label": W2_LABEL})
    return out


def model_replicates(stream: np.ndarray, draws, ppy: float = 252.0) -> np.ndarray:
    """The model stream's demeaned replicate Sharpe on each draw: the class table scorer's own
    convention (`environments.class_table.ClassTable.sharpe(..., demeaned=True)`): subtract the
    full-sample mean, take the rows, mean / std(ddof 1) * sqrt(ppy)."""
    x0 = np.asarray(stream, float) - float(np.mean(stream))
    out = np.empty(len(draws))
    for b, i in enumerate(draws):
        y = x0[i]
        sd = float(y.std(ddof=1))
        out[b] = float(y.mean() / sd * np.sqrt(ppy)) if sd > 0 else 0.0
    return out


def replay_draws(T: int, L: int, seed, B: int) -> list:
    """`quixote.certify.three_nulls`' day-index draws, regenerated: one generator seeded by
    `seed`, one `stationary_bootstrap_indices(T, L, rng)` call per replicate, nothing else drawn
    from it."""
    from estimator.bootstrap import stationary_bootstrap_indices
    rng = np.random.default_rng(seed)
    return [stationary_bootstrap_indices(T, L, rng) for _ in range(B)]


def selection_aware(d: dict, sub: dict, pre: dict, B: int = CERTIFY_B) -> dict:
    """For a model-stream submission: the p of S under the joint null of the session's search and
    the model stream, on shared draws. Falls back to the class envelope where the session's own
    search cannot be replayed."""
    sn, st = pre["sancho"], pre["stats"]
    S = float(sn["S_unw"])
    reason = None
    log = None
    if pre["base"] is None:
        reason = "no base_columns.npy"
    else:
        try:
            from experiments.price_runs import rebuild_session_log
            log = rebuild_session_log(d)
        except Exception as e:                                    # noqa: BLE001
            reason = f"the log could not be rebuilt: {type(e).__name__}"
        if reason is None and (log is None or not getattr(log, "records", None)):
            reason = "no grammar move logged"
        if reason is None and list(getattr(log, "trigger_changes", ()) or ()):
            reason = "a trigger was changed (DEPENDS_ON_JUDGMENT)"
    if reason is None:
        try:
            from environments.planted_panel import CLS
            from quixote.certify import three_nulls
            table = class_table(pre)
            base = np.asarray(pre["base"], float)
            seed = session_seed(d)
            nulls, _ = three_nulls(log, CLS, base, float(np.sqrt(252.0)), B, None, seed, table=table)
            draws = replay_draws(base.shape[0], int(nulls.block_length), seed, B)
            joint = np.maximum(np.asarray(nulls.trigger, float), model_replicates(sn["stream"], draws))
            return {"p": tier_p(S, joint), "basis": "the session's own search (replayed trigger null) and the model "
                    "stream, on shared draws", "B": B, "block_length": int(nulls.block_length), "seed": seed,
                    "label": "selection-aware, descriptive, not a certificate"}
        except Exception as e:                                    # noqa: BLE001
            reason = f"the replay raised: {type(e).__name__}: {e}"
    joint = np.asarray(st["joint_unw_max"], float)
    return {"p": tier_p(S, joint), "basis": "class envelope, not the session's own search", "reason": reason,
            "B": int(joint.size), "seed": 721002, "label": "selection-aware, descriptive, not a certificate"}


def class_table(pre: dict):
    from environments.class_table import ClassTable
    return ClassTable(streams=pre["scored"], members=pre["members"], index=index_of(pre["members"]),
                      panel_hash="etf-recent-precompute", periods_per_year=252.0)


def session_seed(d: dict) -> int:
    st = events_of(d, "start")
    return int(st[0].get("seed", 0)) if st else 0


def replay(d: dict, sub: dict, pre: dict, B: int = CERTIFY_B) -> dict:
    """6.5's trigger replay on the session's logged grammar search, or the reason it is not
    computed. Never invented."""
    if sub["kind"] != "rule":
        return {"status": "not applicable", "reason": "a model-stream submission is not a class search"}
    if pre["base"] is None:
        return {"status": "not computed", "reason": "the precompute holds no base_columns.npy, which certify needs"}
    try:
        from experiments.price_runs import rebuild_session_log
        log = rebuild_session_log(d)
    except Exception as e:                                        # noqa: BLE001
        return {"status": "not computed", "reason": f"the log could not be rebuilt: {type(e).__name__}: {e}"}
    if log is None:
        return {"status": "not computed", "reason": "the log holds no grammar session_log"}
    from environments.planted_panel import CLS
    from experiments.agent_backend import certify_log
    table = class_table(pre)
    base = np.asarray(pre["base"], float)
    sandbox = types.SimpleNamespace(base_feature_columns=lambda: base, periods_per_year=252.0)
    rec = types.SimpleNamespace(seed=session_seed(d), verdict=None,
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
            "S_unw_matches": last.get("candidate_S_unw") is None or abs(float(last["candidate_S_unw"]) - r["S"]) < 5e-4,
            "L90_shown_matches": (last.get("L90_shown") is None) or abs(float(last["L90_shown"]) - r["L90"]) < 5e-4}
        if sub["arm"] == "A" and last.get("L90_shown") is not None:
            raise PricingRefused(f"session {sub['session']}: arm A was shown an L90")
        r["search"] = search_length(d)
        r["flags"] = [MODEL_LOOK_FLAG] if sub["kind"] == "rule" and model_look_before_submit(d) else []
        r["replay"] = replay(d, sub, pre, B)
        if sub["kind"] == "baseline_model":
            r["selection_aware"] = selection_aware(d, sub, pre, B)
        rows.append(r)
    st, sn = pre["stats"], pre["sancho"]
    return {"precompute_manifest_sha256": pre["manifest_sha256"], "n_sessions": submissions["sessions"],
            "no_submit": submissions["no_submit"], "priced": rows,
            "nulls": {"class_unw_max": np.asarray(st["null_unw_max"], float).tolist(),
                      "model_unw": np.asarray(sn["null_unw"], float).tolist(),
                      "class_w2_max": np.asarray(st["null_w2_max"], float).tolist(),
                      "model_w2": np.asarray(sn["null_w2"], float).tolist()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True)
    ap.add_argument("--precompute", required=True)
    ap.add_argument("--submissions", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    bad = registration_refusals(Path(a.precompute))
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
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
