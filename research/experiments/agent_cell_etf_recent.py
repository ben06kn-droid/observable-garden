"""The agent cell on the ETF recent panel: its tools and its launcher
(`prereg/agent-cell-etf-recent.md`, DRAFT; prompts in `prereg/agent-cell-etf-recent-prompts.md`).

**What this module is.** A new surface built on the frozen 6.5 machinery, which it imports and
never edits:
- the grammar is `quixote.agent_adapter.ToolSession`;
- the run record is `experiments.agent_backend.RunRecord`;
- the model driver is `agent_backend._drive_model`, with its served-model assertion;
- the session log writer is `experiments.agent_cell.log_session`, so `price_runs`-style pricing
  can rebuild a log from the file;
- resumption follows `agent_cell.completion_of`.

**Everything an agent can learn comes from the precompute** (`<run>/precompute/`, written by the
BOX-ETF read): `manifest.json`, `sancho_d1.npz`, `class_scored.npy` and `class_stats.npz`.
- The grammar scores a support by **lookup**: the member's index in
  `members_in_order(CLS, 40)` gives its in-sample Sharpe on the scored window.
- **The statistic the moves optimise is the unweighted Sharpe** ("all years equal"). The
  W2-weighted one is shown beside it on every move.
- **The grammar's base** (used by `pick`'s other statistics and by the close-time self-check) is
  the 40 single-feature long members' scored net streams, from `class_scored.npy`.
- No tool reads any other file. No tool shows a name, a date, the panel's size, the arm, a
  p-value or a verdict (registration section 5).

**The new tools** (registration section 4):
- `baseline_model()`: the model stream's two Sharpes and its mean daily turnover, the same text each
  call;
- `submit_candidate(kind)`: fixes the candidate ("rule": the best support reached; "baseline_model").
  **In arm B only,** it adds the gate's UNWEIGHTED L90, S − quantile(null, 0.90): the class's
  unweighted null maxima for a rule, the model stream's own unweighted null for the model stream
  (registration section 0: the unweighted statistic is primary everywhere in the cell);
- `predict(mean, sd, note)`: required before `confirm`; sd ≥ 0;
- `confirm()`: ends the session and writes the `submit` event.

**The launcher refuses unless:**
- `REGISTRATION` is set and is an ancestor of HEAD;
- there are no tracked changes;
- the manifest's SHA-256 equals `PRECOMPUTE_MANIFEST_SHA256`;
- every precompute file's SHA-256 equals the manifest's.

Both constants are set (the registration is live at 00c7af1; the manifest is BOX-ETF's).
**The author launches every session, on the seat.**

**The output folder's own name (its last path component) decides smoke or cell.**
- A smoke's folder name must contain "smoke", for example
  `runs/agent_cell_etf_recent_smoke/2026-10-11-smoke`. A parent folder named `*_smoke` is not
  enough.
- A cell run's folder name must not contain it. The launcher refuses either mismatch.

The cell, 120 sessions per arm (amendment 2):

    python -m experiments.agent_cell_etf_recent --precompute runs/etf_recent/<D>/precompute \\
        --arm both --runs 120 --credential seat --workers 4 --out runs/agent_cell_etf_recent/<D>

The smoke:

    python -m experiments.agent_cell_etf_recent --precompute runs/etf_recent/<D>/precompute \\
        --arm both --runs 5 --credential seat --workers 4 \\
        --out runs/agent_cell_etf_recent_smoke/<D>-smoke --smoke
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import numpy as np

REGISTRATION: str | None = "00c7af167f8ddb9a4874cc29b438926112360fb9"  # prereg/agent-cell-etf-recent.md, live
PRECOMPUTE_MANIFEST_SHA256: str | None = "78583e9b2fdadad7ef64bb6cd1b08b0a0ca9879a15ea84f165a20d2e705b0ae2"  # BOX-ETF, 05642cf
PROMPTS = Path(__file__).resolve().parent.parent / "prereg" / "agent-cell-etf-recent-prompts.md"
FILES = ("sancho_d1.npz", "class_scored.npy", "class_stats.npz")
LAST_IN_SAMPLE = dt.date(2024, 12, 31)
K = 40
ARMS = ("A", "B")
MASTERS = {"A": 20261011, "B": 20261012}      # registration section 11
SMOKE_MASTER = 723100
SMOKE_RUNS = 5
PER_ARM = 120                                  # amendment 2 (was 40)
GRAMMAR_TOOLS = ("pick_prior", "declare_triggers", "change_trigger", "init", "extend_best",
                 "swap_worst", "flip", "refine", "pick", "stop", "restart")
CELL_TOOLS = ("baseline_model", "submit_candidate", "predict", "confirm")
TOOLS = GRAMMAR_TOOLS + CELL_TOOLS
# The cell's own refusal kinds (the grammar's are agent_backend.REFUSAL_KINDS).
CELL_REFUSALS = ("candidate_fixed", "no_candidate", "bad_kind", "bad_sd", "predict_required",
                 "candidate_required", "after_confirm")


class Refused(RuntimeError):
    pass


# -- the prompts ------------------------------------------------------------------------------

def read_prompts(path: Path = PROMPTS) -> dict:
    """{"system": text, "tool:<name>": description}, read verbatim from the prereg file."""
    text = path.read_text()
    blocks = dict(re.findall(r"^### (\S+)\n+```\n(.*?)\n```", text, re.S | re.M))
    missing = ["system"] + [f"tool:{t}" for t in TOOLS if f"tool:{t}" not in blocks]
    missing = [m for m in missing if m not in blocks]
    if missing:
        raise SystemExit(f"{path.name} lacks blocks: {missing}")
    return blocks


def system_prompt(arm: str, prompts: dict | None = None) -> str:
    """Byte-identical for both arms: the arm is not an input to the text."""
    if arm not in ARMS:
        raise ValueError(arm)
    return (prompts or read_prompts())["system"]


# -- the precompute ---------------------------------------------------------------------------

def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Precompute:
    """The pinned files and nothing else. Refuses a file whose SHA-256 is not the manifest's,
    and any date after 2024-12-31."""

    def __init__(self, d: Path, check_hashes: bool = True):
        from environments.class_table import members_in_order
        from environments.planted_panel import CLS
        self.dir = Path(d)
        self.manifest = json.loads((self.dir / "manifest.json").read_text())
        if check_hashes:
            bad = [f for f in FILES if self.manifest.get("sha256", {}).get(f) != _sha(self.dir / f)]
            if bad:
                raise Refused(f"precompute files not their manifest SHA-256: {bad}")
        s = np.load(self.dir / "sancho_d1.npz", allow_pickle=False)
        c = np.load(self.dir / "class_stats.npz", allow_pickle=False)
        dates = [dt.date.fromisoformat(str(x)) for x in s["earned_dates"]]
        last = self.manifest.get("last_earned")
        if (dates and max(dates) > LAST_IN_SAMPLE) or (last and dt.date.fromisoformat(last) > LAST_IN_SAMPLE):
            raise Refused("the precompute holds a date after 2024-12-31")
        self.model = {"S_w": float(s["S_w"]), "S_unw": float(s["S_unw"]),
                      "turnover": float(s["turnover_mean"]), "null_w2": np.asarray(s["null_w2"], float),
                      "null_unw": np.asarray(s["null_unw"], float)}
        self.S_w = np.asarray(c["S_w"], float)
        self.S_unw = np.asarray(c["S_unw"], float)
        self.class_null_w2 = np.asarray(c["null_w2_max"], float)
        self.class_null_unw = np.asarray(c["null_unw_max"], float)
        self.streams = np.load(self.dir / "class_scored.npy", mmap_mode="r")
        self.members = members_in_order(CLS, K)
        if not (len(self.members) == len(self.S_w) == len(self.S_unw) == self.streams.shape[0]):
            raise Refused("the precompute's member count is not the class's")
        self.index = {self._canon(m): i for i, m in enumerate(self.members)}
        singles = [self.index[((k, 1.0),)] for k in range(K)]
        self.base = np.asarray(self.streams[singles], float).T          # (T, 40)

    @staticmethod
    def _canon(support) -> tuple:
        return tuple(sorted(((int(k), float(s)) for k, s in support), key=lambda p: p[0]))

    def idx(self, support) -> int:
        try:
            return self.index[self._canon(support)]
        except KeyError:
            raise Refused("that rule is outside the declared class") from None

    def l90_rule(self, support) -> float:
        """The unweighted L90 (section 0): S − quantile(class unweighted null maxima, 0.90)."""
        return float(self.S_unw[self.idx(support)] - np.quantile(self.class_null_unw, 0.90))

    def l90_model(self) -> float:
        """The model stream's unweighted L90: S − quantile(its unweighted null, 0.90)."""
        return float(self.model["S_unw"] - np.quantile(self.model["null_unw"], 0.90))


