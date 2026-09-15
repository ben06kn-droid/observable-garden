"""Plain-text rendering for verdicts and preflight results."""
from __future__ import annotations

import math
import re
import textwrap

from garden._fmt import pct
from garden.audit import Verdict
from garden.preflight import BREADTHS, TARGET_POWER, PreflightResult

WIDTH = 78
TAGLINES = {
    "PASS": "certified for search breadth",
    "FAIL": "cannot certify",
    "INADMISSIBLE": "search too wide to certify anything",
    "UNDECIDABLE": "transcript alone cannot license a correction",
    "DEGENERATE": "the test statistic broke on this menu",
}
EXPLAIN_TOPIC = {"PASS": "reality-check", "FAIL": "reality-check", "INADMISSIBLE": "inadmissible",
                 "UNDECIDABLE": "undecidable", "DEGENERATE": "degenerate"}


def _row(label: str, value: str, indent: int = 2) -> str:
    return f"{' ' * indent}{label:<{46 - indent}}{value:>16}"


def _num(x: float) -> str:
    return "∞" if math.isinf(x) else f"{x:.2f}"


def _p(p: float) -> str:
    return f"{p:.3f}" if p >= 0.001 else f"{p:.1e}"


def _wrap(text: str, indent: int = 2) -> list[str]:
    lines = []
    for line in text.split("\n"):
        body = line.lstrip()
        lead = " " * (indent + len(line) - len(body))
        item = re.match(r"\d+\.\s+", body)
        hang = lead + " " * (item.end() if item else 0)
        lines.append(textwrap.fill(body, WIDTH, initial_indent=lead, subsequent_indent=hang))
    return lines


def render_verdict(v: Verdict) -> str:
    bound = v.p_value_is_lower_bound
    unreliable = " (unreliable)" if v.status == "DEGENERATE" else ""
    source = "Reality Check bootstrap" if v.method == "reality_check" else "procedure-level re-execution"
    lo, hi = v.null_max_band
    out = [
        f"VERDICT: {v.status} — {TAGLINES[v.status]}",
        "",
        _row("Specifications evaluated", f"{v.n_trials:,}"),
        _row("Periods", f"{v.n_periods:,} ({v.periods_per_year}/yr)"),
        f"  Submitted: {v.submitted} (rank {v.submitted_rank:,} of {v.n_trials:,} by in-sample Sharpe)",
        "",
        f"  Null maximum ({source}, B={v.B:,})",
        _row("mean", _num(v.null_max_mean), indent=4),
        _row("5th–95th percentile", f"{lo:.2f} – {hi:.2f}", indent=4),
        _row(f"critical value at α={v.alpha:g}", _num(v.critical_value), indent=4),
        _row("Reported Sharpe (in-sample)", f"{v.sr_reported:.2f}"),
        _row("Deflated Sharpe" + (" (upper bound)" if bound else unreliable), f"{v.sr_deflated:.2f}"),
        _row("p-value" + (" (lower bound)" if bound else unreliable), _p(v.p_value)),
        "",
        _row("Reference Sharpe (--reference-sharpe)", f"{v.reference_sharpe:.2f}"),
        _row("Power, single pre-specified strategy", f"{pct(v.power_at_reference)} (floor {pct(v.power_floor)})"),
        _row("Effective breadth (not used)", f"{v.effective_breadth:,.1f}"),
        _row("Degenerate tail share",
             f"{v.degenerate_share:.3f} ({v.degenerate_replicates:,} of {v.screen_replicates:,} replicates)"),
    ]
    for reason in v.reasons:
        out.append("")
        out.extend(_wrap(reason))
    out += ["", f"  Methodology: garden explain {EXPLAIN_TOPIC[v.status]}"]
    return "\n".join(out)


def render_preflight(r: PreflightResult) -> str:
    def cols(label: str, values: list[str]) -> str:
        return f"  {label:<38}" + "".join(f"{v:>14}" for v in values)

    labels = [s.label for s in r.scenarios]
    out = [
        f"PREFLIGHT — {r.n_specs:,} specifications, {r.n_periods:,} periods ({r.periods_per_year}/yr), "
        f"α={r.alpha:g}",
        "",
        cols("Reference Sharpe (your choice)", [f"{r.reference_sharpe:.2f}"]),
        "",
        cols("", labels),
        cols("Critical value (null max at 1−α)", [f"{s.critical_value:.2f}" for s in r.scenarios]),
        cols("Power, single pre-specified strategy", [pct(s.power) for s in r.scenarios]),
        cols(f"True Sharpe for {pct(TARGET_POWER)} power", [f"{s.required_sharpe:.2f}" for s in r.scenarios]),
        "",
        f"  True Sharpe needed for {pct(TARGET_POWER)} power at this sample length, by breadth",
        cols("specifications", labels),
    ]
    for i, n in enumerate(BREADTHS):
        out.append(cols(f"{n:>14,}", [f"{s.breadth_table[i][1]:.2f}" for s in r.scenarios]))
    for reason in r.reasons:
        out.append("")
        out.extend(_wrap(reason))
    out += ["", "  Methodology: garden explain power"]
    return "\n".join(out)
