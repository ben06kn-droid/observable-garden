# Search hits: the project codename and novelty claims, 2026-10-08

This is an inventory only; nothing is fixed. It searched every text file except .venv, .git, runs/, data/ and this file.

## 1. The codename "quixote" (case-insensitive), file:line

The package `quixote/` carries the name, so most hits are imports and paths.

```
EXPERIMENTS.md:148:| `fixed-sequence-replay` | what does freezing a search's meta decisions cost, and do declared triggers remove it? | **complete, read 2026-09
SCOPE.md:325:  taken (`quixote/`).
pyproject.toml:24:packages = ["environments", "searchers", "estimator", "garden", "quixote"]
README.md:93:quixote/        Don Quixote, the agent-facing gate: move grammar, session log
learn/stream_tier.py:41:    from quixote.confidence import confidence, render
ROADMAP.md:806:and nothing runs on the seat before that.** The five pre-agent-cell quixote changes
ROADMAP.md:1149:| 3 | **7.2 part one** (Don Quixote, `quixote/`) | local, no runs | tests green; stubs where part two decides |
ROADMAP.md:1388:**Four quixote changes registered 2026-09-28, to implement after 7.3 scripted and
ROADMAP.md:1389:before 6.5's agent cell.** Written in full in `quixote/README.md`; listed here so
ROADMAP.md:1419:**Status 2026-09-29: all five are IMPLEMENTED and tested.** Item 1 in `quixote/certify.py` and `quixote/verdict.py` (`p_certifying` is the submi
ROADMAP.md:1446:first post-fork action, leaving 3% of replayed states valid. **Quixote never
ROADMAP.md:1450:`quixote/README.md`. A gate that replayed the model would inherit exactly the
ROADMAP.md:1455:outcomes, at a cost of roughly 500 trading days to admission. Quixote certifies on
ROADMAP.md:1459:wherever a Quixote novelty line appears (`SCOPE.md`, `quixote/README.md`,
ROADMAP.md:1474:`quixote/README.md` and here, and is to be carried into the note's §4/§5 (the
ROADMAP.md:1613:`quixote/confidence.py` now labels `P_H` that way (`1140c61`). The first launch did not
experiments/planted_edge_preflight.py:20:(`quixote.grammar` semantics, both signs) in the order 6.5's agents most often used:
experiments/regrade_pilot.py:4:`quixote/replay.py`: `_run_logged` indexed the logged content moves by the global
experiments/regrade_pilot.py:54:    from quixote.grammar import Move
experiments/regrade_pilot.py:55:    from quixote.session import MoveRecord, SessionLog
experiments/regrade_pilot.py:83:    from quixote.replay import LoggedPolicy, commitment_check, integrity_check
experiments/regrade_pilot.py:134:    # Compared as a SET, for the reason `quixote/replay.py`'s `_compare` is: a
environments/class_table.py:164:        """A `score_fn(support, statistic)` for `quixote.grammar.Grammar`.
experiments/planted_edge_read.py:9:  (`quixote/certify.py`: CERTIFIED iff p < alpha). The class tier certifies; the trigger
experiments/agent_backend.py:33:from quixote.agent_adapter import ToolRefused, ToolSession
experiments/agent_backend.py:34:from quixote.session import Session
experiments/agent_backend.py:35:from quixote.twins import Masking
experiments/agent_backend.py:302:    """The quixote grammar. Every move is named, the harness performs it, and a
experiments/agent_backend.py:449:    from quixote.certify import certify
experiments/confidence_cell.py:12:  class argmax, the confidence fields of `quixote.confidence` on the class tier, and,
experiments/confidence_cell.py:45:from quixote.confidence import GRID, confidence
experiments/planted_agent.py:17:  (`quixote/replay.py`).
experiments/planted_agent.py:46:from quixote.agent_adapter import ToolSession
experiments/planted_agent.py:47:from quixote.session import Session
experiments/collect_submissions.py:6:`quixote.grammar.weights(support, K)` — the signed indicator over the declared class,
experiments/collect_submissions.py:25:from quixote.grammar import weights
experiments/grade_real.py:312:    from quixote.grammar import weights as grammar_weights
experiments/agent_pilot.py:23:- **replay gate** — the quixote grammar through `quixote/agent_adapter.py`, so
experiments/agent_pilot.py:44:from quixote.agent_adapter import ToolRefused, ToolSession
experiments/agent_pilot.py:45:from quixote.session import Session
experiments/agent_pilot.py:46:from quixote.twins import Masking
experiments/french_insample_read.py:123:    from quixote.confidence import confidence
experiments/unfaithful_searchers.py:50:from quixote.replay import LoggedPolicy
experiments/unfaithful_searchers.py:51:from quixote.grammar import Move
experiments/unfaithful_searchers.py:52:from quixote.replay import commitment_check, integrity_check
experiments/unfaithful_searchers.py:53:from quixote.session import Session, TriggerFired
experiments/unfaithful_searchers.py:54:from quixote.triggers import Trigger
experiments/unfaithful_searchers.py:175:    natural form and `quixote/replay.py` handles an inapplicable logged move by
experiments/unfaithful_searchers.py:490:    Replicate for replicate the procedure p is `quixote.certify.three_nulls`'
experiments/self_enforcement.py:30:from quixote.triggers import Trigger
experiments/diagnostics_2026_10_06.py:356:    from quixote import confidence as cf
experiments/agent_cell_class_p.py:18:1e-12 and not exactly (`quixote/grammar.py`), which is immaterial for a descriptive
experiments/agent_cell_class_p.py:53:    from quixote.grammar import Grammar
experiments/holdout_grading_read.py:166:    from quixote.confidence import GRID, masses
experiments/real_prompts.py:18:from quixote.agent_adapter import CONTENT_TOOLS, META_TOOLS
experiments/real_prompts.py:19:from quixote.triggers import PREDICATES
experiments/real_prompts.py:101:                "table from quixote.orientation, which is built from the feature "
experiments/fidelity.py:56:from quixote.log import render_shown
experiments/fidelity.py:100:    from quixote.grammar import Grammar, Move
experiments/fidelity.py:181:    from quixote.triggers import Trigger
experiments/code_state.py:145:    wider set -- `quixote/fingerprint.py` does -- can have one **without
experiments/planted_twins.py:5:`block_permutation`** (`quixote/twins.py`) — 39 return matrices per level — each
experiments/planted_twins.py:43:from quixote.twins import K_FOR_ALPHA, twin_p_value, twins
experiments/price_runs.py:135:    """The certifying null's replicate rows, as `quixote.certify.three_nulls` draws
experiments/price_runs.py:200:    Replicate rows are drawn exactly as `quixote.certify.three_nulls` draws them:
experiments/price_runs.py:209:    from quixote.confidence import confidence
experiments/price_runs.py:212:    from quixote.confidence import render
experiments/agent_cell.py:51:from quixote.agent_adapter import ToolSession
experiments/agent_cell.py:52:from quixote.orientation import orientation_table, render, table_hash
experiments/agent_cell.py:53:from quixote.session import Session
tests/test_class_table.py:22:from quixote.grammar import Move
tests/test_class_table.py:23:from quixote.replay import identity_check
tests/test_class_table.py:24:from quixote.session import Session
tests/test_class_table.py:196:    from quixote.agent_adapter import QuixoteAgent, ToolSession
tests/test_class_table.py:207:    agent = QuixoteAgent(CLS, policy)
tests/test_class_table.py:211:    sess = Session.on_sandbox(sb_b, CLS, name_prefix="quixote-agent")
tests/test_class_table.py:212:    from quixote.triggers import Trigger
tests/test_class_table.py:301:    from quixote.replay import identity_check
tests/test_class_table.py:333:    from quixote.certify import certify
tests/test_class_table.py:334:    from quixote.triggers import Trigger
tests/test_collect_submissions.py:5:`quixote.grammar.weights`, because a second implementation of "what the submission means"
tests/test_collect_submissions.py:45:    from quixote.grammar import weights
tests/test_agent_adapter.py:18:from quixote.agent_adapter import (CONTENT_TOOLS, META_TOOLS, TOOLS, QuixoteAgent,
tests/test_agent_adapter.py:20:from quixote.grammar import Move
tests/test_agent_adapter.py:21:from quixote.session import Session
tests/test_agent_adapter.py:22:from quixote.triggers import Trigger
tests/test_agent_adapter.py:112:    agent = QuixoteAgent(cls, policy_via_tools)
tests/test_agent_adapter.py:116:    session = Session.on_sandbox(sb_direct, cls, name_prefix="quixote-agent")
tests/test_agent_adapter.py:138:    agent = QuixoteAgent(cls, policy_via_tools)
tests/test_agent_adapter.py:142:    session = Session.on_sandbox(sb_direct, cls, name_prefix="quixote-agent")
tests/test_agent_adapter.py:151:    from quixote.grammar import CONTENT_KINDS
tests/test_agent_adapter.py:277:    from quixote.grammar import Grammar
tests/test_agent_adapter.py:308:    QuixoteAgent(cls, lambda t: t.call("init")).run(sb)          # no explicit submit
tests/test_agent_adapter.py:340:    agent = QuixoteAgent(cls, policy_via_tools)
tests/test_agent_adapter.py:344:    session = Session.on_sandbox(sb_direct, cls, name_prefix="quixote-agent")
tests/test_agent_adapter.py:354:    from quixote.replay import IdentityCheck
tests/test_agent_adapter.py:377:    from quixote.replay import IdentityCheck
tests/test_agent_adapter.py:511:    from quixote.certify import certify
tests/test_agent_adapter.py:573:    from quixote.grammar import CONTENT_KINDS, Grammar, Move
tests/test_agent_adapter.py:604:    from quixote.grammar import Grammar, Move
tests/test_agent_adapter.py:616:    from quixote.replay import LoggedPolicy
tests/test_agent_adapter.py:639:    from quixote.certify import certify
tests/test_fixed_sequence_replay.py:59:    from quixote.grammar import Move
tests/test_fixed_sequence_replay.py:60:    from quixote.triggers import Trigger
tests/test_fixed_sequence_replay.py:61:    from quixote.replay import LoggedPolicy, integrity_check
tests/test_fixed_sequence_replay.py:62:    from quixote.session import Session, TriggerFired
tests/test_fixed_sequence_replay.py:142:    from quixote.grammar import Move
tests/test_fixed_sequence_replay.py:143:    from quixote.replay import LoggedPolicy
tests/test_fixed_sequence_replay.py:144:    from quixote.session import Session, TriggerFired
tests/test_fixed_sequence_replay.py:145:    from quixote.triggers import Trigger
tests/test_fixed_sequence_replay.py:225:    from quixote.replay import integrity_check
tests/test_agent_prompts_real.py:11:from quixote.agent_adapter import CONTENT_TOOLS, META_TOOLS, TOOLS, ToolSession
tests/test_agent_prompts_real.py:12:from quixote.twins import Masking
tests/test_agent_prompts_real.py:21:    from quixote.orientation import orientation_table, render
tests/test_agent_prompts_real.py:99:    """'The trigger list in the prompt is the library in quixote/triggers.py and
tests/test_agent_prompts_real.py:230:    quixote/statistics.py, as it already names the three triggers, and the two
tests/test_agent_prompts_real.py:232:    from quixote.statistics import STATISTICS
tests/test_agent_prompts_real.py:277:    from quixote.statistics import STATISTICS
tests/test_move_completeness.py:3:Registered 2026-09-28 in `quixote/README.md`, implemented after 7.3 scripted.
tests/test_move_completeness.py:23:from quixote.grammar import Move
tests/test_move_completeness.py:24:from quixote.session import Session
tests/test_move_completeness.py:109:    from quixote.grammar import MOVE_KINDS
tests/test_pre_agent_cell.py:4:All three were registered on 2026-09-28/29 in `quixote/README.md` and `ROADMAP.md`
tests/test_pre_agent_cell.py:6:to the submitted specification) is tested in `tests/test_quixote_certify.py`; item
tests/test_pre_agent_cell.py:15:from quixote.grammar import Move
tests/test_pre_agent_cell.py:16:from quixote.session import Session, TriggerFired
tests/test_pre_agent_cell.py:17:from quixote.triggers import Trigger
tests/test_pre_agent_cell.py:76:    from quixote.replay import LoggedPolicy
tests/test_pre_agent_cell.py:207:    from quixote.replay import LoggedPolicy
tests/test_pre_agent_cell.py:208:    from quixote.triggers import PREDICATES, Trigger
tests/test_pre_agent_cell.py:252:    from quixote.triggers import Trigger
tests/test_grade_real.py:224:    from quixote.grammar import weights as gw
tests/test_grade_real.py:300:    from quixote.grammar import weights as gw
tests/test_agent_cell.py:25:    from quixote.orientation import orientation_table, render
tests/test_agent_cell.py:122:    from quixote.agent_adapter import ToolSession
tests/test_agent_cell.py:123:    from quixote.session import Session
tests/test_agent_cell.py:179:    from quixote.agent_adapter import ToolSession
tests/test_agent_cell.py:180:    from quixote.session import Session
tests/test_agent_cell.py:205:    from quixote.log import InformationSet
tests/test_agent_cell.py:264:    from quixote.log import render_shown
tests/test_agent_cell.py:289:    from quixote.log import render_shown
tests/test_agent_cell.py:380:    from quixote.log import render_shown
tests/test_agent_cell.py:423:    from quixote.agent_adapter import ToolSession
tests/test_agent_cell.py:424:    from quixote.session import Session
tests/test_agent_cell.py:443:    from quixote.agent_adapter import ToolSession
tests/test_agent_cell.py:444:    from quixote.replay import LoggedPolicy
tests/test_agent_cell.py:445:    from quixote.session import Session
tests/test_agent_cell.py:484:    from quixote.agent_adapter import ToolSession
tests/test_agent_cell.py:485:    from quixote.session import Session
tests/test_replay_cap.py:12:from quixote.agent_adapter import ToolSession
tests/test_replay_cap.py:13:from quixote.replay import LoggedPolicy, integrity_check
tests/test_replay_cap.py:14:from quixote.session import Session
tests/test_holdout_grading_read.py:13:from quixote.confidence import confidence
tests/test_quixote_certify.py:15:from quixote.certify import CERTIFYING_NULL, certify, three_nulls
tests/test_quixote_certify.py:16:from quixote.drivers import restart_after_k_failures, stop_when_cleared
tests/test_quixote_certify.py:17:from quixote.session import Session
tests/test_quixote_certify.py:18:from quixote.verdict import EXIT_CODES
tests/test_quixote_certify.py:38:    from quixote.replay import LoggedPolicy
tests/test_quixote_certify.py:137:    """Registered 2026-09-28 in `quixote/README.md`, implemented after 7.3 scripted.
tests/test_quixote_certify.py:167:    from quixote.grammar import Move
tests/test_quixote_certify.py:168:    from quixote.session import Session, TriggerFired
tests/test_quixote_certify.py:169:    from quixote.triggers import Trigger
tests/test_orientation.py:12:from quixote.orientation import (CORR_THRESHOLD, EXCLUDED_BY_NAME, orientation_table,
tests/test_orientation.py:72:    from quixote.orientation import CORR_THRESHOLD as C
tests/test_planted_view.py:19:from quixote.agent_adapter import TOOLS, ToolRefused, ToolSession
tests/test_planted_view.py:20:from quixote.orientation import orientation_table, render
tests/test_planted_view.py:21:from quixote.session import Session
tests/test_price_runs_planted.py:21:from quixote.agent_adapter import ToolSession
tests/test_price_runs_planted.py:22:from quixote.session import Session
tests/test_quixote_part_one.py:12:from quixote.consistency import check_picks, contradicted_steps
tests/test_quixote_part_one.py:13:from quixote.grammar import Grammar, Move
tests/test_quixote_part_one.py:14:from quixote.session import Session
tests/test_quixote_part_one.py:15:from quixote.statistics import MINIMISED, STATISTICS, better, evaluate
tests/test_quixote_part_one.py:16:from quixote.twins import (DESTROYS, K_FOR_ALPHA, Masking, block_permutation,
tests/test_quixote_part_one.py:239:    importlib.import_module("quixote.twins")
tests/test_quixote_part_one.py:240:    # `quixote/__init__.py` re-exports the `twins` FUNCTION, which shadows the
tests/test_quixote_part_one.py:242:    tw = sys.modules["quixote.twins"]
tests/test_confidence.py:1:"""Confidence fields (`quixote/confidence.py`; `prereg/confidence-output.md`, draft)."""
tests/test_confidence.py:9:from quixote import confidence as cf
tests/test_confidence.py:85:    from quixote.agent_adapter import ToolSession
tests/test_confidence.py:86:    from quixote.certify import certify
tests/test_confidence.py:87:    from quixote.session import Session
tests/test_confidence.py:146:    from quixote.agent_adapter import ToolSession
tests/test_confidence.py:147:    from quixote.certify import certify
tests/test_confidence.py:148:    from quixote.session import Session
tests/test_unfaithful_searchers.py:123:    from quixote.session import Session
tests/test_unfaithful_searchers.py:145:    from quixote.session import Session
tests/test_unfaithful_searchers.py:173:    from quixote.replay import LoggedPolicy
tests/test_unfaithful_searchers.py:174:    from quixote.session import Session
tests/test_unfaithful_searchers.py:250:    from quixote.session import Session
tests/test_unfaithful_searchers.py:309:    from quixote.session import Session
tests/test_unfaithful_searchers.py:383:    the same number `quixote.certify.three_nulls` would give for that null, on
tests/test_unfaithful_searchers.py:386:    from quixote.certify import three_nulls
tests/test_unfaithful_searchers.py:387:    from quixote.session import Session
tests/test_quixote_milestones.py:1:"""Don Quixote, 7.2 part one: the two milestones, and the invariants they rest on.
tests/test_quixote_milestones.py:20:from quixote.drivers import signed_adaptive
tests/test_quixote_milestones.py:21:from quixote.grammar import Grammar, Move
tests/test_quixote_milestones.py:22:from quixote.replay import LoggedPolicy
tests/test_quixote_milestones.py:23:from quixote.session import Session
tests/test_quixote_milestones.py:142:    """quixote imports garden and estimator; nothing imports quixote."""
tests/test_quixote_milestones.py:146:            assert "import quixote" not in f.read_text(), f
tests/test_quixote_milestones.py:149:def test_quixote_is_not_in_code_paths_and_has_its_own_fingerprint():
tests/test_quixote_milestones.py:151:    from quixote.fingerprint import QUIXOTE_PATHS, quixote_fingerprint
tests/test_quixote_milestones.py:152:    assert "quixote" not in CODE_PATHS          # no published fingerprint moves
tests/test_quixote_milestones.py:153:    assert "quixote" in QUIXOTE_PATHS
tests/test_quixote_milestones.py:154:    assert quixote_fingerprint() != code_fingerprint()
tests/test_quixote_milestones.py:156:        assert dep in QUIXOTE_PATHS             # what quixote imports is inside it
tests/test_quixote_milestones.py:166:    from quixote.replay import identity_check
tests/test_quixote_milestones.py:180:    from quixote.replay import identity_check
tests/test_quixote_milestones.py:205:    from quixote.replay import identity_check
tests/test_quixote_milestones.py:227:from quixote.drivers import restart_after_k_failures, stop_when_cleared  # noqa: E402
tests/test_quixote_milestones.py:308:    from quixote.replay import identity_check
tests/test_quixote_milestones.py:326:    from quixote.replay import identity_check
tests/test_quixote_milestones.py:364:    from quixote.triggers import Trigger
docs/CITATIONS.md:44:**Cited, since 2026-10-02, in `THEORY.md` (the bootstrap definitions, and prior work for P4) and `quixote/README.md` (the central idea), as
docs/CITATIONS.md:64:**Cited for:** the twin rank p-value `(1 + #)/(K + 1)` (`quixote/twins.py`,
docs/CITATIONS.md:81:conservative. `quixote/twins.py` is reworded (2026-10-02), and
docs/CITATIONS.md:95:(`prereg/twin-calibration.md`, `quixote/twins.py`, `quixote/__init__.py`, a test).
tests/test_confidence_cell.py:10:from quixote.confidence import GRID
tests/test_quixote_pricing.py:15:from quixote.certify import certify, three_nulls
tests/test_quixote_pricing.py:16:from quixote.drivers import stop_when_cleared
tests/test_quixote_pricing.py:17:from quixote.pricing import DEFAULT, LICENSED_BY, PricingOptions, steps_to_price
tests/test_quixote_pricing.py:18:from quixote.session import Session
tests/test_quixote_pricing.py:80:    from quixote.grammar import Grammar
tests/test_quixote_pricing.py:81:    from quixote.replay import LoggedPolicy
tests/test_quixote_pricing.py:147:    src = (Path(__file__).resolve().parent.parent / "quixote" / "pricing.py").read_text()
docs/RELATED_WORK_2026.md:93:days to admission — whereas Quixote certifies on the in-sample data already in
docs/RELATED_WORK_2026.md:112:Quixote, because **Quixote never replays the LLM** — it replays harness-executed
tests/test_content_cap.py:11:from quixote.agent_adapter import CONTENT_TOOLS, ToolRefused, ToolSession
tests/test_content_cap.py:12:from quixote.session import Session
prereg/planted-edge.md:898:   Trigger replay as it stands (`quixote/replay.py`) bounds a replicate by the
prereg/planted-edge.md:1372:  trigger changes, so its verdict was DEPENDS_ON_JUDGMENT. `quixote/certify.py`'s
prereg/planted-edge.md:1551:  run: the read used the stored replay verdicts. `quixote/pricing.py` marks local
prereg/estimators-exploratory-2026-10-06.md:300:(`L_0.90`, `quixote/confidence.py`) beside a certified verdict, not a point estimate.
prereg/AGENT_PROMPTS_REAL.md:57:`quixote/agent_adapter.py`. `pick_prior` is there by amendment 1. Appended:
prereg/AGENT_PROMPTS_REAL.md:73:The trigger list in the prompt is the library in `quixote/triggers.py` and is
prereg/AGENT_PROMPTS_REAL.md:150:  (`Masking.ALLOWED_FIELDS` in `quixote/twins.py`, which **refuses** metadata
prereg/AGENT_PROMPTS_REAL.md:203:   list is `quixote/triggers.py`'s library, generated from it;
prereg/AGENT_PROMPTS_REAL.md:218:read. The tool exists in `quixote/agent_adapter.py` and the session already
prereg/AGENT_PROMPTS_REAL.md:243:The block above now names the five statistics of `quixote/statistics.py`, exactly as
prereg/AGENT_PROMPTS_REAL.md:245:the two cannot drift. **IC stays absent**, as `quixote/statistics.py` records: it needs
prereg/AGENT_PROMPTS_REAL.md:300:The block in §2 above states both to the agent. `quixote/session.py` enforces
prereg/AGENT_PROMPTS_REAL.md:301:them (`declare_triggers`, `change_trigger`), and `quixote/agent_adapter.py`
prereg/AGENT_PROMPTS_REAL.md:334:substituted with the rendered table from `quixote/orientation.py`, whose builder
prereg/agent-cell.md:56:**Enforced in code, not asserted in prose.** `quixote/orientation.py`'s builder
prereg/agent-cell.md:256:Corrected in this file and in `quixote/orientation.py`'s own statement of the
prereg/agent-cell.md:316:(`quixote/pricing.py`'s fidelity-driven pricing, which exists behind a flag that
prereg/agent-cell.md:337:before this cell reports: `quixote/pricing.py`'s local-max and fidelity-driven
prereg/agent-cell.md:427:**What is in place.** `quixote/log.py`'s `InformationSet` carries a `shown` field
prereg/agent-cell.md:432:**What is missing.** `quixote/agent_adapter.py` calls `session.propose(move)` with
prereg/agent-cell.md:518:that was sent, BYTE FOR BYTE.** One function, `quixote.log.render_shown`, both
prereg/agent-cell.md:543:(`quixote/agent_adapter.py`). A pick over five features in a signed class adds ten
prereg/agent-cell.md:669:p-value**, because `quixote/certify.py` does not price that null on a run with a
prereg/agent-cell.md:1128:original except the replaced numbers** — built with `quixote.log.render_shown`, the same
prereg/agent-cell.md:1526:verdict or flag depended on it. The same correction is in `quixote/pricing.py`,
prereg/french-panel.md:293:- the confidence curve (`quixote.confidence.confidence`, all its fields).
prereg/holdout-grading.md:67:     with the gate's own `quixote.grammar.weights`.
prereg/holdout-grading.md:150:population Sharpe under stationarity (`quixote/confidence.py`). **Coverage** is the share
prereg/AGENT_PROMPTS.md:212:**14 — 2026-09-21.** `pyproject.toml` gains `quixote` in its `packages` list, for
prereg/AGENT_PROMPTS.md:213:the Don Quixote build. **`pyproject.toml` is inside `code_state.CODE_PATHS`, so
prereg/AGENT_PROMPTS.md:217:install, and alters no import, no estimator, no bar and no verdict. `quixote` is
prereg/AGENT_PROMPTS.md:223:quixote out of `CODE_PATHS` so no fingerprint moves, and add quixote to
prereg/AGENT_PROMPTS.md:231:Quixote runs do not use this fingerprint at all. They record their own, over
prereg/AGENT_PROMPTS.md:232:`quixote` plus everything quixote imports, via `quixote/fingerprint.py`;
prereg/binance-panel.md:229:  the class tier, `quixote.confidence` (P_H) and `RealSandbox` all take
prereg/binance-panel.md:231:  anywhere on the pricing path. (`quixote.confidence`'s default `ppy = 252.0` is always
prereg/confidence-output.md:304:| code, by file | `experiments/confidence_cell.py` `a64ca42`; `experiments/confidence_cell_read.py` `ec6d8ae`; `quixote/confiden
prereg/confidence-output.md:464:From `quixote/confidence.py` (`render`): **`P_H` is printed only beside a certified
prereg/diagnostics-2026-10-06.md:238:  - **Gate:** the curve read as atoms on the grid with `quixote.confidence.masses`.
prereg/agent-pilot.md:12:`quixote/certify.py` is built on it. What no experiment has done is put a
prereg/agent-pilot.md:135:`quixote/agent_adapter.py` now latches: after a stop that fires, only `predict`
prereg/agent-pilot.md:200:  masked ADR panel, open the class, drive `quixote/agent_adapter.py` for the
prereg/agent-pilot.md:226:`quixote/grammar.py`, with two tests, and the pilot is run a third time so that
prereg/agent-pilot.md:313:**What the guard is.** Before pricing anything, `quixote/replay.py` replays the
prereg/agent-pilot.md:744:`quixote/replay.py` found while building 7.3's faithful arm. One of them affects
prereg/agent-pilot.md:850:`Sandbox` plus the quixote grammar is a path only the dry run has taken.
quixote/consistency.py:18:when 7.3 licenses that (`quixote/pricing.py`). Until then the verdict reports it
quixote/consistency.py:32:from quixote.grammar import Grammar
quixote/README.md:1:# Don Quixote
quixote/README.md:7:`quixote/` is the **agent-facing** form of the gate in `garden/`. Where `garden`
quixote/README.md:8:audits a finished transcript, `quixote` sits inside the search while it happens.
quixote/README.md:15:trigger replay is the certifying null (`quixote/certify.py`), and local-max and
quixote/README.md:90:| `verdict.py` | `QuixoteVerdict` — the bracket and bits fields |
quixote/README.md:91:| `fingerprint.py` | what pins a quixote run to its code |
quixote/README.md:174:`QuixoteVerdict` carries item 1's bracket (`p_frozen`, `p_upper`) and item 6's
quixote/README.md:188:`quixote` is deliberately **absent** from `experiments.code_state.CODE_PATHS`.
quixote/README.md:192:Quixote runs record their own, over `QUIXOTE_PATHS` — quixote **plus everything
quixote/README.md:193:quixote imports**.
quixote/README.md:195:**The dependency constraint is exactly two rules:** nothing imports `quixote`
quixote/README.md:197:`experiments`), and `quixote` stays out of `CODE_PATHS`. Which packages quixote
quixote/README.md:200:the meta replay — and all four are inside `QUIXOTE_PATHS`, because a change in
quixote/README.md:201:any of them changes what a quixote run does.
quixote/README.md:205:adding `quixote` to pyproject's `packages` list, since `pyproject.toml` is itself
quixote/README.md:238:`quixote/triggers.py` with its parameter, stamped with the value it saw **before**
quixote/README.md:270:7.1 reported on 2026-09-24, so the first two are built (`quixote/certify.py`):
quixote/README.md:279:default to off** (`quixote/pricing.py`). Both replace a step with the best
quixote/README.md:288:- **the consistency check** (`quixote/consistency.py`) — for every `pick`, the
quixote/README.md:301:  (`quixote/statistics.py`). The library is Sharpe, volatility, autocorrelation
quixote/README.md:308:- **the twin generator and identifier masking** (`quixote/twins.py`) — joint
quixote/README.md:324:requires importing quixote.
quixote/README.md:338:**It does not reach Quixote, and the reason is the grammar.** Quixote **never
quixote/README.md:361:to admission — where Quixote certifies on the in-sample data already in hand and
quixote/README.md:377:`tests/test_quixote_milestones.py` for what is actually guaranteed.
quixote/README.md:440:**Status 2026-09-29: all five are IMPLEMENTED and tested.** Item 1 in `quixote/certify.py` and `quixote/verdict.py` (`p_certifying` is the
quixote/grammar.py:18:each is taken because a declared trigger fired (`quixote/triggers.py`), and the
quixote/grammar.py:50:    # agent says the rule makes (checked by quixote/consistency.py)
quixote/grammar.py:253:        from quixote.statistics import evaluate as stat_of
quixote/grammar.py:287:        from quixote.statistics import better
quixote/certify.py:38:from quixote.confidence import confidence
quixote/certify.py:39:from quixote.confidence import render as render_confidence
quixote/certify.py:40:from quixote.pricing import DEFAULT as NO_PRICING
quixote/certify.py:41:from quixote.pricing import PricingOptions, steps_to_price
quixote/certify.py:42:from quixote.replay import (LoggedPolicy, commitment_check,
quixote/certify.py:44:from quixote.verdict import DEPENDS_ON_JUDGMENT, QuixoteVerdict
quixote/certify.py:73:    `tests/test_quixote_certify.py` holds the two equal. It is repeated here only
quixote/certify.py:139:            pricing: PricingOptions = NO_PRICING, table=None) -> QuixoteVerdict:
quixote/certify.py:156:        return QuixoteVerdict(
quixote/certify.py:170:        # pre-change rule is what replays (`quixote/session.change_trigger`), so
quixote/certify.py:178:            v = QuixoteVerdict(
quixote/certify.py:207:        return QuixoteVerdict(
quixote/certify.py:233:    v = QuixoteVerdict(
prereg/twin-calibration.md:194:`block_permutation`** (`quixote/twins.py`, block 21), seeded by `SeedSequence(seed)`'s
quixote/drivers.py:13:from quixote.grammar import Move
quixote/drivers.py:14:from quixote.session import Session
quixote/drivers.py:105:    from quixote.triggers import stop_when_cleared as trig
quixote/drivers.py:111:    from quixote.triggers import restart_after_failures as trig
prereg/ml-pipeline-exploratory-2026-10-07.md:28:  curve, as for any class (`quixote/confidence.py`).
quixote/log.py:21:from quixote.grammar import Move, Support
quixote/log.py:121:    # True for a log opened through `quixote.agent_adapter.ToolSession`, i.e. the
quixote/fingerprint.py:1:"""How a Don Quixote run is pinned to the code that produced it.
quixote/fingerprint.py:3:`quixote` is deliberately **absent** from `experiments.code_state.CODE_PATHS`.
quixote/fingerprint.py:9:So quixote runs carry their own, over a wider set of paths than the existing one:
quixote/fingerprint.py:10:`quixote` plus **everything quixote imports**. The dependency is one-way --
quixote/fingerprint.py:12:`quixote` -- but a change in `garden` still changes what a quixote run does, so
quixote/fingerprint.py:22:QUIXOTE_PATHS = ("quixote", "garden", "estimator", "environments", "searchers")
quixote/fingerprint.py:25:def quixote_fingerprint() -> str:
quixote/fingerprint.py:26:    """A fingerprint over QUIXOTE_PATHS, computed the same way `code_state` does
quixote/fingerprint.py:29:    inner = code_fingerprint(paths=QUIXOTE_PATHS) if _accepts_paths() else None
quixote/fingerprint.py:33:            "argument; quixote must not widen CODE_PATHS to compensate, because "
quixote/fingerprint.py:35:    return hashlib.sha256(f"quixote:{inner}".encode()).hexdigest()[:16]
quixote/fingerprint.py:43:def quixote_code_state() -> dict:
quixote/fingerprint.py:44:    return {"head": head_sha(), "quixote_fingerprint": quixote_fingerprint(),
quixote/fingerprint.py:46:            "paths": list(QUIXOTE_PATHS),
quixote/fingerprint.py:47:            "note": "quixote is not in experiments.code_state.CODE_PATHS by "
quixote/fingerprint.py:48:                    "design; see quixote/fingerprint.py"}
quixote/session.py:16:from quixote.grammar import Grammar, Move, Support, weights
quixote/session.py:17:from quixote.log import InformationSet, MoveRecord, SessionLog
quixote/session.py:18:from quixote.triggers import Trigger
quixote/session.py:57:    def on_sandbox(cls, sandbox, spec_class, name_prefix: str = "quixote"):
quixote/session.py:62:        from quixote.grammar import weights as _w
quixote/session.py:136:        so the log records the change as a fact and `quixote/certify.py` decides
quixote/session.py:214:        commitment replay rightly refused the run. `quixote/replay.py` has always
quixote/session.py:222:        than by coincidence. `tests/test_quixote_session.py` holds them equal.
quixote/session.py:282:        # (quixote/consistency.py).
quixote/session.py:475:        `quixote.replay` runs, on the basis the session itself searched, at the
quixote/session.py:483:        from quixote.replay import integrity_check
quixote/agent_adapter.py:1:"""The grammar as tools: what an LLM agent is allowed to do in a quixote session.
quixote/agent_adapter.py:5:for what it built. That is exactly the arrangement the quixote grammar exists to
quixote/agent_adapter.py:58:`restart` each take a trigger from `quixote/triggers.py` by name and parameter;
quixote/agent_adapter.py:65:`QuixoteAgent` is the `Searcher` that drives it. Keeping the model out of this
quixote/agent_adapter.py:78:from quixote.grammar import Move
quixote/agent_adapter.py:79:from quixote.log import render_shown
quixote/agent_adapter.py:80:from quixote.session import Session, TriggerFired
quixote/agent_adapter.py:81:from quixote.triggers import PREDICATES, Trigger
quixote/agent_adapter.py:121:    """One quixote session behind a tool surface.
quixote/agent_adapter.py:433:class QuixoteAgent:
quixote/agent_adapter.py:437:    sandbox and submits exactly once, so a quixote run is graded by the same
quixote/agent_adapter.py:442:    name = "quixote-agent"
quixote/verdict.py:1:"""The Verdict Don Quixote returns.
quixote/verdict.py:26:class QuixoteVerdict:
quixote/verdict.py:72:    # `quixote.confidence.confidence`, `prereg/confidence-output.md` (draft). Beside
quixote/verdict.py:76:    # -- local-max and fidelity-driven pricing (quixote/pricing.py) ---------
quixote/__init__.py:1:"""Don Quixote: the agent-facing form of the gate.
quixote/__init__.py:15:- **which null certifies: trigger replay** (`quixote/certify.py`). Its rejection
quixote/__init__.py:25:**Built but not licensed** (`quixote/pricing.py`): local-max pricing and
quixote/__init__.py:33:**Part one is complete.** The consistency check (`quixote/consistency.py`),
quixote/__init__.py:34:`pick` with its statistic library and `else` branch (`quixote/statistics.py`,
quixote/__init__.py:36:(`quixote/twins.py`) are built and tested. Two things are deliberately absent
quixote/__init__.py:46:Dependency direction is one-way and enforced by test: nothing imports `quixote`,
quixote/__init__.py:47:and `quixote` stays out of `CODE_PATHS`. What quixote itself imports is not
quixote/__init__.py:49:`quixote` is deliberately absent from `experiments.code_state.CODE_PATHS`, so
quixote/__init__.py:50:adding it moves no published fingerprint; quixote runs record their own
quixote/__init__.py:51:fingerprint instead. See `quixote/fingerprint.py`.
quixote/__init__.py:53:from quixote.certify import CERTIFYING_NULL, certify, three_nulls
quixote/__init__.py:54:from quixote.consistency import check_picks
quixote/__init__.py:55:from quixote.pricing import PricingOptions
quixote/__init__.py:56:from quixote.statistics import STATISTICS
quixote/__init__.py:57:from quixote.twins import Masking, twin_p_value, twins
quixote/__init__.py:58:from quixote.grammar import Grammar, Move, Support
quixote/__init__.py:59:from quixote.log import InformationSet, MoveRecord, SessionLog
quixote/__init__.py:60:from quixote.verdict import QuixoteVerdict
quixote/__init__.py:63:           "SessionLog", "QuixoteVerdict", "certify", "three_nulls",
quixote/replay.py:34:from quixote.grammar import Grammar, Move
quixote/replay.py:35:from quixote.log import SessionLog
quixote/replay.py:36:from quixote.triggers import Trigger
quixote/replay.py:48:    # quixote.certify reports as engagement, and the condition under which a
quixote/replay.py:101:        # instead of the logged continuation (quixote/pricing.py). Empty by
quixote/pricing.py:26:(`tests/test_quixote_pricing.py` pins this). These rules bite on a continuation
```

## 2. Novelty-claim wording, file:line

These are wording hits. The THEORY.md lines at 135, 277 and 313 are the labelled P4, P4' and P5 headings, and THEORY.md 456–478 is the novelty paragraph that belongs to them. Every other hit is outside those sections.

```
OPEN_QUESTIONS.md:3:## The "no new estimator variants" rule and its carve-outs
OPEN_QUESTIONS.md:203:  new estimator; frozen.
THEORY.md:135:## P4. Winner anchoring is anti-conservative; loser anchoring is conservative (new)
THEORY.md:277:## P4′. The realized-menu null is a uniform mixture over anchor ranks (new)
THEORY.md:313:## P5. Greedy search and the lattice optimum (new, corrected)
THEORY.md:456:**Novelty of the anchoring SIGN result, at the strength the search supports.**
THEORY.md:457:Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior replay of
THEORY.md:478:  on each replicate. The 2026-09-30 search's "no prior replay" sentence above is read
ROADMAP.md:439:   number nobody has.
ROADMAP.md:455:runs on the new gate as well as the old.
ROADMAP.md:464:**Prior art, to be read in full before any novelty claim.**
ROADMAP.md:1049:   holdout) is the number nobody has.
ROADMAP.md:1089:below is described as novel anywhere in this repository; prior art is either
ROADMAP.md:1152:| 6 | item 4's experiment | EC2 | anchor exact under the new statistic |
ROADMAP.md:1422:here because Phase 7 is where the replay tier is built and a novelty claim about it
ROADMAP.md:1458:**Novelty wording, fixed at the strength the search supports**, and used verbatim
ROADMAP.md:1459:wherever a Quixote novelty line appears (`SCOPE.md`, `quixote/README.md`,
ROADMAP.md:1462:(`docs/RELATED_WORK_2026.md`) found no prior replay of an adaptive search's logged
ROADMAP.md:1464:pricing. Not a proof of absence.* **No stronger novelty claim is made anywhere.**
SCOPE.md:327:**Novelty of the replay tier, at the strength the search supports.** Literature
SCOPE.md:328:search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior replay of an
SCOPE.md:342:That the failure mode is real is not novel, and the theory naming it predates
experiments/e_watch_validation.py:159:    reload the first pass's checkpoints and report them as new results. In the
docs/CITATIONS.md:46:**What it says**, and why it matters to novelty wording:
docs/RELATED_WORK_2026.md:273:No prior replay of an adaptive search's logged decisions inside a data-snooping
prereg/adr-features.md:14:No novelty is claimed for anything here.
prereg/adr-features.md:147:   positive, is the readout nobody has, and it needs FAILs to measure.
prereg/pivotal-interrogation.md:4:bracket. Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
prereg/pivotal-interrogation.md:139:under a resampled null. No novelty claim is made here.
prereg/estimators-exploratory-2026-10-06.md:221:Nothing here is a new method.
prereg/README.md:114:**No novelty claims.** No pre-registration, ROADMAP entry or write-up in this
prereg/README.md:115:repository describes a method as novel, new, first or unprecedented. Where prior
prereg/README.md:117:searched". Novelty is settled separately and deliberately, not asserted in
prereg/bracketed-verdicts.md:4:path; validated in 7.3. Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
prereg/adr-universe.md:9:No novelty is claimed for anything here.
prereg/point-estimate.md:18:## Prior art. Nothing here is a new method
prereg/point-estimate.md:29:  to a scripted searcher. **This draft claims no new method.** What it would measure is
prereg/agent-pilot.md:848:**It also exercises the simulated panel behind the grammar for the first time.**
prereg/agent-pilot.md:910:item 1 of the 2026-09-27 list — fired for the first time here and carried the
prereg/agent-pilot.md:1076:pick from a model for the first time**, and the arm's pick yield at the cell's n is
prereg/agent-pilot.md:1143:for the first time.** The arm's yield at the cell's n = 20 per config is unmeasured,
prereg/living-verdict.md:5:is recorded in `ROADMAP.md`. Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
prereg/ml-pipeline-exploratory-2026-10-07.md:189:will follow it. **No new method is claimed.**
prereg/agent-cell.md:1186:`best_so_far_above` is enforced for the first time and fires first on **3 of 20** s3 runs
quixote/README.md:22:stopping, and the living verdict. Nothing here is claimed to be novel; prior art
quixote/README.md:365:**Novelty, stated at the strength the search supports.** Literature search
quixote/README.md:366:2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior replay of an adaptive
prereg/prior-weighted-alpha.md:4:scripted searchers in 7.3, and an arm in 7.4. Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
prereg/confidence-output.md:80:- **Not a posterior.** `C(s)` is a confidence curve. It carries no prior and does not
prereg/twin-calibration.md:6:**This one changes what certifies.** Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
quixote/replay.py:237:                support = list(new)
quixote/replay.py:379:                support = tuple(new)
```
