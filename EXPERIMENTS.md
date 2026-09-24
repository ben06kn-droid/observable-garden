# Experiments

Every experiment, in the order it ran. Names replaced the old `e<n>` / `E<n>`
numbering, which carried no information and collided across two conventions:
lowercase `e4` and uppercase `E19` meant different things, `E19` and `E19c` were
different experiments on different questions, and `e5` was void but still cited
by number throughout.

The old id is kept in this table because git history, `prereg/COMMIT_MAP.md` and
the `git_at_launch` field inside the `figures/*.pkl` data files all record it.
Those are historical records and were not rewritten.

**Three planning documents were removed once the work they described was
finished**, and `1fb464f` is the last commit holding them: `estimator_build_spec.md`
(the original build specification), `GARDEN_WATCH_PLAN.md` (the `watch` build
plan, which also served as the pre-registration for `watch-validation`) and
`note/OUTLINE.md` (drafting decisions for the note, sent 2026-09-16). Docstrings
across `estimator/`, `searchers/` and `experiments/` still cite the build spec by
section as "spec §4.2" and similar; those citations resolve at that commit.

**Two modules deliberately keep their old filenames.** `experiments/e_agent.py`
is the agent harness and `experiments/e_watch_validation.py` the watch
validation; neither carries a number, so neither was part of the problem this
renaming fixes. `e_agent.py` is also the one experiment module named in
`code_state.CODE_PATHS`, so renaming it would move the harness fingerprint that
`runs/*/config.json` records and that amendments 5, 8, 10 and 11 reason about —
a real cost for no gain.

Files use underscores, because a module name must be a Python identifier; this
table and the prose use hyphens for the same experiment.

Results are in `SCOPE.md`, by section name.

**A pre-registration binds an experiment before it sees data, so once that
experiment has reported it has done its work.** The nine below were removed.
Each is intact in git at the commit it was committed at, which is *before* its
run, so the claim that its gates were fixed in advance is still checkable:
`git show <commit>:prereg/<file>`. `prereg/` now holds only what is live — the
agent-arm design (`AGENT_PROMPTS.md`, whose Fable arm is deferred to 2026-09-30
and which pins ROADMAP 6.5-6.7) and the history-rewrite record.

| experiment | pre-registered at | file at that commit |
|---|---|---|
| `pointwise-dominance` | `c8c5d60` | `prereg/E16.md` |
| `graded-coupling` | `254cdda` | `prereg/E17.md` |
| `anchor-rank` | `db6b64e` | `prereg/E17b.md` |
| `search-depth` | `3a2c335` | `prereg/E18.md` |
| `scoring-rule` | `8383b11` | `prereg/E18b.md` |
| `unequal-correlation` | `8f4acb5` | `prereg/E19.md` |
| `feature-count` | `21dbbc1` | `prereg/E19c.md` |
| `non-additive-scoring` | `f298103` | `prereg/E20.md` |
| `oblivious-calibration` | `82bea64` | `prereg/E21.md` |

**Live pre-registrations**, still in `prereg/` because their experiment has not
finished reporting. Amendments are recorded by commit too, so a later reader can
check that each one preceded the code and the run it authorises.

