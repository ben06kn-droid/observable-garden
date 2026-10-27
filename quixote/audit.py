"""`quixote audit`: price a log the harness wrote.

Refuses, before computing anything, a log whose `class_sha256` differs from the class file it
is given, or whose `panel_sha256` differs from the panel file: a verdict priced against another
class or other data is not this search's verdict.

Then it re-executes the log's calls through a fresh harness (the harness is deterministic, so
a log it wrote reproduces call for call) and prices the search two ways:

- **the replay tier** (`quixote.certify`): the logged procedure re-run on bootstrap replicates
  of the panel, so the null accounts for the decisions the search took. Its status is the
  verdict;
- **the class tier**, beside it: the submitted rule's Sharpe against the maxima of the whole
  declared class on the same kind of replicates (`p_class`). It is the upper end of the bracket.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


class AuditRefused(ValueError):
    """The log cannot be priced against the files given."""


@dataclass
class AuditResult:
    status: str
    exit_code: int
    submitted_support: list
    submitted_feature_names: list
    submitted_sharpe: float
    p_replay: float | None
    p_class: float
    class_bar: float
    alpha: float
    B: int
    n_moves: int
    class_size: int
    reasons: list = field(default_factory=list)
    # The first replicates of the certifying null, step by step, only when asked for
    # (`audit_log(..., replicate_paths=n)`): what the search looks like re-grown on noise. Absent
    # otherwise, and left out of to_dict, so a default audit's output is unchanged.
    replicate_paths: list | None = None

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        if d["replicate_paths"] is None:
            del d["replicate_paths"]
        return d


def audit_log(log_path, panel_path, class_path, *, B: int = 2000, seed: int = 0,
              alpha: float | None = None, progress=None, replicate_paths: int = 0) -> AuditResult:
    """Price a log the harness wrote. `progress`, if given, is called as progress(stage, done,
    total) for the class tier ("class") and the replay ("replay"), at most every few hundred
    replicates; it only observes. `replicate_paths=n` also returns the first n replicates of the
    certifying null as paths (each held rule and its Sharpe on that replicate); it changes no
    number."""
    from quixote import classes, panel as P
    from quixote.certify import certify
    from quixote.run import ReplayMismatch, replay
    from quixote.verdict import EXIT_CODES
    log = json.loads(Path(log_path).read_text())
    if not str(log.get("format", "")).startswith("quixote-log/"):
        raise AuditRefused(f"{Path(log_path).name} is not a log the harness wrote")
    csha = classes.file_sha256(class_path)
    if log.get("class_sha256") != csha:
        raise AuditRefused(f"the log's class hash {str(log.get('class_sha256'))[:12]} is not the class "
                           f"file's {csha[:12]}: the search ran under a different class. A class "
                           "changed after results are seen is a search over classes.")
    psha = P.sha256(panel_path)
    if log.get("panel_sha256") != psha:
        raise AuditRefused(f"the log's panel hash {str(log.get('panel_sha256'))[:12]} is not the panel "
                           f"file's {psha[:12]}: the search ran on other data.")
    alpha = float(log.get("alpha", 0.05) if alpha is None else alpha)
    arrays = P.read(panel_path)
    lc = classes.load(class_path, arrays, compute_bar=False)
    try:
        h = replay(log, arrays, lc)
    except ReplayMismatch as e:
        raise AuditRefused(f"the log does not re-execute: {e}") from None
    session = h.tools.session
    support, score = session.submission()
    # the class tier: the submitted rule against the class maxima on bootstrap replicates
    from environments.class_table import ClassTable
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    base = h.sandbox.base_feature_columns()
    L = int(select_block_length(base - base.mean(axis=0)))
    rng = np.random.default_rng(seed)
    T = h.table.T
    if progress is not None:
        progress("class", 0, B)
    rows = [stationary_bootstrap_indices(T, L, rng) for _ in range(B)]
    M = h.table.null_max(rows)
    if progress is not None:
        progress("class", B, B)
    S = float(h.table.sharpe(support))
    p_class = float((1 + np.sum(M >= S)) / (B + 1))
    bar = float(np.quantile(M, 1 - alpha))
    ann = float(np.sqrt(h.panel.periods_per_year))
    paths: list = []
    v = certify(session.log, lc.spec_class, base, ann, alpha=alpha, B=B, seed=seed,
                p_declared_class=p_class, table=h.table, progress=progress,
                replicate_paths=replicate_paths, paths_out=paths if replicate_paths else None)
    names = list(h.panel.feature_names)
    return AuditResult(
        status=v.status, exit_code=EXIT_CODES.get(v.status, 3),
        submitted_support=[[int(k), float(s)] for k, s in support],
        submitted_feature_names=[("+" if s > 0 else "-") + names[int(k)] for k, s in support],
        submitted_sharpe=float(score), p_replay=None if v.p_certifying is None else float(v.p_certifying),
        p_class=p_class, class_bar=bar, alpha=alpha, B=B, n_moves=int(session.log.n_moves),
        class_size=int(h.table.N), reasons=[str(r) for r in v.reasons],
        replicate_paths=paths if replicate_paths else None)


MEANINGS = {
    "CERTIFIED": "the submitted rule clears the bar its own search sets: its Sharpe is unlikely to be "
                 "the luck of a search like this one",
    "FAIL": "the submitted rule does not clear the bar its own search sets: a search like this one "
            "finds a Sharpe this high by luck too often to tell",
    "UNDECIDABLE": "the gate cannot price this run (its reasons say why); nothing is certified",
    "DEPENDS_ON_JUDGMENT": "the search changed a declared rule mid-run; the decision after the change "
                           "cannot be priced, so the verdict is a bracket, not a pass",
    "INADMISSIBLE": "too little power to certify anything at this breadth and length",
    "DEGENERATE": "the inputs carry no information (for example a constant stream)",
}


def render(r: AuditResult, verbose: bool = False) -> str:
    lines = [f"verdict: {r.status}  ({MEANINGS.get(r.status, '')})",
             f"submitted: {' '.join(r.submitted_feature_names)}  in-sample Sharpe {r.submitted_sharpe:.3f} "
             f"after {r.n_moves} moves",
             f"replay tier (the verdict): p {('%.4f' % r.p_replay) if r.p_replay is not None else 'n/a'} "
             f"at alpha {r.alpha:g}, B {r.B}",
             f"class tier (beside it): p {r.p_class:.4f}; the class's bar {r.class_bar:.3f} "
             f"(critical Sharpe over all {r.class_size:,} members)"]
    if verbose:
        lines += [f"  - {x}" for x in r.reasons[:4]]
    elif r.reasons:
        lines.append("--verbose adds the integrity check, the lower bounds and how the null was built")
    return "\n".join(lines)