def _two(S_unw: float, S_w: float) -> str:
    return f"Sharpe (all years equal) {S_unw:.3f}; Sharpe (recent years weighted) {S_w:.3f}"


# -- one session's tool layer -----------------------------------------------------------------

class CellSession:
    """The pure, synchronous tool surface of one session: `call(name, **kw) -> str`. The MCP
    wiring and the tests both go through it, so what a test checks is what an agent receives."""

    def __init__(self, pre: Precompute, arm: str, rec=None, max_turns: int = 60):
        from environments.planted_panel import CLS
        from quixote.agent_adapter import ToolSession
        from quixote.session import Session
        if arm not in ARMS:
            raise ValueError(arm)
        self.pre, self.arm, self.rec = pre, arm, rec
        score = lambda support, statistic="sharpe": self._score(support, statistic)
        sess = Session(CLS, pre.base, float(np.sqrt(252.0)), score_fn=score)
        self.tools = ToolSession(sess, max_turns=max_turns)
        self.candidate = None            # {"kind", "support", "S_w", "S_unw", "L90"}
        self.prediction = None
        self.confirmed = False
        self.outputs: list[str] = []

    def _score(self, support, statistic):
        if statistic != "sharpe":
            raise ValueError(f"unknown statistic {statistic!r}; scoring is Sharpe")
        return float(self.pre.S_unw[self.pre.idx(support)])

    # -- routing -----------------------------------------------------------------------------

    def call(self, name: str, **kw) -> str:
        if self.rec is not None:
            self.rec.n_tool_calls += 1
        try:
            if self.confirmed:
                raise Refused("after_confirm: the session is over")
            if name in GRAMMAR_TOOLS:
                text = self._grammar(name, **kw)
            elif name in CELL_TOOLS:
                text = getattr(self, f"_{name}")(**kw)
            else:
                raise Refused(f"unknown tool {name!r}")
        except Exception as e:                                          # refusals go back as text
            text = f"Refused: {e}"
            if self.rec is not None:
                self._note_refusal(name, str(e))
            self.outputs.append(text)
            return text
        if self.rec is not None:
            self.rec.moves[name] = self.rec.moves.get(name, 0) + 1
            self.rec.log("tool_result", tool=name, args=kw, text=text, ok=True)
        self.outputs.append(text)
        return text

    def _note_refusal(self, tool: str, message: str) -> None:
        from experiments.agent_backend import classify_refusal
        head = message.split(":", 1)[0].strip()
        kind = head if head in CELL_REFUSALS else classify_refusal(message)
        self.rec.refusals.append({"tool": tool, "kind": kind, "message": message})
        self.rec.log("refusal", tool=tool, refusal_kind=kind, message=message)

    def _grammar(self, name: str, **kw) -> str:
        if self.candidate is not None:
            raise Refused("candidate_fixed: the candidate is fixed; only predict and confirm remain")
        if name == "pick_prior":
            kw = {"support": [[int(f), float(s)] for f, s in
                              zip(kw.get("features", []), kw.get("signs") or [1] * len(kw.get("features", [])))],
                  "reason": str(kw.get("reason", ""))}
        res = self.tools.call(name, **kw)
        text = res.text
        st = self.tools.session
        if res.ok and name in ("init", "extend_best", "swap_worst", "flip", "refine", "pick", "restart") and st.support:
            i = self.pre.idx(st.support)
            text = f"{text} | {_two(self.pre.S_unw[i], self.pre.S_w[i])}"
        return text

    # -- the cell's own tools ----------------------------------------------------------------

    def _baseline_model(self) -> str:
        s = self.pre.model
        if self.rec is not None:
            self.rec.log("baseline_model_call")
        return f"Baseline model stream: {_two(s['S_unw'], s['S_w'])}; mean daily turnover {s['turnover']:.3f}."

    def _submit_candidate(self, kind: str = "") -> str:
        if self.candidate is not None:
            raise Refused("candidate_fixed: a candidate is already fixed")
        if kind not in ("rule", "baseline_model"):
            raise Refused('bad_kind: kind must be "rule" or "baseline_model"')
        st = self.tools.session
        if kind == "rule":
            support, _ = st.submission()
            if not support:
                raise Refused("no_candidate: no rule has been reached yet")
            i = self.pre.idx(support)
            cand = {"kind": "rule", "support": [[int(k), float(s)] for k, s in self.pre._canon(support)],
                    "S_w": float(self.pre.S_w[i]), "S_unw": float(self.pre.S_unw[i]),
                    "L90": self.pre.l90_rule(support)}
        else:
            s = self.pre.model
            cand = {"kind": "baseline_model", "support": None, "S_w": s["S_w"], "S_unw": s["S_unw"],
                    "L90": self.pre.l90_model()}
        if not self.tools.submitted:                 # closes the grammar session; its log is kept
            try:
                self.tools.call("submit")
            except Exception:                        # noqa: BLE001 - nothing searched: nothing to close
                pass
        if self.rec is not None:
            self.rec.log("candidate", candidate_kind=cand["kind"], support=cand["support"])
        self.candidate = cand
        head = "rule " + _support(cand["support"]) if kind == "rule" else "the baseline model stream"
        text = f"Candidate fixed: {head}. {_two(cand['S_unw'], cand['S_w'])}."
        if self.arm == "B":
            text += f"\nGate's 90% lower bound for this candidate: L90 = {cand['L90']:.3f}."
        return text

    def _predict(self, mean=None, sd=None, note: str = "") -> str:
        if self.candidate is None:
            raise Refused("candidate_required: call submit_candidate first")
        try:
            m, s = float(mean), float(sd)
        except (TypeError, ValueError):
            raise Refused("bad_sd: mean and sd must be numbers") from None
        if not np.isfinite(m) or not np.isfinite(s) or s < 0:
            raise Refused("bad_sd: sd must be a finite number >= 0")
        self.prediction = {"mean": m, "sd": s, "note": str(note)}
        self.tools.session.predict(m, s, str(note))
        if self.rec is not None:
            self.rec.prediction = {"mean": m, "sd": s}
        return f"prediction {m:.3f} (sd {s:.3f}) recorded"

    def _confirm(self) -> str:
        if self.candidate is None:
            raise Refused("candidate_required: call submit_candidate first")
        if self.prediction is None:
            raise Refused("predict_required: call predict first")
        self.confirmed = True
        if self.rec is not None:
            self.rec.submitted = True
            self.rec.submitted_support = self.candidate["support"]
            self.rec.submitted_sharpe = self.candidate["S_unw"]
            # `RunRecord.log` takes the event kind positionally, so the submission's own
            # fields (which include "kind") are nested under "submission"
            self.rec.log("submit", submission=submit_event(self))
        return "confirmed; the session is over"


