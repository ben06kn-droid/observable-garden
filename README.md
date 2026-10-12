# The Observable Garden: Quixote and Sancho

**Quixote** is a gate between a search for trading rules and the decision to believe what it
found. It judges the winner's backtest against what the best of the same search would look like
on pure noise.
- It works whoever searches: a script, a person or an LLM agent.
- For an agent, it runs the search itself: the agent names each move, the harness carries it out
  and logs it, and the log can be re-run under the null.

**Sancho** is a fixed model to compare against.

The method and its evidence are in the note, [`paper/note.md`](paper/note.md), *Fixed and
adaptive candidate sets under the DSR*.

## Install

```
pip install -e .                  # Python 3.10 or later
pip install -e ".[sancho]"        # adds LightGBM 4.7.0, pinned: Sancho's registered results used it exactly
pip install -e ".[agent]"         # adds the Anthropic SDK, only for the LLM agent example
```

## One minute: run the gate on an example

```
quixote example
```

This audits a bundled log, a scripted searcher's moves on a small synthetic panel in
`examples/`, and prints the verdict:

```
verdict: FAIL  (the submitted rule does not clear the bar its own search sets: a search like this one finds a Sharpe this high by luck too often to tell)
submitted: -mom60_z +rev5_rank  in-sample Sharpe 0.572 after 2 moves
replay tier (the verdict): p 0.9721 at alpha 0.05, B 500
class tier (beside it): p 0.9800; the class's bar 1.888 (critical Sharpe over all 128 members)
```

To audit a log yourself: `quixote audit examples/logs/scripted_session.json --panel
examples/data/tiny_panel.npz --class examples/class.json`.

## Your own agent, in five steps

`examples/README.md` documents each step in full.

1. **Your data as a panel.** Write an `.npz` with `returns` (T × M), `features` (T × M × K),
   `feature_names` and `periods_per_year`, and optionally costs, delay and row labels.
   `examples/make_tiny_panel.py` builds one.
2. **Declare the class before you search.** A JSON file names the features, the maximum number
   in a rule, and whether signs are free, or points to a file of supplied return streams. The
   harness hashes it before the first evaluation and writes the hash into the log.
3. **Write the agent.** It implements one method, `next_move(view) -> {"tool": ...}`. It names a
   move; the harness runs it.
   - `examples/scripted_searcher.py` is a scripted agent.
   - `examples/llm_agent.py` is an LLM adapter. It reads its API key from the environment.
4. **Run it:**
   `quixote run --agent mymodule:MyAgent --panel my.npz --class my_class.json --out log.json`.
   It prints the class's size and its bar on your panel.
5. **Audit the log:** `quixote audit log.json --panel my.npz --class my_class.json`. The audit
   refuses a log whose class or panel hash does not match the files it is given.

**Hold data back.** Before you search:
- `quixote split my.npz --holdout-from <row or date> --out split/` writes the holdout and its
  hash;
- `quixote grade log.json --insample split/insample.npz --holdout split/holdout.npz --class
  my_class.json --out split/` grades the submitted rule once. It refuses a second run on the same
  holdout.

**Why the class is fixed.** A class changed after results are seen is a search over classes, and
the gate would be pricing the wrong search. So the hash is taken before the first evaluation, and
the audit refuses a mismatch.

**Sancho's levers** are in `sancho/config.json`, documented in `sancho/CONFIG.md`. The defaults
are the registered version 2.
- `quixote sancho --panel my.npz [--config my.json] --out dir/` writes the config's hash into the
  output.
- **Sancho needs history before it scores anything.** Its first scored row is 756 (after the
  embargo, 763), so it needs a panel of a few years. On the 600-row example panel it refuses, by
  design.
- A non-default config says, once, that the registered results apply to the default only, and
  that every configuration tried on the same data is another strategy and must be declared as
  such.

## What a verdict means

| status | meaning |
|---|---|
| **PASS** | p is below α: the submitted rule beats what the search would find on noise. |
| **FAIL** | p is at or above α, and the test had the power to tell: the result is what this search finds by luck. |
| **INADMISSIBLE** | p is at or above α, and the search was too wide to certify anything: the test's power against the reference Sharpe (1.0 by default) is below the power floor (0.20). |
| **UNDECIDABLE** | the record alone cannot license a correction, for example returns logged without the search that chose them. |
| **DEGENERATE** | the test statistic broke on this menu. Do not read its p. |

- **The lower bound** (`L_0.90`) is the Sharpe the selected rule is 90% confident of exceeding,
  after the search is paid for.
- **The detection floor** is the smallest Sharpe the gate can certify for a class and a sample
  length. Look at it before you search:

  ```
  quixote power --years 10 --size 82240
  ```
  ```
  smallest Sharpe the gate can certify (the bar): 1.533
  true Sharpe needed for 80% power:                1.800
  ```

  Those are for independent members, the worst case. Correlated members act like fewer, and
  `quixote run` prints the bar measured on your panel.

## What has been validated, and what has not

From the note's Section 7. Nothing here is stated more strongly than the note states it.

- **The direction of the error** under adaptive search is a limit result. It is proved for large
  samples and one common pair score, which requires equal volatilities and correlations. With
  finite samples it is measured, not proved.
- **Other scoring rules.** Outside weighted sums of features the asymmetry is measured, but no
  size is established and nothing is proved.
- **The process bootstrap** is covered in theory for rules that depend on the ranking of Sharpe
  ratios. For correlation-based anchoring with equal correlations the argument is a sketch; with
  unequal correlations it is open.
- **The number of trials is held fixed** in the theory. The 1,500-trial grid and the
  82,240-strategy class are supported by simulation, not by the theorem.
- **Block correlation and unequal volatilities** have not been tested.
- **Stopping-rule replay**, the null Quixote certifies with, had error rates at or below nominal
  on the searchers tested. Exactness is not claimed and nothing is proved.
- **The evidence** in the note's Sections 3 to 6 is scripted searchers and synthetic returns.
  **Whether a result that passes holds out of sample on real data is untested.**
- **Whatever a searcher considers without evaluating is never logged,** at any level of record.

## The research record

Pre-registrations, runs, reads and the code behind the note are in [`research/`](research/README.md).

## Tests

```
pytest tests -m "not slow"        # the quick target, under two minutes (CI runs it)
pytest tests research/tests       # everything; much of research/tests needs machine-local data
```
