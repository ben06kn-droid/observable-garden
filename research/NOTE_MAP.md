# A reader's map from the note to the repository

*Since the 2026-10 cleanup the research record is under `research/`, the engine under
`quixote/engine/` and Sancho under `sancho/` (was `learn2/`). Paths below are from the
repository root. `git show <commit>:<path>` takes the path as it was at that commit, so those
stay in the old form; the tag `pre-cleanup-2026-10-12` has every old path.*

The note, *The Observable Garden: Fixed and adaptive candidate sets under the DSR*, is
distributed separately, on SSRN (<SSRN_LINK>); it is not in this repository. The note tells its
reader that this table exists. Each row is one claim in the note, in the note's order (the
abstract, then Sections 1 to 5, then the closing).

**The note's numbering:** the abstract is unnumbered, and the sections are 1 Setup, 2 The fixed
candidate set, 3 Adaptive search, 4 Size, 5 Don Quixote, 6 Limitations, 7 Closing. Section
numbers in this file follow it. (An earlier draft numbered every section one higher, from
Section 2 Setup to Section 8 Closing.)

**Commits:**
- **Registration** is the commit at which the experiment was pre-registered (or went
  live).
- **Result** is the commit that added its output.
- **Read** is where a separate read commit exists.

The scripted experiments of Sections 2 to 4 record their outputs as
`research/figures/<name>_data.pkl`, with the numbers stated in `research/SCOPE.md` by section name. A
pre-registration that has closed is no longer in `research/prereg/`. It is recovered with `git show
<registration commit>:prereg/<file>`, as `research/EXPERIMENTS.md` explains.

**Limit values are computed two ways:** by Monte Carlo in `research/experiments/limit_model.py`
(2 million draws per cell), and by quadrature of the note's Section 4 integral in
`research/experiments/size_integral.py`. The two agree to 0.001; the largest difference is
0.0009, at ω = 0, K = 80.

**Run times:** "not recorded" means the run did not write its own timing. No figure is
estimated here.

## Numbering: the note against research/THEORY.md

| note | research/THEORY.md |
|---|---|
| The realized-set null as one implementation of the process null (abstract, §1) | Setup (the process null `F_P` and the realized-menu null `F_C`); P1; P4 |
| Proposition 1 (§2) | P1. Fixed menus are valid (known) |
| Proposition 2 (§2) | P2. Sub-maximal selection is conservative (known) |
| Lemma and Direction (§3) | P4. Winner anchoring is anti-conservative; loser anchoring is conservative |
| The rank mixture (§3) | P4′. The realized-menu null is a uniform mixture over anchor ranks |
| Consequences 1 and 2 (§3) | P4′, Corollaries 4.1 and 4.2 |
| Size: the error-rate formula (§4) | P4, "Breadth": the closed form 1 − F_P(F_C⁻¹(1 − α)) and its table |
| Size: when the formula holds (§4) | P4, "Breadth": "Under exchangeability `F_C` does not depend on the data" (the general case is not written out there) |
| Second level of record: a class declared in advance (§5) | P3. The full-class bound |
| Greedy search reaching only part of the class (§5) | P5. Greedy search and the lattice optimum |
| The process bootstrap's partial justification (§6) | P6. When is the recursive bootstrap consistent? |

## Claims