def _support(support) -> str:
    return "[" + ", ".join(f"{int(k)}{'+' if s > 0 else '-'}" for k, s in support) + "]"


def submit_event(cell: CellSession) -> dict:
    """The final `submit` event's `submission` field (registration section 4; read by the
    collector and pricing): {"arm", "kind", "support", "predict", "candidate_S_w",
    "candidate_S_unw", "L90_shown"}."""
    c = cell.candidate
    return {"arm": cell.arm, "kind": c["kind"], "support": c["support"],
            "predict": dict(cell.prediction), "candidate_S_w": c["S_w"], "candidate_S_unw": c["S_unw"],
            "L90_shown": c["L90"] if cell.arm == "B" else None}


# -- MCP wiring (model runs only; never in tests) ---------------------------------------------

def mcp_handlers(cell: CellSession, prompts: dict) -> list:
    from claude_agent_sdk import tool
    schemas = {"init": {}, "extend_best": {}, "swap_worst": {}, "refine": {},
               "flip": {"feature": int},
               "pick": {"among": list[int], "statistic": str, "choice": int},
               "stop": {"trigger": str, "param": float},
               "restart": {"trigger": str, "param": float},
               "declare_triggers": {"triggers": list},
               "change_trigger": {"trigger": str, "param": float, "action": str, "reason": str},
               "pick_prior": {"features": list[int], "signs": list[int], "reason": str},
               "baseline_model": {}, "submit_candidate": {"kind": str},
               "predict": {"mean": float, "sd": float, "note": str}, "confirm": {}}
    out = []
    for name in TOOLS:
        def make(n):
            @tool(n, prompts[f"tool:{n}"], schemas[n])
            async def fn(args, _n=n):
                return {"content": [{"type": "text", "text": cell.call(_n, **_args_for(_n, args))}]}
            return fn
        out.append(make(name))
    return out


