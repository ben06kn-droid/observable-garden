# Examples

| file | what it is |
|---|---|
| `data/tiny_panel.npz` | a small synthetic daily panel: 600 rows, 12 assets, 8 features, a weak planted edge (`make_tiny_panel.py` writes it) |
| `class.json` | a class over that panel: every signed combination of up to 2 of its 8 features (128 members) |
| `scripted_searcher.py` | a scripted agent: declares a stopping rule, anchors, extends, stops, predicts, submits |
| `llm_agent.py` | an adapter that lets a language model name the moves (optional SDK; API key from the environment) |
| `logs/scripted_session.json` | the log `quixote run` wrote for the scripted agent on the tiny panel |

    quixote example                                   # audit the bundled log: a few seconds
    quixote run --agent examples.scripted_searcher:Agent --panel examples/data/tiny_panel.npz \
        --class examples/class.json --out my_session.json
    quixote audit my_session.json --panel examples/data/tiny_panel.npz --class examples/class.json

## Your own agent: the adapter interface

An agent is any object with one method:

```python
class Agent:
    def next_move(self, view) -> dict:
        ...
        return {"tool": "extend_best"}
```

`view` (`quixote.run.View`) is everything the harness shows: `step`, the `tools`, `last` (the
result of the previous call, `{"ok", "text", "state"}`, or `{"refused": text}`), the current
`support` and `best_support`, the `best` Sharpe so far, `info` (the information set the
stopping rules read: failures, last gain, best), the `feature_names`, the `class_name` and the
move budget `max_moves`.

The agent returns **one named move** as a dict. The harness performs it and logs it; the agent
never hands in a rule it built, so the log cannot disagree with what ran. The moves:

| move | arguments | |
|---|---|---|
| `declare_triggers` | `triggers=[{"trigger", "param", "action"}]` | the stopping rules, **before the first evaluation** |
| `declare_budget`, `pick_prior`, `short_list` | | other declarations, also before the first evaluation |
| `init` | | anchor on the best single feature |
| `extend_best` | | add the feature that most improves the held rule |
| `swap_worst` | | replace the weakest held feature |
| `flip` | `feature=k` | reverse one held feature's sign |
| `refine` | | re-fit the held features' signs |
| `pick` | `among=[...]`, `statistic` | choose among named candidates by a named statistic |
| `stop`, `restart` | `trigger`, `param` | only on a declared rule that fires now |
| `change_trigger` | `trigger`, `param`, `reason` | allowed; logged, and the rest of the run is priced as a judgment |
| `predict` | `mean`, `sd`, `note` | the out-of-sample Sharpe the agent expects |
| `submit` | | end; the submission is the best rule reached |

The rules a `trigger` can name: `best_so_far_above`, `failures_at_least`, `last_gain_at_most`.
A refused call is not an error: its reason comes back in `view.last` and the run continues.
If the budget runs out, the harness submits the best rule reached.

`quixote run --agent MODULE:ATTR ...` imports your agent from the current directory.
`examples/llm_agent.py` shows a model behind the same interface; install the SDK with
`pip install -e .[agent]` and set `ANTHROPIC_API_KEY`.

## Your own data: the panel format

One `.npz` file (`quixote/panel.py`):

| array | shape | |
|---|---|---|
| `returns` | (T, M) | simple returns; NaN = not tradable in that row |
| `features` | (T, M, K) | what a rule may use in row t (data up to row t only) |
| `feature_names` | (K,) | |
| `periods_per_year` | scalar | 252 for daily rows |
| `delay` | scalar, default 1 | features at row t earn `returns[t + 1 + delay]` |
| `cost_bps` | scalar, default 5 | one-way cost per unit of turnover |
| `borrow_bps_yr` | scalar, default 50 | borrow on short weight, a year |
| `row_labels`, `asset_names` | (T,), (M,) | optional; `split` accepts a row label |

A rule's book is dollar-neutral at gross 1 over the tradable assets. `quixote.panel.save(...)`
writes the file; `quixote.panel.load(path)` checks it.

**A holdout.** Split it off before the search and grade once after:

    quixote split my_panel.npz --holdout-from 2025-01-02 --out split/
    quixote run --agent my_agent:Agent --panel split/insample.npz --class my_class.json --out log.json
    quixote grade log.json --insample split/insample.npz --holdout split/holdout.npz \
        --class my_class.json --out split/

`split` writes the holdout's SHA-256 and prints no holdout value. `grade` refuses to run twice
on the same holdout: a holdout looked at twice is no longer a holdout.

## The class

The class is the set of rules the search may draw from, in one JSON file:

```json
{"kind": "subsets", "features": ["mom60_z", "rev5_rank"], "max_size": 3, "signed": true}
```

`features` may be `"all"`. A class of supplied return streams is
`{"kind": "streams", "file": "streams.npz"}` (an array `streams` of shape (N, T)); it is
audited as a transcript with `garden audit`.

**Why the class is fixed.** The gate prices a search against everything it could have chosen
from. A class changed after results are seen is a search over classes, and the gate cannot see
that search, so its verdict would be priced against the wrong set. The harness therefore hashes
the class file (and the panel file) before the first evaluation and writes both hashes into the
log, and `quixote audit` **refuses** a log whose class hash does not match the class file it is
given. When a class is loaded the harness prints its size and its bar on the panel: the critical
Sharpe of the class tier at the given alpha.

    quixote power --years 10 --class my_class.json --panel my_panel.npz

prints the smallest Sharpe the gate can certify for that class and that many years, before any
search is run.