| # | claim, in one plain sentence | note | research/THEORY.md | experiment | registration | output; result or read | script; run time |
|---|---|---|---|---|---|---|---|
| 28 | Under adaptive search the realized-set null is a common implementation of the process null, not a substitute for it; the issue is the implementation, not the DSR framework. | abstract; §1 | P1, P4 (and Setup) | none (theory) | — | — | — |
| 1 | If the candidate list ignores the returns, the realized-set test has the correct error rate. | §2, Prop. 1 | P1 | `oblivious-calibration` (E21) | `research/prereg/E21.md` at `82bea64` | `research/figures/oblivious_calibration_data.pkl`; result `b3ce0d5` | `research/experiments/oblivious_calibration.py`; not recorded |
| 2 | A search that reports no more than the maximum of a validly-nulled set keeps the test valid, at a cost in power. | §2, Prop. 2 | P2 | none needed (known) | — | — | — |
| 3 | A greedy rule on a list written in advance shows no excess; the same rule generating its own candidates does. | §2 | P1 | `lattice-control` (e2) | not registered | no file under `research/figures/`; the result is in `research/SCOPE.md` (null calibration and the mechanism) | `research/experiments/lattice_control.py`; not recorded |
| 4 | The best pair containing any fixed feature lies between the best pair with the loser and the best pair with the winner. | §3, Lemma | P4 | `pointwise-dominance` (E16) | `research/prereg/E16.md` at `c8c5d60` | `research/figures/pointwise_dominance_data.pkl`; result `714ee26` | `research/experiments/pointwise_dominance.py`; not recorded |
| 5 | Winner-anchoring makes the realized-set test too lenient, and loser-anchoring too strict. | §3, Direction | P4 | `anchor-coupling` (e15); `pointwise-dominance` (E16) | e15 pre-registered at `675278d`; E16 at `c8c5d60` | `research/figures/anchor_coupling_data.pkl`, result `66eb7ca`; E16 as row 4 | `research/experiments/anchor_coupling.py`, `research/experiments/pointwise_dominance.py`; not recorded |
| 6 | The realized-set null is the average of the K rank-anchored process nulls. | §3, rank mixture | P4′ | limit model (Corollary 4.1: 5.00% ± 0.02 at K = 20, ω = 0.3); `graded-coupling` at τ = 0 | E17 at `254cdda` | `research/figures/graded_coupling_data.pkl`; result `be3c0df` | `research/experiments/limit_model.py`; `research/experiments/size_integral.py` checks P4′ (tests); `research/experiments/graded_coupling.py`; not recorded |
| 7 | A uniformly random anchor is exactly calibrated, and anchoring moves error between ranks rather than creating it. | §3, consequences 1–2 | P4′, Cor. 4.1–4.2 | as row 6; `anchor-rank` (E17b) | E17b at `db6b64e` | `research/figures/anchor_rank_data.pkl`; result `6c076d1` | `research/experiments/anchor_rank.py`; not recorded |
| 8 | The winner-anchored test rejects too often, the random and worst anchors do not, and the process bootstrap restores nominal. | §3, Evidence 1 | P4 | `anchor-coupling` (e15) | `675278d` | as row 5 | as row 5 |
| 9 | The error rises steadily as the anchor draw leans from worst to best, crossing nominal at the uniform draw. | §3, Evidence 2 | P4 | `graded-coupling` (E17) | `254cdda` | result `be3c0df` (trend p = 0.0001) | `research/experiments/graded_coupling.py`; not recorded |
| 10 | With the anchor's rank fixed, the measured rates match the limit values computed in advance. | §3, Evidence 3 | P4, P4′ | `anchor-rank` (E17b) | `db6b64e` | result `6c076d1` | `research/experiments/anchor_rank.py`; not recorded |
| 11 | With finite samples and unequal correlations, the predicted ordering held on almost every reshuffle. | §3, Evidence 4 | P4 | `pointwise-dominance` (E16; 99.9% of replicates); `unequal-correlation` (E19) | E16 `c8c5d60`; E19 `8f4acb5` | E19 `research/figures/unequal_correlation_data.pkl`, result `2e4417d` | `research/experiments/unequal_correlation.py`; not recorded |
| 12 | For crossover rules the asymmetry appears, but the error is small, and no size is claimed. | §3, Evidence 5 | P4 (outside additive scoring) | `non-additive-scoring` (E20) | `research/prereg/E20.md` at `f298103` | `research/figures/non_additive_scoring_data.pkl`; result `4e32903` | `research/experiments/non_additive_scoring.py`; not recorded |
| 13 | The limiting error rate is 1 − F_P(F_C⁻¹(1 − α)), and for the two-stage winner-anchored search F_P is the stated integral. | §4 | P4, Breadth | limit model | — | research/THEORY.md's breadth table | `research/experiments/limit_model.py` (Monte Carlo) and `research/experiments/size_integral.py` (quadrature, under 1 s); they agree to 0.001 |
| 29 | The error-rate expression holds when the realized-set critical value is deterministic in the limit, as with exchangeable features; in a general adaptive search it can stay random and correlated with the reported maximum. | §4 | P4, Breadth | none (theory) | — | — | — |
| 14 | More features, more error: with 80 uncorrelated features about a third of null searches pass a 5% test. | §4 | P4, Breadth | `feature-count` (E19c) | `research/prereg/E19c.md` at `21dbbc1` | `research/figures/feature_count_data.pkl`; result `daf470c` (10.0% to 36.2%, K = 10 to 80) | `research/experiments/feature_count.py`; not recorded |
| 15 | Correlation among features limits this error rather than causing it. | §4 | P4, Breadth | `feature-count` (E19c), the ω = 0.3 cells | as row 14 | as row 14 | as row 14 |
| 16 | A third round, building triples around the winning pair, raises the error further. | §4 | P4 (depth 3) | `search-depth` (E18) | `3a2c335` | `research/figures/search_depth_data.pkl`; result `c21fe86` (winner 10.4%) | `research/experiments/search_depth.py`; not recorded |
| 17 | A random round-2 anchor with round-3 re-anchoring gave an excess too small to detect. | §4 | P4 (depth 3) | `search-depth` (E18) | as row 16 | as row 16 (5.3%; detectable about 6.9%) | as row 16 |
| 18 | Testing against a class declared in advance is valid for any search inside it, at a cost in power. | §5, second level | P3 (with P1, P2) | `calibration-at-1pct` (6.1), arm D | `e9ad319`; closed `406018f` | `research/figures/calibration_at_1pct_armD.txt`; result `18e7e6e` (9.60 / 5.50 / 0.95% at 10 / 5 / 1%) | `research/experiments/calibration_at_1pct.py`; arm D 41.95 CPU-hours over 2,000 draws (its own record) |
| 19 | A greedy search inside the class is tested well below nominal, because it is charged for the whole class. | §5, second level | P3, P5 | `calibration-at-1pct` arm B; `gate-comparison` | `e9ad319`; gate-comparison live `e224f8b`, closed `b42eefb` | `research/figures/calibration_at_1pct_armB.txt`; `research/figures/gate_comparison_read.txt` | `research/experiments/calibration_at_1pct.py`, `research/experiments/gate_comparison.py`; arm B 221.85 CPU-hours over 5,000 draws; gate-comparison 3.71 h wall per cell at 192 workers (their own records) |
| 20 | Re-running logged typed moves reproduces the search exactly, and a log that fails replay is refused. | §5, third level | — (the harness) | `fixed-sequence-replay` (7.1) | `96b48dc` | `research/figures/fixed_sequence_replay_rules.txt`; read `9a68c25` | `research/experiments/fixed_sequence_replay.py`; projected 1,596 CPU-hours at B = 10,000 (its cost file) |
| 21 | Freezing stopping decisions repeats the realized-set error in time, and declared, re-checked stopping rules bring the rate back to nominal or below. | §5, stopping | P2 (below nominal) | `fixed-sequence-replay` (7.1); `unfaithful-searchers` (7.3, the faithful pair) | 7.1 `96b48dc`; 7.3 `359df62` | 7.1 read `9a68c25`; 7.3 read `37abeb2`, closed `17313a0` | `research/experiments/fixed_sequence_replay.py`, `research/experiments/unfaithful_searchers.py`; 7.3 cost $9.28 on a c7a.48xlarge |
| 30 | Replay re-evaluates declared stopping conditions on each reshuffle but holds an agent's content moves at their realized values, so it is liberal at those steps; a replay that matches the original trajectory shows consistency only. | §5 | — (the harness) | `fixed-sequence-replay` (7.1); `bracketed-verdicts` | 7.1 `96b48dc`; bracketed-verdicts drafted `1e8fffe`, amendment 1 `5431e43`, still a draft (`research/prereg/bracketed-verdicts.md`, not live) | 7.1 read `9a68c25` (`research/figures/fixed_sequence_replay_rules.txt`); bracketed-verdicts has no run of its own | `research/experiments/fixed_sequence_replay.py`; as row 20 |
| 22 | With a planted edge on real ETF features, no validity test failed, passes outperformed fails on held-back data, and the lower bounds covered. | §5, beyond the null | P3 | `planted-edge` (7.5), stage 1; `confidence-output` V2 | 7.5 live `bb0dcc4`; V2 live `697bef8` | 7.5 results `30ee870`, read `8660508`; V2 results `0edab26`, read `afdcb53` | `research/experiments/planted_edge.py`; about 3 h 37 min on a c7a.48xlarge (7.5); about 1 h 26 min (V2) |
| 23 | Language-model agents usually earned a pass where a planted edge existed and never where none did. | §7 | — | `planted-edge` (7.5), stage 2 | live `067371d` | results `06a5284`, read `b45dba5` | `research/experiments/planted_agent.py`; seat $28.61, pricing 13 min |
| 24 | On a first panel of real ETFs (6.5; not in Table 3), no submission passed. | §7 | — | `agent-on-real-data` (6.5) and its holdout grading | grading live `3a5483e` | grades `e4bc84b`, read `0426352` (`research/runs/holdout_grading/read.txt`) | `research/experiments/grade_real.py`, `research/experiments/holdout_grading_read.py`; not recorded |
| 25 | ridge_stack, one strategy declared in advance, kept the nominal error rate and passed planted non-linear edges far more often than the class. | §7 | P3 (a class of one) | `ml-ridge-stack-confirmation` | live `77f3ee1` | raw `06358c8`, read `d746a78` (`research/runs/ml_confirm/ridge_stack/read.txt`) | `research/experiments/ml_confirm_ridge_stack.py`; 1,116 s on a c7a.48xlarge (run record) |
| 26 | On French industries 2013–2019, the earlier model, ridge_stack, was refused in-sample. Superseded by Table 3 (row 32), which grades it with the class's best member on the holdout. | §7 (earlier model; see the Table 3 rows) | — | `french-panel`, in-sample read | live `de9da1b` | raw `31622d6`, read `fc92cdb` (`research/runs/french_insample/2026-10-07/read.txt`) | `research/experiments/french_insample_read.py`; 1 min 37 s on the laptop (run record) |
| 31 | Sancho's design (penalty grids, training windows) was settled on synthetic returns before any real panel was read, every real test was registered first, and its stream is built walk-forward. | §7 | P3 (a class of one) | ML version 2: exploratory design and two pilots, then `ml-v2-confirmation` | exploratory note `research/prereg/ml-v2-exploratory-2026-10-08.md` at `6c34389`, pilot sections `817f8d2` and `4688d5e`; confirmation `research/prereg/ml-v2-confirmation.md` live `083c734` (amendment 1 `0b0b358`) | design `ff0ea89`, grids `a570241`; pilot reads `fe7c7ca`, `9e4f6a7`; confirmation raw `1ba8df7`, read `97d2519` | `sancho/` (levers and registered defaults in `sancho/CONFIG.md`; the walk-forward in `sancho/learner.py`); `research/experiments/ml_v2_confirm_2026_10_09.py` |
| 32 | Table 3, French 49 industries 2013–2019 (the earlier model, ridge_stack, and the class's best member): both refused in-sample; on the holdout 2020 – Aug 2026, ridge_stack's 90% lower bound did not hold (+0.017 < +0.065) and the class member's held (−0.001 ≥ −0.518). | §7, Table 3 | P3 | `french-panel` in-sample read; `french-holdout-grading` | in-sample live `de9da1b` (amendment 1 `e1cda69`); grading live `4f11f95` | in-sample raw `31622d6`, read `fc92cdb` (`research/runs/french_insample/2026-10-07/read.txt`); grading raw `c902955`, read `fa1e13c` (`research/runs/french_holdout/2026-10-09/read.txt`) | `research/experiments/french_insample_read.py`; `research/experiments/french_holdout_grade.py`, `research/experiments/read_french_holdout.py` |
| 33 | Table 3, Binance USDT perpetuals, 4h bars, 2021 – Mar 2025: Sancho's stream (d = 0) and the class maximum were both refused; the holdout was not opened. | §7, Table 3 | P3 | `binance-panel` in-sample read | live `ecc07f0` (amendment 1 `79c3dfa`) | raw `a37e4a4`, read `dd05b01` (`research/runs/binance_insample/2026-10-09/read.txt`) | `research/experiments/binance_insample_read.py`, `research/experiments/read_binance_insample.py`; 2,114 s on the laptop (run record) |
| 34 | Table 3, French 49 industries 1926–1989: Sancho's stream was certified under the recency-weighted statistic (d = 1 at the 96% level; d = 0 also, not implementable) and the class maximum refused; on the holdout 1990–1995 each weighted lower bound held (Sancho d = 1: +1.646 ≥ +0.674). | §7, Table 3 | P3 | `french-long-history`, read B1; `french-long-b1-grading` | live `756af89`; grading live `00417de` | raw `314beda`, read `ff04846` (`research/runs/french_long_b1/2026-10-11/read.txt`); grading raw `53d6321`, read `1a10487` (`research/runs/french_long_b1_grade/2026-10-11-r2/read.txt`) | `research/experiments/french_long_read.py`, `research/experiments/read_french_long.py`; `research/experiments/french_long_grade.py`, `research/experiments/read_french_long_grade.py` |
| 35 | Table 3, liquid ETFs 2015–2024: Sancho's stream and the class maximum were refused; on the holdout 2025-01-02 – 2026-10-09 (1.76 years, weak) each weighted lower bound held. | §7, Table 3 | P3 | `etf-recent-panel`; `etf-recent-grading` | live `310225c`; grading live `2fd0346` | raw `05642cf`, read `3552158` (`research/runs/etf_recent/2026-10-11/read.txt`); grading raw `ccfb184`, read `07c77ef` (`research/runs/etf_recent_grade/2026-10-11/read.txt`) | `research/experiments/etf_recent_read.py`, `research/experiments/read_etf_recent.py`; `research/experiments/etf_recent_grade.py`, `research/experiments/read_etf_recent_grade.py` |
| 36 | In 240 agent sessions on the ETF panel the agents converged on three strategies, stated a little over half of their in-sample Sharpe, with no relation to search length; agents shown the lower bound stated lower expectations; the three strategies lost slightly over the 21-month holdout. | §7, the agent cell | — | `agent-cell-etf-recent` | live `00c7af1` (amendments `ecaa516`, `c569873`) | submissions `c37d1a5`, priced `0d6f55d`; holdout grades `ccfb184`; read `a7de2a4` (R1–R4, `research/runs/agent_cell_etf_recent_read/2026-10-11/read.txt`); the panel's own objects, read `07c77ef` (row 35) | `research/experiments/agent_cell_etf_recent.py`, `research/experiments/agent_cell_etf_recent_price.py`, `research/experiments/read_agent_cell_etf_recent.py` |
| 37 | Over several hundred synthetic sessions, stated mean regresses on in-sample Sharpe at about +0.40 and on log evaluation count at about −0.02 (n = 329, the s0 Sonnet cells pooled). | §7, the agent cell | — | `agent-arm` | `research/prereg/AGENT_PROMPTS.md` at `499d66e` (amendments to `33b27ff`); this pooled regression was added after the runs and is not in the registration | result `aa3ce68` (`research/figures/agent_analysis.txt`: +0.3992, −0.0231); written up in `research/SCOPE.md`, The agent arm, at `063416a` | `research/experiments/analyze_agent.py`; not recorded |
| 27 | The limit values come from two scripts, and each measured value from a named experiment; those of Sections 3 to 5 were pre-registered. | §7, reproduction | all | — | the ledger, `research/EXPERIMENTS.md` | — | `research/experiments/limit_model.py`, `research/experiments/size_integral.py` |

Rows 28 to 37 were added on 2026-10-15 for the SSRN version of the note. They sit in the note's order; the
earlier rows keep their numbers, so references to them still hold. Rows 28 and 29 are theory
with no experiment.

Rows 3, 19 and 24 point to experiments whose outputs are spread over several files. The
ledger rows in `research/EXPERIMENTS.md` give the full commit lists.

Sections 1 (Setup) and 6 (Limitations) of the note carry no separate experiments. Section 1 sets up the objects the rows above test, and Section 6 states the limits of those rows.