def _args_for(name: str, args: dict) -> dict:
    a = dict(args or {})
    if name == "flip":
        return {"feature": int(a.get("feature", -1))}
    if name == "pick":
        kw = {"among": a.get("among", []), "statistic": a.get("statistic", "sharpe")}
        if a.get("choice") is not None:
            kw["choice"] = int(a["choice"])
        return kw
    if name in ("stop", "restart"):
        return {"trigger": str(a.get("trigger", "")), "param": float(a.get("param", 0.0))}
    if name == "change_trigger":
        return {"trigger": str(a.get("trigger", "")), "param": float(a.get("param", 0.0)),
                "action": str(a.get("action", "stop")), "reason": str(a.get("reason", ""))}
    return a


def model_driver(cell: CellSession, rec, prompt: str, prompts: dict) -> None:
    from experiments import agent_backend as AB
    AB._drive_model(cell.arm, rec, mcp_handlers(cell, prompts), None, None, K, prompt=prompt)
    rec.endpoint = AB._served_model_assertion(rec)


# -- one run ----------------------------------------------------------------------------------

def run_session(pre: Precompute, arm: str, seed: int, index: int, prompts: dict, *,
                credential: str = "seat", driver=None, smoke: bool = False):
    """One session; `driver(cell, rec, prompt, prompts)` plays the agent (the model, or a scripted
    stand-in in tests). Returns the run record."""
    from experiments.agent_backend import MAX_TURNS, RunRecord
    from experiments.agent_cell import log_session
    rec = RunRecord(run_id=run_id_for(arm, seed, index, smoke), arm=arm, seed=seed)
    rec.credential = credential
    rec.log("start", arm=arm, index=index, seed=seed, smoke=smoke,
            precompute_manifest_sha256=_sha(pre.dir / "manifest.json"))
    cell = CellSession(pre, arm, rec, max_turns=MAX_TURNS)
    prompt = system_prompt(arm, prompts)
    (driver or model_driver)(cell, rec, prompt, prompts)
    if not cell.confirmed and not rec.no_submit:
        rec.no_submit = True
        rec.log("no_submit", detail="ended without confirm" if rec.error is None else f"error: {rec.error}")
    log_session(rec, cell.tools)
    if not cell.confirmed:
        rec.submitted, rec.submitted_support, rec.submitted_sharpe = False, None, None
    rec.log("end")
    return rec