| pre-registration | committed at | amendments and deviations |
|---|---|---|
| `calibration-at-1pct` | `e9ad319` | 1, skip the sizing smoke — `4f556bb`; deviation 1 and amendment 2, arm D — `0ab5653`; 3, what rule 4's ordering rests on — `4cb8404` |
| `costs-and-regime-change` | `16457d9` | 1, the cost half cannot measure what it claims — `04dcc53`; 2, withdraw the cost half entirely — `2ba240f` |
| `heterogeneous-correlation-fat-tails` | `96b48dc` | 1, the one-sided validity rule — `5b8042c`; 2, cell (B) pinned and a replication branch — `6739589`; 3, cell (A) needs rho>0 and two nulls per draw — `7cc4c67`; deviation 1, the skipped pre-launch smoke — `35a3fab`; deviation 2, box change partway through cell (C), cross-box check identical, interim outputs disclosed — `7582ad6`; the n = 2,000 reading and cell (A)'s ECDF departure — `a408304`; the replication passes, recorded as a family false alarm — `b8df48f` |
| `fixed-sequence-replay` | `96b48dc` | 1, rule 1's one-sided form — `5b8042c`; 2, the widened fill and a fifth searcher — `c2acb41`; 3, rule 1's replication branch and rule 3's "material" — `2ba32d4`; 4, null 4 withdrawn — `587aa34`; 5, MetaAdaptive's restart mismatch and its fix — `19a87bd`; 6, the trigger-evaluated fill, a paired rule 3, six searchers — `17589fd`; 7, B by a cost rule fixed before measuring — `0cf734f`; deviation 1, the session on the c7a.8xlarge, run unattended — `1505653`; the reading at n = 2,000 — `9a68c25` |
| `gate-comparison` | `92d4751` (draft), live `e224f8b` | 1, arm D's decomposition, slack searchers, rules 3 and 4 replaced — `8baa888`; 2, rule 2's one-sided form — `5b8042c`; 3, the launch gate satisfied — `40654ce`; 4, a replication branch for rules 1 and 2 on 210000–211999 — `40654ce`; 5, `BudgetedRandom` specified — `40654ce`; 6, what 7.0 no longer decides, rule 4's tie branch reworded — `40654ce`; 7, cost, instance, and the dedicated smoke block 980000–980999 — `40654ce`; 8, the holdout certifier's test — `622e1f0`; 9, rule 5 reads the PASS − FAIL gap in median gross OOS Sharpe — `e224f8b` |



## What pins the code a result ran on

Audited 2026-09-20, after arm D exposed the defect. Two mechanisms exist and
they cover different things:

- **`git_at_launch`** (`experiments.search_depth.git_state`) records HEAD and a
  dirty flag. Scripted experiments in `figures/` carry this and nothing else.
- **The `code_state` harness fingerprint** hashes every file under `CODE_PATHS`
  plus the pre-registration's design sections. It is recorded **per agent run**
  in `runs/<batch>/runs.csv` and is what stops a batch mid-flight when the code
  moves. **No `figures/*_data.pkl` carries one.**

**Five committed results carry `(dirty)`**, and for none of them does a
fingerprint independently pin the code, because scripted experiments do not
record one:

| result | commit | in main history | independently fingerprinted |
|---|---|---|---|
| `calibration_at_1pct_armB` | `4f556bb` | yes | no |
| `calibration_at_1pct_armC` | `4f556bb` | yes | no |
| `calibration_at_1pct_armD` | `04dcc53` | yes | no |
| `e_watch_validation` | `7fc06ba` | yes | no |
| `e_watch_validation_T2000` | `7fc06ba` | yes | no |

**Arm D's flag is proven spurious.** Checked on the instance while it still
held the tree: `git diff HEAD` was empty and `git status --porcelain` listed
only untracked paths — the checkpoint directory and the run's own outputs in
`figures/`. The code that ran was exactly `04dcc53`.

**Arms B and C are functionally pinned by reproduction**, which is stronger than
a flag. Arm D, proven clean, reran arm B's seeds and reproduced results exactly:

| pair | shared seeds | what matched | what that pins |
|---|---|---|---|
| D against B | 2,000 | `p_value` **bit-identical**, greedy and adaptive | the DGP, the sandbox, both searchers, and the full-class null engine at B = 10,000 |
| C against B | 500 | `sr_sel` **bit-identical**, greedy and adaptive (max abs diff 0.0) | the DGP, the sandbox and both searchers |

Arm C's p-values differ from arm B's, as they must: arm C prices at B = 50,000
against arm B's B = 10,000, so the nulls are different objects. What arm C can
share, and does share exactly, is the observed statistic. **So arm C's bootstrap
path at B = 50,000 is the one thing no other run reproduces**; everything
upstream of it is pinned.

**The two watch validations are pinned by neither.** No later run reproduces
them, and no fingerprint was recorded. They stand on commit `7fc06ba` alone.
Nothing is being rerun on this basis.

`git_state` was fixed in `18e7e6e` to count tracked modifications only and to
report untracked paths separately, so a future `(dirty)` means what it says.
Results produced before that commit carry the old, uninformative flag.

**A separate gap, in the other direction: 92 agent runs are pinned by commit
alone.** Fingerprint coverage in the agent batches is not complete.

