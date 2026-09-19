"""garden audit | preflight | explain | example.

Exit codes: 0 PASS, 1 FAIL, 2 INADMISSIBLE, 3 UNDECIDABLE, 4 DEGENERATE, 64 usage or input error.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sys
from pathlib import Path

from garden.audit import audit
from garden.examples import EXAMPLES, load as load_example, path as example_path
from garden.explain import TOPICS, explain
from garden.preflight import preflight
from garden.report import render_preflight, render_verdict
from garden.transcript import MENU_KINDS, TranscriptError, load_benchmark, load_csv, load_npz

EXIT_USAGE = 64  # sysexits EX_USAGE, clear of every verdict code


class _Parser(argparse.ArgumentParser):
    # argparse exits 2 on bad usage, which would collide with INADMISSIBLE.
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="garden", description="A gate between a search and the decision to believe its output.",
                epilog="Exit codes: 0 PASS, 1 FAIL, 2 INADMISSIBLE, 3 UNDECIDABLE, 4 DEGENERATE, 64 usage or input error.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("audit", help="verdict on a finished search")
    a.add_argument("transcript", nargs="?",
                   help="transcript .npz, or a wide .csv (first column labels periods, one column per spec)")
    a.add_argument("--example", choices=sorted(EXAMPLES), help="audit a bundled example instead of a file")
    a.add_argument("--submitted", help="spec id that was chosen (required for .csv, overrides .npz)")
    a.add_argument("--menu-kind", choices=MENU_KINDS, help="override menu_kind (.csv default: unknown)")
    a.add_argument("--periods-per-year", type=int, help="override periods per year (.csv default: 252)")
    a.add_argument("--benchmark", metavar="CSV",
                   help="benchmark return series (first column labels periods, one return column), "
                        "subtracted from every specification before demeaning. The null becomes zero "
                        "excess return over it instead of zero return")
    a.add_argument("--alpha", type=float, default=0.05)
    a.add_argument("--reference-sharpe", type=float, default=1.0,
                   help="true Sharpe to compute power against (default 1.0)")
    a.add_argument("--power-floor", type=float, default=0.20)
    a.add_argument("--B", type=int, default=10_000, help="bootstrap replicates (default 10,000)")
    a.add_argument("--block-length", type=int, help="stationary bootstrap mean block length (default: Politis-White)")
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--json", action="store_true")

    f = sub.add_parser("preflight", help="power of a search before running it")
    f.add_argument("--specs", type=int, required=True, help="number of specifications you intend to evaluate")
    f.add_argument("--periods", type=int, required=True, help="in-sample periods")
    f.add_argument("--reference-sharpe", type=float, required=True,
                   help="plausible true Sharpe; no default, since it depends on asset class and frequency")
    f.add_argument("--rho", type=float, help="expected correlation between specifications, reported alongside "
                                             "the independent-trials worst case")
    f.add_argument("--benchmark", metavar="CSV",
                   help="benchmark return series you intend to measure against; its length is checked "
                        "against --periods and the null is reported as zero excess return over it")
    f.add_argument("--periods-per-year", type=int, default=252)
    f.add_argument("--alpha", type=float, default=0.05)
    f.add_argument("--power-floor", type=float, default=0.20)
    f.add_argument("--json", action="store_true")

    e = sub.add_parser("explain", help="methodology and citations")
    e.add_argument("topic", nargs="?", choices=list(TOPICS))

    x = sub.add_parser("example", help="write a bundled example transcript to .npz")
    x.add_argument("name", choices=sorted(EXAMPLES))
    x.add_argument("--out", required=True)
    return p


def _load(args):
    if (args.transcript is None) == (args.example is None):
        raise TranscriptError("give a transcript path or --example (one, not both)")
    overrides = {k: v for k, v in (("submitted", args.submitted), ("menu_kind", args.menu_kind),
                                   ("periods_per_year", args.periods_per_year)) if v is not None}
    if args.example:
        return dataclasses.replace(load_example(args.example), **overrides)
    path = Path(args.transcript)
    if path.suffix.lower() == ".csv":
        if "submitted" not in overrides:
            raise TranscriptError("a .csv transcript needs --submitted")
        return load_csv(path, **overrides)
    return dataclasses.replace(load_npz(path), **overrides)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    try:
        if args.command == "audit":
            transcript = _load(args)
            bench = bench_name = None
            if args.benchmark:
                bench = load_benchmark(args.benchmark, transcript.n_periods)
                bench_name = Path(args.benchmark).name
            verdict = audit(transcript, alpha=args.alpha, B=args.B, reference_sharpe=args.reference_sharpe,
                            power_floor=args.power_floor, block_length=args.block_length, seed=args.seed,
                            benchmark=bench, benchmark_name=bench_name)
            print(json.dumps(verdict.to_dict(), indent=2) if args.json else render_verdict(verdict))
            return verdict.exit_code
        if args.command == "preflight":
            bench_name = None
            if args.benchmark:
                load_benchmark(args.benchmark, args.periods)      # validates length against --periods
                bench_name = Path(args.benchmark).name
            result = preflight(args.specs, args.periods, args.reference_sharpe, args.periods_per_year,
                               args.alpha, args.power_floor, args.rho, bench_name)
            print(json.dumps(result.to_dict(), indent=2) if args.json else render_preflight(result))
            return 0
        if args.command == "explain":
            print(explain(args.topic))
            return 0
        shutil.copyfile(example_path(args.name), args.out)
        print(f"wrote {args.out}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"garden: error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