# -- retries and workers (registration section 3: an execution detail) -------------------------

# A model-service error, not the agent's behaviour: retried on the same session and seed, never
# counted as a new session. A `no_submit` (max turns, or no confirm) carries no such error and is
# never retried.
TRANSIENT = re.compile(r"rate.?limit|\b429\b|\b529\b|\b50[23]\b|overloaded|timed? ?out|timeout|"
                       r"connection|temporar|ECONNRESET|server.?error|api.?error", re.I)
MAX_ATTEMPTS = 5
BACKOFF_S = (60, 120, 240, 480)


def is_transient(error) -> bool:
    return bool(error) and bool(TRANSIENT.search(str(error)))


class RetriesExhausted(RuntimeError):
    """A session's transient-error retries ran out: it is not written; the launcher stops
    (amendment 1) and a resume reruns it on the same index and seed."""


def _attempts_path(out, run_id: str) -> Path:
    return Path(out) / f"{run_id}.attempts.json"


def run_with_retry(pre, arm: str, seed: int, index: int, prompts: dict, *, credential="seat",
                   driver=None, smoke=False, sleep=time.sleep, out=None):
    """The session, retried on a transient model-service error with the same seed, at most
    MAX_ATTEMPTS times. Failed attempts are kept under `retried_attempts` in the final record (and
    carried across a stop in `<run_id>.attempts.json` when `out` is given). If the retries run out,
    raises RetriesExhausted and nothing is written for the session (amendment 1). A `no_submit` or a
    non-transient error is final."""
    rid = run_id_for(arm, seed, index, smoke)
    side = _attempts_path(out, rid) if out is not None else None
    tried = json.loads(side.read_text()) if side is not None and side.exists() else []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        rec = run_session(pre, arm, seed, index, prompts, credential=credential, driver=driver, smoke=smoke)
        if not is_transient(getattr(rec, "error", None)):
            break
        tried.append({"attempt": len(tried) + 1, "error": str(rec.error), "events": rec.events})
        if side is not None:
            side.write_text(json.dumps(tried, default=str))
        if attempt == MAX_ATTEMPTS:
            raise RetriesExhausted(f"{rid}: {MAX_ATTEMPTS} attempts failed with a transient error "
                                   f"({tried[-1]['error']}); nothing written for this session")
        sleep(BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)])
    if tried:
        rec.events.insert(len(rec.events) - 1, {"t": time.time(), "kind": "retried_attempts", "attempts": tried})
    return rec


