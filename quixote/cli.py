"""quixote: example | run | audit | power | split | grade | sancho.

Exit codes: 0 PASS or CERTIFIED, 1 FAIL, 2 INADMISSIBLE, 3 UNDECIDABLE, 4 DEGENERATE,
5 DEPENDS_ON_JUDGMENT, 64 usage or input error. `garden` remains as an alias for the
transcript audit (`garden audit | preflight | explain | example`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_USAGE = 64
REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"


class _Parser(argparse.ArgumentParser):
    def error(self, message):                    # argparse's 2 would collide with INADMISSIBLE
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="quixote", description="A gate between a search for trading rules and the "
                "decision to believe what it found.",
                epilog="Exit codes: 0 PASS/CERTIFIED, 1 FAIL, 2 INADMISSIBLE, 3 UNDECIDABLE, "
                       "4 DEGENERATE, 5 DEPENDS_ON_JUDGMENT, 64 usage or input error.")
    sub = p.add_subparsers(dest="command", required=True, parser_class=_Parser)

    e = sub.add_parser("example", help="audit the bundled example log and print the verdict")
    e.add_argument("--B", type=int, default=500)
    e.add_argument("--json", action="store_true")

    r = sub.add_parser("run", help="run an agent through the harness and write its log")
    r.add_argument("--agent", required=True, help="MODULE:ATTR, e.g. examples.scripted_searcher:Agent")
    r.add_argument("--panel", required=True)
    r.add_argument("--class", dest="cls", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--max-moves", type=int, default=60)
    r.add_argument("--alpha", type=float, default=0.05)

    a = sub.add_parser("audit", help="price a log the harness wrote")
    a.add_argument("log")
    a.add_argument("--panel", required=True)
    a.add_argument("--class", dest="cls", required=True)
    a.add_argument("--B", type=int, default=2000)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--json", action="store_true")

    w = sub.add_parser("power", help="the detection floor for a class and a number of years")
    w.add_argument("--years", type=float, required=True)
    g = w.add_mutually_exclusive_group(required=True)
    g.add_argument("--class", dest="cls")
    g.add_argument("--size", type=int)
    w.add_argument("--panel", help="resolves a class whose features are 'all'")
    w.add_argument("--alpha", type=float, default=0.05)
    w.add_argument("--periods-per-year", type=int, default=252)
    w.add_argument("--json", action="store_true")

    s = sub.add_parser("split", help="split a panel into in-sample and holdout files")
    s.add_argument("panel")
    s.add_argument("--holdout-from", required=True, help="a row index or a row label")
    s.add_argument("--out", required=True)
    s.add_argument("--json", action="store_true")

    d = sub.add_parser("grade", help="grade a log's submitted rule on the holdout, once")
    d.add_argument("log")
    d.add_argument("--insample", required=True)
    d.add_argument("--holdout", required=True)
    d.add_argument("--class", dest="cls", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--json", action="store_true")

    sub.add_parser("sancho", help="run Sancho, the fixed model (see `quixote sancho --help`)",
                   add_help=False)
    return p


def _print(obj, as_json: bool, text: str) -> None:
    print(json.dumps(obj, indent=1, default=float) if as_json else text)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["sancho"]:
        try:
            from sancho.cli import main as sancho_main
        except ImportError as e:
            print(f"quixote sancho: Sancho's command line is not available ({e})", file=sys.stderr)
            return EXIT_USAGE
        return int(sancho_main(argv[1:]) or 0)
    a = _parser().parse_args(argv)
    from quixote import audit as A, classes, holdout as H, panel as P, power as W, run as R
    try:
        if a.command == "example":
            res = A.audit_log(EXAMPLES / "logs" / "scripted_session.json",
                              EXAMPLES / "data" / "tiny_panel.npz", EXAMPLES / "class.json", B=a.B)
            _print(res.to_dict(), a.json,
                   "The bundled example: a scripted searcher's log on a small synthetic panel "
                   "(examples/).\n" + A.render(res))
            return res.exit_code
        if a.command == "run":
            agent = R.load_agent(a.agent)
            log = R.run_session(agent, a.panel, a.cls, a.out, seed=a.seed, max_moves=a.max_moves,
                                alpha=a.alpha)
            print(f"wrote {a.out}: {log['n_moves']} moves, submitted "
                  f"{log['submitted']['support']} (in-sample Sharpe {log['submitted']['score']:.3f}). "
                  f"Price it with: quixote audit {a.out} --panel {a.panel} --class {a.cls}")
            return 0
        if a.command == "audit":
            res = A.audit_log(a.log, a.panel, a.cls, B=a.B, seed=a.seed)
            _print(res.to_dict(), a.json, A.render(res))
            return res.exit_code
        if a.command == "power":
            if a.size is not None:
                size = a.size
            else:
                lc = classes.load(a.cls, P.read(a.panel) if a.panel else None, compute_bar=False)
                if lc.size < 1:
                    raise classes.ClassError("this class's features are 'all': give --panel to count them")
                size = lc.size
            f = W.floor(size, a.years, alpha=a.alpha, periods_per_year=a.periods_per_year)
            _print(f.to_dict(), a.json, f.render())
            return 0
        if a.command == "split":
            rec = H.split(a.panel, a.holdout_from, a.out)
            _print(rec, a.json, f"in-sample {rec['insample_rows']} rows -> {a.out}/insample.npz; holdout "
                   f"{rec['holdout_rows']} rows -> {a.out}/holdout.npz (sha256 {rec['holdout_sha256'][:16]}); "
                   "no holdout value printed. Search on the in-sample file only.")
            return 0
        if a.command == "grade":
            rec = H.grade(a.log, a.insample, a.holdout, a.cls, a.out)
            _print(rec, a.json, f"holdout net Sharpe {rec['holdout_net_sharpe']:.3f} over "
                   f"{rec['graded_periods']} periods (in-sample {rec['insample_sharpe']:.3f}); "
                   f"net return {rec['holdout_net_return']:+.2%}. This holdout is now graded and "
                   "will not be graded again.")
            return 0
    except (A.AuditRefused, classes.ClassError, P.PanelError, H.HoldoutRefused, FileNotFoundError,
            ValueError) as e:
        print(f"quixote {a.command}: refused: {e}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