| batch | runs | fingerprints | commit-pinned only |
|---|---|---|---|
| `b1-baseline` | 80 | none recorded | **80** |
| `b2-arms` | 241 | 4 distinct, 12 rows missing | **12** |
| `b3-models` | 180 | 1 | 0 |
| `b4-s3-recal` | 80 | 2 | 0 |
| `b5-opus` | 80 | 1 | 0 |

Those 92 runs carry no harness fingerprint, so a code change during them would
not have stopped the batch and is not detectable after the fact. They are used
in the `calibration-at-1pct` arm A re-score and in `costs-and-regime-change`;
both report pooled rates over hundreds of runs, so the exposure is a fraction of
one batch rather than a whole result, but it is not zero and is recorded here
rather than in a footnote.

## Phase 6

| name | question | result |
|---|---|---|
| `calibration-at-1pct` | is the declared-class gate calibrated at 1%, not just 5%? | arm A: 15 of 419 graded agent runs reject at 5%. arm B: conservative, and unable to answer — see deviation 1. arm C running; arm D pre-registered, not run |
| `costs-and-regime-change` | what does a PASS survive once the regime shifts? (cost half withdrawn, amendment 2) | ran 2026-09-20 |
| `gate-comparison` | which of the three certifiers should the gate use, and in what order should 7.2 fall back? | **live 2026-09-24.** Launch gate satisfied (amendment 3): arm D reported and process replay is sized. Driver written (`experiments/gate_comparison.py`); scaling curve and smoke on the registered cost-only block 980000–980999 next, then the run |
| `fixed-sequence-replay` | what does freezing a search's meta decisions cost, and do declared triggers remove it? | **complete, read 2026-09-24.** Rule 1 passes for all six searchers, so the replay tier is built on declared triggers. Freezing is liberal (+0.012 at 5% for the bar searchers) and sits 0.44 in sup-norm from the policy null, which declared triggers remove. Rule 3: the fill is liberal against a width-2 beam (1,506 of 1,507 draws) and conservative against continuations it dominates, but the inflation is not detectable (no discordant draws, McNemar p = 1.0), so strengthening the agent-path fill is optional and stated |
| `heterogeneous-correlation-fat-tails` | does the full-class null survive factor-structured correlation and fat tails? | **complete, read 2026-09-21/22.** Yes, in all three cells at n = 2,000. Rule 1 held on containment everywhere; its KS check rejected once, in cell (A) (p = 0.0090), and the registered replication on 410000–411999 passed (p = 0.8503), so that is recorded as a family false alarm. Rule 2: no liberal searcher in any cell. Block lengths moved off 1 in (B) and (C); guard counts zero |
| `agent-pilot` | does the harness survive a model on a real panel? (5 runs, ADR panel; harness shake-out and engagement only, **no verdict claim**) | registered 2026-09-24, not yet run |
| `bracketed-verdicts` | what does reporting two p-values cost for a decision the gate cannot replay? | draft, not live |
| `prior-weighted-alpha` | is splitting alpha between a declared short list and the adaptive search worth the power? | draft, not live |
| `living-verdict` | can a certification be kept under continuous review and revoked? (stub, built after the paper) | draft, not live |
| `stability-statistic` | does minimum-Sharpe-across-blocks reduce non-persistent passes enough to justify its power cost? | draft, not live |
| `twin-calibration` | does re-running the same agent on placebo twins certify what the log-based null misses? | draft, not live |
| `bits-of-selection` | is there a common unit for how much a search looked at? (measurement only, enters no verdict) | draft, not live |
| `pivotal-interrogation` | can DEPENDS_ON_JUDGMENT be resolved by querying the agent only where its answer could move the verdict? | draft, not live |

`prereg/gate-comparison.md` went **live on 2026-09-24**, when both conditions its opening named were met: `calibration-at-1pct` arm D reported, and process replay was sized by `fixed-sequence-replay` (amendment 3). It is in the commit table above from that date. Nine amendments precede any draw, and no 7.0 data existed when any of them was written. The remaining Phase 7 amendment drafts are still **committed but not live**: they are in the tree so they cannot be lost, they have not been reviewed, and they authorise nothing.

## Null calibration and the mechanism

