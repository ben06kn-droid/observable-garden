"""A scripted searcher that restarts: the bundled example of a longer search.

It declares one rule before it looks at anything, restart after two moves that do not beat the
best so far, and has no stop rule of its own, so its search ends when the harness runs out of
anchors (recorded as a stop on `exhausted`) or the move budget. On each stem it anchors, extends,
then alternates swapping the weakest feature and flipping the newest one. Every move is kept;
a move that does not beat the best so far counts as a failure. As in `scripted_searcher.py`,
every number it sees comes from the harness.

    quixote run --agent examples.restart_searcher:Agent --panel examples/data/tiny_panel.npz \\
        --class examples/class.json --out examples/logs/restart_session.json
"""

RULE = {"trigger": "failures_at_least", "param": 2, "action": "restart"}


class Agent:
    """`next_move(view) -> dict`: the adapter interface (`quixote.run.Agent`)."""

    def __init__(self):
        self.phase = "declare"
        self.turn = 0          # moves on the current stem

    def next_move(self, view) -> dict:
        if self.phase == "declare":
            self.phase = "anchor"
            return {"tool": "declare_triggers", "triggers": [RULE]}   # before the first evaluation
        if self.phase == "anchor":
            self.phase = "search"
            return {"tool": "init"}
        if self.phase == "predict":
            self.phase = "submit"
            return {"tool": "predict", "mean": round(0.5 * (view.best or 0.0), 3), "sd": 0.5,
                    "note": "half the in-sample Sharpe"}
        if self.phase == "submit":
            return {"tool": "submit"}

        last = view.last or {}
        if "refused" in last or (last.get("ok") is False and "no anchor left" in last.get("text", "")):
            self.phase = "predict"                 # out of anchors, or nothing left to do
            return self.next_move(view)
        if (view.info.get("failures") or 0) >= RULE["param"]:
            self.turn = 0                          # the declared rule fires: a new stem
            return {"tool": "restart", "trigger": RULE["trigger"], "param": RULE["param"]}
        self.turn += 1
        if len(view.support) < 2:
            return {"tool": "extend_best"}
        if self.turn % 2 == 0:
            return {"tool": "swap_worst"}
        return {"tool": "flip", "feature": int(view.support[-1][0])}
