"""7.5 build item 3: the masked agent-facing view (`environments/planted_view.py`).

The registered test: **no real feature name crosses**. Everything an agent on a planted
panel can be shown is collected and searched: the system prompt, the orientation table,
the tool schemas, every tool result and refusal from a policy that calls every tool, and
`get_data`. The panel is synthetic, but it carries the real 40 ETF feature names and
real tickers, so a leak of either would show here.
"""
import json
import re

import numpy as np
import pytest

from environments import planted_panel as pp
from environments.planted_view import FeatureMask, agent_view, asset_permutation
from environments.real_panel import ETF_BASE
from environments.real_sandbox import RealSandbox
from quixote.agent_adapter import TOOLS, ToolRefused, ToolSession
from quixote.orientation import orientation_table, render
from quixote.session import Session
from tests.test_planted_panel import _panel

REAL_NAMES = [f"{nm}{sfx}" for nm in ETF_BASE for sfx in ("_z", "_rank")]
TICKERS = ["AGG", "DIA", "EEM", "EFA", "GLD", "IWM", "QQQ", "SPY"]


def _real_named_panel(K=40, M=8, T=400, seed=0):
    from dataclasses import replace
    p = _panel(T=T, M=M, K=K, seed=seed)
    return replace(p, feature_names=REAL_NAMES[:K], assets=TICKERS[:M],
                   meta={**p.meta, "prereg": "prereg/agent-on-real-data.md",
                         "source": "etf-daily"})


def _drive_every_tool(tools: ToolSession) -> list[str]:
    """Call every tool at least once, refusals included, and return all the text an
    agent would receive."""
    seen = [json.dumps(tools.tool_schemas())]

    def call(name, **kw):
        try:
            seen.append(tools.call(name, **kw).to_json())
        except (ToolRefused, ValueError) as e:
            seen.append(str(e))

    call("declare_triggers", triggers=[
        {"trigger": "failures_at_least", "param": 10, "action": "stop"},
        {"trigger": "failures_at_least", "param": 10, "action": "restart"}])
    call("pick_prior", support=[[3, 1.0]], reason="prior")
    call("short_list", supports=[[[1, 1.0]], [[2, -1.0]]])
    call("declare_budget", budget=30)
    call("init")
    call("pick", among=[0, 1, 2, 3], statistic="autocorr_1", choice=1)
    call("flip", feature=39)                     # refused unless held
    call("flip", feature=tools.session.support[0][0])
    call("refine")
    call("extend_best", keep=False)
    call("swap_worst")
    call("restart", trigger="failures_at_least", param=10)    # refused: does not fire
    call("change_trigger", trigger="failures_at_least", param=0, action="restart")
    call("restart", trigger="failures_at_least", param=0)
    call("change_trigger", trigger="failures_at_least", param=0, action="stop")
    call("stop", trigger="failures_at_least", param=0)
    call("extend_best")                          # refused: stopped
    call("predict", mean=0.4, sd=0.2)
    call("submit")
    call("no_such_tool")
    return seen


def _contains_any(text: str, words) -> list[str]:
    return [w for w in words if re.search(rf"(?<![A-Za-z0-9_]){re.escape(w)}"
                                          rf"(?![A-Za-z0-9_])", text)]


def test_no_real_feature_name_or_ticker_crosses_to_the_agent():
    from experiments.real_prompts import system_prompt_for
    panel = _real_named_panel()
    view, mask = agent_view(panel, 640000)
    sandbox = RealSandbox(view, spec_class=pp.CLS)
    tools = ToolSession(Session.on_sandbox(sandbox, pp.CLS, name_prefix="t"),
                        max_turns=60)
    seen = _drive_every_tool(tools)
    seen.append(render(orientation_table(view.features, labels=None, seed=640000)))
    for arm in ("replay gate", "replay gate (reasoned pick)"):
        seen.append(system_prompt_for(arm, view.features.shape[1],
                                      view.features.shape[2], 3))
    df = sandbox.get_data()
    seen.append(" ".join(map(str, df.columns)) + " " + " ".join(map(str, df["asset"].unique())))
    seen.append(json.dumps({"name": view.name, "meta": view.meta,
                            "assets": view.assets, "features": view.feature_names}))
    text = "\n".join(seen)
    assert _contains_any(text, REAL_NAMES) == []
    assert _contains_any(text, TICKERS) == []
    assert "etf" not in text.lower() and "prereg" not in text
    assert "submitted" in text                   # the policy really ran to the end


def test_the_view_is_the_true_panel_with_its_feature_axis_permuted():
    panel = _real_named_panel()
    view, mask = agent_view(panel, 640001)
    assert view.feature_names == [f"F{j:02d}" for j in range(40)]
    for j in range(40):
        assert np.array_equal(view.features[:, :, j], panel.features[:, :, mask.perm[j]])
    for a in ("returns", "cost_rate", "borrow_rate", "tradable"):
        assert np.array_equal(getattr(view, a), getattr(panel, a))
    assert sorted(view.assets) == [f"A{i:03d}" for i in range(8)]


def test_the_permutation_is_the_registered_stream_and_differs_by_panel():
    perms = [FeatureMask.for_seed(s, 40).perm for s in range(640000, 640006)]
    for s, p in zip(range(640000, 640006), perms):
        assert p == tuple(int(k) for k in pp.masking_permutation(s, 40))
        assert p != tuple(range(40))
    assert len(set(perms)) == len(perms)
    # index 32 (beta252_z on the ETF panel) lands on a different label per panel
    assert len({p.index(32) for p in perms}) > 1
    assert sorted(asset_permutation(640000, 40, 8)) == list(range(8))


def test_a_masked_support_unmasks_to_the_same_stream():
    """What the agent searched, mapped back, is the specification the harness prices."""
    panel = _real_named_panel()
    view, mask = agent_view(panel, 640002)
    masked = ((4, 1.0), (17, -1.0), (30, 1.0))
    true = mask.to_true(masked)
    assert mask.to_masked(true) == masked
    w_v, w_t = np.zeros(40), np.zeros(40)
    for k, s in masked:
        w_v[k] = s
    for k, s in true:
        w_t[k] = s
    a = view.stream_for_scores(view.scores_for_weights(w_v))
    b = panel.stream_for_scores(panel.scores_for_weights(w_t))
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-15)


def test_every_tool_was_exercised():
    """The leak test is only as wide as the surface it drove."""
    import inspect
    src = inspect.getsource(_drive_every_tool)
    missing = [t for t in TOOLS if f'"{t}"' not in src]
    assert missing == []