| name | old | question | result |
|---|---|---|---|
| `null-calibration` | e1 | are oblivious searchers uniform under the null? | yes; Adaptive is not |
| `recursive-calibration` | e1r | does replaying selection inside each replicate fix it? | yes |
| `lattice-control` | e2 | is it adaptive selection or adaptive generation? | generation |
| `procedure-level-validation` | e3 | does the cheap repair match a reconstruction-free gold standard? | +0.019, Monte Carlo noise |
| `adaptive-powered` | e4 | the same at n=500, properly powered | naive 13.6%, recursive 3.4% |
| `dose-response-beam` | e5 | does inflation grade with beam width? | **void** — an anchor bug made NeighborAdaptive into Adaptive; superseded by `search-depth` |
| `procedure-spotcheck` | e5b | a reconstruction-free spot check | agrees |
| `baseline-diagnostic` | e5c | is the 0.06-vs-0.05 baseline gap real? | inconclusive; most likely sampling noise |
| `entropy-diagnostic` | e5d | does beam entropy track inflation better than divergence? | no — the predicted winner lost |

## Predictive power and the cost of breadth

| name | old | question | result |
|---|---|---|---|
| `signal-landscape-pilot` | e6 | is the s=3 landscape degenerate? | no |
| `predictive-power-v1` | e7 | do the corrections predict out-of-sample Sharpe? | mixed; target was noise-dominated |
| `dgp-criterion-check` | e8 | does the DGP clear the Lo measurement-noise floor? | no — analytic scoring was required |
| `predictive-power` | e9 | the rerun with both DGP fixes | bias, not RMSE, separates the three corrections |
| `power-vs-signal` | e10 | does power track effect size? | yes, monotonically |
| `power-vs-breadth-pinned` | e11 | what does breadth cost at fixed finding quality? | power falls 7.5× from N=10 to N=1000 |
| `type-m-by-power` | e12 | how much do passing results overstate? | 11.9× at 6% power; sign flips near 30% |

## The degeneracy check

| name | old | question | result |
|---|---|---|---|
| `degeneracy-calibration` | e13 | can broken critical values be detected? | the first rule over-refused |
| `degeneracy-recalibration` | e14 | recalibrate on fresh seeds | 0 of 9,000 dense refused; 89.8% of broken bars caught |

## Winner-chasing

| name | old | question | result |
|---|---|---|---|
| `anchor-coupling` | e15 | which anchor rule distorts the naive bootstrap? | only the one built on the winner |
| `pointwise-dominance` | E16 | is the P4 lemma the mechanism? | yes, on 99.9% of replicates |
| `graded-coupling` | E17 | does distortion grade with coupling? | yes, trend p = 0.0001 |
| `anchor-rank` | E17b | does it grade with the anchor's rank? | yes, matching the limit at every rank |
| `search-depth` | E18 | depth 3, re-anchoring, beam widths | winner 10.4%; recursive decisions agree across widths |
| `scoring-rule` | E18b | does the scoring rule explain the gap to `adaptive-powered`? | no |
| `unequal-correlation` | E19 | does P4 survive non-exchangeable features? | the conclusion holds where the proof does not |
| `feature-count` | E19c | does inflation grow with the candidate count? | 10.0% → 36.2% from K=10 to K=80 |
| `non-additive-scoring` | E20 | does the sign survive scoring that is not a weighted sum? | yes; size about one point |

## Controls and the agent arm

| name | old | question | result |
|---|---|---|---|
| `oblivious-calibration` | E21 | are oblivious searchers calibrated at every menu size and correlation? | yes, all 56 cells |
| `watch-validation` | — | scripted searchers under `watch` | type-I nominal; power matches preflight |
| `agent-arm` | — | LLM searchers under the gate, 661 runs | see `SCOPE.md`, The agent arm, and `runs/` |
| `full-class-power` | E22 | what does the declared-class tier cost in power? | not yet run |

## Supporting scripts

`limit_model.py` reproduces every limit number in `THEORY.md`.
`make_schedule.py` generates the agent-arm run schedules.
`build_manifest.py` builds `runs/`'s per-batch tables.
`analyze_agent.py` produces the agent-arm analysis.
`plot_*.py` build the figures. `verify_*.py` are standing checks, not experiments.
