"""Six diagnostics on the ADR class table. No agent, no verdict, no search.

Asked for on 2026-09-24 before deciding whether the cost model needs an
amendment ahead of 7.4. The panel's live search reaches an annualised Sharpe of
107 at `periods_per_year = 19,152`, which is large enough that the question is
not "which specification" but "is this a real edge, a bounce artifact, or a
leak".

Each item below is a **look at real in-sample data** and is recorded as such in
`data/adr_manifest.json` under `looks`, with its date and what was seen. That is
the same discipline `ret1_z` was recorded under: a number the researcher has seen
makes a human declaration of the thing it concerns non-oblivious.

    python -m experiments.adr_cost_diagnostics

1. gross against net Sharpe, for the class maximum and for pilot_3's submission;
2. per-name P&L of the class maximum, and each name's spread estimate against
   its price, with which names sit at the registered floor;
3. which features the top members use;
4. the same statistic with the signal lagged one extra bar;
5. the class maximum on the placebo control panel;
6. the class maximum at 2x and 4x spread.

**Nothing here changes `SHARPE_CAP` or the annualisation**, which the same
instruction holds back pending a decision.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

from data.adr_costs import FLOOR_BPS, FLOOR_CENTS
from environments.class_table import build_class_table, members_in_order, streams_for
from environments.real_panel import ADR_BENCH, ADR_TREATED, build_adr_panel
from garden.spec_class import SubsetClass

# prereg/adr-features.md section 3: "Signed subsets of size <= 2 over K = 22:
# 968 members". Not depth 3 - that is the ETF panel's class, and the pilot used
# it here by mistake (recorded in prereg/agent-pilot.md).
CLS = SubsetClass(max_size=2, signed=True)
CONTROLS = ["ARM", "NXPI", "SPOT"]          # prereg/adr-universe.md, the placebo panel
MANIFEST = Path(__file__).resolve().parent.parent / "data" / "adr_manifest.json"
OUT = Path(__file__).resolve().parent.parent / "figures" / "adr_cost_diagnostics.txt"


def sharpe_of(x: np.ndarray, ann: float) -> float:
    """The sandbox's own statistic, uncapped, as `environments/class_table.py`
    explains."""
    s = float(np.std(x, ddof=1))
    return float(np.mean(x) / s * ann) if s > 0 else 0.0


def decomposed(panel, support) -> dict:
    """One member's gross, cost, borrow and net streams, plus per-name P&L.

    Re-walks `RealPanel`'s own book-keeping rather than re-deriving it, so the
    net stream here is the table's column and the parts sum to it.
    """
    T, M, K = panel.features.shape
    w_prev = np.zeros(M)
    held = np.zeros(M)
    weights = np.zeros((T, M))
    wv = np.zeros(K)
    for k, s in support:
        wv[k] = s
    for t in range(T):
        free = panel.tradable[t]
        if panel.flat_overnight and panel.session_start[t]:
            held = np.zeros(M)
        target = np.where(free, panel.features[t] @ wv, 0.0)
        if free.any():
            target = target - target[free].mean() * free
            gross = np.abs(target[free]).sum()
            if gross > 0:
                target = target / gross
        new = np.where(free, target, held)
        if panel.flat_overnight and panel.session_end[t]:
            new = np.zeros(M)
        weights[t] = new
        held = new
    prev = np.vstack([np.zeros((1, M)), weights[:-1]])
    pnl_by_name = weights * panel.returns
    cost_by_name = np.abs(weights - prev) * panel.cost_rate
    borrow_by_name = np.clip(-weights, 0, None) * panel.borrow_rate
    return {"weights": weights,
            "gross": pnl_by_name.sum(axis=1),
            "cost": cost_by_name.sum(axis=1),
            "borrow": borrow_by_name.sum(axis=1),
            "net": (pnl_by_name - cost_by_name - borrow_by_name).sum(axis=1),
            "pnl_by_name": pnl_by_name.sum(axis=0),
            "cost_by_name": cost_by_name.sum(axis=0),
            "turnover_by_name": np.abs(weights - prev).sum(axis=0)}


def class_max(panel, table=None, chunk: int = 1024) -> tuple[float, tuple]:
    """The best member of the declared class on this panel, by net Sharpe."""
    if table is not None:
        best, j = table.max_sharpe(chunk=chunk)
        return best, table.members[j]
    K = panel.features.shape[2]
    members = members_in_order(CLS, K)
    ann = float(np.sqrt(panel.periods_per_year))
    best, best_m = float("-inf"), None
    for start in range(0, len(members), chunk):
        block = streams_for(panel, members[start:start + chunk])
        std = block.std(axis=1, ddof=1)
        s = np.where(std > 0, block.mean(axis=1) / np.where(std > 0, std, 1.0), 0.0) * ann
        j = int(np.argmax(s))
        if float(s[j]) > best:
            best, best_m = float(s[j]), members[start + j]
    return best, best_m


def lagged_panel(panel):
    """The same panel with the signal delayed one extra bar: the score formed at
    the close of bar t is used from bar t+1 instead of t. A leak collapses; a
    bounce artifact mostly survives; a real signal degrades gradually."""
    f = np.zeros_like(panel.features)
    f[1:] = panel.features[:-1]
    return replace(panel, features=f, name=panel.name + "-lag1")


def scaled_spread(panel, factor: float):
    return replace(panel, cost_rate=panel.cost_rate * factor,
                   name=f"{panel.name}-spread{factor:g}x")


def placebo_panel():
    """The three registered controls (ARM, NXPI, SPOT).

    They have no home market, and `prereg/adr-features.md` section 2 already says
    what to do about it: "Controls take XAMS's boundary (11:30 ET, 12:30 ET in
    clock-mismatch weeks) as a pseudo-close, so every specification is defined on
    them and every home-close prediction can fail there." The builder follows
    that rather than inventing a rule."""
    return build_adr_panel(names=CONTROLS)


def main() -> int:
    t0 = time.time()
    L: list[str] = []

    def say(line=""):
        L.append(line)
        print(line, flush=True)

    panel = build_adr_panel()
    ann = float(np.sqrt(panel.periods_per_year))
    table = build_class_table(panel, CLS, "adr")
    names = list(panel.assets)
    say("ADR cost diagnostics — LOOKS AT REAL IN-SAMPLE DATA, recorded in the manifest")
    say("=" * 78)
    say(f"panel {panel.features.shape}, periods_per_year {panel.periods_per_year:,.0f}, "
        f"annualisation {ann:.1f}")
    say(f"class {CLS.name}: {table.N:,} members")
    say("")

    # -- 1. gross against net ------------------------------------------------
    best, best_member = class_max(panel, table)
    pilot3 = ((1, 1.0), (0, 1.0), (3, 1.0))         # pilot_3's submitted support
    say("THE PANEL WAS CORRECTED BEFORE THESE NUMBERS WERE TAKEN. The first run of")
    say("these diagnostics found a look-ahead leak: ADR returns were not shifted, so a")
    say("weight formed from bar b's features earned bar b's OWN return, against")
    say("prereg/adr-features.md section 4 ('signal at the close of bar b, position held")
    say("over bar b+1'). Everything below is on the corrected panel.")
    say("")
    say("1. GROSS vs NET")
    say("-" * 78)
    rows = [("class max", best_member), ("pilot_3 submission", pilot3)]
    diag = {}
    for label, support in rows:
        d = decomposed(panel, support)
        diag[label] = d
        g, n = sharpe_of(d["gross"], ann), sharpe_of(d["net"], ann)
        say(f"  {label:20} {_fmt(support, panel)}")
        say(f"    gross Sharpe {g:9.3f}   net Sharpe {n:9.3f}   "
            f"cost drag {g - n:8.3f} ({(g - n) / abs(g) * 100 if g else 0:.1f}%)")
        say(f"    per bar: gross {d['gross'].mean():+.3e}  cost {d['cost'].mean():.3e}  "
            f"borrow {d['borrow'].mean():.3e}  net {d['net'].mean():+.3e}")
        say(f"    turnover per bar {np.abs(np.diff(d['weights'], axis=0)).sum(axis=1).mean():.4f} "
            "(gross 1 book)")
    say("")

    # -- 2. per-name P&L, spread against price -------------------------------
    d = diag["class max"]
    floor_bps = FLOOR_BPS
    say("2. PER-NAME P&L OF THE CLASS MAX, AND THE SPREAD EACH NAME PAYS")
    say("-" * 78)
    say(f"  registered floor: max(estimate, {FLOOR_CENTS} / price, {FLOOR_BPS} bps); "
        "cost_rate = spread/2 + fee")
    say(f"  {'name':6}{'gross P&L':>12}{'cost':>11}{'net':>12}{'turnover':>10}"
        f"{'cost bps':>10}{'at floor?':>11}")
    at_floor = []
    for i, nm in enumerate(names):
        live = panel.cost_rate[:, i][panel.tradable[:, i]]
        cost_bps = float(np.median(live)) * 1e4 if live.size else float("nan")
        # cost_rate is spread/2 + fee, so the floor's contribution is floor/2
        floored_frac = float(np.mean(live <= (floor_bps * 1e-4) / 2 + 1e-12)) if live.size else 0.0
        if floored_frac > 0.5:
            at_floor.append(nm)
        say(f"  {nm:6}{d['pnl_by_name'][i]:12.4f}{d['cost_by_name'][i]:11.4f}"
            f"{d['pnl_by_name'][i] - d['cost_by_name'][i]:12.4f}"
            f"{d['turnover_by_name'][i]:10.1f}{cost_bps:10.2f}"
            f"{floored_frac * 100:10.0f}%")
    say(f"  names whose cost sits at the floor for most bars: {at_floor or 'none'}")
    say("")

    # -- 3. which features the top members use -------------------------------
    say("3. WHAT THE TOP MEMBERS USE")
    say("-" * 78)
    scores = np.empty(table.N)
    for start in range(0, table.N, 1024):
        block = np.asarray(table.streams[start:start + 1024], dtype=float)
        std = block.std(axis=1, ddof=1)
        scores[start:start + block.shape[0]] = np.where(
            std > 0, block.mean(axis=1) / np.where(std > 0, std, 1.0), 0.0) * ann
    order = np.argsort(-scores)[:20]
    tally = Counter()
    for j in order:
        for k, s in table.members[j]:
            tally[f"{'-' if s < 0 else '+'}{panel.feature_names[k]}"] += 1
    for j in order[:8]:
        say(f"  {scores[j]:9.3f}  {_fmt(table.members[j], panel)}")
    say("  feature usage across the top 20:")
    for feat, n in tally.most_common():
        say(f"    {n:3}x  {feat}")
    say("")

    # -- 4. one extra bar of lag ---------------------------------------------
    say("4. THE SAME STATISTIC WITH THE SIGNAL LAGGED ONE EXTRA BAR")
    say("-" * 78)
    lag = lagged_panel(panel)
    lag_best, lag_member = class_max(lag)
    same = streams_for(lag, [best_member])[0]
    say(f"  class max unlagged {best:9.3f}   lagged {lag_best:9.3f}   "
        f"({lag_best / best * 100 if best else 0:.0f}% retained)")
    say(f"  the SAME member lagged: {sharpe_of(same, ann):9.3f}")
    say(f"  lagged argmax: {_fmt(lag_member, panel)}")
    say("")

    # -- 5. the placebo panel ------------------------------------------------
    say("5. THE CLASS MAX ON THE PLACEBO CONTROL PANEL")
    say("-" * 78)
    try:
        pl = placebo_panel()
        pl_best, pl_member = class_max(pl)
        say(f"  controls {CONTROLS}: {pl.features.shape}")
        say(f"  class max {pl_best:9.3f}   against {best:9.3f} on the treated panel")
        say(f"  {_fmt(pl_member, pl)}")
        say("  NOTE: the controls take XAMS's boundary as a pseudo-close, which is what")
        say("  prereg/adr-features.md section 2 registers. prereg/adr-universe.md records")
        say("  the placebo limitation: all three controls are technology names.")
    except Exception as e:                      # reported, not swallowed
        pl_best = None
        say(f"  NOT COMPUTED: {type(e).__name__}: {e}")
    say("")

    # -- 6. wider spreads ----------------------------------------------------
    say("6. THE CLASS MAX AT 2x AND 4x SPREAD")
    say("-" * 78)
    wider = {}
    for factor in (2.0, 4.0):
        b, m = class_max(scaled_spread(panel, factor))
        wider[factor] = b
        say(f"  {factor:g}x: class max {b:9.3f}   ({b / best * 100 if best else 0:.0f}% of 1x)   "
            f"{_fmt(m, panel)}")
    say("")
    say(f"total {time.time() - t0:.0f}s")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n")
    _record_look(best, best_member, panel, diag, lag_best, pl_best, wider, at_floor)
    print(f"\nwritten to {OUT} and recorded as a look in {MANIFEST.name}")
    return 0


def _fmt(support, panel) -> str:
    return " ".join(f"{'-' if s < 0 else '+'}{panel.feature_names[k]}" for k, s in support)


def _record_look(best, best_member, panel, diag, lag_best, pl_best, wider, at_floor) -> None:
    """Every number above is now seen. The manifest says so."""
    m = json.loads(MANIFEST.read_text())
    looks = m.setdefault("looks", [])
    g = sharpe_of(diag["class max"]["gross"], float(np.sqrt(panel.periods_per_year)))
    looks.append({
        "date": "2026-09-24",
        "what": "six cost diagnostics on the ADR class table (experiments/adr_cost_diagnostics.py)",
        "why": ("asked for before deciding whether the cost model needs an amendment "
                "ahead of 7.4; no agent involved, no search, no verdict"),
        "seen": {
            "class_max_net_sharpe": round(float(best), 4),
            "class_max_gross_sharpe": round(float(g), 4),
            "class_max_member": _fmt(best_member, panel),
            "class_max_lagged_one_bar": None if lag_best is None else round(float(lag_best), 4),
            "placebo_class_max": None if pl_best is None else round(float(pl_best), 4),
            "class_max_at_2x_spread": round(float(wider.get(2.0, float("nan"))), 4),
            "class_max_at_4x_spread": round(float(wider.get(4.0, float("nan"))), 4),
            "names_at_the_cost_floor": at_floor,
        },
        "consequence": (
            "Any HUMAN-declared specification informed by these numbers is not "
            "oblivious and is inadmissible for a prior-weighted short list on this "
            "panel, exactly as recorded for ret1_z. An agent that never saw them is "
            "unaffected. No verdict, rate or threshold is derived here."),
        "report": "figures/adr_cost_diagnostics.txt",
    })
    MANIFEST.write_text(json.dumps(m, indent=1))


if __name__ == "__main__":
    raise SystemExit(main())
