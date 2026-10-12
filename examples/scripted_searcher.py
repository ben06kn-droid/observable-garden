"""A scripted searcher: the simplest agent the harness runs.

It declares one stopping rule before it looks at anything, anchors on the best single feature,
extends while that helps, stops when its declared rule fires (or when the support is full),
states an expectation and submits. Every number it sees comes from the harness; it never builds
a rule itself.

    quixote run --agent examples.scripted_searcher:Agent --panel examples/data/tiny_panel.npz \\
        --class examples/class.json --out examples/logs/scripted_session.json
"""

RULE = {"trigger": "last_gain_at_most", "param": 0.0, "action": "stop"}


class Agent:
    """`next_move(view) -> dict`: the adapter interface (`quixote.run.Agent`)."""

    def __init__(self, max_size: int = 2):
        self.max_size = max_size
        self.phase = "declare"

    def next_move(self, view) -> dict:
        if self.phase == "declare":
            self.phase = "anchor"
            return {"tool": "declare_triggers", "triggers": [RULE]}   # before the first evaluation
        if self.phase == "anchor":
            self.phase = "extend"
            return {"tool": "init"}
        if self.phase == "extend":
            gain = view.info.get("last_gain")
            refused = view.last is not None and "refused" in view.last
            if refused or len(view.support) >= self.max_size or (gain is not None and gain <= 0.0
                                                                 and len(view.support) > 1):
                self.phase = "predict"
                if gain is not None and gain <= 0.0:          # the declared rule fires: stop on it
                    return {"tool": "stop", "trigger": RULE["trigger"], "param": RULE["param"]}
            else:
                return {"tool": "extend_best"}
        if self.phase == "predict":
            self.phase = "submit"
            best = view.best or 0.0
            return {"tool": "predict", "mean": round(0.5 * best, 3), "sd": 0.5,
                    "note": "half the in-sample Sharpe"}
        return {"tool": "submit"}