def _job(payload) -> str:
    """One session in this process: its own precompute handle, its own records. Module-level so a
    process pool can pickle it."""
    pre_dir, arm, index, seed, credential, smoke, out, driver = payload
    pre = Precompute(Path(pre_dir))
    rec = run_with_retry(pre, arm, seed, index, read_prompts(), credential=credential, driver=driver,
                         smoke=smoke, out=out)
    (Path(out) / f"{rec.run_id}.json").write_text(json.dumps(rec.to_json(), indent=1, default=str))
    side = _attempts_path(out, rec.run_id)
    if side.exists():
        side.unlink()                                  # merged into the session's own log
    return rec.run_id


def run_all(pre_dir: Path, todo: list, out: Path, *, workers: int = 1, credential="seat", smoke=False,
            driver=None) -> list[str]:
    """Every scheduled session. The list and its seeds are fixed before this is called; workers only
    change how many run at once."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    jobs = [(str(pre_dir), a, i, s, credential, smoke, str(out), driver) for a, i, s in todo]
    n = len(jobs)
    if workers <= 1:
        done = []
        for k, j in enumerate(jobs, 1):
            done.append(_job(j))
            print(f"  {done[-1]} done ({k}/{n})", flush=True)
        return done
    # each session is reported the moment it finishes (2026-10-11: the first version printed only
    # after all sessions had finished); the returned list stays in schedule order
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(_job, j): k for k, j in enumerate(jobs)}
        out_ids = [None] * n
        for m, f in enumerate(as_completed(futs), 1):
            out_ids[futs[f]] = f.result()
            print(f"  {out_ids[futs[f]]} done ({m}/{n})", flush=True)
    return out_ids


# -- planning, resumption, refusals -----------------------------------------------------------

def run_id_for(arm: str, seed: int, index: int, smoke: bool = False) -> str:
    return f"{'smoke' if smoke else 'cellE'}_{index}_{arm}_{seed}"


def schedule(arm: str, runs: int, smoke: bool = False) -> list[tuple[str, int, int]]:
    """(arm, index, seed), interleaved A0, B0, A1, B1, ... and fixed by index."""
    if smoke:
        seeds = [int(s) for s in np.random.default_rng(SMOKE_MASTER).integers(0, 2**31 - 1, size=SMOKE_RUNS)]
        return [(ARMS[i % 2], i, seeds[i]) for i in range(min(runs, SMOKE_RUNS))]
    seeds = {a: [int(s) for s in np.random.default_rng(MASTERS[a]).integers(0, 2**31 - 1, size=PER_ARM)]
             for a in ARMS}
    arms = ARMS if arm == "both" else (arm,)
    return [(a, i, seeds[a][i]) for i in range(min(runs, PER_ARM)) for a in arms]


def plan(out: Path, arm: str, runs: int, smoke: bool = False) -> dict:
    """Resume per run id, as `agent_cell`: complete files are skipped, partial ones deleted and
    redone. Decided before anything starts."""
    from experiments.agent_cell import completion_of, is_complete
    todo, skipped, redone = [], [], []
    for a, i, s in schedule(arm, runs, smoke):
        path = Path(out) / f"{run_id_for(a, s, i, smoke)}.json"
        state = completion_of(path)
        if is_complete(state):
            skipped.append(path.stem)
            continue
        if state == "partial":
            path.unlink()
            redone.append(path.stem)
        todo.append((a, i, s))
    return {"todo": todo, "skipped": skipped, "redone": redone}


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def refusals(precompute: Path, out: Path, smoke: bool) -> list[str]:
    bad = []
    if REGISTRATION is None:
        bad.append("the registration is not live (REGISTRATION is unset)")
    elif _git("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode != 0:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    man = Path(precompute) / "manifest.json"
    if PRECOMPUTE_MANIFEST_SHA256 is None:
        bad.append("the precompute manifest is not pinned (PRECOMPUTE_MANIFEST_SHA256 is unset)")
    elif not man.exists() or _sha(man) != PRECOMPUTE_MANIFEST_SHA256:
        bad.append("the precompute manifest is missing or not its pinned SHA-256")
    elif man.exists():
        m = json.loads(man.read_text())
        wrong = [f for f in FILES if not (Path(precompute) / f).exists()
                 or m.get("sha256", {}).get(f) != _sha(Path(precompute) / f)]
        if wrong:
            bad.append(f"precompute files not their manifest SHA-256: {wrong}")
    if smoke != ("smoke" in Path(out).name):
        bad.append("the output folder's own name must contain 'smoke' for a smoke (e.g. "
                   "runs/agent_cell_etf_recent_smoke/<D>-smoke) and must not for a cell run")
    return bad


def main(argv=None) -> int:
    from experiments.agent_backend import MAX_TURNS, MODEL
    from experiments.code_state import code_state
    ap = argparse.ArgumentParser()
    ap.add_argument("--precompute", required=True)
    ap.add_argument("--arm", choices=("A", "B", "both"), default="both")
    ap.add_argument("--runs", type=int, required=True, help="sessions per arm (smoke: in all)")
    ap.add_argument("--credential", choices=("seat", "api"), default="seat")
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=1, help="sessions at once (registration: 4 on the seat)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    bad = refusals(Path(a.precompute), out, a.smoke)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    prompts = read_prompts()
    pre = Precompute(Path(a.precompute))
    out.mkdir(parents=True, exist_ok=True)
    p = plan(out, a.arm, a.runs, a.smoke)
    print(f"  {len(p['skipped'])} complete skipped; {len(p['redone'])} partial deleted and redone; "
          f"{len(p['todo'])} to run", flush=True)
    try:
        run_all(Path(a.precompute), p["todo"], out, workers=a.workers, credential=a.credential, smoke=a.smoke)
    except RetriesExhausted as e:
        print(f"STOPPED (amendment 1): {e}\n  resume with the same command; complete sessions are skipped "
              f"and this one reruns on its own seed", flush=True)
        return 2
    sched = schedule(a.arm, a.runs, a.smoke)
    (out / "run_config.json").write_text(json.dumps({
        "registration": REGISTRATION, "precompute_manifest_sha256": PRECOMPUTE_MANIFEST_SHA256,
        "prompts_sha256": _sha(PROMPTS), "model": MODEL, "max_turns": MAX_TURNS,
        "credential": a.credential, "smoke": a.smoke, "workers": a.workers,
        "masters": {"smoke": SMOKE_MASTER} if a.smoke else MASTERS,
        "schedule": [{"arm": x, "index": i, "seed": s, "run_id": run_id_for(x, s, i, a.smoke)} for x, i, s in sched],
        "resume": {"skipped_complete": p["skipped"], "deleted_partial": p["redone"]},
        "code_state": code_state(), "written": time.time()}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
