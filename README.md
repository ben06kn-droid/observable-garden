# observable-garden

This repository asks whether the best result of a search over trading strategies can
be told apart from the best of many tries on pure noise when the search is adaptive.
It shows that a null built only from the strategies a search logged errs in a direction
set by what the search builds on. It also shows that a record letting the search be
re-run under the null repairs it. On synthetic panels the test (called the gate in this
repository) keeps its error rate and certifies planted edges; on real data no strategy
has yet earned a certificate.

**The note:** `docs/note.md`, *Fixed and adaptive candidate sets under the DSR*.
`docs/NOTE_MAP.md` maps each of its claims to the experiment, registration, commits and
script behind it. Its limit values are computed two ways, by Monte Carlo in
`experiments/limit_model.py` and by quadrature in `experiments/size_integral.py`, and
the two agree to 0.001.

**Where things are:**
- `estimator/`, `garden/`, `quixote/`: the gate: its estimators, the `garden` audit
  command, and the harness that replays an agent's logged search.
- `environments/`, `searchers/`, `learn/`, `learn2/`: the panels (real and planted), the scripted searchers, and the machine-learning predictors.
- `experiments/`: one script per experiment, with its reader.
- `prereg/` and `EXPERIMENTS.md`: the pre-registrations, and the ledger of every
  experiment with its commits.
- `runs/`, `figures/`, `docs/`: raw outputs, result files, and the note with its map.

**Run it:**
- **The test suite:** `pip install -e ".[dev]"`, then `pytest -q`, from the repository
  root. That is about 1,340 tests, and about 12 minutes on a laptop.
  - Three files skip without the agent SDK, which the dependencies do not install.
  - The machine-learning tests also need LightGBM 4.7.0, which is pinned and installed
    from its wheel.
- **One small experiment, end to end:** `python -m experiments.size_integral`. It
  computes the winner-anchored limit error rate by quadrature at THEORY.md's eight
  (ω, K) cells, and prints them beside the table. It takes under one second.

**Every backtest is the best of many tries. Nobody writes down the tries.
An agent does.**

A good backtest may only be the luckiest of a thousand attempts, and the
correction for that has always needed a number no human researcher keeps: how
hard they searched. This repo is a gate that reads the search's own log and
returns a verdict.

```
pip install -e .
garden audit --example null_grid     # FAIL          the best of nothing
garden audit --example real_edge     # PASS          survives the search that found it
garden audit --example overwide      # INADMISSIBLE  too broad to prove anything
```

Every verdict prints its bar, its power and a reason per check, so you can
argue with it. It refuses rather than flatter: **UNDECIDABLE** when the log
can't license a correction, **DEGENERATE** when the statistic breaks.

## What it has measured

- A search over 1,000 noise-heavy trials reports Sharpe **2.03**. The truth
  is **0.21**. Reading only the transcript, the gate calls the decay to
  within **0.017**.
- Let a search chase its own winners and the textbook correction fails: over
  **a third** of pure-noise searches clear a nominal 5% bar.
- Two repairs hold everywhere tested. With a searcher that reaches its
  declared class, the gate rejects **9.60 / 5.50 / 0.95%** at nominal
  10 / 5 / 1.
- Declare the tightest class your search can reach. Over-declaring took one
  searcher from nominal to **1.35%**, which is power thrown away.
- A PASS is not a promise. Reverse the true signal and its advantage erodes
  from **+0.46** to **+0.08**. It never inverts.
- Real-data holdout (ETF panel, 80 agent submissions): none was certified
  in-sample. On the sealed 2023-2025 holdout their median net Sharpe was
  **+0.71** [-0.28, +1.74], not distinguishable from zero; the gate's lower
  bounds held; the agents' stated confidence did not rank their strategies.
  (`EXPERIMENTS.md`, 6.5 holdout grading.)
- Machine-learning arm (planted panels, registered confirmation): held its
  false-positive rate (14 of 400 null panels certified at zero cost) and
  certified a planted non-linear edge at net Sharpe 1.5 in **59%** of panels
  against **14%** for the rule-class tier, a difference of **+0.45** [+0.40,
  +0.50]. The edges were planted by construction; part of the gain is the
  lower bar a single declared strategy faces. (`EXPERIMENTS.md`, ridge_stack
  confirmation.)
- French 49-industry panel, 2010-2019, in-sample: neither registered test
  certified. The learned strategy's net Sharpe was **0.55** (p = 0.074 against
  a threshold of 0.04); the best of 82,240 rules reached **0.68** (p = 0.96
  against 0.01). Both are consistent with the detection floor registered in
  advance. (`EXPERIMENTS.md`, French 49-industry, in-sample read.)

**Not yet shown:** no certificate has been earned on real data, so whether a
pass holds out of sample is untested there.

## Next: a gate for agents that think

*Where it stands: the agent arm and a real-data holdout have been run; their
results are recorded in `EXPERIMENTS.md`.*

An agent doesn't search a fixed menu. It decides what to try next. The second
gate prices the decisions, not just the trials:

- **Replays what can be replayed.** Moves are typed and harness-executed, so
  each resample re-runs the agent's rules and lets them choose differently.
- **Charges for what can't.** A decision with no stated rule is priced at the
  best of its alternatives. Ambiguity costs power, never validity.
- **Reports its own doubt.** When the verdict turns on a judgment call, it
  says so and names the call.
- **Twins.** The same agent, re-run on placebo copies of the data where the
  null is true. The real run's rank among them is the p-value, whatever the
  log missed.

Design, rules and gates: `ROADMAP.md`, Phase 7.

## Prior work

The engine is White's Reality Check (2000). It is twenty-six years old and
it is the right tool. This project asks what a logged search lets you do with
it. `SCOPE.md` has every number and caveat, `THEORY.md` the proofs, and
`EXPERIMENTS.md` the commit each pre-registration was fixed at.

Gençay (2026) and Kinlay (2026a) published the observation that an agent's trial
count is observable by construction before this project's first record; this
project reached it independently. Neither addresses whether the logged candidate
set suffices when the search is adaptive, which is the subject here.

Kinlay (2026b) is concurrent, independent work reaching two of the same
conclusions: that data-snooping tests calibrated on a family fixed in advance are
inflated when pointed at the search's own trace, and that a Deflated Sharpe fed an
effective trial count passes too often. This project's records are earlier —
`3446f10`, 2026-09-14 for the effective-N double-counting result, and `309332d`
with `34934a1`, 2026-09-15 for the family-versus-trace distinction — and its
account of the effective-N error derives it from `Var[SR_n]`, which that work does
not contain.

The full search, with read-levels for every reference, is
`docs/RELATED_WORK_2026.md` (2026-09-30).

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Layout

```
garden/         the gate: transcript format, audit, preflight, explain, CLI
quixote/        Don Quixote, the agent-facing gate: move grammar, session log
environments/   simulated data, the sandbox contract, price worlds
searchers/      scripted, meta-adaptive, dose-response and diagnostic searchers
estimator/      naive, recursive, trigger-replay and procedure-level bootstraps
experiments/    one module per experiment, named in EXPERIMENTS.md; parallel runner
prereg/         every experiment's rules, fixed before it ran
cloud/          EC2 setup and detached-run scripts
tests/, figures/, runs/
```
